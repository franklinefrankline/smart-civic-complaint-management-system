import os
from flask import Flask, session, g, render_template, request, jsonify, Response, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import inspect, text, event
from sqlalchemy.orm import joinedload, Session
from config import config_by_name, BASE_DIR

db = SQLAlchemy()

from app.utils.ttl_cache import app_cache


@event.listens_for(Session, 'after_commit')
def _invalidate_cache_on_commit(session):
    app_cache.invalidate_prefix()


def _run_safe_schema_migrations(app):
    """
    Non-destructive, idempotent schema checks so production MySQL tables
    (including databases created from older database.sql dumps) have all
    columns and column lengths required by the application models.
    Never drops tables or deletes existing data.
    """
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    # Fast sentinel check so additional Gunicorn workers/cold boots skip full schema introspection once migrated
    if {'complaints', 'contact_messages', 'notifications', 'workers'}.issubset(table_names):
        try:
            comp_idx = {idx['name'] for idx in inspector.get_indexes('complaints')}
            contact_idx = {idx['name'] for idx in inspector.get_indexes('contact_messages')}
            notif_idx = {idx['name'] for idx in inspector.get_indexes('notifications')}
            worker_cols = {c['name'] for c in inspector.get_columns('workers')}
            if (
                'idx_comp_updated' in comp_idx
                and 'idx_contact_read_created' in contact_idx
                and 'idx_notif_complaint' in notif_idx
                and 'employee_id' in worker_cols
            ):
                return
        except Exception:
            pass

    dialect = db.engine.dialect.name
    is_mysql = dialect == 'mysql'

    with db.engine.begin() as conn:
        if 'users' in table_names:
            user_cols = {c['name'] for c in inspector.get_columns('users')}
            if 'is_password_reset_required' not in user_cols:
                conn.execute(text(
                    'ALTER TABLE users ADD COLUMN is_password_reset_required BOOLEAN NOT NULL DEFAULT FALSE'
                ))
            if 'password_changed_at' not in user_cols:
                conn.execute(text(
                    'ALTER TABLE users ADD COLUMN password_changed_at DATETIME NULL'
                ))

        if 'complaints' in table_names:
            comp_cols = {c['name']: c for c in inspector.get_columns('complaints')}
            alter_complaints = [
                ('assigned_officer_id', 'INT NULL'),
                ('assigned_worker_id', 'INT NULL'),
                ('officer_assigned_at', 'DATETIME NULL'),
                ('worker_assigned_at', 'DATETIME NULL'),
                ('admin_remarks', 'TEXT NULL'),
                ('officer_remarks', 'TEXT NULL'),
                ('verification_remarks', 'TEXT NULL'),
                ('verified_at', 'DATETIME NULL'),
            ]
            for col_name, col_def in alter_complaints:
                if col_name not in comp_cols:
                    conn.execute(text(f'ALTER TABLE complaints ADD COLUMN {col_name} {col_def}'))

            # Ensure MySQL complaints.status is VARCHAR(60) instead of restricted ENUM
            if is_mysql and 'status' in comp_cols:
                col_type_str = str(comp_cols['status'].get('type', '')).upper()
                if 'ENUM' in col_type_str or 'VARCHAR(30)' in col_type_str:
                    conn.execute(text(
                        "ALTER TABLE complaints MODIFY COLUMN status VARCHAR(60) NOT NULL DEFAULT 'Submitted'"
                    ))

        if 'complaint_status_history' in table_names and is_mysql:
            hist_cols = {c['name']: c for c in inspector.get_columns('complaint_status_history')}
            for col_name, nullable_def in [('previous_status', 'NULL'), ('new_status', 'NOT NULL')]:
                if col_name in hist_cols:
                    col_type_str = str(hist_cols[col_name].get('type', '')).upper()
                    if 'VARCHAR(30)' in col_type_str or 'VARCHAR(2' in col_type_str:
                        conn.execute(text(
                            f'ALTER TABLE complaint_status_history MODIFY COLUMN {col_name} VARCHAR(60) {nullable_def}'
                        ))

        if 'complaint_attachments' in table_names:
            att_cols = {c['name'] for c in inspector.get_columns('complaint_attachments')}
            if 'file_data' not in att_cols:
                blob_type = 'LONGBLOB NULL' if is_mysql else 'BLOB NULL'
                conn.execute(text(f'ALTER TABLE complaint_attachments ADD COLUMN file_data {blob_type}'))

        if 'notifications' in table_names:
            notif_cols = {c['name'] for c in inspector.get_columns('notifications')}
            if 'complaint_id' not in notif_cols:
                conn.execute(text('ALTER TABLE notifications ADD COLUMN complaint_id INT NULL'))
            existing_indexes = {idx['name'] for idx in inspector.get_indexes('notifications')}
            if 'idx_notif_user_read' not in existing_indexes:
                conn.execute(text('CREATE INDEX idx_notif_user_read ON notifications (user_id, is_read)'))
            if 'idx_notif_complaint' not in existing_indexes:
                conn.execute(text('CREATE INDEX idx_notif_complaint ON notifications (complaint_id)'))

        if 'workers' in table_names:
            worker_cols = {c['name'] for c in inspector.get_columns('workers')}
            if 'employee_id' not in worker_cols:
                conn.execute(text('ALTER TABLE workers ADD COLUMN employee_id VARCHAR(50) NULL'))
            worker_indexes = {idx['name'] for idx in inspector.get_indexes('workers')}
            if 'idx_workers_employee_id' not in worker_indexes and 'employee_id' not in worker_indexes:
                try:
                    conn.execute(text('CREATE UNIQUE INDEX idx_workers_employee_id ON workers (employee_id)'))
                except Exception:
                    pass

        # Non-destructive performance indexes for existing production tables
        index_specs = {
            'complaints': [
                ('idx_comp_status', 'status'),
                ('idx_comp_citizen_created', 'citizen_id, created_at'),
                ('idx_comp_dept_status_created', 'department_id, status, created_at'),
                ('idx_comp_officer_created', 'assigned_officer_id, created_at'),
                ('idx_comp_worker', 'assigned_worker_id'),
                ('idx_comp_category', 'category_id'),
                ('idx_comp_priority', 'priority'),
                ('idx_comp_created', 'created_at'),
                ('idx_comp_updated', 'updated_at'),
            ],
            'complaint_assignments': [
                ('idx_assign_to_status', 'assigned_to_user_id, status'),
                ('idx_assign_complaint', 'complaint_id'),
            ],
            'complaint_status_history': [
                ('idx_hist_complaint_created', 'complaint_id, created_at'),
            ],
            'users': [
                ('idx_users_role_active', 'role, is_active'),
                ('idx_users_dept', 'department_id'),
            ],
            'contact_messages': [
                ('idx_contact_read_created', 'is_read, created_at'),
            ],
        }
        for tbl_name, idx_list in index_specs.items():
            if tbl_name not in table_names:
                continue
            existing_tbl_indexes = {idx['name'] for idx in inspector.get_indexes(tbl_name)}
            for idx_name, cols_expr in idx_list:
                if idx_name not in existing_tbl_indexes:
                    try:
                        conn.execute(text(f'CREATE INDEX {idx_name} ON {tbl_name} ({cols_expr})'))
                    except Exception:
                        pass


def _wants_json_response():
    return (
        request.path.startswith('/api/')
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.is_json
        or 'application/json' in request.headers.get('Accept', '')
    )


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__)
    cfg_cls = config_by_name.get(config_name, config_by_name['default'])
    app.config.from_object(cfg_cls)

    if not app.config.get('TESTING'):
        from config import _build_database_config
        is_cloud, db_uri, eng_opts, db_user, db_pw, db_host, db_port, db_name, db_cfg_err = _build_database_config()
        app.config.update(
            IS_CLOUD=is_cloud,
            SQLALCHEMY_DATABASE_URI=db_uri,
            SQLALCHEMY_ENGINE_OPTIONS=eng_opts,
            DB_USER=db_user,
            DB_PASSWORD=db_pw,
            DB_HOST=db_host,
            DB_PORT=db_port,
            DB_NAME=db_name,
            DB_CONFIG_ERROR=db_cfg_err,
        )

    # Honor reverse-proxy headers from Render and Vercel (HTTPS proto, client IP)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Ensure upload directories exist safely as absolute paths (with /tmp fallback for read-only cloud filesystems)
    upload_dir = app.config.get('UPLOAD_FOLDER', '/tmp/uploads')
    if not os.path.isabs(upload_dir):
        upload_dir = os.path.abspath(os.path.join(BASE_DIR, upload_dir))
    app.config['UPLOAD_FOLDER'] = upload_dir
    try:
        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(os.path.join(upload_dir, 'complaints'), exist_ok=True)
        os.makedirs(os.path.join(upload_dir, 'proofs'), exist_ok=True)
    except Exception:
        app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
        try:
            os.makedirs('/tmp/uploads/complaints', exist_ok=True)
            os.makedirs('/tmp/uploads/proofs', exist_ok=True)
        except Exception:
            pass

    # Initialize extensions
    db.init_app(app)

    # Register local timezone Jinja filter so all timestamps reflect user's local current time
    from app.utils.helpers import format_local_time
    app.jinja_env.filters['local_time'] = format_local_time

    # Import models so SQLAlchemy is aware of them
    from app import models

    # Initialize database tables & additive-only migrations (NEVER drops, resets, or auto-seeds production)
    app.config['DB_STARTUP_ERROR'] = app.config.get('DB_CONFIG_ERROR')
    with app.app_context():
        if app.config.get('TESTING'):
            try:
                db.create_all()
                _run_safe_schema_migrations(app)
            except Exception as e:
                app.logger.warning(f"Test DB startup notice: {e}")
        elif app.config.get('DB_STARTUP_ERROR'):
            app.logger.critical(app.config['DB_STARTUP_ERROR'])
        else:
            try:
                db.session.execute(text('SELECT 1'))
                db.create_all()
                _run_safe_schema_migrations(app)
                if os.environ.get('AUTO_SEED', '').strip().lower() != 'false':
                    from app.models.department import Department
                    from app.models.user import User
                    from sqlalchemy.exc import IntegrityError
                    has_departments = Department.query.first() is not None
                    has_admin = User.query.filter_by(role='admin').first() is not None
                    if not has_departments or not has_admin:
                        try:
                            from app.services.seed_service import seed_all
                            seed_all()
                        except IntegrityError:
                            # Concurrent multi-worker startup already seeded initial records.
                            db.session.rollback()
            except Exception as e:
                import re as _re
                db.session.rollback()
                raw_reason = str(getattr(e, 'orig', e))
                safe_reason = _re.sub(r'://([^:@]+):([^@]+)@', r'://***:***@', raw_reason)
                safe_reason = _re.sub(r"'[^']+'@'[^']+'", "'***'@'***'", safe_reason)
                if len(safe_reason) > 220:
                    safe_reason = safe_reason[:220] + '...'
                app.config['DB_STARTUP_ERROR'] = (
                    f"Database connection failed ({type(e).__name__}). Verify database credentials, host access, and database name."
                )
                app.logger.critical(
                    f"Production DB connection failed (halting initialization): {type(e).__name__} - {safe_reason}"
                )

    @app.before_request
    def guard_database_availability():
        if app.config.get('DB_STARTUP_ERROR') and not request.path.startswith(('/static/', '/health', '/healthz', '/api/health')):
            if _wants_json_response():
                return jsonify({
                    'success': False,
                    'error': 'Database Unavailable',
                    'message': app.config['DB_STARTUP_ERROR'],
                }), 503
            return render_template(
                'public/error.html',
                code=503,
                title="Database Connection Unavailable",
                message=app.config['DB_STARTUP_ERROR'],
            ), 503

    # CORS preflight handler (strictly limited to configured allowed origins)
    @app.before_request
    def handle_cors_preflight():
        if request.method == 'OPTIONS':
            origin = request.headers.get('Origin', '').rstrip('/')
            allowed = app.config.get('CORS_ALLOWED_ORIGINS', [])
            if origin in allowed:
                resp = app.make_default_options_response()
                resp.headers['Access-Control-Allow-Origin'] = origin
                resp.headers['Access-Control-Allow-Credentials'] = 'true'
                resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
                resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, Accept'
                resp.headers['Vary'] = 'Origin'
                return resp

    @app.after_request
    def apply_cors_headers(response):
        origin = request.headers.get('Origin', '').rstrip('/')
        allowed = app.config.get('CORS_ALLOWED_ORIGINS', [])
        if origin and origin in allowed:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, Accept'
            response.headers['Vary'] = 'Origin'
        return response

    # Context processor for templates
    @app.context_processor
    def inject_global_data():
        from app.utils.translations import get_translation
        current_lang = session.get('lang', 'en')

        def t(key, default=None):
            return get_translation(key, current_lang, default)

        if request.path.startswith(('/api/', '/static/', '/health', '/uploads/', '/proofs/')):
            return dict(
                current_user=None,
                current_lang=current_lang,
                t=t,
                unread_notifications_count=0,
                api_base_url=app.config.get('API_BASE_URL', ''),
                available_languages=[
                    {'code': 'en', 'name': 'English', 'native': 'English'},
                    {'code': 'ta', 'name': 'Tamil', 'native': 'தமிழ்'},
                    {'code': 'hi', 'name': 'Hindi', 'native': 'हिन्दी'}
                ]
            )

        from app.models.user import User
        from app.models.notification import Notification

        user_id = session.get('user_id')
        cached_user = getattr(g, 'user', None)
        user = cached_user if (user_id and cached_user is not None and getattr(cached_user, 'id', None) == user_id) else None
        unread_notifications_count = 0
        if user is None and user_id:
            try:
                user = (
                    db.session.query(User)
                    .options(joinedload(User.department))
                    .filter_by(id=user_id)
                    .first()
                )
                if user is not None:
                    g.user = user
            except Exception:
                db.session.rollback()
                user = None

        if user:
            cache_key = f"notif:unread:{user.id}"
            use_cache = not app.config.get('TESTING')
            cached_count = app_cache.get(cache_key) if use_cache else None
            if cached_count is not None:
                unread_notifications_count = cached_count
            else:
                try:
                    unread_notifications_count = Notification.query.filter_by(
                        user_id=user.id, is_read=False
                    ).count()
                    if use_cache:
                        app_cache.set(cache_key, unread_notifications_count, ttl_seconds=15)
                except Exception:
                    db.session.rollback()

        def t(key, default=None):
            return get_translation(key, current_lang, default)

        return dict(
            current_user=user,
            current_lang=current_lang,
            t=t,
            unread_notifications_count=unread_notifications_count,
            api_base_url=app.config.get('API_BASE_URL', ''),
            available_languages=[
                {'code': 'en', 'name': 'English', 'native': 'English'},
                {'code': 'ta', 'name': 'Tamil', 'native': 'தமிழ்'},
                {'code': 'hi', 'name': 'Hindi', 'native': 'हिन्दी'}
            ]
        )

    # Global error handlers (JSON for API/AJAX, HTML template for pages)
    @app.errorhandler(403)
    def forbidden(error):
        if _wants_json_response():
            return jsonify({'success': False, 'error': 'Access forbidden'}), 403
        return render_template('public/error.html', code=403, title="Access Forbidden", message="You do not have permission to access this resource."), 403

    @app.errorhandler(404)
    def not_found(error):
        if _wants_json_response():
            return jsonify({'success': False, 'error': 'Resource not found'}), 404
        return render_template('public/error.html', code=404, title="Page Not Found", message="The requested page could not be located."), 404

    @app.errorhandler(413)
    def payload_too_large(error):
        if _wants_json_response():
            return jsonify({'success': False, 'error': 'Uploaded file exceeds maximum 10 MB limit.'}), 413
        return render_template('public/error.html', code=413, title="File Too Large", message="Uploaded file exceeds the 10 MB limit."), 413

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        app.logger.exception("Unhandled 500 error: %s", error)
        if _wants_json_response():
            return jsonify({
                'success': False,
                'error': 'Internal server error occurred. Please try again.',
                'message': 'Internal server error occurred. Please try again.',
            }), 500
        return render_template('public/error.html', code=500, title="System Error", message="An unexpected error occurred. Our technical team has been notified."), 500

    # Health check endpoints for Render & Uptime probes
    @app.route('/health')
    @app.route('/healthz')
    def health_check():
        if app.config.get('DB_STARTUP_ERROR'):
            return jsonify({
                'status': 'error',
                'service': 'smart-civic-complaint-system',
                'database': 'misconfigured',
                'message': app.config['DB_STARTUP_ERROR'],
            }), 503
        try:
            db.session.execute(text('SELECT 1'))
            return jsonify({
                'status': 'ok',
                'service': 'smart-civic-complaint-system',
                'database': 'connected',
                'dialect': db.engine.dialect.name
            }), 200
        except Exception:
            return jsonify({
                'status': 'degraded',
                'service': 'smart-civic-complaint-system',
                'database': 'disconnected'
            }), 503

    # Register Blueprints
    from app.routes.public import public_bp
    from app.routes.auth import auth_bp
    from app.routes.citizen import citizen_bp
    from app.routes.admin import admin_bp
    from app.routes.officer import officer_bp
    from app.routes.worker import worker_bp
    from app.routes.api import api_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(citizen_bp, url_prefix='/citizen')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(officer_bp, url_prefix='/officer')
    app.register_blueprint(worker_bp, url_prefix='/worker')
    app.register_blueprint(api_bp, url_prefix='/api')

    # Persistent uploads handler: checks local disk first, falls back to MySQL BLOB storage
    def _serve_attachment_from_db(filename_or_path):
        import mimetypes
        from app.models.attachment import ComplaintAttachment
        clean = filename_or_path.replace('\\', '/').lstrip('/')
        basename = os.path.basename(clean)
        att = ComplaintAttachment.query.filter(
            (ComplaintAttachment.filename == basename)
            | (ComplaintAttachment.file_path == clean)
            | (ComplaintAttachment.file_path == f"uploads/{clean}")
            | (ComplaintAttachment.file_path == f"uploads/proofs/{basename}")
            | (ComplaintAttachment.file_path == f"uploads/complaints/{basename}")
        ).first()
        if att and att.file_data:
            mime = att.mime_type or 'application/octet-stream'
            if mime == 'application/octet-stream':
                guessed, _ = mimetypes.guess_type(att.filename or basename)
                if guessed:
                    mime = guessed
            resp = Response(att.file_data, mimetype=mime)
            resp.headers['Cache-Control'] = 'public, max-age=86400'
            return resp
        return None

    def _resolved_upload_root():
        raw_dir = app.config.get('UPLOAD_FOLDER', '/tmp/uploads')
        return raw_dir if os.path.isabs(raw_dir) else os.path.abspath(os.path.join(BASE_DIR, raw_dir))

    @app.route('/uploads/<path:filename>', strict_slashes=False)
    def uploaded_file(filename):
        clean_filename = filename.replace('\\', '/')
        while clean_filename.startswith('uploads/'):
            clean_filename = clean_filename[8:]

        abs_upload_dir = _resolved_upload_root()
        for candidate_dir in (abs_upload_dir, os.path.abspath(os.path.join(BASE_DIR, 'uploads'))):
            file_path = os.path.join(candidate_dir, clean_filename)
            if os.path.isfile(file_path):
                try:
                    return send_from_directory(candidate_dir, clean_filename)
                except Exception:
                    pass

        db_resp = _serve_attachment_from_db(clean_filename)
        if db_resp is not None:
            return db_resp

        return render_template('public/error.html', code=404, title="File Not Found", message="The requested attachment could not be found."), 404

    @app.route('/proofs/<path:filename>', strict_slashes=False)
    def uploaded_proofs(filename):
        clean = filename.replace('\\', '/')
        abs_upload_dir = _resolved_upload_root()
        for candidate_dir in (
            os.path.join(abs_upload_dir, 'proofs'),
            os.path.abspath(os.path.join(BASE_DIR, 'uploads', 'proofs')),
        ):
            if os.path.isfile(os.path.join(candidate_dir, clean)):
                try:
                    return send_from_directory(candidate_dir, clean)
                except Exception:
                    pass

        db_resp = _serve_attachment_from_db(clean)
        if db_resp is not None:
            return db_resp

        return render_template('public/error.html', code=404, title="File Not Found", message="The requested proof file could not be found."), 404

    return app


# Default application instance for WSGI servers (e.g. gunicorn app:app)
app = create_app()
