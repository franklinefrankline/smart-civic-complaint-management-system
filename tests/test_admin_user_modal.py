import unittest
from app import create_app, db
from app.models.user import User

class TestAdminUserModal(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Create Admin
        self.admin = User(
            full_name='Test Admin',
            email='admin_modal_test@civic.gov',
            mobile_number='9811122233',
            role='admin',
            is_active=True
        )
        self.admin.set_password('Admin@123')
        db.session.add(self.admin)

        # Create existing citizen
        self.citizen = User(
            full_name='Existing Citizen',
            email='existing_citizen@civic.gov',
            mobile_number='9844455566',
            role='citizen',
            is_active=True
        )
        self.citizen.set_password('Citizen@123')
        db.session.add(self.citizen)
        db.session.commit()

        # Login as admin
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin.id
            sess['role'] = 'admin'

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_duplicate_mobile_does_not_close_form(self):
        """When submitting duplicate mobile via AJAX, return 400 with field='mobile' without closing modal"""
        res = self.client.post('/admin/users', data={
            'action': 'add_user',
            'full_name': 'New User Test',
            'email': 'new_unique_email@civic.gov',
            'mobile': '9844455566',  # duplicate mobile
            'role': 'citizen',
            'password': 'Password@123'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})

        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['field'], 'mobile')
        self.assertIn('mobile number already exists', data['message'])

    def test_duplicate_email_does_not_close_form(self):
        """When submitting duplicate email via AJAX, return 400 with field='email' without closing modal"""
        res = self.client.post('/admin/users', data={
            'action': 'add_user',
            'full_name': 'New User Test',
            'email': 'existing_citizen@civic.gov',  # duplicate email
            'mobile': '9877788899',  # unique mobile
            'role': 'citizen',
            'password': 'Password@123'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})

        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['field'], 'email')
        self.assertIn('email already exists', data['message'])

    def test_duplicate_both_indicates_both_fields(self):
        """When submitting both duplicate email and mobile, return 400 with field='both'"""
        res = self.client.post('/admin/users', data={
            'action': 'add_user',
            'full_name': 'New User Test',
            'email': 'existing_citizen@civic.gov',
            'mobile': '9844455566',
            'role': 'citizen',
            'password': 'Password@123'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})

        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['field'], 'both')

    def test_successful_user_creation(self):
        """When submitting unique details, create user and return 200 success"""
        res = self.client.post('/admin/users', data={
            'action': 'add_user',
            'full_name': 'Valid User',
            'email': 'valid_brand_new@civic.gov',
            'mobile': '9877711122',
            'role': 'citizen',
            'password': 'Password@123'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        user = User.query.filter_by(email='valid_brand_new@civic.gov').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.mobile_number, '9877711122')

    def test_non_ajax_fallback_preserves_modal_and_inputs(self):
        """When submitting via regular POST, template renders with modal_open=True and preserved data"""
        res = self.client.post('/admin/users', data={
            'action': 'add_user',
            'full_name': 'Fallback User',
            'email': 'fallback_unique@civic.gov',
            'mobile': '9844455566',  # duplicate
            'role': 'citizen',
            'password': 'Password@123'
        })

        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn('Fallback User', html)
        self.assertIn('fallback_unique@civic.gov', html)
        self.assertIn('User with this mobile number already exists.', html)

if __name__ == '__main__':
    unittest.main()
