import unittest
from app import create_app, db
from app.models.user import User
from app.models.department import Department
from app.models.category import ComplaintCategory
from app.models.complaint import Complaint
from app.models.workflow import Worker, ComplaintAssignment, ComplaintStatusHistory
from app.models.notification import Notification

class AccountDeletionTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        # Seed Department and Category
        self.dept = Department(name='Sanitation Dept', code='SAN', is_active=True)
        db.session.add(self.dept)
        db.session.flush()

        self.cat = ComplaintCategory(
            name='Garbage Removal',
            department_id=self.dept.id,
            default_priority='medium',
            sla_hours=48,
            is_active=True
        )
        db.session.add(self.cat)
        db.session.commit()

        # Seed Admin
        self.admin = User(
            role='admin',
            full_name='Master Admin',
            email='admin.del@test.gov',
            mobile_number='9999000001',
            is_active=True
        )
        self.admin.set_password('Admin@123')

        # Seed Citizen
        self.citizen = User(
            role='citizen',
            full_name='Citizen John',
            email='citizen.del@test.gov',
            mobile_number='9999000002',
            is_active=True
        )
        self.citizen.set_password('Citizen@123')

        # Seed Officer
        self.officer = User(
            role='officer',
            full_name='Officer Mike',
            email='officer.del@test.gov',
            mobile_number='9999000003',
            department_id=self.dept.id,
            is_active=True
        )
        self.officer.set_password('Officer@123')

        # Seed Worker
        self.worker_user = User(
            role='worker',
            full_name='Worker Bob',
            email='worker.del@test.gov',
            mobile_number='9999000004',
            department_id=self.dept.id,
            is_active=True
        )
        self.worker_user.set_password('Worker@123')

        db.session.add_all([self.admin, self.citizen, self.officer, self.worker_user])
        db.session.commit()

        self.worker_profile = Worker(user_id=self.worker_user.id, department_id=self.dept.id)
        db.session.add(self.worker_profile)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login_admin(self):
        return self.client.post('/auth/login', data={
            'login_id': 'admin.del@test.gov',
            'password': 'Admin@123'
        }, follow_redirects=True)

    def test_admin_cannot_delete_self(self):
        """Admin is prevented from deleting their own active account"""
        self.login_admin()
        res = self.client.post('/admin/users', data={
            'action': 'delete_user',
            'user_id': self.admin.id
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Security restriction: You cannot delete your own active administrator account.', res.data)
        admin_check = User.query.get(self.admin.id)
        self.assertIsNotNone(admin_check)

    def test_admin_delete_citizen_with_complaints(self):
        """Admin can permanently delete a citizen account and its associated complaints/histories"""
        # Create a complaint filed by citizen
        c = Complaint(
            complaint_ref='CMP-TEST-DEL01',
            citizen_id=self.citizen.id,
            department_id=self.dept.id,
            category_id=self.cat.id,
            title='Test Complaint for Citizen Deletion',
            description='Detailed test description',
            status='Submitted'
        )
        db.session.add(c)
        db.session.flush()

        hist = ComplaintStatusHistory(
            complaint_id=c.id,
            changed_by_user_id=self.citizen.id,
            previous_status=None,
            new_status='Submitted',
            remarks='Registered'
        )
        notif = Notification(user_id=self.citizen.id, title='Welcome', message='Account created')
        db.session.add_all([hist, notif])
        db.session.commit()

        citizen_id = self.citizen.id
        complaint_id = c.id

        self.login_admin()
        res = self.client.post('/admin/users', data={
            'action': 'delete_user',
            'user_id': citizen_id
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'permanently deleted', res.data)

        # Verify citizen is gone from DB
        self.assertIsNone(User.query.get(citizen_id))
        # Verify complaint and notif are cleaned up
        self.assertIsNone(Complaint.query.get(complaint_id))
        self.assertEqual(Notification.query.filter_by(user_id=citizen_id).count(), 0)

    def test_admin_delete_worker_account(self):
        """Admin can permanently delete a worker account and its profile"""
        worker_id = self.worker_user.id
        self.login_admin()
        res = self.client.post('/admin/users', data={
            'action': 'delete_user',
            'user_id': worker_id
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'permanently deleted', res.data)
        self.assertIsNone(User.query.get(worker_id))
        self.assertEqual(Worker.query.filter_by(user_id=worker_id).count(), 0)

    def test_admin_delete_officer_account(self):
        """Admin can permanently delete an officer account"""
        officer_id = self.officer.id
        self.login_admin()
        res = self.client.post('/admin/users', data={
            'action': 'delete_user',
            'user_id': officer_id
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'permanently deleted', res.data)
        self.assertIsNone(User.query.get(officer_id))

    def test_ui_renders_delete_action_options(self):
        """UI pages for users, citizens, officers, and workers contain Delete buttons"""
        self.login_admin()

        # Users table
        res_users = self.client.get('/admin/users')
        self.assertEqual(res_users.status_code, 200)
        self.assertIn(b'name="action" value="delete_user"', res_users.data)
        self.assertIn(b'Current Admin', res_users.data)

        # Citizens table
        res_citizens = self.client.get('/admin/citizens')
        self.assertEqual(res_citizens.status_code, 200)
        self.assertIn(b'name="action" value="delete_user"', res_citizens.data)

        # Officers table
        res_officers = self.client.get('/admin/officers')
        self.assertEqual(res_officers.status_code, 200)
        self.assertIn(b'name="action" value="delete_user"', res_officers.data)

        # Workers table
        res_workers = self.client.get('/admin/workers')
        self.assertEqual(res_workers.status_code, 200)
        self.assertIn(b'name="action" value="delete_user"', res_workers.data)
