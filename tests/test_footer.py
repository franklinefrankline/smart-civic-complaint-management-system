import unittest
from app import create_app, db
from app.models.user import User

class FooterDisplayTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        # Seed admin and citizen
        self.admin = User(role='admin', full_name='Admin User', email='admin.footer@test.gov', mobile_number='9999999991', is_active=True)
        self.admin.set_password('Admin@123')
        self.citizen = User(role='citizen', full_name='Citizen User', email='citizen.footer@test.gov', mobile_number='9999999992', is_active=True)
        self.citizen.set_password('Citizen@123')
        db.session.add_all([self.admin, self.citizen])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_footer_displayed_on_home_page_only(self):
        # 1. Home Page MUST have footer
        res_home = self.client.get('/')
        self.assertEqual(res_home.status_code, 200)
        self.assertIn(b'<footer class="footer">', res_home.data)

        # 2. Login Page MUST NOT have footer
        res_login = self.client.get('/auth/login')
        self.assertEqual(res_login.status_code, 200)
        self.assertNotIn(b'<footer class="footer">', res_login.data)

        # 3. Register Page MUST NOT have footer
        res_register = self.client.get('/auth/register')
        self.assertEqual(res_register.status_code, 200)
        self.assertNotIn(b'<footer class="footer">', res_register.data)

        # 4. Other Public Pages (e.g. About, Track) MUST NOT have footer
        res_about = self.client.get('/about')
        self.assertEqual(res_about.status_code, 200)
        self.assertNotIn(b'<footer class="footer">', res_about.data)

        res_track = self.client.get('/track')
        self.assertEqual(res_track.status_code, 200)
        self.assertNotIn(b'<footer class="footer">', res_track.data)

        # 5. Citizen Dashboard MUST NOT have footer
        self.client.post('/auth/login', data={'login_id': 'citizen.footer@test.gov', 'password': 'Citizen@123'})
        res_cit_dash = self.client.get('/citizen/dashboard')
        self.assertEqual(res_cit_dash.status_code, 200)
        self.assertNotIn(b'<footer class="footer">', res_cit_dash.data)

        # 6. Admin Dashboard MUST NOT have footer
        self.client.get('/auth/logout')
        self.client.post('/auth/login', data={'login_id': 'admin.footer@test.gov', 'password': 'Admin@123'})
        res_admin_dash = self.client.get('/admin/dashboard')
        self.assertEqual(res_admin_dash.status_code, 200)
        self.assertNotIn(b'<footer class="footer">', res_admin_dash.data)

if __name__ == '__main__':
    unittest.main()
