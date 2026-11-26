import unittest
from app import create_app, db
from app.models.user import User
from app.models.department import Department

class HeaderVisibilityTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        # Seed Department & Users
        self.dept = Department(name='Civic Engineering & Infrastructure', code='CEI', is_active=True)
        db.session.add(self.dept)
        db.session.commit()

        self.admin = User(role='admin', full_name='Admin Boss', email='admin.vis@test.gov', mobile_number='9999333331', is_active=True)
        self.admin.set_password('Admin@123')

        self.officer = User(role='officer', full_name='Officer Sam', email='officer.vis@test.gov', mobile_number='9999333332', department_id=self.dept.id, is_active=True)
        self.officer.set_password('Officer@123')

        self.worker = User(role='worker', full_name='Worker Bob', email='worker.vis@test.gov', mobile_number='9999333333', department_id=self.dept.id, is_active=True)
        self.worker.set_password('Worker@123')

        self.citizen = User(role='citizen', full_name='Citizen Jane', email='citizen.vis@test.gov', mobile_number='9999333334', city='Metro City', is_active=True)
        self.citizen.set_password('Citizen@123')

        db.session.add_all([self.admin, self.officer, self.worker, self.citizen])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_header_visible_on_home_page(self):
        """1. Home page – Header visible"""
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'<nav class="navbar', res.data)
        self.assertIn(b'SCF', res.data)
        self.assertIn(b'Smart Civic Flow', res.data)
        self.assertIn(b'Smart Civic Complaint Management System', res.data)
        self.assertIn(b'class="nav-links"', res.data)

    def test_header_visible_on_signin_page(self):
        """2. Sign In page – Header visible"""
        res = self.client.get('/auth/login')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'<nav class="navbar', res.data)
        self.assertIn(b'Smart Civic Flow', res.data)
        self.assertIn(b'class="nav-links"', res.data)

    def test_header_visible_on_signup_page(self):
        """3. Sign Up page – Header visible"""
        res = self.client.get('/auth/register')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'<nav class="navbar', res.data)
        self.assertIn(b'Smart Civic Flow', res.data)
        self.assertIn(b'class="nav-links"', res.data)

    def test_header_hidden_on_admin_dashboard(self):
        """4. Administrator dashboard – Header hidden"""
        self.client.post('/auth/login', data={'login_id': 'admin.vis@test.gov', 'password': 'Admin@123'})
        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b'<nav class="navbar', res.data)
        # Sidebar remains present
        self.assertIn(b'id="dashboardSidebar"', res.data)

    def test_header_hidden_on_officer_dashboard(self):
        """5. Department Officer dashboard – Header hidden"""
        self.client.post('/auth/login', data={'login_id': 'officer.vis@test.gov', 'password': 'Officer@123'})
        res = self.client.get('/officer/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b'<nav class="navbar', res.data)
        self.assertIn(b'id="dashboardSidebar"', res.data)

    def test_header_hidden_on_worker_dashboard(self):
        """6. Field Worker dashboard – Header hidden"""
        self.client.post('/auth/login', data={'login_id': 'worker.vis@test.gov', 'password': 'Worker@123'})
        res = self.client.get('/worker/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b'<nav class="navbar', res.data)
        self.assertIn(b'id="dashboardSidebar"', res.data)

    def test_header_hidden_on_all_other_internal_pages(self):
        """7. All other internal pages – Header hidden"""
        # Citizen dashboard & complaints
        self.client.post('/auth/login', data={'login_id': 'citizen.vis@test.gov', 'password': 'Citizen@123'})
        for url in ['/citizen/dashboard', '/citizen/complaints', '/citizen/complaints/new', '/citizen/profile']:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Failed on {url}")
            self.assertNotIn(b'<nav class="navbar', res.data)
            self.assertIn(b'id="dashboardSidebar"', res.data)

        # Admin internal management pages
        self.client.get('/auth/logout')
        self.client.post('/auth/login', data={'login_id': 'admin.vis@test.gov', 'password': 'Admin@123'})
        for url in ['/admin/complaints', '/admin/citizens', '/admin/departments', '/admin/officers', '/admin/workers', '/admin/analytics', '/admin/settings']:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Failed on {url}")
            self.assertNotIn(b'<nav class="navbar', res.data)
            self.assertIn(b'id="dashboardSidebar"', res.data)

    def test_track_page_has_sidebar_and_no_navbar(self):
        """8. Track Complaint page has global public navbar, no sidebar menu bar, and active Track link"""
        # Unauthenticated public track
        self.client.get('/auth/logout')
        res_unauth = self.client.get('/track')
        self.assertEqual(res_unauth.status_code, 200)
        self.assertIn(b'<nav class="navbar', res_unauth.data)
        self.assertNotIn(b'id="dashboardSidebar"', res_unauth.data)
        self.assertIn(b'Public Complaint Tracking', res_unauth.data)
        self.assertIn(b'href="/track" class="nav-link active"', res_unauth.data)

        # Authenticated citizen track inside dashboard sidebar (/citizen/track)
        self.client.post('/auth/login', data={'login_id': 'citizen.vis@test.gov', 'password': 'Citizen@123'})
        res_cit_track = self.client.get('/citizen/track')
        self.assertEqual(res_cit_track.status_code, 200)
        self.assertNotIn(b'<nav class="navbar', res_cit_track.data)
        self.assertIn(b'id="dashboardSidebar"', res_cit_track.data)
        self.assertIn(b'Track Complaint Status', res_cit_track.data)
        self.assertIn(b'href="/citizen/track"', res_cit_track.data)

        # Authenticated citizen public track (/track) retains public navbar
        res_auth = self.client.get('/track')
        self.assertEqual(res_auth.status_code, 200)
        self.assertIn(b'<nav class="navbar', res_auth.data)
        self.assertNotIn(b'id="dashboardSidebar"', res_auth.data)
        self.assertIn(b'href="/track" class="nav-link active"', res_auth.data)
