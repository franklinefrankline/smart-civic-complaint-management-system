import unittest
import os
from app import create_app, db
from app.models.user import User

class GlassmorphismAuthTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        # Seed sample test citizen if not exists
        if not User.query.filter_by(email='glass.citizen@example.com').first():
            u = User(
                role='citizen',
                full_name='Glass Citizen',
                email='glass.citizen@example.com',
                mobile_number='9876543210',
                is_active=True
            )
            u.set_password('Citizen@123')
            db.session.add(u)
            db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_css_glassmorphism_tokens(self):
        css_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'static', 'css', 'main.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        # Check Light & Dark Theme Glass Tokens
        self.assertIn('--auth-bg-ambient', css)
        self.assertIn('--auth-glass-bg', css)
        self.assertIn('--auth-glass-border', css)
        self.assertIn('--auth-glass-shadow', css)
        self.assertIn('--auth-welcome-bg', css)
        self.assertIn('--auth-input-bg', css)

        # Check Card and Section Classes
        self.assertIn('.auth-page-wrapper', css)
        self.assertIn('.auth-glass-card', css)
        self.assertIn('.auth-welcome-panel', css)
        self.assertIn('.auth-form-panel', css)
        self.assertIn('.auth-btn-ghost', css)
        self.assertIn('.auth-btn-primary', css)

    def test_login_page_renders_split_glass_card(self):
        res = self.client.get('/auth/login')
        self.assertEqual(res.status_code, 200)
        # Check structure
        self.assertIn(b"auth-glass-card", res.data)
        self.assertIn(b"auth-welcome-panel", res.data)
        self.assertIn(b"auth-form-panel", res.data)
        self.assertIn(b"Welcome Back!", res.data)
        self.assertIn(b"Sign In", res.data)
        self.assertIn(b"Sign Up", res.data)
        self.assertIn(b'name="login_id"', res.data)
        self.assertIn(b'name="password"', res.data)
        self.assertIn(b'name="remember"', res.data)

    def test_register_page_renders_split_glass_card(self):
        res = self.client.get('/auth/register')
        self.assertEqual(res.status_code, 200)
        # Check structure
        self.assertIn(b"auth-glass-card", res.data)
        self.assertIn(b"auth-welcome-panel", res.data)
        self.assertIn(b"auth-form-panel", res.data)
        self.assertIn(b"Create Account", res.data)
        self.assertIn(b"Welcome Back!", res.data)
        self.assertIn(b'name="full_name"', res.data)
        self.assertIn(b'name="email"', res.data)
        self.assertIn(b'name="mobile"', res.data)
        self.assertIn(b'name="password"', res.data)
        self.assertIn(b'name="confirm_password"', res.data)

    def test_functional_login_and_registration(self):
        # 1. Test Login
        login_res = self.client.post('/auth/login', data={
            'login_id': 'glass.citizen@example.com',
            'password': 'Citizen@123',
            'remember': 'on'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b"Citizen Dashboard", login_res.data)

        # 2. Logout
        self.client.get('/auth/logout')

        # 3. Test Register
        reg_res = self.client.post('/auth/register', data={
            'full_name': 'New Registered Citizen',
            'email': 'new.glass@example.com',
            'mobile': '9123456789',
            'password': 'Password@123',
            'confirm_password': 'Password@123'
        }, follow_redirects=True)
        self.assertEqual(reg_res.status_code, 200)
        self.assertIn(b"Registration successful", reg_res.data)

        # 4. Login with newly registered user
        login_new = self.client.post('/auth/login', data={
            'login_id': 'new.glass@example.com',
            'password': 'Password@123'
        }, follow_redirects=True)
        self.assertEqual(login_new.status_code, 200)
        self.assertIn(b"Citizen Dashboard", login_new.data)

    def test_two_sided_sliding_auth_structure(self):
        # Verify both login and register templates include the two-sided slider architecture
        for endpoint in ['/auth/login', '/auth/register']:
            res = self.client.get(endpoint)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b'id="authSliderCard"', res.data)
            self.assertIn(b'auth-slider-card', res.data)
            self.assertIn(b'auth-overlay-container', res.data)
            self.assertIn(b'sign-in-container', res.data)
            self.assertIn(b'sign-up-container', res.data)
            self.assertIn(b'overlay-left', res.data)
            self.assertIn(b'overlay-right', res.data)
            self.assertIn(b'id="slideSignInBtn"', res.data)
            self.assertIn(b'id="slideSignUpBtn"', res.data)
            self.assertIn(b'switch-to-signin', res.data)
            self.assertIn(b'switch-to-signup', res.data)

    def test_default_active_states(self):
        # Login page starts in signin-active state
        login_res = self.client.get('/auth/login')
        self.assertIn(b'auth-slider-card auth-glass-card signin-active', login_res.data)

        # Register page starts in default state (without signin-active)
        reg_res = self.client.get('/auth/register')
        self.assertIn(b'auth-slider-card auth-glass-card" id="authSliderCard"', reg_res.data)
        self.assertNotIn(b'auth-slider-card auth-glass-card signin-active', reg_res.data)

    def test_js_sliding_controller_logic(self):
        js_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'static', 'js', 'main.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            js = f.read()
        self.assertIn('authSliderCard', js)
        self.assertIn('slideSignInBtn', js)
        self.assertIn('slideSignUpBtn', js)
        self.assertIn('signin-active', js)
        self.assertIn('switch-to-signin', js)
        self.assertIn('switch-to-signup', js)

if __name__ == '__main__':
    unittest.main()
