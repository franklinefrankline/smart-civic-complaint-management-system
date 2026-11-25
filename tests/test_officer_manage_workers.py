import unittest
from app import create_app, db
from app.models.user import User
from app.models.department import Department
from app.models.category import ComplaintCategory
from app.models.complaint import Complaint
from app.models.workflow import Worker


class OfficerManageWorkersTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.dept_water = Department(name='Water Supply & Sewage', code='WATER', is_active=True)
        self.dept_roads = Department(name='Roads & Infrastructure', code='ROADS', is_active=True)
        db.session.add_all([self.dept_water, self.dept_roads])
        db.session.flush()

        self.cat_water = ComplaintCategory(
            name='Water Pipe Burst',
            department_id=self.dept_water.id,
            default_priority='high',
            sla_hours=48,
            is_active=True,
        )
        self.cat_roads = ComplaintCategory(
            name='Pothole Repair',
            department_id=self.dept_roads.id,
            default_priority='medium',
            sla_hours=96,
            is_active=True,
        )
        db.session.add_all([self.cat_water, self.cat_roads])
        db.session.flush()

        self.admin = User(
            role='admin',
            full_name='Master Admin',
            email='admin@civic.gov',
            mobile_number='9000000001',
            is_active=True,
        )
        self.admin.set_password('Admin@123')

        self.citizen = User(
            role='citizen',
            full_name='Citizen Reporter',
            email='citizen@civic.gov',
            mobile_number='9000000002',
            is_active=True,
        )
        self.citizen.set_password('Citizen@123')

        # Existing worker in Roads department (must NEVER be visible/editable by Water officer)
        self.roads_worker_user = User(
            role='worker',
            full_name='Roads Technician',
            email='roads.worker@civic.gov',
            mobile_number='9000000003',
            department_id=self.dept_roads.id,
            is_active=True,
        )
        self.roads_worker_user.set_password('Worker@123')

        db.session.add_all([self.admin, self.citizen, self.roads_worker_user])
        db.session.flush()

        self.roads_worker = Worker(
            user_id=self.roads_worker_user.id,
            department_id=self.dept_roads.id,
            employee_id='EMP-RDS-001',
            designation='Road Crew Lead',
            is_available=True,
        )
        db.session.add(self.roads_worker)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_end_to_end_officer_worker_creation_and_rbac(self):
        ajax_headers = {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}

        # 1. Administrator creates a Department Officer for Water Supply & Sewage
        admin_client = self.app.test_client()
        login_admin = admin_client.post(
            '/auth/login',
            data={'login_id': 'admin@civic.gov', 'password': 'Admin@123'},
            follow_redirects=True,
        )
        self.assertEqual(login_admin.status_code, 200)

        create_off = admin_client.post(
            '/admin/officers',
            data={
                'action': 'add_officer',
                'full_name': 'Water Officer One',
                'email': 'water.officer@civic.gov',
                'mobile': '9123456780',
                'department_id': self.dept_water.id,
                'password': 'Officer@123',
            },
            headers=ajax_headers,
        )
        self.assertEqual(create_off.status_code, 200)
        self.assertTrue(create_off.get_json()['success'])

        officer_user = User.query.filter_by(email='water.officer@civic.gov').first()
        self.assertIsNotNone(officer_user)
        # Clear initial reset requirement as officer completes activation or login flow
        officer_user.is_password_reset_required = False
        db.session.commit()

        # 2. Department Officer logs in
        officer_client = self.app.test_client()
        res_off_login = officer_client.post(
            '/auth/login',
            data={'login_id': 'water.officer@civic.gov', 'password': 'Officer@123'},
            follow_redirects=True,
        )
        self.assertEqual(res_off_login.status_code, 200)
        self.assertIn(b'Manage Workers', res_off_login.data)

        # 3. Officer opens Manage Workers page -> sees own dept, does NOT see Roads worker
        res_mw = officer_client.get('/officer/workers')
        self.assertEqual(res_mw.status_code, 200)
        html_mw = res_mw.get_data(as_text=True)
        self.assertIn('Manage Workers', html_mw)
        self.assertIn('Water Supply &amp; Sewage', html_mw)
        self.assertIn('readonly', html_mw)
        self.assertNotIn('Roads Technician', html_mw)
        self.assertNotIn('EMP-RDS-001', html_mw)

        # 4. Officer creates a new Field Worker
        res_add = officer_client.post(
            '/officer/workers',
            data={
                'action': 'add_worker',
                'full_name': 'Suresh Water Tech',
                'email': 'suresh.water@civic.gov',
                'mobile': '9876501234',
                'employee_id': 'EMP-WTR-101',
                'designation': 'Pipeline Specialist',
                'password': 'WorkerPass@123',
                'account_status': 'active',
            },
            headers=ajax_headers,
        )
        self.assertEqual(res_add.status_code, 200)
        add_json = res_add.get_json()
        self.assertTrue(add_json['success'])

        # Duplicate email and duplicate Employee ID must be rejected cleanly
        res_dup_email = officer_client.post(
            '/officer/workers',
            data={
                'action': 'add_worker',
                'full_name': 'Duplicate Email',
                'email': 'suresh.water@civic.gov',
                'mobile': '9876501999',
                'employee_id': 'EMP-WTR-102',
                'password': 'WorkerPass@123',
            },
            headers=ajax_headers,
        )
        self.assertEqual(res_dup_email.status_code, 400)
        self.assertFalse(res_dup_email.get_json()['success'])

        res_dup_emp = officer_client.post(
            '/officer/workers',
            data={
                'action': 'add_worker',
                'full_name': 'Duplicate EmpID',
                'email': 'other.water@civic.gov',
                'mobile': '9876501888',
                'employee_id': 'emp-wtr-101',
                'password': 'WorkerPass@123',
            },
            headers=ajax_headers,
        )
        self.assertEqual(res_dup_emp.status_code, 400)
        self.assertIn('Employee ID', res_dup_emp.get_json()['message'])

        # 5. Verify worker saved in DB with hashed password & officer's department
        worker_user = User.query.filter_by(email='suresh.water@civic.gov').first()
        self.assertIsNotNone(worker_user)
        self.assertEqual(worker_user.role, 'worker')
        self.assertEqual(worker_user.department_id, self.dept_water.id)
        self.assertNotEqual(worker_user.password_hash, 'WorkerPass@123')
        self.assertTrue(worker_user.check_password('WorkerPass@123'))
        self.assertIsNotNone(worker_user.worker_profile)
        self.assertEqual(worker_user.worker_profile.employee_id, 'EMP-WTR-101')
        self.assertEqual(worker_user.worker_profile.department_id, self.dept_water.id)

        # Create two complaints: one assigned to Suresh, one unassigned/other worker
        c_assigned = Complaint(
            complaint_ref='CMP-202611-WTR01',
            citizen_id=self.citizen.id,
            category_id=self.cat_water.id,
            department_id=self.dept_water.id,
            title='Broken Valve Street 5',
            description='Main supply valve leaking heavily near block A.',
            priority='high',
            status='Assigned to Department',
            assigned_officer_id=officer_user.id,
        )
        c_unassigned = Complaint(
            complaint_ref='CMP-202611-WTR02',
            citizen_id=self.citizen.id,
            category_id=self.cat_water.id,
            department_id=self.dept_water.id,
            title='Other Street Pressure Drop',
            description='Unassigned complaint that worker must NOT see.',
            priority='medium',
            status='Assigned to Department',
            assigned_officer_id=officer_user.id,
        )
        db.session.add_all([c_assigned, c_unassigned])
        db.session.commit()

        # Officer assigns c_assigned to Suresh directly from Manage Workers
        res_assign = officer_client.post(
            '/officer/workers',
            data={
                'action': 'assign_complaint',
                'worker_id': worker_user.worker_profile.id,
                'complaint_id': c_assigned.id,
                'instructions': 'Inspect valve seal immediately.',
            },
            headers=ajax_headers,
        )
        self.assertEqual(res_assign.status_code, 200)
        self.assertTrue(res_assign.get_json()['success'])

        # 6 & 7. New worker logs in and sees ONLY their assigned task and correct department
        worker_client = self.app.test_client()
        res_wrk_login = worker_client.post(
            '/auth/login',
            data={'login_id': 'suresh.water@civic.gov', 'password': 'WorkerPass@123'},
            follow_redirects=False,
        )
        self.assertEqual(res_wrk_login.status_code, 302)
        self.assertIn('/worker/dashboard', res_wrk_login.headers['Location'])

        res_wrk_dash = worker_client.get('/worker/dashboard')
        self.assertEqual(res_wrk_dash.status_code, 200)
        dash_html = res_wrk_dash.get_data(as_text=True)
        self.assertIn('Water Supply &amp; Sewage', dash_html)
        self.assertIn('EMP-WTR-101', dash_html)
        self.assertIn('Broken Valve Street 5', dash_html)
        self.assertNotIn('Other Street Pressure Drop', dash_html)

        # Worker must NOT get Officer or Admin permissions
        self.assertEqual(worker_client.get('/officer/workers', headers=ajax_headers).status_code, 403)
        self.assertEqual(worker_client.get('/admin/users', headers=ajax_headers).status_code, 403)
        # Worker cannot open unassigned task detail
        res_other_task = worker_client.get(f'/worker/tasks/{c_unassigned.id}', follow_redirects=False)
        self.assertEqual(res_other_task.status_code, 302)

        # 8. Officer CANNOT create an Administrator or Officer account (tampered role rejected 403)
        for forbidden_role in ('admin', 'officer'):
            res_priv = officer_client.post(
                '/officer/workers',
                data={
                    'action': 'add_worker',
                    'role': forbidden_role,
                    'full_name': f'Forged {forbidden_role}',
                    'email': f'forged.{forbidden_role}@civic.gov',
                    'mobile': '9988776655',
                    'employee_id': f'EMP-BAD-{forbidden_role}',
                    'password': 'Password@123',
                },
                headers=ajax_headers,
            )
            self.assertEqual(res_priv.status_code, 403)
            self.assertIsNone(User.query.filter_by(email=f'forged.{forbidden_role}@civic.gov').first())

        # 9. Officer CANNOT create a worker in another department or modify another department's worker
        res_cross_dept = officer_client.post(
            '/officer/workers',
            data={
                'action': 'add_worker',
                'department_id': self.dept_roads.id,
                'full_name': 'Cross Dept Worker',
                'email': 'cross.dept@civic.gov',
                'mobile': '9988776644',
                'employee_id': 'EMP-CROSS-1',
                'password': 'Password@123',
            },
            headers=ajax_headers,
        )
        self.assertEqual(res_cross_dept.status_code, 403)
        self.assertIsNone(User.query.filter_by(email='cross.dept@civic.gov').first())

        res_cross_edit = officer_client.post(
            '/officer/workers',
            data={
                'action': 'edit_worker',
                'worker_id': self.roads_worker.id,
                'full_name': 'Hacked Roads Tech',
                'email': 'roads.worker@civic.gov',
                'mobile': '9000000003',
                'employee_id': 'EMP-RDS-001',
            },
            headers=ajax_headers,
        )
        self.assertEqual(res_cross_edit.status_code, 403)
        res_cross_toggle = officer_client.post(
            '/officer/workers',
            data={'action': 'toggle_status', 'worker_id': self.roads_worker.id},
            headers=ajax_headers,
        )
        self.assertEqual(res_cross_toggle.status_code, 403)

        # Officer CAN edit and toggle own department's worker
        res_edit_ok = officer_client.post(
            '/officer/workers',
            data={
                'action': 'edit_worker',
                'worker_id': worker_user.worker_profile.id,
                'full_name': 'Suresh Water Senior Tech',
                'email': 'suresh.water@civic.gov',
                'mobile': '9876501234',
                'employee_id': 'EMP-WTR-101',
                'designation': 'Senior Pipeline Specialist',
                'account_status': 'active',
                'is_available': '1',
            },
            headers=ajax_headers,
        )
        self.assertEqual(res_edit_ok.status_code, 200)
        db.session.refresh(worker_user)
        self.assertEqual(worker_user.full_name, 'Suresh Water Senior Tech')

        res_deactivate = officer_client.post(
            '/officer/workers',
            data={'action': 'toggle_status', 'worker_id': worker_user.worker_profile.id},
            headers=ajax_headers,
        )
        self.assertEqual(res_deactivate.status_code, 200)
        db.session.refresh(worker_user)
        self.assertFalse(worker_user.is_active)

        # 10. Administrator can still manage all users across all departments
        res_admin_users = admin_client.get('/admin/users')
        self.assertEqual(res_admin_users.status_code, 200)
        users_html = res_admin_users.get_data(as_text=True)
        self.assertIn('Suresh Water Senior Tech', users_html)
        self.assertIn('Roads Technician', users_html)
        self.assertIn('Water Officer One', users_html)

        res_admin_reactivate = admin_client.post(
            '/admin/users',
            data={'action': 'toggle_status', 'user_id': worker_user.id},
            headers=ajax_headers,
        )
        self.assertEqual(res_admin_reactivate.status_code, 200)
        db.session.refresh(worker_user)
        self.assertTrue(worker_user.is_active)


if __name__ == '__main__':
    unittest.main()
