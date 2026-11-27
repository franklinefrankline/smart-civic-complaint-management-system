import unittest
import os
from app import create_app, db

class LegalAndCookiesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_privacy_policy_page_sections(self):
        res = self.client.get('/privacy')
        self.assertEqual(res.status_code, 200)
        content = res.data.decode('utf-8')

        # Check all 13 required sections
        self.assertIn("Introduction", content)
        self.assertIn("Information We Collect", content)
        self.assertIn("Personal Information", content)
        self.assertIn("Account Information", content)
        self.assertIn("How We Use Information", content)
        self.assertIn("Data Storage and Security", content)
        self.assertIn("Information Sharing", content)
        self.assertIn("Data Retention", content)
        self.assertIn("User Rights", content)
        self.assertIn("Access, Correction and Deletion", content)
        self.assertIn("Children's Privacy", content)
        self.assertIn("Policy Updates", content)
        self.assertIn("Contact Information", content)

        # Contact details accuracy
        self.assertIn("1800-425-0000", content)
        self.assertIn("civic-desk@gov.portal", content)

        # STRICT COMPLIANCE REQUIREMENT: No DPDP mention
        self.assertNotIn("DPDP", content)
        self.assertNotIn("dpdp", content.lower())
        self.assertNotIn("digital personal data protection", content.lower())

    def test_cookie_policy_page_sections(self):
        res = self.client.get('/cookies')
        self.assertEqual(res.status_code, 200)
        content = res.data.decode('utf-8')

        # Check all 10 required sections
        self.assertIn("What Are Cookies?", content)
        self.assertIn("Why We Use Cookies", content)
        self.assertIn("Essential Cookies", content)
        self.assertIn("Functional Cookies", content)
        self.assertIn("Analytics Cookies", content)
        self.assertIn("Cookie Preferences", content)
        self.assertIn("Managing and Disabling Cookies", content)
        self.assertIn("Third-Party Cookies", content)
        self.assertIn("Changes to This Cookie Policy", content)
        self.assertIn("Contact Information", content)

        # Check interactive preferences button
        self.assertIn("openCookieSettings()", content)

        # Accurate cookie disclosures
        self.assertIn("session", content)
        self.assertIn("civic_cookie_consent", content)

        # STRICT COMPLIANCE REQUIREMENT: No DPDP mention
        self.assertNotIn("DPDP", content)
        self.assertNotIn("dpdp", content.lower())
        self.assertNotIn("digital personal data protection", content.lower())

    def test_terms_and_conditions_page(self):
        res = self.client.get('/terms')
        self.assertEqual(res.status_code, 200)
        content = res.data.decode('utf-8')
        self.assertIn("Terms and Conditions", content)
        self.assertIn("Acceptance of Terms", content)
        self.assertIn("Citizen Account Registration", content)
        self.assertIn("Truthful Grievance Submissions", content)
        self.assertIn("Governing Law", content)

    def test_cookie_banner_and_settings_modal_in_base(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        content = res.data.decode('utf-8')

        # Banner elements
        self.assertIn('id="cookieConsentBanner"', content)
        self.assertIn('id="cookieAcceptAll"', content)
        self.assertIn('id="cookieRejectOptional"', content)
        self.assertIn('id="cookieCustomize"', content)

        # Modal elements
        self.assertIn('id="cookieSettingsModal"', content)
        self.assertIn('id="prefFunctional"', content)
        self.assertIn('id="prefAnalytics"', content)
        self.assertIn('id="cookieSaveCustom"', content)

        # Essential cookies always active indicator
        self.assertIn('Always Active', content)

    def test_footer_legal_links_integrated(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        content = res.data.decode('utf-8')

        # Check footer links presence and targets
        self.assertIn('/privacy', content)
        self.assertIn('/cookies', content)
        self.assertIn('/terms', content)
        self.assertIn('openCookieSettings()', content)

        self.assertIn('Privacy Policy', content)
        self.assertIn('Cookie Policy', content)
        self.assertIn('Cookie Settings', content)
        self.assertIn('Terms and Conditions', content)

    def test_password_visibility_toggle_buttons(self):
        # 1. Sign In / Register pages have the eye toggle button
        for endpoint in ['/auth/login', '/auth/register']:
            res = self.client.get(endpoint)
            self.assertEqual(res.status_code, 200)
            content = res.data.decode('utf-8')
            self.assertIn('auth-password-toggle', content)
            self.assertIn('togglePasswordVisibility(this)', content)
            self.assertTrue('data-lucide="eye"' in content or '<svg' in content)

    def test_js_helpers_present(self):
        js_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'static', 'js', 'main.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            js = f.read()

        self.assertIn('togglePasswordVisibility', js)
        self.assertIn('openCookieSettings', js)
        self.assertIn('saveCookiePreferences', js)
        self.assertIn('cookieConsentBanner', js)
        self.assertIn('cookieSettingsModal', js)

    def test_strict_no_dpdp_across_all_templates_and_routes(self):
        app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app')
        forbidden_terms = ['dpdp', 'dpdpa', 'digital personal data protection']

        for root, dirs, files in os.walk(app_dir):
            for file in files:
                if file.endswith(('.html', '.py', '.js', '.css')):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read().lower()
                        for term in forbidden_terms:
                            self.assertNotIn(term, text, f"Forbidden term '{term}' found in {file_path}")

if __name__ == '__main__':
    unittest.main()
