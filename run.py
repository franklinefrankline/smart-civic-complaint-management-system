import sys
import os
from datetime import datetime, timedelta
from app import create_app, db
from app.models.user import User
from app.models.department import Department
from app.models.category import ComplaintCategory
from app.models.complaint import Complaint
from app.models.workflow import Worker, ComplaintAssignment, ComplaintStatusHistory
from app.models.attachment import ComplaintAttachment
from app.models.notification import Notification
from app.models.feedback import Feedback
from app.models.audit import AuditLog, SystemSetting
from app.services.sla_service import calculate_sla_due_date
from app.utils.helpers import generate_complaint_ref

app = create_app()

def init_db():
    """Create all database tables in MySQL"""
    with app.app_context():
        print("Connecting to MySQL and initializing schema...")
        db.create_all()
        print("Schema successfully initialized in MySQL!")

def seed_db():
    """Populate database with initial civic departments, categories, and test accounts"""
    with app.app_context():
        init_db()
        print("Seeding civic departments and complaint categories...")
        from app.services.seed_service import seed_all
        seed_all()
        print("Database initialization completed with civic departments, categories, settings, administrator, officers, and workers.")

def create_admin():
    """Interactive command to create a custom administrator"""
    with app.app_context():
        import getpass
        print("\n--- Create Municipal Administrator ---")
        full_name = input("Admin Full Name: ").strip() or "Administrator"
        email = input("Admin Email: ").strip().lower()
        if not email:
            print("Email is required.")
            return
        if User.query.filter_by(email=email).first():
            print(f"Error: User with email '{email}' already exists.")
            return
        mobile = input("Admin Mobile Number: ").strip() or "9900000000"
        password = getpass.getpass("Admin Password: ")
        if len(password) < 8:
            print("Password must be at least 8 characters.")
            return

        admin_user = User(
            role='admin',
            full_name=full_name,
            email=email,
            mobile_number=mobile,
            is_active=True
        )
        admin_user.set_password(password)
        db.session.add(admin_user)
        db.session.commit()
        print(f"Administrator account '{email}' created successfully!")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == 'init-db':
            init_db()
        elif cmd == 'seed-db':
            seed_db()
        elif cmd == 'create-admin':
            create_admin()
        elif cmd == 'check-migrations':
            with app.app_context():
                from app.services.backup_service import get_migration_status
                status = get_migration_status()
                print("Migration Status:", status)
        elif cmd == 'backup-db':
            with app.app_context():
                from app.services.backup_service import create_verified_backup
                allow_empty = '--allow-empty' in sys.argv[2:]
                res = create_verified_backup(allow_empty=allow_empty)
                print(f"Verified backup created: {res['path']}")
                print(f"Dialect: {res['dialect']} | Total rows: {res['total_rows']}")
                print(f"Counts: {res['counts']}")
        elif cmd == 'restore-db':
            if len(sys.argv) < 3:
                print("Usage: python run.py restore-db <backup_file.json>")
                sys.exit(1)
            with app.app_context():
                from app.services.backup_service import restore_verified_backup
                res = restore_verified_backup(sys.argv[2])
                print("Restore completed:", res)
        else:
            print(f"Unknown command: {cmd}")
            print("Available commands: init-db, seed-db, create-admin, check-migrations, backup-db, restore-db")
    else:
        if app.config.get('DB_STARTUP_ERROR'):
            print(f"FATAL DATABASE ERROR: {app.config['DB_STARTUP_ERROR']}")
            sys.exit(1)

        # Development / Production server
        port = int(os.environ.get('PORT', 5000))
        host = '0.0.0.0' if os.environ.get('PORT') else '127.0.0.1'
        print(f"Starting Smart Civic Complaint System on http://{host}:{port}")
        app.run(host=host, port=port, debug=False if os.environ.get('RENDER') else True)
