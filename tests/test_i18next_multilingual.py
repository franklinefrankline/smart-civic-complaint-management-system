import json
import os
import re
import unittest

from app import create_app, db
from app.models.category import ComplaintCategory
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.notification import Notification
from app.models.user import User
from app.models.workflow import ComplaintAssignment, Worker
from app.utils.translations import LOCALE_BUNDLES, SUPPORTED_LANGUAGES, translate_text


class I18nextMultilingualTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.dept = Department(name='Water Supply & Sewage', code='WATER_I18N', is_active=True)
        db.session.add(self.dept)
        db.session.flush()

        self.cat = ComplaintCategory(
            name='Drinking Water Pipe Leakage',
            department_id=self.dept.id,
            default_priority='urgent',
            sla_hours=24,
            is_active=True,
        )
        db.session.add(self.cat)
        db.session.flush()

        self.admin = User(role='admin', full_name='I18n Admin', email='i18n.admin@civic.gov', mobile_number='9820000001', is_active=True)
        self.admin.set_password('Admin@123')

        self.officer = User(role='officer', department_id=self.dept.id, full_name='I18n Officer', email='i18n.officer@civic.gov', mobile_number='9820000002', is_active=True)
        self.officer.set_password('Officer@123')

        self.worker_user = User(role='worker', department_id=self.dept.id, full_name='I18n Worker', email='i18n.worker@civic.gov', mobile_number='9820000003', is_active=True)
        self.worker_user.set_password('Worker@123')

        self.citizen = User(role='citizen', full_name='I18n Citizen', email='i18n.citizen@civic.gov', mobile_number='9820000004', is_active=True)
        self.citizen.set_password('Citizen@123')

        db.session.add_all([self.admin, self.officer, self.worker_user, self.citizen])
        db.session.flush()

        self.worker = Worker(user_id=self.worker_user.id, department_id=self.dept.id, employee_id='EMP-I18N-01')
        db.session.add(self.worker)
        db.session.flush()

        self.complaint = Complaint(
            complaint_ref='CMP-I18N-1001',
            citizen_id=self.citizen.id,
            department_id=self.dept.id,
            category_id=self.cat.id,
            assigned_officer_id=self.officer.id,
            assigned_worker_id=self.worker_user.id,
            title='Main Street Water Pipe Leak',
            description='Heavy drinking water pipeline leak near civic junction.',
            priority='urgent',
            status='Assigned',
        )
        db.session.add(self.complaint)
        db.session.flush()

        self.assignment = ComplaintAssignment(
            complaint_id=self.complaint.id,
            assigned_by_user_id=self.officer.id,
            assigned_to_user_id=self.worker_user.id,
            status='Assigned',
            instructions='Inspect and repair water pipe.',
        )
        db.session.add(self.assignment)
        db.session.flush()

        self.notif = Notification(
            user_id=self.citizen.id,
            complaint_id=self.complaint.id,
            title='Complaint Submitted: CMP-I18N-1001',
            message='Complaint registered by citizen.',
            notification_type='info',
        )
        db.session.add(self.notif)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _login(self, client, email, password):
        res = client.post('/auth/login', data={'login_id': email, 'password': password}, follow_redirects=False)
        self.assertIn(res.status_code, (200, 302))

    def test_locale_files_complete_symmetry_and_scripts_present(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        for vendor_file in [
            'app/static/js/vendor/i18next.min.js',
            'app/static/js/vendor/i18nextBrowserLanguageDetector.min.js',
            'app/static/js/i18n.js',
        ]:
            self.assertTrue(os.path.isfile(os.path.join(base_dir, vendor_file)), msg=f"Missing {vendor_file}")

        en_doc = json.load(open(os.path.join(base_dir, 'src', 'locales', 'en', 'translation.json'), encoding='utf-8'))
        ta_doc = json.load(open(os.path.join(base_dir, 'src', 'locales', 'ta', 'translation.json'), encoding='utf-8'))
        hi_doc = json.load(open(os.path.join(base_dir, 'src', 'locales', 'hi', 'translation.json'), encoding='utf-8'))

        self.assertEqual(set(en_doc['keys'].keys()), set(ta_doc['keys'].keys()))
        self.assertEqual(set(en_doc['keys'].keys()), set(hi_doc['keys'].keys()))
        self.assertEqual(set(en_doc['phrases'].keys()), set(ta_doc['phrases'].keys()))
        self.assertEqual(set(en_doc['phrases'].keys()), set(hi_doc['phrases'].keys()))

        # Verify Tamil & Hindi unicode scripts are actually present across keys and phrases
        ta_unicode_hits = sum(1 for v in ta_doc['phrases'].values() if re.search(r'[\u0B80-\u0BFF]', v))
        hi_unicode_hits = sum(1 for v in hi_doc['phrases'].values() if re.search(r'[\u0900-\u097F]', v))
        self.assertGreater(ta_unicode_hits, 1000)
        self.assertGreater(hi_unicode_hits, 1000)

        # Verify /locales/<lang>/translation.json endpoint serves all 3 languages
        c = self.app.test_client()
        for lang in SUPPORTED_LANGUAGES:
            r = c.get(f'/locales/{lang}/translation.json')
            self.assertEqual(r.status_code, 200)
            payload = r.get_json()
            self.assertEqual(payload['_meta']['language'], lang)

    def test_public_and_role_pages_translate_across_en_ta_hi_without_leaking_identifiers(self):
        # Verify dynamic helper preserves emails, refs, and translates workflow/departments
        self.assertEqual(translate_text('Water Supply & Sewage', 'ta'), 'குடிநீர் விநியோகம் மற்றும் கழிவுநீர்')
        self.assertEqual(translate_text('Water Supply & Sewage', 'hi'), 'जल आपूर्ति एवं सीवेज')
        self.assertIn('CMP-I18N-1001', translate_text('Complaint Submitted: CMP-I18N-1001', 'ta'))

        c = self.app.test_client()
        # Switch to Tamil and verify public pages + switcher UI + i18next assets
        r_lang = c.post('/api/language', json={'lang': 'ta'})
        self.assertEqual(r_lang.status_code, 200)
        self.assertTrue(r_lang.get_json()['success'])

        for url in ['/', '/about', '/how-it-works', '/departments', '/track', '/contact', '/auth/login', '/auth/register', '/privacy', '/cookies', '/terms']:
            res = c.get(url)
            self.assertEqual(res.status_code, 200, msg=f"Tamil GET failed: {url}")
            html = res.get_data(as_text=True)
            self.assertIn('lang="ta"', html)
            self.assertIn('data-lang-switcher', html)
            self.assertIn('i18next.min.js', html)
            self.assertIn('i18n.js', html)
            self.assertIn('English', html)
            self.assertIn('தமிழ்', html)
            self.assertIn('हिन्दी', html)

        # Switch to Hindi and test Admin / Officer / Worker / Citizen dashboards
        admin_c = self.app.test_client()
        self._login(admin_c, 'i18n.admin@civic.gov', 'Admin@123')
        admin_c.post('/api/language', json={'lang': 'hi'})
        for url in ['/admin/dashboard', '/admin/complaints', f'/admin/complaints/{self.complaint.id}', '/admin/users', '/admin/officers', '/admin/workers', '/admin/departments', '/admin/analytics', '/admin/audit-logs', '/admin/settings']:
            r = admin_c.get(url)
            self.assertEqual(r.status_code, 200, msg=f"Admin Hindi GET failed: {url}")
            html = r.get_data(as_text=True)
            self.assertIn('lang="hi"', html)
            self.assertIn('प्रशासन', html)  # Administration sidebar section in Hindi

        # Verify Tamil Officer, Worker, Citizen views
        for email, pw, urls, expected_ta in [
            ('i18n.officer@civic.gov', 'Officer@123', ['/officer/dashboard', '/officer/incoming', '/officer/complaints', f'/officer/complaints/{self.complaint.id}', '/officer/workers', '/officer/assignments', '/officer/verification', '/officer/escalations', '/officer/reports', '/officer/notifications', '/officer/profile'], 'துறை செயல்பாடுகள்'),
            ('i18n.worker@civic.gov', 'Worker@123', ['/worker/dashboard', '/worker/tasks', f'/worker/tasks/{self.complaint.id}', '/worker/history', '/worker/notifications', '/worker/profile'], 'களப் பணியாளர் பணிகள்'),
            ('i18n.citizen@civic.gov', 'Citizen@123', ['/citizen/dashboard', '/citizen/complaints', '/citizen/complaints/new', f'/citizen/complaints/{self.complaint.id}', '/citizen/feedback', '/citizen/notifications', '/citizen/profile'], 'குடிமக்கள் சேவைகள்'),
        ]:
            rc = self.app.test_client()
            self._login(rc, email, pw)
            rc.post('/api/language', json={'lang': 'ta'})
            for url in urls:
                res = rc.get(url)
                self.assertEqual(res.status_code, 200, msg=f"Role {email} Tamil GET failed: {url}")
                self.assertIn(expected_ta, res.get_data(as_text=True))

    def test_persistent_language_across_refresh_logout_login_and_cross_device_without_accept_language_override(self):
        # Device 1: citizen logs in, sets Tamil, logs out, and keeps Tamil even with German Accept-Language
        dev1 = self.app.test_client()
        self._login(dev1, 'i18n.citizen@civic.gov', 'Citizen@123')
        res = dev1.post('/api/language', json={'lang': 'ta'})
        self.assertEqual(res.status_code, 200)

        db.session.refresh(self.citizen)
        self.assertEqual(self.citizen.preferred_language, 'ta')

        # Refresh with different Accept-Language header -> must NOT override user choice
        r_dash = dev1.get('/citizen/dashboard', headers={'Accept-Language': 'fr-FR,de;q=0.9'})
        self.assertEqual(r_dash.status_code, 200)
        self.assertIn('lang="ta"', r_dash.get_data(as_text=True))

        # Verify backend API /api/notifications returns translated notifications in Tamil
        r_notif = dev1.get('/api/notifications')
        self.assertEqual(r_notif.status_code, 200)
        notif_json = r_notif.get_json()
        self.assertTrue(len(notif_json['notifications']) >= 1)
        self.assertIn('குடிமகனால் புகார் பதிவு செய்யப்பட்டது.', notif_json['notifications'][0]['message'])
        self.assertIn('CMP-I18N-1001', notif_json['notifications'][0]['title'])

        # Logout preserves Tamil on the public/login portal
        r_out = dev1.get('/auth/logout', follow_redirects=True)
        self.assertEqual(r_out.status_code, 200)
        out_html = r_out.get_data(as_text=True)
        self.assertIn('lang="ta"', out_html)
        self.assertIn('நீங்கள் வெற்றிகரமாக வெளியேறிவிட்டீர்கள்.', out_html)

        # Device 2 (fresh client with no cookies/localStorage) logs in -> receives saved account DB preference ('ta')
        dev2 = self.app.test_client()
        self._login(dev2, 'i18n.citizen@civic.gov', 'Citizen@123')
        r_dev2 = dev2.get('/citizen/dashboard')
        self.assertEqual(r_dev2.status_code, 200)
        self.assertIn('lang="ta"', r_dev2.get_data(as_text=True))

        # Backend validation error translates when Hindi is active
        dev3 = self.app.test_client()
        dev3.post('/api/language', json={'lang': 'hi'})
        r_bad_reg = dev3.post(
            '/auth/register',
            data={'full_name': 'Test User', 'email': 'i18n.citizen@civic.gov', 'mobile': '9820000004', 'password': 'Password1', 'confirm_password': 'Password1'},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(r_bad_reg.status_code, 400)
        bad_json = r_bad_reg.get_json()
        self.assertIn('ईमेल पता और फोन नंबर पहले से पंजीकृत हैं', bad_json['message'])

    def test_language_switcher_placement_left_sidebar_on_dashboards_and_top_right_on_public_pages(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        back_btn_src = open(os.path.join(base_dir, 'app', 'templates', 'shared', '_back_button.html'), encoding='utf-8').read()
        sidebar_src = open(os.path.join(base_dir, 'app', 'templates', 'shared', '_sidebar.html'), encoding='utf-8').read()
        navbar_src = open(os.path.join(base_dir, 'app', 'templates', 'shared', '_navbar.html'), encoding='utf-8').read()
        main_js_src = open(os.path.join(base_dir, 'app', 'static', 'js', 'main.js'), encoding='utf-8').read()

        # Public top-right navbar retains the language switcher
        self.assertIn('data-lang-switcher', navbar_src)
        # Left sidebar keeps the language switcher (expanded and collapsed)
        main_css_src = open(os.path.join(base_dir, 'app', 'static', 'css', 'main.css'), encoding='utf-8').read()
        self.assertIn('sidebar-lang-control', sidebar_src)
        self.assertIn('sidebar-lang-collapsed-badge', sidebar_src)
        self.assertIn('data-lang-switcher', sidebar_src)
        self.assertIn('.dashboard-sidebar.sidebar-collapsed .sidebar-lang-collapsed-badge', main_css_src)
        # Dashboard top-right action bar & main.js must NOT render a top-right language switcher
        self.assertNotIn('data-lang-switcher', back_btn_src)
        self.assertNotIn('createGlobalLangSelector', main_js_src)


if __name__ == '__main__':
    unittest.main()
