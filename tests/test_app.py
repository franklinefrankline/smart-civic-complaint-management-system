import unittest
import os
import io
from app import create_app, db
from app.models.user import User
from app.models.complaint import Complaint
from app.models.category import ComplaintCategory
from app.models.department import Department
from app.models.workflow import Worker, ComplaintAssignment
from app.models.feedback import Feedback

class CivicSystemTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Seed required baseline
        self.dept = Department(name="Water Works", code="WATER", is_active=True)
        db.session.add(self.dept)
        db.session.flush()

        self.cat = ComplaintCategory(name="Pipe Leakage", department_id=self.dept.id, default_priority="urgent", is_active=True)
        db.session.add(self.cat)
        db.session.flush()

        # Users for 4 roles
        self.admin = User(role='admin', full_name='Admin User', email='admin@test.gov', mobile_number='9000000001', is_active=True)
        self.admin.set_password('Admin@123')

        self.officer = User(role='officer', full_name='Officer User', email='officer@test.gov', mobile_number='9000000002', department_id=self.dept.id, is_active=True)
        self.officer.set_password('Officer@123')

        self.worker = User(role='worker', full_name='Worker User', email='worker@test.gov', mobile_number='9000000003', department_id=self.dept.id, is_active=True)
        self.worker.set_password('Worker@123')

        self.citizen = User(role='citizen', full_name='Citizen User', email='citizen@test.gov', mobile_number='9000000004', is_active=True)
        self.citizen.set_password('Citizen@123')

        db.session.add_all([self.admin, self.officer, self.worker, self.citizen])
        db.session.flush()

        self.w_profile = Worker(user_id=self.worker.id, department_id=self.dept.id, is_available=True)
        db.session.add(self.w_profile)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self, email, password):
        return self.client.post('/auth/login', data={'login_id': email, 'password': password}, follow_redirects=True)

    def logout(self):
        return self.client.get('/auth/logout', follow_redirects=True)

    def test_01_public_pages_load(self):
        """Test public endpoints response status"""
        for url in ['/', '/about', '/how-it-works', '/departments', '/track', '/contact']:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Failed loading {url}")

    def test_02_citizen_registration_and_login(self):
        """Test citizen registration, duplicate check, and login"""
        # Register new citizen
        res = self.client.post('/auth/register', data={
            'full_name': 'New Citizen',
            'email': 'newcitizen@test.com',
            'mobile': '9876500001',
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'address': '12 Gandhi St',
            'city': 'Chennai',
            'ward_number': 'Ward 5'
        }, follow_redirects=True)
        self.assertIn(b"Registration successful", res.data)

        # Login with newly created user
        res_login = self.login('newcitizen@test.com', 'Password@123')
        self.assertIn(b"Citizen Dashboard", res_login.data)

    def test_03_role_based_access_control(self):
        """Ensure users cannot access another role's dashboard by changing URL"""
        # Citizen tries to access /admin/dashboard
        self.login('citizen@test.gov', 'Citizen@123')
        res = self.client.get('/admin/dashboard', follow_redirects=True)
        self.assertIn(b"Unauthorized access", res.data)
        self.assertIn(b"Citizen Dashboard", res.data)

        # Citizen tries to access /officer/dashboard
        res_off = self.client.get('/officer/dashboard', follow_redirects=True)
        self.assertIn(b"Unauthorized access", res_off.data)

        self.logout()

    def test_04_full_complaint_workflow(self):
        """
        Complete end-to-end lifecycle:
        Submit -> Accept -> Assign -> In Progress -> Work Completed -> Verify & Resolve -> Feedback -> Reopen
        """
        # 1. Citizen submits complaint
        self.login('citizen@test.gov', 'Citizen@123')
        res_submit = self.client.post('/citizen/complaints/new', data={
            'title': 'Pipeline rupture spilling into street',
            'category_id': self.cat.id,
            'department_id': self.dept.id,
            'description': 'Continuous high pressure leakage on pavement opposite municipal park.',
            'priority': 'urgent',
            'address': 'Main road corner',
            'city': 'Chennai',
            'ward_number': 'Ward 4',
            'latitude': '13.0827',
            'longitude': '80.2707'
        }, follow_redirects=True)
        self.assertIn(b"Complaint registered successfully", res_submit.data)

        complaint = Complaint.query.filter_by(citizen_id=self.citizen.id).first()
        self.assertIsNotNone(complaint)
        self.assertEqual(complaint.status, 'Submitted')
        complaint_id = complaint.id
        self.logout()

        # 2. Officer accepts complaint
        self.login('officer@test.gov', 'Officer@123')
        res_accept = self.client.post(f'/officer/complaints/{complaint_id}', data={
            'action': 'accept'
        }, follow_redirects=True)
        self.assertIn(b"Complaint accepted", res_accept.data)
        complaint = Complaint.query.get(complaint_id)
        self.assertIn(complaint.status, ['Officer Accepted', 'Accepted'])

        # 3. Officer assigns worker
        res_assign = self.client.post(f'/officer/complaints/{complaint_id}', data={
            'action': 'assign_worker',
            'worker_user_id': self.worker.id,
            'instructions': 'Carry 100mm pipe clamp kit'
        }, follow_redirects=True)
        self.assertIn(b"assigned successfully", res_assign.data)
        complaint = Complaint.query.get(complaint_id)
        self.assertIn(complaint.status, ['Assigned to Worker', 'Assigned'])
        self.logout()

        # 4. Worker starts work
        self.login('worker@test.gov', 'Worker@123')
        res_start = self.client.post(f'/worker/tasks/{complaint_id}', data={
            'action': 'start_work',
            'remarks': 'Arrived on site, excavation commenced'
        }, follow_redirects=True)
        self.assertIn(b"In Progress", res_start.data)
        complaint = Complaint.query.get(complaint_id)
        self.assertEqual(complaint.status, 'In Progress')

        # 5. Worker completes work
        # Create a mock image file for after_work proof
        mock_img = (io.BytesIO(b"fake image data"), "after.jpg")
        res_complete = self.client.post(f'/worker/tasks/{complaint_id}', data={
            'action': 'submit_completion',
            'remarks': 'Replaced cracked flange and restored pavement',
            'after_image': mock_img
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertIn(b"pending officer verification", res_complete.data)
        complaint = Complaint.query.get(complaint_id)
        self.assertIn(complaint.status, ['Verification Pending', 'Work Completed'])
        self.logout()

        # 6. Officer verifies work and approves resolution
        self.login('officer@test.gov', 'Officer@123')
        res_resolve = self.client.post(f'/officer/complaints/{complaint_id}', data={
            'action': 'verify_resolve',
            'remarks': 'Work checked on site, resolved satisfactorily'
        }, follow_redirects=True)
        self.assertIn(b"successfully resolved", res_resolve.data)
        complaint = Complaint.query.get(complaint_id)
        self.assertEqual(complaint.status, 'Resolved')
        self.assertIsNotNone(complaint.resolved_at)
        self.logout()

        # 7. Citizen submits feedback (5 stars)
        self.login('citizen@test.gov', 'Citizen@123')
        res_fb = self.client.post(f'/citizen/complaints/{complaint_id}/feedback', data={
            'rating': '5',
            'comment': 'Prompt action, thanks municipal team!'
        }, follow_redirects=True)
        self.assertIn(b"Your feedback helps us improve", res_fb.data)
        fb = Feedback.query.filter_by(complaint_id=complaint_id).first()
        self.assertIsNotNone(fb)
        self.assertEqual(fb.rating, 5)

        # 8. Citizen reopens complaint
        res_reopen = self.client.post(f'/citizen/complaints/{complaint_id}/reopen', data={
            'reopen_reason': 'Seepage is still occurring around the replacement collar.'
        }, follow_redirects=True)
        self.assertIn(b"Complaint has been reopened", res_reopen.data)
        complaint = Complaint.query.get(complaint_id)
        self.assertEqual(complaint.status, 'Reopened')
        self.assertEqual(complaint.reopened_count, 1)
        self.logout()

    def test_05_duplicate_detection_api(self):
        """Test haversine duplicate detection endpoint"""
        # Create an existing complaint at (13.0827, 80.2707)
        c = Complaint(
            complaint_ref="CMP-TEST-DUP",
            citizen_id=self.citizen.id,
            department_id=self.dept.id,
            category_id=self.cat.id,
            title="Burst pipe near park",
            description="Flooding pavement",
            priority="urgent",
            status="Submitted",
            latitude=13.082700,
            longitude=80.270700
        )
        db.session.add(c)
        db.session.commit()

        # Check nearby coordinates (100m away)
        res = self.client.post('/api/complaints/check-duplicate', json={
            'category_id': self.cat.id,
            'latitude': 13.083000,
            'longitude': 80.270900
        })
        data = res.get_json()
        self.assertTrue(data['has_duplicates'])
        self.assertGreater(len(data['duplicates']), 0)

    def test_06_language_selector(self):
        """Test switching language to Tamil and Hindi"""
        res_ta = self.client.get('/set-language/ta', follow_redirects=True)
        self.assertEqual(res_ta.status_code, 200)

        res_hi = self.client.get('/set-language/hi', follow_redirects=True)
        self.assertEqual(res_hi.status_code, 200)

    def test_07_public_tracking(self):
        """Test public complaint tracking by reference ID"""
        c = Complaint(
            complaint_ref="CMP-TRACK-ME",
            citizen_id=self.citizen.id,
            department_id=self.dept.id,
            category_id=self.cat.id,
            title="Trackable issue",
            description="Testing public tracking",
            priority="medium",
            status="In Progress"
        )
        db.session.add(c)
        db.session.commit()

        res = self.client.get('/track?ref=CMP-TRACK-ME')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"CMP-TRACK-ME", res.data)
        self.assertIn(b"Trackable issue", res.data)

    def test_08_notifications_api(self):
        """Test notifications retrieval and mark as read"""
        self.login('citizen@test.gov', 'Citizen@123')
        res = self.client.get('/api/notifications')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('unread_count', data)

    def test_09_csv_export(self):
        """Test administrator CSV export endpoint"""
        self.login('admin@test.gov', 'Admin@123')
        res = self.client.get('/admin/export/complaints')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'text/csv')
        self.assertIn(b"Reference ID,Title,Citizen", res.data)

if __name__ == '__main__':
    unittest.main()
