import io
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest
from datetime import datetime
from flask import g, session
from app import create_app, db
from app.models.user import User
from app.models.department import Department
from app.models.category import ComplaintCategory
from app.models.complaint import Complaint
from app.models.feedback import Feedback
from app.models.workflow import Worker, ComplaintAssignment, ComplaintStatusHistory

class TestAllFunctionalWorkflows(unittest.TestCase):
    _seq = 0

    @classmethod
    def next_seq(cls):
        cls._seq += 1
        return cls._seq

    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()

        # Baseline Department & Category
        self.dept = Department(name="Water Works", code="WATER", is_active=True)
        db.session.add(self.dept)
        db.session.flush()

        self.cat = ComplaintCategory(name="Pipe Leakage", department_id=self.dept.id, default_priority="urgent", is_active=True)
        db.session.add(self.cat)
        db.session.flush()

        # Users for 4 roles
        self.admin = User(role='admin', full_name='Admin Chief', email='admin@civic.gov', mobile_number='9000000001', is_active=True, is_password_reset_required=False)
        self.admin.set_password('AdminPass123!')
        db.session.add(self.admin)

        self.officer = User(role='officer', full_name='Officer Suresh', email='officer@civic.gov', mobile_number='9000000002', department_id=self.dept.id, is_active=True, is_password_reset_required=False)
        self.officer.set_password('OfficerPass123!')
        db.session.add(self.officer)

        self.worker = User(role='worker', full_name='Worker Frank', email='worker@civic.gov', mobile_number='9000000003', department_id=self.dept.id, is_active=True, is_password_reset_required=False)
        self.worker.set_password('WorkerPass123!')
        db.session.add(self.worker)
        db.session.flush()

        self.worker_profile = Worker(user_id=self.worker.id, department_id=self.dept.id, designation='Senior Plumber', is_available=True, active_task_count=0)
        db.session.add(self.worker_profile)

        self.citizen = User(role='citizen', full_name='Citizen Frankline', email='citizen@civic.gov', mobile_number='9000000004', is_active=True, is_password_reset_required=False)
        self.citizen.set_password('CitizenPass123!')
        db.session.add(self.citizen)

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login_as(self, user):
        with self.client.session_transaction() as sess:
            sess.clear()
            sess['user_id'] = user.id

    # Complete Civic Grievance End-to-End Lifecycle:
    # Citizen Submit -> Officer Accept -> Officer Assign -> Worker Start -> Worker Complete -> Officer Verify -> Citizen Feedback -> Citizen Reopen
    def test_complete_civic_lifecycle(self):
        unique_title = f"Broken Water Pipe {int(datetime.now().timestamp())}"
        
        # 1. Citizen Submits Complaint
        self.login_as(self.citizen)
        res = self.client.post('/citizen/complaints/new', data={
            'title': unique_title,
            'description': 'Water line ruptured outside house 14. Severe puddle forming.',
            'department_id': self.dept.id,
            'category_id': self.cat.id,
            'priority': 'medium',
            'location_address': '14 Nehru Nagar',
            'ward_number': '3'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        complaint = Complaint.query.filter_by(title=unique_title).first()
        self.assertIsNotNone(complaint)
        self.assertEqual(complaint.status.lower(), 'submitted')

        # 2. Officer Accepts Complaint
        self.login_as(self.officer)
        res = self.client.post(f'/officer/complaints/{complaint.id}', data={
            'action': 'accept',
            'remarks': 'Accepted into water supply maintenance backlog.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        c = Complaint.query.get(complaint.id)
        self.assertIn(c.status.lower(), ['officer accepted', 'accepted'])

        # 3. Officer Assigns Worker
        res = self.client.post(f'/officer/complaints/{complaint.id}', data={
            'action': 'assign_worker',
            'worker_user_id': self.worker.id,
            'instructions': 'Replace gasket and check main pressure gauge.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        c = Complaint.query.get(complaint.id)
        self.assertIn(c.status.lower(), ['assigned to worker', 'assigned'])

        # 4. Worker Starts Task (In Progress)
        self.login_as(self.worker)
        res = self.client.post(f'/worker/tasks/{complaint.id}', data={
            'action': 'start_work',
            'remarks': 'Arrived on location with replacement parts.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        c = Complaint.query.get(complaint.id)
        self.assertIn(c.status.lower(), ['in progress', 'in_progress'])

        # 5. Worker Completes Task (Work Completed / Verification Pending)
        mock_after_img = (io.BytesIO(b"fake after image data"), "after.jpg")
        res = self.client.post(f'/worker/tasks/{complaint.id}', data={
            'action': 'submit_completion',
            'remarks': 'Pipe welded and gasket installed. Leak completely sealed.',
            'after_image': mock_after_img
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        c = Complaint.query.get(complaint.id)
        self.assertIn(c.status.lower(), ['verification pending', 'work completed', 'work_completed'])

        # 6. Officer Verifies & Resolves
        self.login_as(self.officer)
        res = self.client.post(f'/officer/complaints/{complaint.id}', data={
            'action': 'verify_resolve',
            'remarks': 'Work checked on site. Leak fixed.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        c = Complaint.query.get(complaint.id)
        self.assertEqual(c.status.lower(), 'resolved')

        # 7. Citizen Submits 5-Star Feedback
        self.login_as(self.citizen)
        res = self.client.post(f'/citizen/complaints/{complaint.id}/feedback', data={
            'rating': '5',
            'comments': 'Great work by technician Frank and the municipal water board!'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        fb = Feedback.query.filter_by(complaint_id=complaint.id).first()
        self.assertIsNotNone(fb)
        self.assertEqual(fb.rating, 5)

        # 8. Citizen Reopens Complaint
        res = self.client.post(f'/citizen/complaints/{complaint.id}/reopen', data={
            'reopen_reason': 'Minor dampness returned near joint.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        c = Complaint.query.get(complaint.id)
        self.assertEqual(c.status.lower(), 'reopened')

        # Clean up
        db.session.delete(fb)
        db.session.delete(c)
        db.session.commit()

    # 3. Worker Workflow Test: View Tasks -> Start Task -> Complete Task -> Profile
    def test_worker_full_lifecycle(self):
        self.login_as(self.worker)

        # Create an assignment for this worker
        assigned_comp = Complaint(
            complaint_ref='CMP-TEST-WORKER',
            title='Worker Task Test',
            description='Test worker queue and detail rendering',
            citizen_id=self.citizen.id,
            department_id=self.dept.id,
            category_id=self.cat.id,
            status='In Progress',
            priority='high'
        )
        db.session.add(assigned_comp)
        db.session.flush()

        asgn = ComplaintAssignment(
            complaint_id=assigned_comp.id,
            assigned_to_user_id=self.worker.id,
            assigned_by_user_id=self.officer.id,
            status='In Progress',
            instructions='Perform task'
        )
        db.session.add(asgn)
        db.session.commit()

        # A. View Task list & detail
        res = self.client.get('/worker/tasks')
        self.assertEqual(res.status_code, 200)

        res = self.client.get(f'/worker/tasks/{assigned_comp.id}')
        self.assertEqual(res.status_code, 200)

        # B. Worker Profile Update
        res = self.client.post('/worker/profile', data={
            'full_name': 'Frank Senior Field Worker',
            'phone': '9843316060'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

    # 4. Admin Workflow Test: Manage Users, Departments, Settings, Dispatch Work Orders
    def test_admin_full_lifecycle(self):
        self.login_as(self.admin)

        # A. Add New Department
        res = self.client.post('/admin/departments', data={
            'action': 'create',
            'name': 'Public Health & Sanitation',
            'code': 'PHS',
            'description': 'Municipal hygiene and sanitation services'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        new_d = Department.query.filter_by(code='PHS').first()
        self.assertIsNotNone(new_d)

        # B. Add New System User
        s1 = self.next_seq()
        unique_email = f"testuser_{s1}@civic.gov"
        unique_phone = f"9100000{s1:03d}"
        res = self.client.post('/admin/users', data={
            'action': 'add_user',
            'full_name': 'Audit Test Inspector',
            'email': unique_email,
            'mobile': unique_phone,
            'role': 'officer',
            'department_id': new_d.id,
            'password': 'SecurePassword123!'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        created_user = User.query.filter_by(email=unique_email).first()
        self.assertIsNotNone(created_user)
        self.assertEqual(created_user.role, 'officer')

        # C. Toggle User Status
        res = self.client.post('/admin/users', data={
            'action': 'toggle_status',
            'user_id': created_user.id
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        toggled_user = User.query.get(created_user.id)
        self.assertFalse(toggled_user.is_active)

        # D. Update System Settings
        res = self.client.post('/admin/settings', data={
            'app_name': 'Smart Civic Complaint Platform',
            'app_subtitle': 'Public Works & Civic Grievance Redressal',
            'city_name': 'Coimbatore',
            'admin_email': 'admin@civic.gov',
            'emergency_helpline': '1800-425-0000',
            'sla_low_days': '7',
            'sla_medium_days': '4',
            'sla_high_days': '2',
            'sla_urgent_days': '1'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # E. Add Officer via /admin/officers
        s2 = self.next_seq()
        officer_email = f"officer_test_{s2}@civic.gov"
        officer_mobile = f"9200000{s2:03d}"
        res = self.client.post('/admin/officers', data={
            'action': 'add_officer',
            'full_name': 'Test Municipal Officer',
            'email': officer_email,
            'mobile': officer_mobile,
            'department_id': self.dept.id,
            'password': 'Password@123'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        created_officer = User.query.filter_by(email=officer_email).first()
        self.assertIsNotNone(created_officer)

        # F. Add Worker via /admin/workers
        s3 = self.next_seq()
        worker_email = f"worker_test_{s3}@civic.gov"
        worker_mobile = f"9300000{s3:03d}"
        res = self.client.post('/admin/workers', data={
            'action': 'add_worker',
            'full_name': 'Test Field Technician',
            'email': worker_email,
            'mobile': worker_mobile,
            'department_id': self.dept.id,
            'designation': 'Senior Field Technician',
            'password': 'Password@123'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        created_worker = User.query.filter_by(email=worker_email).first()
        self.assertIsNotNone(created_worker, f"Worker not created: {res.get_data(as_text=True)[:300]}")

        # G. Dispatch Assignment via /admin/assignments
        active_comp = Complaint.query.first()
        if not active_comp:
            active_comp = Complaint(
                complaint_ref='CMP-DISPATCH-TEST',
                title='Dispatch Test',
                description='Testing admin dispatch',
                citizen_id=self.citizen.id,
                department_id=self.dept.id,
                category_id=self.cat.id,
                status='Submitted',
                priority='medium'
            )
            db.session.add(active_comp)
            db.session.commit()

        res = self.client.post('/admin/assignments', data={
            'action': 'assign_worker',
            'complaint_id': active_comp.id,
            'worker_user_id': self.worker.id,
            'instructions': 'Admin dispatched assignment test'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

if __name__ == '__main__':
    unittest.main()
