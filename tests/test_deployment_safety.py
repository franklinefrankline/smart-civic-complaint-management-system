import os
import tempfile
import unittest
from app import create_app, db
from app.models.user import User
from app.models.department import Department
from app.models.category import ComplaintCategory
from app.models.complaint import Complaint
from app.models.workflow import Worker, ComplaintAssignment, ComplaintStatusHistory
from app.models.notification import Notification
from app.models.audit import AuditLog
from app.services.complaint_service import (
    assign_department_officer,
    assign_complaint_to_worker,
)
from app.services.backup_service import (
    create_verified_backup,
    restore_verified_backup,
    get_migration_status,
)
from config import _build_database_config, BASE_DIR


class DeploymentSafetyTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.dept = Department(name='Public Water Works', code='WATER_SAFE', is_active=True)
        db.session.add(self.dept)
        db.session.flush()

        self.cat = ComplaintCategory(
            name='Main Pipe Burst',
            department_id=self.dept.id,
            default_priority='high',
            sla_hours=48,
            is_active=True,
        )
        db.session.add(self.cat)
        db.session.flush()

        self.admin = User(role='admin', full_name='Deploy Admin', email='admin.safe@civic.gov', mobile_number='9700000001', is_active=True)
        self.admin.set_password('Admin@123')
        self.officer = User(role='officer', full_name='Deploy Officer', email='officer.safe@civic.gov', mobile_number='9700000002', department_id=self.dept.id, is_active=True)
        self.officer.set_password('Officer@123')
        self.worker_user = User(role='worker', full_name='Deploy Worker', email='worker.safe@civic.gov', mobile_number='9700000003', department_id=self.dept.id, is_active=True)
        self.worker_user.set_password('Worker@123')
        db.session.add_all([self.admin, self.officer, self.worker_user])
        db.session.flush()

        self.worker = Worker(
            user_id=self.worker_user.id,
            department_id=self.dept.id,
            employee_id='EMP-SAFE-01',
            designation='Water Technician',
            is_available=True,
        )
        db.session.add(self.worker)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_cloud_without_mysql_refuses_ephemeral_sqlite_fallback(self):
        orig_env = os.environ.copy()
        try:
            for k in (
                'DATABASE_URL', 'MYSQL_URL', 'MYSQL_PUBLIC_URL', 'MYSQL_DATABASE_URL', 'DB_URL',
                'SQLALCHEMY_DATABASE_URI', 'DB_HOST', 'MYSQLHOST', 'MYSQL_HOST',
                'DB_USER', 'MYSQLUSER', 'MYSQL_USER',
                'DB_PASSWORD', 'MYSQLPASSWORD', 'MYSQL_PASSWORD',
                'DB_PORT', 'MYSQLPORT', 'MYSQL_PORT',
                'DB_NAME', 'DB_DATABASE', 'MYSQLDATABASE', 'MYSQL_DATABASE', 'MYSQL_DB',
                'ALLOW_EPHEMERAL_SQLITE',
            ):
                os.environ.pop(k, None)
            os.environ['RENDER'] = 'true'

            is_cloud, uri, _, _, _, _, _, _, err = _build_database_config()
            self.assertTrue(is_cloud)
            self.assertIsNotNone(err)
            self.assertNotEqual(uri, 'sqlite:////tmp/smart_civic.db')
            self.assertIn('Render Environment Variables', err)

            # Underscore MySQL env var aliases (e.g. MYSQL_HOST, MYSQL_DATABASE) also resolve cleanly
            os.environ['MYSQL_HOST'] = 'mysql.prod.example.com'
            os.environ['MYSQL_USER'] = 'produser'
            os.environ['MYSQL_PASSWORD'] = 'ProdPass@123'
            os.environ['MYSQL_DATABASE'] = 'civic_prod'
            _, alias_uri, _, _, _, _, _, _, alias_err = _build_database_config()
            self.assertIsNone(alias_err)
            self.assertTrue(alias_uri.startswith('mysql+pymysql://produser:'))
            self.assertIn('mysql.prod.example.com:3306/civic_prod', alias_uri)
        finally:
            os.environ.clear()
            os.environ.update(orig_env)

    def test_no_destructive_sql_in_schema_or_startup(self):
        sql_path = os.path.join(BASE_DIR, 'database.sql')
        with open(sql_path, 'r', encoding='utf-8') as fh:
            sql_text = fh.read().upper()
        self.assertNotIn('DROP TABLE', sql_text)
        self.assertNotIn('DROP DATABASE', sql_text)
        self.assertNotIn('TRUNCATE', sql_text)

        init_path = os.path.join(BASE_DIR, 'app', '__init__.py')
        with open(init_path, 'r', encoding='utf-8') as fh:
            init_src = fh.read()
        self.assertNotIn('drop_all', init_src)

    def test_end_to_end_records_backup_rebuild_and_login_preservation(self):
        client = self.app.test_client()

        # 1. Register a test citizen account
        reg = client.post('/auth/register', data={
            'full_name': 'Safe Citizen User',
            'email': 'safe.citizen@civic.gov',
            'mobile': '9700000099',
            'password': 'CitizenPass@123',
            'confirm_password': 'CitizenPass@123',
            'address': '10 Green St',
            'city': 'Chennai',
            'ward_number': '12',
        }, follow_redirects=True)
        self.assertEqual(reg.status_code, 200)
        citizen = User.query.filter_by(email='safe.citizen@civic.gov').first()
        self.assertIsNotNone(citizen)

        # 2. Citizen logs in & submits a test complaint
        login_res = client.post('/auth/login', data={'login_id': 'safe.citizen@civic.gov', 'password': 'CitizenPass@123'})
        self.assertEqual(login_res.status_code, 302)
        comp_res = client.post('/citizen/complaints/new', data={
            'title': 'Deployment preservation leak report',
            'category_id': self.cat.id,
            'department_id': self.dept.id,
            'priority': 'high',
            'description': 'Verifying complaint, history, and notification persistence across rebuilds.',
            'ward_number': '12',
            'city': 'Chennai',
        }, follow_redirects=False)
        comp_id = int(comp_res.headers['Location'].rstrip('/').split('/')[-1])
        complaint = db.session.get(Complaint, comp_id)
        self.assertIsNotNone(complaint)

        # 3 & 4. Assign to Department Officer and Field Worker
        assign_department_officer(complaint, self.dept.id, self.officer.id, self.admin, admin_remarks='Deploy test triage')
        assign_complaint_to_worker(complaint, self.worker_user.id, self.officer, instructions='Deploy test dispatch')

        # Record counts & IDs BEFORE simulated build/restart
        before_counts = {
            'users': User.query.count(),
            'complaints': Complaint.query.count(),
            'assignments': ComplaintAssignment.query.count(),
            'history': ComplaintStatusHistory.query.count(),
            'notifications': Notification.query.count(),
            'audit': AuditLog.query.count(),
            'workers': Worker.query.count(),
        }
        orig_citizen_id = citizen.id
        orig_citizen_hash = citizen.password_hash
        orig_comp_id = complaint.id

        # 5. Verified backup creation + non-empty protection
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_path = os.path.join(tmpdir, 'verified_prod_backup.json')
            backup_meta = create_verified_backup(output_dir=tmpdir, target_file=backup_path)
            self.assertTrue(backup_meta['verified'])
            self.assertEqual(backup_meta['counts']['users'], before_counts['users'])
            self.assertEqual(backup_meta['counts']['complaints'], before_counts['complaints'])

            # Restore check (idempotent, preserves existing rows)
            restore_res = restore_verified_backup(backup_path)
            self.assertEqual(restore_res['restored_counts']['users'], 0)

        mig_status = get_migration_status()
        self.assertTrue(mig_status['is_up_to_date'])

        # 6. Simulate a new application startup / build against the same persistent DB
        db.create_all()
        from app import _run_safe_schema_migrations
        _run_safe_schema_migrations(self.app)

        # 7. Confirm counts, IDs, password hashes, and roles remained unchanged
        after_counts = {
            'users': User.query.count(),
            'complaints': Complaint.query.count(),
            'assignments': ComplaintAssignment.query.count(),
            'history': ComplaintStatusHistory.query.count(),
            'notifications': Notification.query.count(),
            'audit': AuditLog.query.count(),
            'workers': Worker.query.count(),
        }
        self.assertEqual(before_counts, after_counts)
        citizen_after = User.query.filter_by(email='safe.citizen@civic.gov').first()
        self.assertEqual(citizen_after.id, orig_citizen_id)
        self.assertEqual(citizen_after.password_hash, orig_citizen_hash)
        comp_after = db.session.get(Complaint, orig_comp_id)
        self.assertEqual(comp_after.status, 'Assigned to Worker')

        # 8 & 9. Existing citizen still logs in & history/notifications remain intact
        client2 = self.app.test_client()
        relogin = client2.post('/auth/login', data={'login_id': 'safe.citizen@civic.gov', 'password': 'CitizenPass@123'})
        self.assertEqual(relogin.status_code, 302)
        notifs = client2.get('/api/notifications').get_json()
        self.assertGreaterEqual(len(notifs['notifications']), 1)
        detail_html = client2.get(f'/citizen/complaints/{orig_comp_id}').get_data(as_text=True)
        self.assertIn('Deployment preservation leak report', detail_html)
        self.assertIn('Deploy test triage', detail_html)


if __name__ == '__main__':
    unittest.main()
