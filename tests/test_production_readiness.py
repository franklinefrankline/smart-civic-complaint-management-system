import io
import os
import unittest
from app import create_app, db
from app.models.user import User
from app.models.department import Department
from app.models.category import ComplaintCategory
from app.models.complaint import Complaint
from app.models.workflow import Worker
from app.models.attachment import ComplaintAttachment
from app.models.notification import Notification
from config import _build_database_config


class ProductionReadinessTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.dept = Department(name='Water Supply', code='WATER', is_active=True)
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

        self.admin = User(role='admin', full_name='Admin Prod', email='admin@prod.gov', mobile_number='9111111111', is_active=True)
        self.admin.set_password('Admin@123')
        self.officer = User(role='officer', full_name='Officer Prod', email='officer@prod.gov', mobile_number='9111111112', department_id=self.dept.id, is_active=True)
        self.officer.set_password('Officer@123')
        self.worker = User(role='worker', full_name='Worker Prod', email='worker@prod.gov', mobile_number='9111111113', department_id=self.dept.id, is_active=True)
        self.worker.set_password('Worker@123')
        self.citizen = User(role='citizen', full_name='Citizen Prod', email='citizen@prod.gov', mobile_number='9111111114', is_active=True)
        self.citizen.set_password('Citizen@123')

        db.session.add_all([self.admin, self.officer, self.worker, self.citizen])
        db.session.flush()
        db.session.add(Worker(user_id=self.worker.id, department_id=self.dept.id, is_available=True))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self, email, password):
        return self.client.post('/auth/login', data={'login_id': email, 'password': password}, follow_redirects=True)

    def test_health_endpoints(self):
        for ep in ['/health', '/healthz', '/api/health']:
            res = self.client.get(ep)
            self.assertEqual(res.status_code, 200, f"{ep} failed")
            data = res.get_json()
            self.assertEqual(data['status'], 'ok')
            self.assertEqual(data['database'], 'connected')

    def test_cors_restricted_to_vercel_origin(self):
        res_ok = self.client.get('/api/stats/summary', headers={'Origin': 'https://sccmt.vercel.app'})
        self.assertEqual(res_ok.status_code, 200)
        self.assertEqual(res_ok.headers.get('Access-Control-Allow-Origin'), 'https://sccmt.vercel.app')
        self.assertEqual(res_ok.headers.get('Access-Control-Allow-Credentials'), 'true')

        res_opt = self.client.options('/api/notifications', headers={'Origin': 'https://sccmt.vercel.app'})
        self.assertIn(res_opt.status_code, (200, 204))
        self.assertEqual(res_opt.headers.get('Access-Control-Allow-Origin'), 'https://sccmt.vercel.app')

        res_bad = self.client.get('/api/stats/summary', headers={'Origin': 'https://untrusted.example.com'})
        self.assertEqual(res_bad.status_code, 200)
        self.assertIsNone(res_bad.headers.get('Access-Control-Allow-Origin'))

    def test_unauthenticated_redirect_uses_relative_next_and_api_returns_401(self):
        res_page = self.client.get('/admin/departments')
        self.assertEqual(res_page.status_code, 302)
        loc = res_page.headers.get('Location', '')
        self.assertIn('/auth/login', loc)
        self.assertIn('next=/admin/departments', loc)
        self.assertNotIn('onrender.com', loc)

        res_ajax = self.client.get('/admin/departments', headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(res_ajax.status_code, 401)
        self.assertFalse(res_ajax.get_json()['success'])

    def test_mysql_uri_normalization_and_ssl_handling(self):
        orig_env = os.environ.copy()
        try:
            os.environ['RENDER'] = 'true'
            os.environ['DATABASE_URL'] = 'mysql://user1:p%40ss@db.example.com:3306/civic?ssl-mode=REQUIRED'
            _, uri, opts, *_ = _build_database_config()
            self.assertTrue(uri.startswith('mysql+pymysql://'))
            self.assertNotIn('ssl-mode', uri)
            self.assertIn('ssl', opts['connect_args'])
            self.assertTrue(opts['pool_pre_ping'])

            del os.environ['DATABASE_URL']
            os.environ['DB_HOST'] = 'mysql.example.net'
            os.environ['DB_USER'] = 'admin'
            os.environ['DB_PASSWORD'] = 'P@ss#123'
            os.environ['DB_NAME'] = 'sccmt_prod'
            _, uri2, *_ = _build_database_config()
            self.assertIn('mysql+pymysql://admin:P%40ss%23123@mysql.example.net:3306/sccmt_prod', uri2)
        finally:
            os.environ.clear()
            os.environ.update(orig_env)

    def test_persistent_attachment_serving_and_worker_progress_and_queues(self):
        # 1. Citizen registers complaint with image upload
        self.login('citizen@prod.gov', 'Citizen@123')
        fake_img = (io.BytesIO(b'\x89PNG\r\n\x1a\nfakeimagedata'), 'leak.png')
        res = self.client.post('/citizen/complaints/new', data={
            'title': 'Burst pipe near school gate',
            'category_id': self.cat.id,
            'description': 'Water flowing across the road continuously since morning.',
            'priority': 'high',
            'address': '12 Main St',
            'ward_number': 'Ward 2',
            'pincode': '600001',
            'attachments': fake_img,
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        comp = Complaint.query.first()
        self.assertIsNotNone(comp)
        att = ComplaintAttachment.query.filter_by(complaint_id=comp.id).first()
        self.assertIsNotNone(att)
        self.assertIsNotNone(att.file_data)
        self.assertTrue(len(att.file_data) > 0)

        # Simulate Render ephemeral disk wipe by deleting local file if written
        disk_path = os.path.join(self.app.config['UPLOAD_FOLDER'], 'complaints', att.filename)
        if os.path.exists(disk_path):
            os.remove(disk_path)

        # Verify attachment still serves cleanly from DB BLOB storage!
        img_res = self.client.get(f'/{att.file_path}')
        self.assertEqual(img_res.status_code, 200)
        self.assertIn(b'fakeimagedata', img_res.data)
        self.client.get('/auth/logout')

        # 2. Admin assigns Department & Officer
        self.login('admin@prod.gov', 'Admin@123')
        self.client.post(f'/admin/complaint/{comp.id}', data={
            'action': 'assign_department_officer',
            'department_id': self.dept.id,
            'officer_id': self.officer.id,
            'admin_remarks': 'Urgent dispatch'
        }, follow_redirects=True)
        self.client.get('/auth/logout')

        # 3. Officer sees it in /officer/incoming and assigns worker
        self.login('officer@prod.gov', 'Officer@123')
        inc_res = self.client.get('/officer/incoming')
        self.assertEqual(inc_res.status_code, 200)
        self.assertIn(comp.complaint_ref.encode(), inc_res.data)

        self.client.post(f'/officer/complaint/{comp.id}', data={
            'action': 'assign_worker',
            'worker_user_id': self.worker.id,
            'instructions': 'Repair joint immediately'
        }, follow_redirects=True)
        self.client.get('/auth/logout')

        # 4. Worker sees task on dashboard, starts work, posts progress note (previously NameError!), and completes with proof
        self.login('worker@prod.gov', 'Worker@123')
        w_dash = self.client.get('/worker/dashboard')
        self.assertEqual(w_dash.status_code, 200)
        self.assertIn(comp.complaint_ref.encode(), w_dash.data)

        self.client.post(f'/worker/task/{comp.id}', data={'action': 'start_work', 'remarks': 'Arrived'}, follow_redirects=True)
        prog_res = self.client.post(f'/worker/task/{comp.id}', data={'action': 'update_progress', 'progress_notes': 'Replaced gasket'}, follow_redirects=True)
        self.assertEqual(prog_res.status_code, 200)
        self.assertIn(b'Progress update recorded', prog_res.data)

        proof_img = (io.BytesIO(b'\x89PNG\r\n\x1a\nafterproofdata'), 'after.png')
        comp_res = self.client.post(f'/worker/task/{comp.id}', data={
            'action': 'submit_completion',
            'remarks': 'Pipe sealed and pressure tested cleanly.',
            'after_image': proof_img
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(comp_res.status_code, 200)
        self.assertIn(b'Work submitted successfully', comp_res.data)
        self.client.get('/auth/logout')

        # Verify notifications delivered to officer and citizen
        self.assertTrue(Notification.query.filter_by(user_id=self.officer.id).count() >= 2)
        self.assertTrue(Notification.query.filter_by(user_id=self.citizen.id).count() >= 3)

    def test_admin_live_updates_fingerprint_changes_on_new_complaint(self):
        # 1. Admin polls /api/live-updates before any complaint
        self.login('admin@prod.gov', 'Admin@123')
        res1 = self.client.get('/api/live-updates')
        self.assertEqual(res1.status_code, 200)
        d1 = res1.get_json()
        self.assertEqual(d1['total_count'], 0)
        self.client.get('/auth/logout')

        # 2. Citizen submits a new complaint
        self.login('citizen@prod.gov', 'Citizen@123')
        self.client.post('/citizen/complaints/new', data={
            'title': 'Streetlight failure at main crossroad',
            'category_id': self.cat.id,
            'description': 'The streetlight pole is completely dark since yesterday night.',
            'priority': 'high',
            'address': 'Crossroad 3',
            'ward_number': 'Ward 2',
            'pincode': '600001'
        }, follow_redirects=True)
        self.client.get('/auth/logout')

        # 3. Admin polls /api/live-updates without page refresh -> fingerprint & counts update
        self.login('admin@prod.gov', 'Admin@123')
        res2 = self.client.get('/api/live-updates')
        self.assertEqual(res2.status_code, 200)
        d2 = res2.get_json()
        self.assertEqual(d2['total_count'], 1)
        self.assertEqual(d2['pending_count'], 1)
        self.assertNotEqual(d1['fingerprint'], d2['fingerprint'])
        self.assertIsNotNone(d2['latest_notification'])
        self.assertIn('New Complaint:', d2['latest_notification']['title'])

    def test_zero_browser_native_popups_and_centralized_modal_present(self):
        import re
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_dir = os.path.join(base_dir, 'app')
        native_hits = []
        for root, _, files in os.walk(app_dir):
            for fname in files:
                if fname.endswith(('.html', '.js', '.py')):
                    fpath = os.path.join(root, fname)
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as fp:
                        for lineno, line in enumerate(fp, 1):
                            if re.search(r'(?<!show)\b(alert|confirm|prompt)\s*\(|window\.(alert|confirm|prompt)\s*\(', line):
                                native_hits.append(f"{fpath}:{lineno}")
        self.assertEqual(native_hits, [], f"Native browser popups found: {native_hits}")

        # Verify centralized confirmation modal & custom triggers render for admin pages
        self.login('admin@prod.gov', 'Admin@123')
        for route in ['/admin/workers', '/admin/officers', '/admin/citizens', '/admin/users', '/admin/departments', '/admin/settings']:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b'id="sccmtConfirmModal"', res.data)
            self.assertIn(b'id="toastContainer"', res.data)
            self.assertIn(b'data-confirm=', res.data)
            self.assertNotIn(b'return confirm(', res.data)

        # Verify main.js central notification/confirmation providers and custom form validation
        js_path = os.path.join(app_dir, 'static', 'js', 'main.js')
        with open(js_path, 'r', encoding='utf-8') as fp:
            js = fp.read()
        for symbol in ['window.showConfirm', 'window.showToast', 'NotificationProvider', 'ConfirmDialog', 'ToastContainer', 'useNotification', 'useConfirmation', 'form.noValidate = true']:
            self.assertIn(symbol, js)

    def test_realtime_sse_all_4_roles_and_missed_notification_recovery(self):
        dept_id = self.dept.id
        cat_id = self.cat.id
        officer_id = self.officer.id
        worker_id = self.worker.id

        # Unauthenticated SSE stream must be blocked (401)
        unauth_stream = self.client.get('/api/stream')
        self.assertEqual(unauth_stream.status_code, 401)

        # Create 4 separate browser sessions (Citizen, Admin, Officer, Worker)
        c_client = self.app.test_client()
        a_client = self.app.test_client()
        o_client = self.app.test_client()
        w_client = self.app.test_client()

        c_client.post('/auth/login', data={'login_id': 'citizen@prod.gov', 'password': 'Citizen@123'})
        a_client.post('/auth/login', data={'login_id': 'admin@prod.gov', 'password': 'Admin@123'})
        o_client.post('/auth/login', data={'login_id': 'officer@prod.gov', 'password': 'Officer@123'})
        w_client.post('/auth/login', data={'login_id': 'worker@prod.gov', 'password': 'Worker@123'})

        # Capture Admin initial cursor before disconnect
        a_init = a_client.get('/api/live-updates').get_json()
        admin_cursor = a_init['latest_notif_id']

        # 1. Citizen submits complaint -> Admin SSE stream & DB notification immediately reflect it
        c_client.post('/citizen/complaints/new', data={
            'title': 'Major main pipeline rupture',
            'category_id': cat_id,
            'description': 'High volume water leak flooding the main street intersection.',
            'priority': 'urgent',
            'address': '101 Main Road',
            'ward_number': 'Ward 3',
            'pincode': '600001'
        }, follow_redirects=True)
        comp = Complaint.query.first()
        self.assertIsNotNone(comp)
        comp_id = comp.id
        comp_ref = comp.complaint_ref

        sse_admin = a_client.get(f'/api/stream?since_id={admin_cursor}')
        self.assertEqual(sse_admin.status_code, 200)
        self.assertIn('text/event-stream', sse_admin.content_type)
        body = sse_admin.data.decode('utf-8')
        self.assertIn('event: sync', body)
        self.assertIn(comp_ref, body)

        # Verify Admin received persisted notification with complaint_id
        a_notifs = a_client.get('/api/notifications').get_json()
        self.assertEqual(a_notifs['unread_count'], 1)
        self.assertEqual(a_notifs['notifications'][0]['complaint_id'], comp_id)

        # 2. Admin assigns Officer -> Officer sees update & notification immediately
        a_client.post(f'/admin/complaint/{comp_id}', data={
            'action': 'assign_department_officer',
            'department_id': dept_id,
            'officer_id': officer_id,
            'admin_remarks': 'Dispatch immediately.'
        }, follow_redirects=True)
        o_sync = o_client.get('/api/live-updates').get_json()
        self.assertEqual(o_sync['total_count'], 1)
        self.assertEqual(o_sync['unread_notifications'], 1)
        self.assertEqual(o_sync['latest_notification']['complaint_id'], comp_id)

        # 3. Officer assigns Worker -> Worker receives notification with complaint ID, location, department & instructions
        o_client.post(f'/officer/complaint/{comp_id}', data={
            'action': 'assign_worker',
            'worker_user_id': worker_id,
            'instructions': 'Carry hydraulic wrench'
        }, follow_redirects=True)
        w_notifs = w_client.get('/api/notifications').get_json()
        self.assertEqual(w_notifs['unread_count'], 1)
        w_msg = w_notifs['notifications'][0]['message']
        self.assertIn(comp_ref, w_msg)
        self.assertIn('Water Supply', w_msg)
        self.assertIn('Carry hydraulic wrench', w_msg)

        # 4. Worker starts work -> Officer and Admin receive updates
        w_client.post(f'/worker/task/{comp_id}', data={'action': 'start_work', 'remarks': 'Started repairs'}, follow_redirects=True)
        o_notifs_after_start = o_client.get('/api/notifications').get_json()
        self.assertTrue(any('Work Started' in n['title'] for n in o_notifs_after_start['notifications']))

        # 5. Worker submits completion -> Officer & Admin notified; Citizen receives single clean notification (no duplicate)
        after_img = (io.BytesIO(b'\x89PNG\r\n\x1a\nafter'), 'done.png')
        w_client.post(f'/worker/task/{comp_id}', data={
            'action': 'submit_completion',
            'remarks': 'Replaced pipe flange and tested.',
            'after_image': after_img
        }, content_type='multipart/form-data', follow_redirects=True)
        o_notifs_verif = o_client.get('/api/notifications').get_json()
        self.assertTrue(any('Work Submitted for Verification' in n['title'] for n in o_notifs_verif['notifications']))

        # 6. Officer requests rework -> Worker notified with reason
        o_client.post(f'/officer/complaint/{comp_id}', data={
            'action': 'return_rework',
            'rework_reason': 'Need clearer valve closeup photo.'
        }, follow_redirects=True)
        w_notifs_rework = w_client.get('/api/notifications').get_json()
        self.assertTrue(any('Rework Required' in n['title'] and 'valve closeup' in n['message'] for n in w_notifs_rework['notifications']))

        # 7. Officer approves completion -> Citizen & Admin resolved updates
        o_client.post(f'/officer/complaint/{comp_id}', data={
            'action': 'verify_resolve',
            'remarks': 'Approved cleanly.'
        }, follow_redirects=True)
        c_notifs = c_client.get('/api/notifications').get_json()
        self.assertTrue(any('Complaint Resolved' in n['title'] for n in c_notifs['notifications']))
        # Ensure Citizen never sees Admin or Officer internal notifications
        self.assertFalse(any('Work Submitted for Verification' in n['title'] for n in c_notifs['notifications']))

        # 8. Mark single notification read -> unread count decreases & persists across new session login
        first_nid = c_notifs['notifications'][0]['id']
        prev_unread = c_notifs['unread_count']
        c_client.post(f'/api/notifications/{first_nid}/read')
        c_client.get('/auth/logout')

        c_new_device = self.app.test_client()
        c_new_device.post('/auth/login', data={'login_id': 'citizen@prod.gov', 'password': 'Citizen@123'})
        c_persisted = c_new_device.get('/api/notifications').get_json()
        self.assertEqual(c_persisted['unread_count'], prev_unread - 1)

        # 9. Network reconnect recovery (Last-Event-ID / since_id) returns missed notifications
        reconnect_sync = a_client.get(f'/api/live-updates?since_id={admin_cursor}').get_json()
        self.assertTrue(len(reconnect_sync['new_notifications']) >= 3)

    def test_global_gif_loader_asset_and_all_pages_configured(self):
        # 1. Exact animated GIF binary exists in static assets and serves over HTTP
        gif_path = os.path.join(self.app.static_folder, 'img', 'loader.gif')
        self.assertTrue(os.path.isfile(gif_path), 'loader.gif missing from app/static/img/')
        with open(gif_path, 'rb') as fh:
            header = fh.read(6)
        self.assertIn(header, (b'GIF89a', b'GIF87a'))

        gif_res = self.client.get('/static/img/loader.gif')
        self.assertEqual(gif_res.status_code, 200)
        self.assertIn('image/gif', gif_res.content_type)
        self.assertEqual(len(gif_res.data), os.path.getsize(gif_path))
        gif_res.close()

        # 2. Global GIF loading overlay configured on all public and role dashboard pages
        public_pages = ['/', '/auth/login']
        for route in public_pages:
            res = self.client.get(route)
            html = res.get_data(as_text=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn('id="globalPageLoader"', html)
            self.assertIn('img/loader.gif', html)
            self.assertNotIn('id="pageProgressBar"', html)
            self.assertNotIn('class="scf-loader-ring"', html)

        role_dashboards = [
            ('citizen@prod.gov', 'Citizen@123', '/citizen/dashboard'),
            ('admin@prod.gov', 'Admin@123', '/admin/dashboard'),
            ('officer@prod.gov', 'Officer@123', '/officer/dashboard'),
            ('worker@prod.gov', 'Worker@123', '/worker/dashboard'),
        ]
        for email, pwd, dash in role_dashboards:
            client = self.app.test_client()
            login_res = client.post('/auth/login', data={'login_id': email, 'password': pwd}, follow_redirects=True)
            self.assertEqual(login_res.status_code, 200)
            dash_res = client.get(dash)
            html = dash_res.get_data(as_text=True)
            self.assertEqual(dash_res.status_code, 200)
            self.assertIn('id="globalPageLoader"', html)
            self.assertIn('img/loader.gif', html)
            self.assertNotIn('id="pageProgressBar"', html)
            self.assertNotIn('class="scf-loader-ring"', html)

        css_path = os.path.join(self.app.static_folder, 'css', 'main.css')
        with open(css_path, 'r', encoding='utf-8') as fh:
            css = fh.read()
        self.assertNotIn('@keyframes scfLoaderSpin', css)
        self.assertNotIn('@keyframes btnSpinner', css)
        self.assertNotIn('.global-page-loader', css)

    def test_ttl_cache_invalidation_and_live_snapshot_queries(self):
        from app.utils.ttl_cache import TTLCache
        cache = TTLCache(max_entries=8)
        cache.set('public:index', {'ok': True}, ttl_seconds=30)
        self.assertEqual(cache.get('public:index'), {'ok': True})
        cache.invalidate_prefix('public:')
        self.assertIsNone(cache.get('public:index'))

        from app.services.complaint_service import build_admin_analytics_payload
        payload = build_admin_analytics_payload()
        self.assertIn('submitted', payload['summary'])

        client = self.app.test_client()
        login_res = client.post('/auth/login', data={'login_id': 'admin@prod.gov', 'password': 'Admin@123'})
        self.assertEqual(login_res.status_code, 302)
        snap = client.get('/api/live-updates')
        self.assertEqual(snap.status_code, 200)
        snap_json = snap.get_json()
        self.assertIn('fingerprint', snap_json)
        self.assertIn('unread_notifications', snap_json)

    def test_admin_analytics_empty_and_populated_metrics(self):
        a_client = self.app.test_client()
        self.assertEqual(
            a_client.post('/auth/login', data={'login_id': 'admin@prod.gov', 'password': 'Admin@123'}, follow_redirects=True).status_code,
            200
        )

        # 1. Empty state renders clean KPIs and empty-state guidance without errors
        res_empty = a_client.get('/admin/analytics')
        self.assertEqual(res_empty.status_code, 200)
        html_empty = res_empty.get_data(as_text=True)
        self.assertIn('No Complaints Registered Yet', html_empty)
        self.assertIn('id="deptAnalyticsTableBody"', html_empty)

        api_empty = a_client.get('/api/admin/analytics-data')
        self.assertEqual(api_empty.status_code, 200)
        self.assertEqual(api_empty.get_json()['summary']['total'], 0)

        # Non-admin role must be rejected (403)
        c_client = self.app.test_client()
        c_client.post('/auth/login', data={'login_id': 'citizen@prod.gov', 'password': 'Citizen@123'})
        self.assertEqual(c_client.get('/api/admin/analytics-data').status_code, 403)

        # 2. Newly submitted complaint (department_id=None before routing) is attributed via category department
        c1 = Complaint(
            complaint_ref='CMP-ANL-001',
            citizen_id=self.citizen.id,
            department_id=None,
            category_id=self.cat.id,
            title='Street water burst',
            description='Heavy water pipe leak near junction.',
            priority='high',
            status='Submitted',
        )
        c2 = Complaint(
            complaint_ref='CMP-ANL-002',
            citizen_id=self.citizen.id,
            department_id=self.dept.id,
            category_id=self.cat.id,
            title='Fixed water line',
            description='Resolved main pipe issue.',
            priority='medium',
            status='Resolved',
        )
        db.session.add_all([c1, c2])
        db.session.commit()

        api_pop = a_client.get('/api/admin/analytics-data')
        self.assertEqual(api_pop.status_code, 200)
        data = api_pop.get_json()
        self.assertEqual(data['summary']['total'], 2)
        self.assertEqual(data['summary']['pending'], 1)
        self.assertEqual(data['summary']['resolved'], 1)
        self.assertEqual(data['summary']['resolution_rate'], 50.0)
        self.assertEqual(data['dept_totals'], [2])
        self.assertEqual(data['dept_resolved'], [1])
        self.assertEqual(data['cat_labels'], ['Pipe Leak'])
        self.assertEqual(data['cat_totals'], [2])

        res_pop = a_client.get('/admin/analytics')
        self.assertEqual(res_pop.status_code, 200)
        self.assertIn('Water Supply', res_pop.get_data(as_text=True))

    def test_full_page_layout_no_half_screen_constraints(self):
        import re
        templates_dir = os.path.join(self.app.root_path, 'templates')
        for root, _, files in os.walk(templates_dir):
            for fname in files:
                if not fname.endswith('.html'):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, 'r', encoding='utf-8') as fh:
                    content = fh.read()
                self.assertIsNone(
                    re.search(r'<div[^>]*class=["\'][^"\']*dashboard-content[^"\']*["\'][^>]*max-width', content),
                    f"Template {fname} still constrains .dashboard-content with inline max-width"
                )

        css_path = os.path.join(self.app.static_folder, 'css', 'main.css')
        with open(css_path, 'r', encoding='utf-8') as fh:
            css = fh.read()
        self.assertIn('max-width: calc(100vw - var(--sidebar-expanded-width)) !important;', css)
        self.assertIn('width: 100% !important;', css)

    def test_public_pages_have_global_navbar_and_no_back_buttons(self):
        for route in ['/', '/contact', '/about', '/departments', '/how-it-works', '/cookies', '/privacy', '/terms', '/track']:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"{route} failed")
            html = res.get_data(as_text=True)
            self.assertEqual(html.count('<nav class="navbar"'), 1, f"Expected single navbar on {route}")
            self.assertNotIn('data-back-nav', html, f"Back button must be removed from public route {route}")
            self.assertNotIn('page-back-bar', html, f"Back button bar must be removed from public route {route}")
            self.assertNotIn('history.back', html, f"history.back must not be on public route {route}")

        # Track page should NOT render the left sidebar menu bar
        track_html = self.client.get('/track').get_data(as_text=True)
        self.assertNotIn('id="dashboardSidebar"', track_html)

        # Logged-in users visiting public pages get single navbar and single notifMenu (no duplicate)
        a_client = self.app.test_client()
        a_client.post('/auth/login', data={'login_id': 'admin@prod.gov', 'password': 'Admin@123'})
        for route in ['/', '/contact', '/about', '/departments', '/how-it-works', '/track']:
            html = a_client.get(route).get_data(as_text=True)
            self.assertEqual(html.count('<nav class="navbar"'), 1)
            self.assertEqual(html.count('id="notifMenu"'), 1, f"Duplicate notifMenu on {route}")
            self.assertNotIn('data-back-nav', html)

    def test_contact_form_sends_message_to_admin_dashboard_and_notifies(self):
        res = self.client.post('/contact', data={
            'name': 'Priya Citizen',
            'contact': 'priya@example.com',
            'message': 'Need help updating my ward details on grievance form.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        a_client = self.app.test_client()
        a_client.post('/auth/login', data={'login_id': 'admin@prod.gov', 'password': 'Admin@123'})

        # Admin receives real-time notification
        notifs = a_client.get('/api/notifications').get_json()
        self.assertTrue(any('New Contact Inquiry' in n['title'] and 'Priya Citizen' in n['message'] for n in notifs['notifications']))

        # Admin dashboard displays the contact inquiry card and message
        dash_html = a_client.get('/admin/dashboard').get_data(as_text=True)
        self.assertIn('id="contactInquiriesCard"', dash_html)
        self.assertIn('Priya Citizen', dash_html)
        self.assertIn('Need help updating my ward details on grievance form.', dash_html)

        # Admin can mark inquiry reviewed
        from app.models.contact import ContactMessage
        msg = ContactMessage.query.filter_by(name='Priya Citizen').first()
        self.assertIsNotNone(msg)
        self.assertFalse(msg.is_read)
        mark_res = a_client.post(f'/admin/contact-messages/{msg.id}/read', follow_redirects=True)
        self.assertEqual(mark_res.status_code, 200)
        db.session.refresh(msg)
        self.assertTrue(msg.is_read)

    def test_global_navbar_consistent_across_all_public_pages(self):
        public_nav_pages = [
            ('/', '/'),
            ('/about', '/about'),
            ('/how-it-works', '/how-it-works'),
            ('/departments', '/departments'),
            ('/track', '/track'),
            ('/contact', '/contact'),
            ('/privacy', None),
            ('/cookies', None),
            ('/terms', None),
            ('/auth/login', None),
            ('/auth/register', None),
            ('/auth/forgot-password', None),
        ]
        nav_hrefs = ['href="/"', 'href="/about"', 'href="/how-it-works"', 'href="/departments"', 'href="/track"', 'href="/contact"']

        for route, active_href in public_nav_pages:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Public route {route} failed")
            html = res.get_data(as_text=True)
            self.assertIn('<nav class="navbar"', html, f"Global navbar missing on {route}")
            self.assertIn('id="mobileNavToggle"', html, f"Mobile hamburger menu missing on {route}")
            for h in nav_hrefs:
                self.assertIn(h, html, f"Navbar link {h} missing on {route}")
            if active_href:
                self.assertIn(
                    f'href="{active_href}" class="nav-link active" aria-current="page"',
                    html,
                    f"Active highlight missing for {active_href} on {route}"
                )

        # Verify sticky & responsive navbar CSS rules remain intact
        css_path = os.path.join(self.app.static_folder, 'css', 'main.css')
        with open(css_path, 'r', encoding='utf-8') as fh:
            css = fh.read()
        self.assertIn('position: sticky;', css)
        self.assertIn('.nav-links.mobile-open {', css)

    def test_scf_animated_logo_and_branding_present(self):
        from PIL import Image
        img_dir = os.path.join(self.app.static_folder, 'img')
        for fname, min_frames in [('scf-logo.webp', 10), ('scf-hero-logo.webp', 10), ('scf-logo.png', 1), ('favicon.png', 1)]:
            fpath = os.path.join(img_dir, fname)
            self.assertTrue(os.path.isfile(fpath), f'Missing logo asset {fname}')
            with Image.open(fpath) as im:
                self.assertGreaterEqual(getattr(im, 'n_frames', 1), min_frames)
                if fname == 'favicon.png':
                    self.assertEqual(im.size[0], im.size[1], 'Favicon must be 1:1 square so browser does not squish it')
            res = self.client.get(f'/static/img/{fname}')
            self.assertEqual(res.status_code, 200)
            res.close()

        home_html = self.client.get('/').get_data(as_text=True)
        self.assertIn('SCF', home_html)
        self.assertIn('Smart Civic Flow', home_html)
        self.assertNotIn('class="brand-title-paren"', home_html)
        self.assertIn('/static/img/scf-logo.webp', home_html)
        self.assertNotIn('/static/img/scf-hero-logo.webp', home_html)
        self.assertIn('/static/img/favicon.png', home_html)

        # Contact page omits static helpline phone and support email
        contact_html = self.client.get('/contact').get_data(as_text=True)
        self.assertNotIn('1800-425-0000', contact_html)
        self.assertNotIn('support@smartcivic.gov.portal', contact_html)

    def test_sidebar_brand_and_profile_no_clipping(self):
        css_path = os.path.join(self.app.static_folder, 'css', 'main.css')
        with open(css_path, 'r', encoding='utf-8') as fh:
            css = fh.read()
        # Expanded sidebar hides floating .sidebar-label inside profile card so name/meta stay visible
        self.assertIn('.sidebar-user-card .sidebar-label {\n  display: none;\n}', css)
        self.assertIn('.sidebar-user-details {\n  display: flex;\n  flex-direction: column;\n  flex: 1;\n  min-width: 0;', css)
        self.assertIn('.sidebar-brand-link {\n  display: flex;\n  align-items: center;\n  gap: 0.5rem;\n  color: var(--text-primary);\n  text-decoration: none;\n  flex: 1;\n  min-width: 0;', css)

        sidebar_path = os.path.join(self.app.root_path, self.app.template_folder, 'shared', '_sidebar.html')
        with open(sidebar_path, 'r', encoding='utf-8') as fh:
            sidebar_src = fh.read()
        self.assertIn('<span class="sidebar-brand-sub">Smart Civic Flow</span>', sidebar_src)

    def test_chartjs_loaded_only_on_chart_pages(self):
        home_html = self.client.get('/').get_data(as_text=True)
        self.assertNotIn('chart.umd.min.js', home_html)

        a_client = self.app.test_client()
        a_client.post('/auth/login', data={'login_id': 'admin@prod.gov', 'password': 'Admin@123'})
        self.assertIn('chart.umd.min.js', a_client.get('/admin/dashboard').get_data(as_text=True))
        self.assertIn('chart.umd.min.js', a_client.get('/admin/analytics').get_data(as_text=True))

    def test_indexes_pagination_and_async_json_button_actions(self):
        from sqlalchemy import inspect
        insp = inspect(db.engine)
        comp_indexes = {idx['name'] for idx in insp.get_indexes('complaints')}
        self.assertIn('idx_comp_status', comp_indexes)
        self.assertIn('idx_comp_dept_status_created', comp_indexes)

        # Citizen submits complaint -> Admin assigns via AJAX JSON -> Officer assigns worker via AJAX JSON -> Worker updates via AJAX JSON -> Officer resolves via AJAX JSON -> Citizen feedback via AJAX JSON
        ajax_headers = {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}

        c_client = self.app.test_client()
        c_client.post('/auth/login', data={'login_id': 'citizen@prod.gov', 'password': 'Citizen@123'})
        res_sub = c_client.post('/citizen/complaints/new', data={
            'title': 'Async button workflow leak test',
            'category_id': self.cat.id,
            'department_id': self.dept.id,
            'priority': 'high',
            'description': 'Testing non-blocking async JSON action buttons end to end.',
            'ward_number': '5',
            'city': 'Chennai'
        }, follow_redirects=False)
        comp_id = int(res_sub.headers['Location'].rstrip('/').split('/')[-1])

        a_client = self.app.test_client()
        a_client.post('/auth/login', data={'login_id': 'admin@prod.gov', 'password': 'Admin@123'})
        r1 = a_client.post(f'/admin/complaints/{comp_id}', data={
            'action': 'assign_department_officer',
            'department_id': self.dept.id,
            'officer_id': self.officer.id,
            'admin_remarks': 'Fast async route'
        }, headers=ajax_headers)
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.get_json()['success'])
        self.assertEqual(r1.get_json()['status'], 'Assigned to Department')

        o_client = self.app.test_client()
        o_client.post('/auth/login', data={'login_id': 'officer@prod.gov', 'password': 'Officer@123'})
        r2 = o_client.post(f'/officer/complaint/{comp_id}', data={
            'action': 'assign_worker',
            'worker_user_id': self.worker.id,
            'instructions': 'Dispatch immediately'
        }, headers=ajax_headers)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.get_json()['status'], 'Assigned to Worker')

        w_client = self.app.test_client()
        w_client.post('/auth/login', data={'login_id': 'worker@prod.gov', 'password': 'Worker@123'})
        r3 = w_client.post(f'/worker/task/{comp_id}', data={
            'action': 'start_work',
            'remarks': 'Started site work cleanly'
        }, headers=ajax_headers)
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r3.get_json()['status'], 'In Progress')

        # Contact inquiry AJAX submission + Admin Mark Reviewed AJAX
        r_contact = self.client.post('/contact', data={
            'name': 'Async Contact',
            'contact': 'async@test.gov',
            'message': 'Fast AJAX inquiry submission verification.'
        }, headers=ajax_headers)
        self.assertEqual(r_contact.status_code, 200)
        self.assertTrue(r_contact.get_json()['success'])

        from app.models.contact import ContactMessage
        msg = ContactMessage.query.filter_by(name='Async Contact').first()
        r_mark = a_client.post(f'/admin/contact-messages/{msg.id}/read', headers=ajax_headers)
        self.assertEqual(r_mark.status_code, 200)
        self.assertTrue(r_mark.get_json()['success'])

    def test_timeout_resilience_and_fast_priority_ajax(self):
        # Verify both Vercel origins are allowed in CORS
        res_indol = self.client.get(
            '/api/stats/summary',
            headers={'Origin': 'https://smart-civic-complaint-management-sy-indol.vercel.app'}
        )
        self.assertEqual(res_indol.status_code, 200)
        self.assertEqual(
            res_indol.headers.get('Access-Control-Allow-Origin'),
            'https://smart-civic-complaint-management-sy-indol.vercel.app'
        )

        # Create complaint and test single-roundtrip priority update (no full HTML reload needed)
        c_client = self.app.test_client()
        c_client.post('/auth/login', data={'login_id': 'citizen@prod.gov', 'password': 'Citizen@123'})
        res_sub = c_client.post('/citizen/complaints/new', data={
            'title': 'Timeout resilience test complaint',
            'category_id': self.cat.id,
            'department_id': self.dept.id,
            'priority': 'low',
            'description': 'Verifying single-roundtrip AJAX priority updates without redundant reloads.',
            'ward_number': '2',
            'city': 'Chennai'
        }, follow_redirects=False)
        comp_id = int(res_sub.headers['Location'].rstrip('/').split('/')[-1])

        ajax_headers = {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}
        a_client = self.app.test_client()
        a_client.post('/auth/login', data={'login_id': 'admin@prod.gov', 'password': 'Admin@123'})
        r_prio = a_client.post(f'/admin/complaints/{comp_id}', data={
            'action': 'change_priority',
            'new_priority': 'urgent'
        }, headers=ajax_headers)
        self.assertEqual(r_prio.status_code, 200)
        prio_json = r_prio.get_json()
        self.assertTrue(prio_json['success'])
        self.assertEqual(prio_json['priority'], 'urgent')
        self.assertFalse(prio_json['reload_sections'])

        # Verify client JS includes extended 55s timeout, non-fatal refresh handling, and proxy-safe polling
        main_js_path = os.path.join(self.app.static_folder, 'js', 'main.js')
        notif_js_path = os.path.join(self.app.static_folder, 'js', 'notifications.js')
        with open(main_js_path, 'r', encoding='utf-8') as fh:
            main_js = fh.read()
        with open(notif_js_path, 'r', encoding='utf-8') as fh:
            notif_js = fh.read()
        self.assertIn('55000', main_js)
        self.assertIn('sccmt_last_warm_ts', main_js)
        self.assertIn('isVercelProxied', notif_js)

    def test_local_timezone_rendering_for_actions(self):
        from datetime import datetime
        from app.utils.helpers import format_local_time
        sample_utc = datetime(2026, 11, 25, 11, 13, 9)
        rendered_ist = str(format_local_time(sample_utc, '%d %b %Y, %I:%M %p'))
        self.assertIn('data-utc="2026-11-25T11:13:09Z"', rendered_ist)
        self.assertIn('25 Nov 2026, 04:43 PM', rendered_ist)

        # Verify browser timezone cookie overrides server rendering dynamically
        c_client = self.app.test_client()
        c_client.post('/auth/login', data={'login_id': 'citizen@prod.gov', 'password': 'Citizen@123'})
        c_client.set_cookie('sccmt_tz_offset', '-330')
        res_sub = c_client.post('/citizen/complaints/new', data={
            'title': 'Local time action verification',
            'category_id': self.cat.id,
            'department_id': self.dept.id,
            'priority': 'medium',
            'description': 'Checking local timezone display in track and detail timelines.',
            'ward_number': '3',
            'city': 'Chennai'
        }, follow_redirects=False)
        comp_id = int(res_sub.headers['Location'].rstrip('/').split('/')[-1])
        comp = db.session.get(Complaint, comp_id)
        track_html = self.client.get(f'/track?ref={comp.complaint_ref}').get_data(as_text=True)
        self.assertIn('data-utc="', track_html)
        self.assertIn('<time datetime="', track_html)

    def test_analytics_empty_overlays_hide_cleanly_when_complaints_exist(self):
        a_client = self.app.test_client()
        a_client.post('/auth/login', data={'login_id': 'admin@prod.gov', 'password': 'Admin@123'})

        # With >=1 complaint, empty overlays must be hidden and NOT force inline display: flex over [hidden]
        db.session.add(Complaint(
            complaint_ref='CMP-202611-CHRT1',
            citizen_id=self.citizen.id,
            category_id=self.cat.id,
            department_id=self.dept.id,
            title='Chart visibility test',
            description='Ensure analytics charts are never covered by empty state overlay.',
            priority='medium',
            status='Submitted',
        ))
        db.session.commit()

        html = a_client.get('/admin/analytics').get_data(as_text=True)
        self.assertIn('id="deptChartEmpty" class="analytics-empty-state" hidden', html)
        self.assertIn('id="categoryChartEmpty" class="analytics-empty-state" hidden', html)
        self.assertIn('id="statusChartEmpty" class="analytics-empty-state" hidden', html)
        self.assertIn('display: none;', html)

        css_path = os.path.join(self.app.static_folder, 'css', 'main.css')
        with open(css_path, 'r', encoding='utf-8') as fh:
            css = fh.read()
        self.assertIn('.analytics-empty-state[hidden]', css)


if __name__ == '__main__':
    unittest.main()
