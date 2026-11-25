"""
Non-destructive database backup, recovery, and migration status verification utilities.
Never deletes or overwrites existing production records or non-empty backups.
"""
import base64
import json
import os
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import inspect, text
from app import db


BACKUP_TABLE_ORDER = [
    'system_settings',
    'departments',
    'complaint_categories',
    'users',
    'workers',
    'complaints',
    'complaint_assignments',
    'complaint_status_history',
    'complaint_attachments',
    'notifications',
    'feedback',
    'contact_messages',
    'audit_logs',
]


def _serialize_val(val):
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return {'__type__': 'datetime', 'value': val.isoformat()}
    if isinstance(val, Decimal):
        return {'__type__': 'decimal', 'value': str(val)}
    if isinstance(val, (bytes, bytearray)):
        return {'__type__': 'bytes', 'value': base64.b64encode(bytes(val)).decode('ascii')}
    return val


def _deserialize_val(val):
    if isinstance(val, dict) and '__type__' in val:
        kind = val['__type__']
        raw = val['value']
        if kind == 'datetime':
            return datetime.fromisoformat(raw)
        if kind == 'decimal':
            return Decimal(raw)
        if kind == 'bytes':
            return base64.b64decode(raw.encode('ascii'))
    return val


def get_migration_status():
    """Inspect current database schema status without modifying any table or row."""
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    missing_tables = [t for t in BACKUP_TABLE_ORDER if t not in existing_tables]

    pending_columns = []
    checks = {
        'users': ['is_password_reset_required', 'password_changed_at'],
        'workers': ['employee_id'],
        'complaints': ['assigned_officer_id', 'assigned_worker_id', 'verified_at'],
        'complaint_attachments': ['file_data'],
        'notifications': ['complaint_id'],
    }
    for tbl, cols in checks.items():
        if tbl in existing_tables:
            present = {c['name'] for c in inspector.get_columns(tbl)}
            for col in cols:
                if col not in present:
                    pending_columns.append(f"{tbl}.{col}")

    return {
        'dialect': db.engine.dialect.name,
        'existing_tables': sorted(existing_tables),
        'missing_tables': missing_tables,
        'pending_columns': pending_columns,
        'is_up_to_date': not missing_tables and not pending_columns,
    }


def create_verified_backup(output_dir=None, target_file=None, allow_empty=False):
    """
    Create a verified JSON snapshot of all tables and row counts.
    Never overwrites a non-empty backup file with an empty snapshot.
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'backups')
    os.makedirs(output_dir, exist_ok=True)

    if target_file is None:
        stamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        target_file = os.path.join(output_dir, f'backup_{stamp}.json')

    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    tables_data = {}
    counts = {}
    with db.engine.connect() as conn:
        for table in BACKUP_TABLE_ORDER:
            if table not in existing_tables:
                continue
            rows = conn.execute(text(f"SELECT * FROM `{table}`" if db.engine.dialect.name == 'mysql' else f'SELECT * FROM "{table}"')).mappings().all()
            serialized = [{k: _serialize_val(v) for k, v in dict(r).items()} for r in rows]
            tables_data[table] = serialized
            counts[table] = len(serialized)

    total_rows = sum(counts.values())
    if total_rows == 0 and not allow_empty:
        raise ValueError("Refusing to write empty backup snapshot (0 records across all tables).")

    # Protect any pre-existing non-empty target file from being replaced by an empty snapshot
    if os.path.exists(target_file):
        try:
            with open(target_file, 'r', encoding='utf-8') as prev_fp:
                prev_data = json.load(prev_fp)
            prev_total = sum(prev_data.get('counts', {}).values())
            if prev_total > 0 and total_rows == 0:
                raise ValueError(f"Refusing to overwrite non-empty backup '{target_file}' with empty data.")
        except ValueError:
            raise
        except Exception:
            pass

    payload = {
        'created_at_utc': datetime.utcnow().isoformat() + 'Z',
        'dialect': db.engine.dialect.name,
        'counts': counts,
        'total_rows': total_rows,
        'tables': tables_data,
    }

    tmp_path = f"{target_file}.tmp"
    with open(tmp_path, 'w', encoding='utf-8') as fp:
        json.dump(payload, fp, indent=2)
    os.replace(tmp_path, target_file)

    # Read-back verification
    with open(target_file, 'r', encoding='utf-8') as fp:
        verified_payload = json.load(fp)
    verified_counts = {t: len(verified_payload.get('tables', {}).get(t, [])) for t in counts}
    if verified_counts != counts:
        raise RuntimeError("Backup verification mismatch after writing snapshot.")

    return {
        'path': target_file,
        'dialect': payload['dialect'],
        'counts': counts,
        'total_rows': total_rows,
        'verified': True,
    }


def restore_verified_backup(backup_path):
    """
    Safely restore missing records from a verified backup inside a single atomic transaction.
    Skips already-existing primary keys so existing production rows are never overwritten.
    """
    if not os.path.isfile(backup_path):
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    with open(backup_path, 'r', encoding='utf-8') as fp:
        payload = json.load(fp)

    tables_data = payload.get('tables', {})
    if not tables_data:
        raise ValueError("Backup file contains no table records.")

    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    is_mysql = db.engine.dialect.name == 'mysql'
    restored_counts = {}

    with db.engine.begin() as conn:
        for table in BACKUP_TABLE_ORDER:
            if table not in tables_data or table not in existing_tables:
                continue
            rows = tables_data[table]
            if not rows:
                restored_counts[table] = 0
                continue

            q_tbl = f"`{table}`" if is_mysql else f'"{table}"'
            existing_ids = set(
                r[0] for r in conn.execute(text(f"SELECT id FROM {q_tbl}")).all()
            ) if 'id' in rows[0] else set()

            inserted = 0
            for raw_row in rows:
                if 'id' in raw_row and raw_row['id'] in existing_ids:
                    continue
                row = {k: _deserialize_val(v) for k, v in raw_row.items()}
                cols = ', '.join(f"`{k}`" if is_mysql else f'"{k}"' for k in row.keys())
                placeholders = ', '.join(f":{k}" for k in row.keys())
                conn.execute(text(f"INSERT INTO {q_tbl} ({cols}) VALUES ({placeholders})"), row)
                inserted += 1
            restored_counts[table] = inserted

    return {'restored_counts': restored_counts, 'backup_path': backup_path}
