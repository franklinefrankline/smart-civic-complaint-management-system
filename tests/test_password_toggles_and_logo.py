import glob
import os
import re
import unittest
from app import create_app, db
from app.models.user import User


class PasswordTogglesAndLogoTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.temp_user = User(
            role='worker',
            full_name='Reset Test Worker',
            email='reset.pw@civic.gov',
            mobile_number='9866666601',
            is_active=True,
            is_password_reset_required=True,
        )
        self.temp_user.set_password('Welcome@123')
        db.session.add(self.temp_user)
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.ctx.pop()

    def test_force_reset_password_page_has_toggles_and_valid_logo(self):
        client = self.app.test_client()
        login_res = client.post(
            '/auth/login',
            data={'login_id': 'reset.pw@civic.gov', 'password': 'Welcome@123'},
            follow_redirects=True,
        )
        self.assertEqual(login_res.status_code, 200)
        html = login_res.get_data(as_text=True)

        self.assertIn('Set Your New Password', html)
        self.assertIn('id="forceNewPassword"', html)
        self.assertIn('id="forceConfirmPassword"', html)
        self.assertEqual(html.count('onclick="togglePasswordVisibility(this)"'), 2)
        self.assertIn('aria-pressed="false"', html)
        self.assertIn('scf-logo.webp', html)
        self.assertIn('scf-logo.png', html)

        # Verify logo endpoints serve valid non-empty image assets
        r_webp = client.get('/static/img/scf-logo.webp?v=20261126f')
        self.assertEqual(r_webp.status_code, 200)
        self.assertGreater(len(r_webp.data), 1000)

        r_png = client.get('/static/img/scf-logo.png?v=20261126f')
        self.assertEqual(r_png.status_code, 200)
        self.assertGreater(len(r_png.data), 1000)

    def test_every_password_input_across_templates_has_accessible_inline_toggle(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        templates = glob.glob(os.path.join(base_dir, 'app', 'templates', '*', '*.html'))
        checked = 0
        for path in templates:
            content = open(path, encoding='utf-8').read()
            for m in re.finditer(r'<input\b[^>]*type="password"[^>]*>', content):
                checked += 1
                window = content[m.start():m.start() + 900]
                self.assertIn('togglePasswordVisibility(this)', window, f"Missing password toggle near {path}")
                self.assertIn('type="button"', window, f"Toggle button must not submit form in {path}")
                self.assertNotIn('tabindex="-1"', window.split('</button>')[0], f"Toggle must stay keyboard focusable in {path}")
        self.assertGreaterEqual(checked, 10)


if __name__ == '__main__':
    unittest.main()
