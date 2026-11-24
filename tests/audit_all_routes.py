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


def run_audit():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    results = []
    
    with app.app_context():
        # Retrieve or verify test users
        admin = User.query.filter_by(role='admin').first()
        officer = User.query.filter_by(role='officer').first()
        worker_user = User.query.filter_by(role='worker').first()
        citizen = User.query.filter_by(role='citizen').first()
        
        dept = Department.query.first()
        cat = ComplaintCategory.query.first()
        complaint = Complaint.query.first()
        complaint_id = complaint.id if complaint else 1
        complaint_ref = complaint.complaint_ref if complaint else 'CMP-TEST'
        
        print(f"Loaded Context: Admin={admin.email if admin else None}, Officer={officer.email if officer else None}, Worker={worker_user.email if worker_user else None}, Citizen={citizen.email if citizen else None}")
        print(f"Complaint ID={complaint_id}, Ref={complaint_ref}, Dept ID={dept.id if dept else None}")
        
        client = app.test_client()
        
        def test_endpoint(name, url, method='GET', data=None, user=None, expected_status=[200, 302]):
            try:
                with client.session_transaction() as sess:
                    sess.clear()
                    if user:
                        sess['user_id'] = user.id
                
                if method == 'GET':
                    res = client.get(url, follow_redirects=False)
                elif method == 'POST':
                    res = client.post(url, data=data or {}, follow_redirects=False)
                
                status_ok = res.status_code in expected_status
                results.append({
                    'name': name,
                    'url': url,
                    'method': method,
                    'user': user.role if user else 'anonymous',
                    'status': res.status_code,
                    'ok': status_ok,
                    'redirect': res.headers.get('Location') if res.status_code in [301, 302] else None,
                    'error': None
                })
            except Exception as e:
                import traceback
                results.append({
                    'name': name,
                    'url': url,
                    'method': method,
                    'user': user.role if user else 'anonymous',
                    'status': 'EXCEPTION',
                    'ok': False,
                    'redirect': None,
                    'error': f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
                })

        # --- 1. PUBLIC ROUTES ---
        test_endpoint('Public Home', '/')
        test_endpoint('Public About', '/about')
        test_endpoint('Public Departments', '/departments')
        test_endpoint('Public How It Works', '/how-it-works')
        test_endpoint('Public Contact (GET)', '/contact')
        test_endpoint('Public Contact (POST)', '/contact', method='POST', data={
            'name': 'Audit Tester',
            'email': 'tester@example.com',
            'subject': 'Test Subject',
            'message': 'This is an audit test message.'
        }, expected_status=[200, 302])
        test_endpoint('Public Cookies', '/cookies')
        test_endpoint('Public Privacy', '/privacy')
        test_endpoint('Public Terms', '/terms')
        test_endpoint('Public Track (GET)', '/track')
        test_endpoint('Public Track (POST valid ref)', '/track', method='POST', data={'complaint_ref': complaint_ref})
        test_endpoint('Public Set Language', '/set-language/en', expected_status=[302])

        # --- 2. AUTH ROUTES ---
        test_endpoint('Auth Login (GET)', '/auth/login')
        test_endpoint('Auth Login (POST invalid)', '/auth/login', method='POST', data={'login': 'bad@example.com', 'password': 'bad'}, expected_status=[200, 302])
        test_endpoint('Auth Register (GET)', '/auth/register')
        test_endpoint('Auth Forgot Password (GET)', '/auth/forgot-password')
        test_endpoint('Auth Logout', '/auth/logout', user=citizen, expected_status=[302])
        test_endpoint('Auth Force Reset (GET without session)', '/auth/force-reset-password', expected_status=[302])

        # --- 3. CITIZEN ROUTES ---
        test_endpoint('Citizen Dashboard', '/citizen/dashboard', user=citizen)
        test_endpoint('Citizen Complaints List', '/citizen/complaints', user=citizen)
        test_endpoint('Citizen New Complaint (GET)', '/citizen/complaints/new', user=citizen)
        test_endpoint('Citizen Complaint Detail', f'/citizen/complaints/{complaint_id}', user=citizen)
        test_endpoint('Citizen Feedback', '/citizen/feedback', user=citizen)
        test_endpoint('Citizen Notifications', '/citizen/notifications', user=citizen)
        test_endpoint('Citizen Profile (GET)', '/citizen/profile', user=citizen)

        # --- 4. OFFICER ROUTES ---
        test_endpoint('Officer Dashboard', '/officer/dashboard', user=officer)
        test_endpoint('Officer Complaints List', '/officer/complaints', user=officer)
        test_endpoint('Officer Complaint Detail', f'/officer/complaints/{complaint_id}', user=officer)
        test_endpoint('Officer Incoming', '/officer/incoming', user=officer)
        test_endpoint('Officer Escalations', '/officer/escalations', user=officer)
        test_endpoint('Officer Verification', '/officer/verification', user=officer)
        test_endpoint('Officer Workers', '/officer/workers', user=officer)
        test_endpoint('Officer Reports', '/officer/reports', user=officer)
        test_endpoint('Officer Notifications', '/officer/notifications', user=officer)
        test_endpoint('Officer Profile (GET)', '/officer/profile', user=officer)

        # --- 5. WORKER ROUTES ---
        test_endpoint('Worker Dashboard', '/worker/dashboard', user=worker_user)
        test_endpoint('Worker Tasks List', '/worker/tasks', user=worker_user)
        test_endpoint('Worker Task Detail', f'/worker/tasks/{complaint_id}', user=worker_user, expected_status=[200, 302])
        test_endpoint('Worker History', '/worker/history', user=worker_user)
        test_endpoint('Worker Notifications', '/worker/notifications', user=worker_user)
        test_endpoint('Worker Profile (GET)', '/worker/profile', user=worker_user)

        # --- 6. ADMIN ROUTES ---
        test_endpoint('Admin Dashboard', '/admin/dashboard', user=admin)
        test_endpoint('Admin Complaints List', '/admin/complaints', user=admin)
        test_endpoint('Admin Complaint Detail', f'/admin/complaints/{complaint_id}', user=admin)
        test_endpoint('Admin Citizens List', '/admin/citizens', user=admin)
        test_endpoint('Admin Departments List', '/admin/departments', user=admin)
        test_endpoint('Admin Officers List', '/admin/officers', user=admin)
        test_endpoint('Admin Workers List', '/admin/workers', user=admin)
        test_endpoint('Admin Assignments List', '/admin/assignments', user=admin)
        test_endpoint('Admin Users List', '/admin/users', user=admin)
        test_endpoint('Admin Analytics', '/admin/analytics', user=admin)
        test_endpoint('Admin Audit Logs', '/admin/audit-logs', user=admin)
        test_endpoint('Admin Notifications', '/admin/notifications', user=admin)
        test_endpoint('Admin Settings', '/admin/settings', user=admin)
        test_endpoint('Admin Export Complaints CSV', '/admin/export/complaints', user=admin)

        # --- 7. API ROUTES ---
        test_endpoint('API Stats Summary', '/api/stats/summary')
        test_endpoint('API Complaint Locations', '/api/complaints/locations')
        test_endpoint('API Notifications (logged in)', '/api/notifications', user=citizen)
        test_endpoint('API SLA Check (admin)', '/api/sla/check', method='POST', user=admin, expected_status=[200, 302])
        if cat:
            test_endpoint('API Dept by Category', f'/api/departments/by-category/{cat.id}')
        test_endpoint('API Check Duplicate', '/api/complaints/check-duplicate', method='POST', data={
            'title': 'Test Leaking Pipe',
            'department_id': dept.id if dept else 1,
            'category_id': cat.id if cat else 1
        })

    # Output report
    passed = 0
    failed = 0
    print("\n" + "="*80)
    print(f"{'ENDPOINT NAME':<35} {'URL':<35} {'ROLE':<10} {'STATUS':<8} {'RESULT'}")
    print("="*80)
    for r in results:
        status_str = str(r['status'])
        res_str = "PASS" if r['ok'] else "FAIL"
        if r['ok']:
            passed += 1
        else:
            failed += 1
        print(f"{r['name']:<35} {r['url']:<35} {r['user']:<10} {status_str:<8} {res_str}")
        if not r['ok']:
            print(f"   --> REDIRECT: {r['redirect']}")
            if r['error']:
                print(f"   --> ERROR:\n{r['error']}")
    
    print("="*80)
    print(f"Total Tested: {len(results)} | Passed: {passed} | Failed: {failed}")
    print("="*80)
    return failed

if __name__ == '__main__':
    failed_count = run_audit()
    sys.exit(1 if failed_count > 0 else 0)
