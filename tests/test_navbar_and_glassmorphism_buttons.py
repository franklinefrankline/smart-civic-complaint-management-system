import unittest
from app import create_app, db
from app.models.user import User
from app.models.department import Department
import os

class NavbarAndGlassmorphismButtonsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        # Seed Department
        self.dept = Department(name='Civic Engineering & Infrastructure', code='CEI', is_active=True)
        db.session.add(self.dept)
        db.session.commit()

        # Seed Users
        self.admin = User(role='admin', full_name='Admin Commander', email='admin.nav@test.gov', mobile_number='9999111111', is_active=True)
        self.admin.set_password('Admin@123')

        self.officer = User(role='officer', full_name='Officer Sarah', email='officer.nav@test.gov', mobile_number='9999111112', department_id=self.dept.id, is_active=True)
        self.officer.set_password('Officer@123')

        self.worker = User(role='worker', full_name='Worker Bob', email='worker.nav@test.gov', mobile_number='9999111113', department_id=self.dept.id, is_active=True)
        self.worker.set_password('Worker@123')

        self.citizen = User(role='citizen', full_name='Citizen Alice', email='citizen.nav@test.gov', mobile_number='9999111114', city='Central City', is_active=True)
        self.citizen.set_password('Citizen@123')

        db.session.add_all([self.admin, self.officer, self.worker, self.citizen])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_navbar_unauthenticated_layout_and_elements(self):
        """Verify 3-section layout, branding, 6 nav links, and unauthenticated action controls"""
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)

        # 1. Left Section - Branding
        self.assertIn(b'class="brand-title"', res.data)
        self.assertIn(b'Smart Civic Complaint Management System', res.data)
        self.assertIn(b'class="brand-subtitle"', res.data)
        self.assertIn(b'MUNICIPAL REDRESSAL PORTAL', res.data)

        # 2. Center Section - 6 Navigation Links in order
        self.assertIn(b'class="nav-links"', res.data)
        self.assertIn(b'href="/"', res.data)
        self.assertIn(b'href="/about"', res.data)
        self.assertIn(b'href="/how-it-works"', res.data)
        self.assertIn(b'href="/departments"', res.data)
        self.assertIn(b'href="/track"', res.data)
        self.assertIn(b'href="/contact"', res.data)

        # 3. Right Section - Action Controls (Unauthenticated)
        self.assertNotIn(b'class="lang-select"', res.data)
        self.assertIn(b'id="themeToggle"', res.data)
        self.assertIn(b'href="/auth/login"', res.data)
        self.assertIn(b'href="/auth/register"', res.data)
        self.assertIn(b'id="mobileNavToggle"', res.data)

    def test_navbar_authenticated_all_roles(self):
        """Verify action controls on Home page when logged in for all 4 roles, and hidden on dashboards"""
        # Admin: Navbar visible on Home page (/), hidden on /admin/dashboard
        self.client.post('/auth/login', data={'login_id': 'admin.nav@test.gov', 'password': 'Admin@123'})
        res_home_admin = self.client.get('/')
        self.assertEqual(res_home_admin.status_code, 200)
        self.assertIn(b'Admin Console', res_home_admin.data)
        self.assertIn(b'id="notifToggleBtn"', res_home_admin.data)
        self.assertIn(b'class="btn btn-secondary btn-sm nav-logout-btn"', res_home_admin.data)

        res_admin_dash = self.client.get('/admin/dashboard')
        self.assertEqual(res_admin_dash.status_code, 200)
        self.assertNotIn(b'<nav class="navbar', res_admin_dash.data)

        # Officer: Navbar visible on Home page (/), hidden on /officer/dashboard
        self.client.get('/auth/logout')
        self.client.post('/auth/login', data={'login_id': 'officer.nav@test.gov', 'password': 'Officer@123'})
        res_home_officer = self.client.get('/')
        self.assertIn(b'Officer Console', res_home_officer.data)

        res_officer_dash = self.client.get('/officer/dashboard')
        self.assertEqual(res_officer_dash.status_code, 200)
        self.assertNotIn(b'<nav class="navbar', res_officer_dash.data)

        # Worker: Navbar visible on Home page (/), hidden on /worker/dashboard
        self.client.get('/auth/logout')
        self.client.post('/auth/login', data={'login_id': 'worker.nav@test.gov', 'password': 'Worker@123'})
        res_home_worker = self.client.get('/')
        self.assertIn(b'Worker Console', res_home_worker.data)

        res_worker_dash = self.client.get('/worker/dashboard')
        self.assertEqual(res_worker_dash.status_code, 200)
        self.assertNotIn(b'<nav class="navbar', res_worker_dash.data)

        # Citizen: Navbar visible on Home page (/), hidden on /citizen/dashboard
        self.client.get('/auth/logout')
        self.client.post('/auth/login', data={'login_id': 'citizen.nav@test.gov', 'password': 'Citizen@123'})
        res_home_cit = self.client.get('/')
        self.assertIn(b'id="notifToggleBtn"', res_home_cit.data)
        self.assertIn(b'href="/auth/logout"', res_home_cit.data)

        res_cit_dash = self.client.get('/citizen/dashboard')
        self.assertEqual(res_cit_dash.status_code, 200)
        self.assertNotIn(b'<nav class="navbar', res_cit_dash.data)

    def test_navbar_css_dimensions_and_alignment(self):
        """Verify dark navy background, flexbox alignment, height, and nowrap rules in CSS"""
        css_path = os.path.join(self.app.root_path, 'static', 'css', 'main.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        # Dark navy background and fixed 70px height
        self.assertIn('.navbar {', css)
        self.assertIn('background-color: #0f172a;', css)
        self.assertIn('height: 70px;', css)

        # 3-section container alignment
        self.assertIn('.navbar-container {', css)
        self.assertIn('display: flex;', css)
        self.assertIn('align-items: center;', css)
        self.assertIn('justify-content: space-between;', css)

        # Branding nowrap
        self.assertIn('.brand-link {', css)
        self.assertIn('white-space: nowrap;', css)
        self.assertIn('.brand-title {', css)
        self.assertIn('.brand-subtitle {', css)

        # Nav links horizontal row & centering
        self.assertIn('.nav-links {', css)
        self.assertIn('justify-content: center;', css)
        self.assertIn('flex: 1;', css)
        self.assertIn('.nav-link {', css)

        # Controls alignment & uniform heights
        self.assertIn('.nav-actions {', css)
        self.assertIn('.lang-select {', css)
        self.assertIn('.theme-toggle-btn {', css)
        self.assertIn('.nav-actions .notif-btn {', css)
        self.assertIn('.nav-actions .nav-logout-btn {', css)

        # Responsive media queries
        self.assertIn('@media (max-width: 1200px) and (min-width: 901px)', css)
        self.assertIn('@media (max-width: 900px)', css)
        self.assertIn('.nav-links.mobile-open {', css)

    def test_option5_glassmorphism_button_system(self):
        """Verify Option 5 Glassmorphism buttons (backdrop blur, frosted glass, borders, shadows, dark/light)"""
        css_path = os.path.join(self.app.root_path, 'static', 'css', 'main.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        # Base Button Glassmorphism
        self.assertIn('.btn {', css)
        self.assertIn('backdrop-filter: blur(12px);', css)
        self.assertIn('border-radius: var(--radius-sm);', css)
        self.assertIn('will-change: transform, box-shadow;', css)

        # Button Variants
        self.assertIn('.btn-primary {', css)
        self.assertIn('linear-gradient(135deg, rgba(30, 64, 175, 0.92)', css)
        self.assertIn('border: 1px solid rgba(255, 255, 255, 0.25);', css)

        self.assertIn('.btn-secondary {', css)
        self.assertIn('background: rgba(255, 255, 255, 0.72);', css)

        self.assertIn('.btn-success {', css)
        self.assertIn('.btn-danger {', css)
        self.assertIn('.btn-warning {', css)
        self.assertIn('.btn-outline {', css)

        # Button Sizes
        self.assertIn('.btn-sm {', css)
        self.assertIn('.btn-lg {', css)

        # Dark Theme Glass Adjustments
        self.assertIn('[data-theme="dark"] .btn-primary {', css)
        self.assertIn('[data-theme="dark"] .btn-secondary {', css)
        self.assertIn('[data-theme="dark"] .btn-outline {', css)

        # Loading & States
        self.assertIn('.btn:hover {', css)
        self.assertIn('transform: translateY(-1.5px);', css)
        self.assertIn('.btn:active {', css)
        self.assertIn('scale(0.985);', css)
        self.assertIn('.btn-loading {', css)
        self.assertIn('btnSpinner', css)

    def test_sidebar_theme_toggle_present_across_all_roles(self):
        """Verify theme toggle button is rendered in the sidebar across all roles and pages"""
        # 1. Admin dashboard sidebar has theme toggle
        self.client.post('/auth/login', data={'login_id': 'admin.nav@test.gov', 'password': 'Admin@123'})
        res_admin = self.client.get('/admin/dashboard')
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn(b'class="theme-toggle-btn sidebar-header-theme-btn"', res_admin.data)
        self.assertIn(b'class="sidebar-link sidebar-footer-link theme-toggle-btn"', res_admin.data)

        # 2. Officer dashboard sidebar has theme toggle
        self.client.get('/auth/logout')
        self.client.post('/auth/login', data={'login_id': 'officer.nav@test.gov', 'password': 'Officer@123'})
        res_officer = self.client.get('/officer/dashboard')
        self.assertEqual(res_officer.status_code, 200)
        self.assertIn(b'class="theme-toggle-btn sidebar-header-theme-btn"', res_officer.data)

        # 3. Worker dashboard sidebar has theme toggle
        self.client.get('/auth/logout')
        self.client.post('/auth/login', data={'login_id': 'worker.nav@test.gov', 'password': 'Worker@123'})
        res_worker = self.client.get('/worker/dashboard')
        self.assertEqual(res_worker.status_code, 200)
        self.assertIn(b'class="theme-toggle-btn sidebar-header-theme-btn"', res_worker.data)

        # 4. Citizen dashboard sidebar has theme toggle
        self.client.get('/auth/logout')
        self.client.post('/auth/login', data={'login_id': 'citizen.nav@test.gov', 'password': 'Citizen@123'})
        res_citizen = self.client.get('/citizen/dashboard')
        self.assertEqual(res_citizen.status_code, 200)
        self.assertIn(b'class="theme-toggle-btn sidebar-header-theme-btn"', res_citizen.data)

        # 5. Public track page renders clean without sidebar menu bar
        self.client.get('/auth/logout')
        res_track = self.client.get('/track')
        self.assertEqual(res_track.status_code, 200)
        self.assertNotIn(b'id="dashboardSidebar"', res_track.data)
        self.assertIn(b'data-back-nav', res_track.data)
