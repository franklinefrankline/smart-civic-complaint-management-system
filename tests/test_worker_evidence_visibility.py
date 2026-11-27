import io
import os
import unittest
from app import create_app, db
from app.models.attachment import ComplaintAttachment
from app.models.category import ComplaintCategory
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.user import User
from app.models.workflow import ComplaintAssignment, Worker


class WorkerEvidenceVisibilityTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.dept = Department(name='Water Supply', code='WATER_EV', is_active=True)
        self.other_dept = Department(name='Roads Division', code='ROADS_EV', is_active=True)
        db.session.add_all([self.dept, self.other_dept])
        db.session.flush()

        self.cat = ComplaintCategory(
            name='Pipeline Leak',
            department_id=self.dept.id,
            default_priority='high',
            sla_hours=48,
            is_active=True,
        )
        db.session.add(self.cat)
        db.session.flush()

        self.admin = User(role='admin', full_name='Evidence Admin', email='ev.admin@civic.gov', mobile_number='9833333301', is_active=True)
        self.admin.set_password('Admin@123')

        self.officer = User(role='officer', department_id=self.dept.id, full_name='Water Dept Officer', email='ev.officer@civic.gov', mobile_number='9833333302', is_active=True)
        self.officer.set_password('Officer@123')

        self.other_officer = User(role='officer', department_id=self.other_dept.id, full_name='Roads Dept Officer', email='ev.other@civic.gov', mobile_number='9833333305', is_active=True)
        self.other_officer.set_password('Officer@123')

        self.worker_user = User(role='worker', department_id=self.dept.id, full_name='Ramesh Field Worker', email='ev.worker@civic.gov', mobile_number='9833333303', is_active=True)
        self.worker_user.set_password('Worker@123')

        self.citizen = User(role='citizen', full_name='Anitha Citizen', email='ev.citizen@civic.gov', mobile_number='9833333304', is_active=True)
        self.citizen.set_password('Citizen@123')

        db.session.add_all([self.admin, self.officer, self.other_officer, self.worker_user, self.citizen])
        db.session.flush()

        db.session.add(Worker(user_id=self.worker_user.id, department_id=self.dept.id, employee_id='EMP-EV-01', designation='Technician', is_available=True))

        self.complaint = Complaint(
            complaint_ref='CMP-EV-2026',
            citizen_id=self.citizen.id,
            department_id=self.dept.id,
            category_id=self.cat.id,
            assigned_officer_id=self.officer.id,
            assigned_worker_id=self.worker_user.id,
            title='Burst Water Pipe on 4th Cross Street',
            description='Continuous water leakage affecting road access.',
            priority='high',
            status='Assigned to Worker',
        )
        db.session.add(self.complaint)
        db.session.flush()

        db.session.add(ComplaintAssignment(
            complaint_id=self.complaint.id,
            assigned_to_user_id=self.worker_user.id,
            assigned_by_user_id=self.officer.id,
            status='Assigned',
        ))
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.ctx.pop()

    def _login(self, client, email, password):
        resp = client.post('/auth/login', data={'login_id': email, 'password': password}, follow_redirects=False)
        self.assertIn(resp.status_code, (302, 200))

    def test_worker_evidence_photos_visible_on_admin_and_officer_dashboards_and_details(self):
        w_client = self.app.test_client()
        self._login(w_client, 'ev.worker@civic.gov', 'Worker@123')

        # 1. Worker starts work with Pre-Work photo uploaded with generic octet-stream mimetype
        res_start = w_client.post(
            f'/worker/task/{self.complaint.id}',
            data={
                'action': 'start_work',
                'remarks': 'Arrived at leaking valve chamber',
                'before_image': (io.BytesIO(b'\xff\xd8\xff\xe0preworkbytes'), 'prework_site.jpg', 'application/octet-stream'),
            },
            content_type='multipart/form-data',
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(res_start.status_code, 200)
        self.assertTrue(res_start.get_json()['success'])

        # 2. Worker uploads an intermediate site evidence photo via update_progress
        res_prog = w_client.post(
            f'/worker/task/{self.complaint.id}',
            data={
                'action': 'update_progress',
                'progress_notes': 'Exposed cracked joint and installed collar',
                'evidence_image': (io.BytesIO(b'\x89PNG\r\n\x1a\nmidwork'), 'site_collar.png'),
            },
            content_type='multipart/form-data',
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(res_prog.status_code, 200)
        self.assertTrue(res_prog.get_json()['success'])

        # 3. Worker completes task with After-Work proof photo
        res_done = w_client.post(
            f'/worker/task/{self.complaint.id}',
            data={
                'action': 'submit_completion',
                'remarks': 'Valve sealed cleanly and pressure verified',
                'after_image': (io.BytesIO(b'\x89PNG\r\n\x1a\nafterworkbytes'), 'completed_repair.png'),
            },
            content_type='multipart/form-data',
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(res_done.status_code, 200)
        self.assertTrue(res_done.get_json()['success'])

        atts = ComplaintAttachment.query.filter_by(complaint_id=self.complaint.id).all()
        self.assertEqual(len(atts), 3)
        for att in atts:
            self.assertTrue(att.is_image, f"{att.filename} should be treated as an image")
            # Remove ephemeral disk file to confirm DB BLOB serving works in cloud production
            disk_path = os.path.join(self.app.config['UPLOAD_FOLDER'], att.file_path.replace('uploads/', ''))
            if os.path.isfile(disk_path):
                os.remove(disk_path)

        # 4. Admin sees worker evidence photos on BOTH /admin/dashboard and /admin/complaints/<id>
        a_client = self.app.test_client()
        self._login(a_client, 'ev.admin@civic.gov', 'Admin@123')

        admin_dash_html = a_client.get('/admin/dashboard').get_data(as_text=True)
        self.assertIn('workerEvidenceCard', admin_dash_html)
        self.assertIn('CMP-EV-2026', admin_dash_html)
        self.assertIn('Ramesh Field Worker', admin_dash_html)
        for att in atts:
            self.assertIn(att.public_url, admin_dash_html)

        admin_detail_html = a_client.get(f'/admin/complaints/{self.complaint.id}').get_data(as_text=True)
        for att in atts:
            self.assertIn(f'<img src="{att.public_url}"', admin_detail_html)
            img_resp = a_client.get(att.public_url)
            self.assertEqual(img_resp.status_code, 200)
            self.assertTrue(img_resp.mimetype.startswith('image/'))

        # 5. Assigned department officer sees evidence on BOTH /officer/dashboard and /officer/complaints/<id>
        o_client = self.app.test_client()
        self._login(o_client, 'ev.officer@civic.gov', 'Officer@123')

        officer_dash_html = o_client.get('/officer/dashboard').get_data(as_text=True)
        self.assertIn('officerWorkerEvidenceCard', officer_dash_html)
        self.assertIn('CMP-EV-2026', officer_dash_html)
        self.assertIn('Ramesh Field Worker', officer_dash_html)
        for att in atts:
            self.assertIn(att.public_url, officer_dash_html)

        officer_detail_html = o_client.get(f'/officer/complaints/{self.complaint.id}').get_data(as_text=True)
        for att in atts:
            self.assertIn(f'<img src="{att.public_url}"', officer_detail_html)

        # 6. Unrelated department officer does NOT see another department's evidence on /officer/dashboard
        other_client = self.app.test_client()
        self._login(other_client, 'ev.other@civic.gov', 'Officer@123')
        other_dash_html = other_client.get('/officer/dashboard').get_data(as_text=True)
        self.assertNotIn('CMP-EV-2026', other_dash_html)

    def test_upload_serving_works_even_with_relative_upload_folder_and_404_renders_cleanly(self):
        # Simulate relative UPLOAD_FOLDER='uploads' from environment/config
        orig_folder = self.app.config['UPLOAD_FOLDER']
        self.app.config['UPLOAD_FOLDER'] = 'uploads'
        try:
            a_client = self.app.test_client()
            self._login(a_client, 'ev.admin@civic.gov', 'Admin@123')
            missing_res = a_client.get('/uploads/proofs/definitely-missing-file.jpg')
            self.assertEqual(missing_res.status_code, 404)
            self.assertIn('File Not Found', missing_res.get_data(as_text=True))
        finally:
            self.app.config['UPLOAD_FOLDER'] = orig_folder


if __name__ == '__main__':
    unittest.main()
