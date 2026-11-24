import unittest
from datetime import datetime
from app import create_app, db
from app.models.user import User

class TestFirstTimePasswordReset(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Create Department
        from app.models.department import Department
        self.dept = Department(name='Public Works', code='PWD', description='PWD Dept')
        db.session.add(self.dept)

        # Create Admin
        self.admin = User(
            full_name='Master Admin',
            email='master_admin@civic.gov',
            mobile_number='9800000001',
            role='admin',
            is_active=True,
            is_password_reset_required=False,
            password_changed_at=datetime.utcnow()
        )
        self.admin.set_password('Admin@123')
        db.session.add(self.admin)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_admin_created_user_requires_password_reset(self):
        # 1. Admin logs in
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin.id
            sess['role'] = 'admin'

        # 2. Admin creates a new department officer
        res = self.client.post('/admin/users', data={
            'action': 'add_user',
            'full_name': 'New Officer',
            'email': 'officer_test@civic.gov',
            'mobile': '9812345678',
            'role': 'officer',
            'department_id': self.dept.id,
            'password': 'InitialTempPassword@123'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(res.status_code, 200)

        # Verify user in database has is_password_reset_required=True
        user = User.query.filter_by(email='officer_test@civic.gov').first()
        self.assertIsNotNone(user)
        self.assertTrue(user.is_password_reset_required)
        self.assertIsNone(user.password_changed_at)

        # Verify admin users table shows "Pending Reset"
        res_users = self.client.get('/admin/users')
        html = res_users.data.decode('utf-8')
        self.assertIn('Pending Reset', html)

        # 3. Admin logs out
        self.client.get('/auth/logout')

        # 4. New Officer logs in with temporary password
        res_login = self.client.post('/auth/login', data={
            'login_id': 'officer_test@civic.gov',
            'password': 'InitialTempPassword@123'
        }, follow_redirects=False)

        # Must redirect to force-reset-password
        self.assertEqual(res_login.status_code, 302)
        self.assertIn('/auth/force-reset-password', res_login.location)

        # 5. Access force-reset-password page
        res_reset_page = self.client.get('/auth/force-reset-password')
        self.assertEqual(res_reset_page.status_code, 200)
        self.assertIn('Set Your New Password', res_reset_page.data.decode('utf-8'))
        self.assertIn('New Officer', res_reset_page.data.decode('utf-8'))

        # 6. Try submitting mismatched passwords
        res_mismatch = self.client.post('/auth/force-reset-password', data={
            'new_password': 'MyNewPassword@123',
            'confirm_password': 'WrongMismatchPassword@123'
        }, follow_redirects=True)
        self.assertIn('Passwords do not match', res_mismatch.data.decode('utf-8'))
        user_check = User.query.filter_by(email='officer_test@civic.gov').first()
        self.assertTrue(user_check.is_password_reset_required)

        # 7. Submit valid new password
        res_success = self.client.post('/auth/force-reset-password', data={
            'new_password': 'OfficerSecret@2026',
            'confirm_password': 'OfficerSecret@2026'
        }, follow_redirects=True)
        self.assertEqual(res_success.status_code, 200)
        self.assertIn('Your password has been successfully updated', res_success.data.decode('utf-8'))

        # User is now on their officer dashboard
        self.assertIn('Department Officer', res_success.data.decode('utf-8'))

        # Verify database state
        user_updated = User.query.filter_by(email='officer_test@civic.gov').first()
        self.assertFalse(user_updated.is_password_reset_required)
        self.assertIsNotNone(user_updated.password_changed_at)
        self.assertTrue(user_updated.check_password('OfficerSecret@2026'))
        self.assertFalse(user_updated.check_password('InitialTempPassword@123'))

        # 8. Check admin view now shows "Changed"
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin.id
            sess['role'] = 'admin'
        res_admin_view = self.client.get('/admin/users')
        admin_html = res_admin_view.data.decode('utf-8')
        self.assertIn('Changed', admin_html)

if __name__ == '__main__':
    unittest.main()
