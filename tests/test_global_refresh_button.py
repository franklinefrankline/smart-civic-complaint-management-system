import unittest
from app import create_app, db
from app.models.category import ComplaintCategory
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.user import User
from app.models.workflow import Worker


class GlobalRefreshButtonTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.dept = Department(name='Water Works', code='WATER_REF', is_active=True)
        db.session.add(self.dept)
        db.session.flush()

        self.cat = ComplaintCategory(
            name='Pipe Leak',
            department_id=self.dept.id,
            default_priority='high',
            sla_hours=48,
            is_active=True,
        )
        db.session.add(self.cat)
        db.session.flush()

        self.admin = User(role='admin', full_name='Refresh Admin', email='ref.admin@civic.gov', mobile_number='9810000001', is_active=True)
        self.admin.set_password('Admin@123')

        self.officer = User(role='officer', department_id=self.dept.id, full_name='Refresh Officer', email='ref.officer@civic.gov', mobile_number='9810000002', is_active=True)
        self.officer.set_password('Officer@123')

        self.worker_user = User(role='worker', department_id=self.dept.id, full_name='Refresh Worker', email='ref.worker@civic.gov', mobile_number='9810000003', is_active=True)
        self.worker_user.set_password('Worker@123')

        self.citizen = User(role='citizen', full_name='Refresh Citizen', email='ref.citizen@civic.gov', mobile_number='9810000004', is_active=True)
        self.citizen.set_password('Citizen@123')

        db.session.add_all([self.admin, self.officer, self.worker_user, self.citizen])
        db.session.flush()

        self.worker = Worker(user_id=self.worker_user.id, department_id=self.dept.id, employee_id='EMP-REF-01')
        db.session.add(self.worker)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _login_as(self, client, email, password):
        res = client.post('/auth/login', data={'login_id': email, 'password': password}, follow_redirects=False)
        self.assertIn(res.status_code, (200, 302))

    def test_public_pages_include_global_refresh_button(self):
        c = self.app.test_client()
        for url in ['/', '/about', '/how-it-works', '/departments', '/track', '/contact', '/auth/login', '/auth/register']:
            res = c.get(url)
            self.assertEqual(res.status_code, 200, msg=f"Failed public GET {url}")
            html = res.get_data(as_text=True)
            self.assertIn('data-global-refresh', html, msg=f"Missing refresh button on {url}")

    def test_protected_routes_stay_protected_without_session(self):
        c = self.app.test_client()
        for protected_url in ['/admin/dashboard', '/officer/dashboard', '/worker/dashboard', '/citizen/dashboard']:
            res = c.get(protected_url, follow_redirects=False)
            self.assertEqual(res.status_code, 302)
            self.assertIn('/auth/login', res.headers.get('Location', ''))

    def test_admin_officer_worker_citizen_pages_refresh_preserve_session_and_reload_latest_data(self):
        # 1. Admin across all admin pages
        admin_client = self.app.test_client()
        self._login_as(admin_client, 'ref.admin@civic.gov', 'Admin@123')
        admin_urls = [
            '/admin/dashboard',
            '/admin/complaints?status=Submitted',
            '/admin/citizens',
            '/admin/departments',
            '/admin/officers',
            '/admin/workers',
            '/admin/assignments',
            '/admin/analytics',
            '/admin/notifications',
            '/admin/audit-logs',
            '/admin/settings',
        ]
        for url in admin_urls:
            r1 = admin_client.get(url)
            r2 = admin_client.get(url)
            self.assertEqual(r1.status_code, 200, msg=f"Admin initial GET failed: {url}")
            self.assertEqual(r2.status_code, 200, msg=f"Admin refresh GET failed: {url}")
            self.assertIn('main.js', r2.get_data(as_text=True))

        # 2. Officer across all officer pages
        off_client = self.app.test_client()
        self._login_as(off_client, 'ref.officer@civic.gov', 'Officer@123')
        for url in [
            '/officer/dashboard',
            '/officer/incoming',
            '/officer/complaints?priority=high',
            '/officer/workers',
            '/officer/assignments',
            '/officer/verification',
            '/officer/escalations',
            '/officer/reports',
            '/officer/notifications',
            '/officer/profile',
        ]:
            r = off_client.get(url)
            self.assertEqual(r.status_code, 200, msg=f"Officer refresh GET failed: {url}")

        # 3. Worker across all worker pages
        wrk_client = self.app.test_client()
        self._login_as(wrk_client, 'ref.worker@civic.gov', 'Worker@123')
        for url in [
            '/worker/dashboard',
            '/worker/tasks?status=Assigned',
            '/worker/tasks?status=In%20Progress',
            '/worker/tasks?status=Work%20Completed',
            '/worker/history',
            '/worker/notifications',
            '/worker/profile',
        ]:
            r = wrk_client.get(url)
            self.assertEqual(r.status_code, 200, msg=f"Worker refresh GET failed: {url}")

        # 4. Citizen + verify reloading same URL pulls newly committed DB record cleanly while keeping session
        cit_client = self.app.test_client()
        self._login_as(cit_client, 'ref.citizen@civic.gov', 'Citizen@123')
        for url in [
            '/citizen/dashboard',
            '/citizen/complaints',
            '/citizen/complaints/new',
            '/citizen/feedback',
            '/citizen/notifications',
            '/citizen/profile',
        ]:
            self.assertEqual(cit_client.get(url).status_code, 200, msg=f"Citizen GET failed: {url}")

        # Simulate DB update committed after initial page load, then refresh same Admin URL
        new_comp = Complaint(
            complaint_ref='CMP-REFRESH-999',
            citizen_id=self.citizen.id,
            department_id=self.dept.id,
            category_id=self.cat.id,
            title='Fresh Pipe Break Visible On Refresh',
            description='Added directly in DB before clicking Refresh button.',
            status='Submitted',
        )
        db.session.add(new_comp)
        db.session.commit()

        refreshed_list = admin_client.get('/admin/complaints?status=Submitted')
        self.assertEqual(refreshed_list.status_code, 200)
        html_after = refreshed_list.get_data(as_text=True)
        self.assertIn('CMP-REFRESH-999', html_after)
        self.assertIn('Fresh Pipe Break Visible On Refresh', html_after)

        # Verify session preserved for admin
        with admin_client.session_transaction() as sess:
            self.assertEqual(sess.get('user_id'), self.admin.id)
            self.assertEqual(sess.get('user_role'), 'admin')


if __name__ == '__main__':
    unittest.main()
