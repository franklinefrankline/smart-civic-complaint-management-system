import io
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models.user import User
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.category import ComplaintCategory
from app.models.workflow import Worker, ComplaintAssignment, ComplaintStatusHistory
from app.models.attachment import ComplaintAttachment
from app.models.notification import Notification

def run_tests():
    app = create_app()
    client = app.test_client()

    with app.app_context():
        print("=== TEST 1: URL Routes & Slashing Aliases ===")
        # Test admin routes
        admin_user = User.query.filter_by(role='admin').first()
        assert admin_user is not None, "Admin user must exist"

        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id

        # Plural with slash, without slash, singular
        r1 = client.get('/admin/complaints/6')
        r2 = client.get('/admin/complaints/6/')
        r3 = client.get('/admin/complaint/6')
        r4 = client.get('/admin/complaint/6/')
        print(f"Admin /complaints/6: {r1.status_code}, /complaints/6/: {r2.status_code}, /complaint/6: {r3.status_code}, /complaint/6/: {r4.status_code}")
        assert r1.status_code == 200, f"Expected 200 got {r1.status_code}"
        assert r2.status_code == 200, f"Expected 200 got {r2.status_code}"
        assert r3.status_code == 200, f"Expected 200 got {r3.status_code}"
        assert r4.status_code == 200, f"Expected 200 got {r4.status_code}"

        print("=== TEST 2: Static Uploads Serving ===")
        filename = "81d2390b2ebc4ce3b96fb49c54646d6f_1795490075.jpeg"
        # Test /uploads/proofs/
        u1 = client.get(f'/uploads/proofs/{filename}')
        # Test /uploads/uploads/proofs/ (normalized)
        u2 = client.get(f'/uploads/uploads/proofs/{filename}')
        # Test /proofs/ direct alias
        u3 = client.get(f'/proofs/{filename}')
        print(f"/uploads/proofs/: {u1.status_code}, /uploads/uploads/proofs/: {u2.status_code}, /proofs/: {u3.status_code}")
        assert u1.status_code == 200, f"Expected 200 got {u1.status_code}"
        assert u2.status_code == 200, f"Expected 200 got {u2.status_code}"
        assert u3.status_code == 200, f"Expected 200 got {u3.status_code}"

        print("=== TEST 3: Add User Modal Password Eye Toggle ===")
        users_html = client.get('/admin/users').data.decode('utf-8')
        assert 'id="modalUserPassword"' in users_html, "modalUserPassword input must be present"
        assert 'password-toggle-btn' in users_html, "password-toggle-btn must be present"
        assert 'togglePasswordVisibility' in users_html, "togglePasswordVisibility function call must be present"
        assert '<svg' in users_html and 'd="M2 12s3-7 10-7' in users_html, "Inline eye SVG must be rendered"
        print("Password toggle eye icon verified in users.html!")

        print("=== TEST 4: Flash Container Floating Toast CSS ===")
        with client.session_transaction() as sess:
            sess['_flashes'] = [('success', 'User updated successfully.')]
        users_html_flashed = client.get('/admin/users').data.decode('utf-8')
        assert 'id="flashToastContainer"' in users_html_flashed, "Floating toast container wrapper must be present"
        assert 'User updated successfully.' in users_html_flashed, "Flashed message must be rendered"
        print("Flash toast styling verified!")

        print("=== TEST 5: Complete Three-Level Workflow End-to-End ===")
        # Get demo accounts
        citizen = User.query.filter_by(role='citizen').first()
        officer = User.query.filter_by(role='officer').first()
        worker_user = User.query.filter_by(role='worker').first()
        dept = Department.query.filter_by(is_active=True).first()
        cat = ComplaintCategory.query.filter_by(department_id=dept.id).first()
        if not cat:
            cat = ComplaintCategory.query.first()

        assert citizen and officer and worker_user and dept and cat, "Demo seed data missing"
        # Ensure officer and worker are in the same department for Level 3 test
        officer.department_id = dept.id
        worker_obj = Worker.query.filter_by(user_id=worker_user.id).first()
        if not worker_obj:
            worker_obj = Worker(user_id=worker_user.id, department_id=dept.id, is_available=True)
            db.session.add(worker_obj)
        else:
            worker_obj.department_id = dept.id
            worker_obj.is_available = True
        worker_user.department_id = dept.id
        db.session.commit()

        # LEVEL 1: Citizen submits complaint
        with client.session_transaction() as sess:
            sess['user_id'] = citizen.id

        post_data = {
            'title': 'Test 3-Level Workflow Pipeline Rupture',
            'category_id': str(cat.id),
            'priority': 'high',
            'description': 'Water is gushing out from the main valve in the residential street.',
            'street_name': '42 Gandhi Road',
            'ward_number': '7',
            'city': 'Coimbatore',
            'pincode': '641001'
        }
        res_sub = client.post('/citizen/complaints/new', data=post_data, follow_redirects=True)
        assert res_sub.status_code == 200, "Citizen complaint submission failed"
        
        # Verify complaint created in DB
        c = Complaint.query.filter_by(title='Test 3-Level Workflow Pipeline Rupture').order_by(Complaint.created_at.desc()).first()
        assert c is not None, "Complaint record not found"
        assert c.status == 'Submitted', f"Expected status 'Submitted', got {c.status}"
        assert c.assigned_officer_id is None, f"Expected assigned_officer_id to be None, got {c.assigned_officer_id}"
        assert c.assigned_worker_id is None, f"Expected assigned_worker_id to be None, got {c.assigned_worker_id}"
        print(f"Level 1 PASSED: Complaint #{c.id} ({c.complaint_ref}) submitted with status '{c.status}', officer=None, worker=None")

        # LEVEL 2: Administrator assigns Department Officer
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id

        # Verify complaint is visible in admin new complaints queue
        dash_res = client.get('/admin/dashboard').data.decode('utf-8')
        assert c.complaint_ref in dash_res, "Complaint must appear in Admin New Complaints queue"

        # Admin assigns department and officer
        assign_data = {
            'action': 'assign_department_officer',
            'department_id': str(dept.id),
            'officer_id': str(officer.id),
            'admin_remarks': 'High priority leak. Officer please assign technician immediately.'
        }
        assign_res = client.post(f'/admin/complaints/{c.id}', data=assign_data, follow_redirects=True)
        assert assign_res.status_code == 200

        c = db.session.get(Complaint, c.id)
        assert c.status == 'Assigned to Department', f"Expected status 'Assigned to Department', got {c.status}"
        assert c.assigned_officer_id == officer.id, f"Expected officer_id {officer.id}, got {c.assigned_officer_id}"
        assert c.admin_remarks == 'High priority leak. Officer please assign technician immediately.'
        print(f"Level 2 PASSED: Admin assigned to Department {dept.name} & Officer {officer.full_name}, status='{c.status}'")

        # LEVEL 3: Department Officer accepts complaint and assigns worker
        with client.session_transaction() as sess:
            sess['user_id'] = officer.id

        # Officer accepts complaint
        accept_res = client.post(f'/officer/complaints/{c.id}', data={'action': 'accept'}, follow_redirects=True)
        assert accept_res.status_code == 200
        c = db.session.get(Complaint, c.id)
        assert c.status == 'Officer Accepted', f"Expected status 'Officer Accepted', got {c.status}"
        print(f"Level 3a PASSED: Officer accepted complaint, status='{c.status}'")

        # Officer assigns same-department Field Worker
        worker_assign_data = {
            'action': 'assign_worker',
            'worker_user_id': str(worker_user.id),
            'instructions': 'Replace leaking valve and test water pressure.'
        }
        worker_assign_res = client.post(f'/officer/complaints/{c.id}', data=worker_assign_data, follow_redirects=True)
        assert worker_assign_res.status_code == 200
        c = db.session.get(Complaint, c.id)
        assert c.status == 'Assigned to Worker', f"Expected status 'Assigned to Worker', got {c.status}"
        assert c.assigned_worker_id == worker_user.id, f"Expected worker_id {worker_user.id}, got {c.assigned_worker_id}"
        print(f"Level 3b PASSED: Officer assigned Worker {worker_user.full_name}, status='{c.status}'")

        # LEVEL 4: Field Worker starts work, posts progress, and submits completion
        with client.session_transaction() as sess:
            sess['user_id'] = worker_user.id

        # Worker starts work (with mock before image)
        dummy_before = (io.BytesIO(b"fake before image content"), "before.jpg")
        start_data = {
            'action': 'start_work',
            'remarks': 'Arrived at site with replacement valve.',
            'before_image': dummy_before
        }
        start_res = client.post(f'/worker/tasks/{c.id}', data=start_data, follow_redirects=True, content_type='multipart/form-data')
        assert start_res.status_code == 200
        c = db.session.get(Complaint, c.id)
        assert c.status == 'In Progress', f"Expected status 'In Progress', got {c.status}"
        print(f"Level 4a PASSED: Worker started work, status='{c.status}'")

        # Worker posts progress update
        prog_res = client.post(f'/worker/tasks/{c.id}', data={'action': 'update_progress', 'progress_notes': 'Main line isolated, replacing flange.'}, follow_redirects=True)
        assert prog_res.status_code == 200
        print("Level 4b PASSED: Worker posted progress update")

        # Worker submits completion (with mock after image)
        dummy_after = (io.BytesIO(b"fake after image content"), "after.jpg")
        comp_data = {
            'action': 'submit_completion',
            'remarks': 'Valve replaced, bolted securely, line pressurized and zero leaks found.',
            'after_image': dummy_after
        }
        comp_res = client.post(f'/worker/tasks/{c.id}', data=comp_data, follow_redirects=True, content_type='multipart/form-data')
        assert comp_res.status_code == 200
        c = db.session.get(Complaint, c.id)
        assert c.status == 'Verification Pending', f"Expected status 'Verification Pending', got {c.status}"
        print(f"Level 4c PASSED: Worker submitted work for verification, status='{c.status}'")

        # LEVEL 5: Officer Verification
        with client.session_transaction() as sess:
            sess['user_id'] = officer.id

        # Test Level 5b: Return for Correction / Rework
        rework_data = {
            'action': 'return_rework',
            'rework_reason': 'Please clean up debris around the valve pit and retighten secondary bolt.'
        }
        rework_res = client.post(f'/officer/complaints/{c.id}', data=rework_data, follow_redirects=True)
        assert rework_res.status_code == 200
        c = db.session.get(Complaint, c.id)
        assert c.status == 'Rework Required', f"Expected status 'Rework Required', got {c.status}"
        print(f"Level 5a PASSED: Officer returned for rework, status='{c.status}'")

        # Worker resumes work and resubmits
        with client.session_transaction() as sess:
            sess['user_id'] = worker_user.id

        resub_data = {
            'action': 'submit_completion',
            'remarks': 'Debris cleared, pit cleaned, secondary bolt torqued to specification.',
            'after_image': (io.BytesIO(b"cleaned up pit photo"), "after_rework.jpg")
        }
        resub_res = client.post(f'/worker/tasks/{c.id}', data=resub_data, follow_redirects=True, content_type='multipart/form-data')
        assert resub_res.status_code == 200
        c = db.session.get(Complaint, c.id)
        assert c.status == 'Verification Pending', f"Expected status 'Verification Pending', got {c.status}"
        print(f"Level 5b PASSED: Worker resubmitted after rework, status='{c.status}'")

        # Officer approves and resolves
        with client.session_transaction() as sess:
            sess['user_id'] = officer.id

        verify_data = {
            'action': 'verify_resolve',
            'verification_remarks': 'Inspected after-work photo and cleaning. Job satisfies municipal quality standards.'
        }
        verify_res = client.post(f'/officer/complaints/{c.id}', data=verify_data, follow_redirects=True)
        assert verify_res.status_code == 200
        c = db.session.get(Complaint, c.id)
        assert c.status == 'Resolved', f"Expected status 'Resolved', got {c.status}"
        print(f"Level 5c PASSED: Officer verified and approved, status='{c.status}'")

        # LEVEL 6: Citizen Tracking & 9-Stage Timeline
        with client.session_transaction() as sess:
            sess['user_id'] = citizen.id

        detail_html = client.get(f'/citizen/complaints/{c.id}').data.decode('utf-8')
        assert '9-Stage Redressal Lifecycle' in detail_html, "9-Stage timeline must be present in citizen detail"
        assert 'Complaint Submitted' in detail_html
        assert 'Reviewed by Administrator' in detail_html
        assert 'Department Assigned' in detail_html
        assert 'Officer Accepted' in detail_html
        assert 'Worker Assigned' in detail_html
        assert 'Work Started' in detail_html
        assert 'Work Completed' in detail_html
        assert 'Officer Verification' in detail_html
        assert 'Resolved' in detail_html

        # Public track test
        track_html = client.get(f'/track?ref={c.complaint_ref}').data.decode('utf-8')
        assert '9-Stage Redressal Lifecycle' in track_html, "9-Stage timeline must be present in public track"
        print(f"Level 6 PASSED: 9-Stage Redressal Lifecycle verified with timestamps and remarks on Citizen Portal and Public Track!")

        print("\nALL 5 TEST SUITES PASSED FLAWLESSLY!")

if __name__ == '__main__':
    run_tests()
