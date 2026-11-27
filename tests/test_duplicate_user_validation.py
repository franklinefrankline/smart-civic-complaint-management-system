import unittest
from sqlalchemy.exc import IntegrityError
from app import create_app, db
from app.models.department import Department
from app.models.user import User
from app.models.workflow import Worker
from app.services.user_service import (
    DUP_BOTH_MSG,
    DUP_BOTH_TITLE,
    DUP_EMAIL_MSG,
    DUP_EMAIL_TITLE,
    DUP_MOBILE_MSG,
    DUP_MOBILE_TITLE,
    resolve_duplicate_integrity_error,
)


class DuplicateUserValidationAllFormsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.dept = Department(name='Water Works', code='WATER_DUP', is_active=True)
        db.session.add(self.dept)
        db.session.flush()

        self.admin = User(
            role='admin',
            full_name='Dup Admin',
            email='dup.admin@civic.gov',
            mobile_number='9855555501',
            is_active=True,
        )
        self.admin.set_password('Admin@123')

        self.officer = User(
            role='officer',
            department_id=self.dept.id,
            full_name='Dup Officer',
            email='dup.officer@civic.gov',
            mobile_number='9855555502',
            is_active=True,
        )
        self.officer.set_password('Officer@123')

        self.existing_user = User(
            role='citizen',
            full_name='Existing User',
            email='existing.person@civic.gov',
            mobile_number='9855555599',
            is_active=True,
        )
        self.existing_user.set_password('Citizen@123')

        db.session.add_all([self.admin, self.officer, self.existing_user])
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.ctx.pop()

    def _login(self, client, email, password):
        res = client.post('/auth/login', data={'login_id': email, 'password': password}, follow_redirects=False)
        self.assertIn(res.status_code, (200, 302))

    def _assert_duplicate_matrix(self, client, url, extra_fields, unique_email, unique_mobile):
        # 1. Duplicate email (mixed case + surrounding spaces)
        r_email = client.post(
            url,
            data={**extra_fields, 'email': '  EXISTING.Person@Civic.Gov ', 'mobile': unique_mobile},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(r_email.status_code, 400)
        d_email = r_email.get_json()
        self.assertFalse(d_email['success'])
        self.assertEqual(d_email['field'], 'email')
        self.assertEqual(d_email['title'], DUP_EMAIL_TITLE)
        self.assertEqual(d_email['message'], DUP_EMAIL_MSG)

        # 2. Duplicate phone (with dashes/spaces normalization)
        r_mobile = client.post(
            url,
            data={**extra_fields, 'email': unique_email, 'mobile': '98555-555 99'},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(r_mobile.status_code, 400)
        d_mobile = r_mobile.get_json()
        self.assertFalse(d_mobile['success'])
        self.assertEqual(d_mobile['field'], 'mobile')
        self.assertEqual(d_mobile['title'], DUP_MOBILE_TITLE)
        self.assertEqual(d_mobile['message'], DUP_MOBILE_MSG)

        # 3. Both duplicate
        r_both = client.post(
            url,
            data={**extra_fields, 'email': 'EXISTING.PERSON@CIVIC.GOV', 'mobile': '9855555599'},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(r_both.status_code, 400)
        d_both = r_both.get_json()
        self.assertFalse(d_both['success'])
        self.assertEqual(d_both['field'], 'both')
        self.assertEqual(d_both['title'], DUP_BOTH_TITLE)
        self.assertEqual(d_both['message'], DUP_BOTH_MSG)

    def test_admin_officers_workers_users_and_officer_workers_duplicate_checks(self):
        a_client = self.app.test_client()
        self._login(a_client, 'dup.admin@civic.gov', 'Admin@123')

        # Admin -> Add Officer
        self._assert_duplicate_matrix(
            a_client,
            '/admin/officers',
            {'action': 'add_officer', 'full_name': 'New Officer', 'department_id': self.dept.id, 'password': 'Password@123'},
            unique_email='brand.new.officer@civic.gov',
            unique_mobile='9855500001',
        )
        ok_off = a_client.post(
            '/admin/officers',
            data={
                'action': 'add_officer',
                'full_name': 'Brand New Officer',
                'email': '  Brand.New.Officer@Civic.Gov ',
                'mobile': '98555-00001',
                'department_id': self.dept.id,
                'password': 'Password@123',
            },
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(ok_off.status_code, 200)
        self.assertTrue(ok_off.get_json()['success'])
        self.assertIsNotNone(User.query.filter_by(email='brand.new.officer@civic.gov', mobile_number='9855500001').first())

        # Admin -> Add Worker
        self._assert_duplicate_matrix(
            a_client,
            '/admin/workers',
            {'action': 'add_worker', 'full_name': 'New Worker', 'department_id': self.dept.id, 'password': 'Password@123'},
            unique_email='brand.new.worker@civic.gov',
            unique_mobile='9855500002',
        )
        ok_wrk = a_client.post(
            '/admin/workers',
            data={
                'action': 'add_worker',
                'full_name': 'Brand New Worker',
                'email': 'brand.new.worker@civic.gov',
                'mobile': '9855500002',
                'department_id': self.dept.id,
                'password': 'Password@123',
            },
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(ok_wrk.status_code, 200)
        self.assertIsNotNone(User.query.filter_by(email='brand.new.worker@civic.gov').first())

        # Admin -> Add Citizen via /admin/users (and non-AJAX modal preservation check)
        self._assert_duplicate_matrix(
            a_client,
            '/admin/users',
            {'action': 'add_user', 'full_name': 'New Citizen', 'role': 'citizen', 'password': 'Password@123'},
            unique_email='brand.new.citizen@civic.gov',
            unique_mobile='9855500003',
        )
        non_ajax_off = a_client.post(
            '/admin/officers',
            data={
                'action': 'add_officer',
                'full_name': 'Preserved Officer Name',
                'email': 'existing.person@civic.gov',
                'mobile': '9855500099',
                'department_id': self.dept.id,
                'password': 'Password@123',
            },
        )
        html_off = non_ajax_off.get_data(as_text=True)
        self.assertEqual(non_ajax_off.status_code, 200)
        self.assertIn('Preserved Officer Name', html_off)
        self.assertIn(DUP_EMAIL_MSG, html_off)

        # Admin -> Duplicate Department name/code & missing Dispatch checks
        dup_dept_res = a_client.post(
            '/admin/departments',
            data={'action': 'create', 'name': 'Water Works', 'code': 'WATER_DUP'},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(dup_dept_res.status_code, 400)
        dup_dept_data = dup_dept_res.get_json()
        self.assertFalse(dup_dept_data['success'])
        self.assertEqual(dup_dept_data['field'], 'dept_both')
        self.assertIn('title', dup_dept_data)

        bad_dispatch_res = a_client.post(
            '/admin/assignments',
            data={'action': 'assign_worker', 'complaint_id': '', 'worker_user_id': ''},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(bad_dispatch_res.status_code, 400)
        bad_dispatch_data = bad_dispatch_res.get_json()
        self.assertFalse(bad_dispatch_data['success'])
        self.assertEqual(bad_dispatch_data['field'], 'complaint_id')
        self.assertIn('title', bad_dispatch_data)

        # Department Officer -> Add Worker + Inactive worker edit/reactivate check
        o_client = self.app.test_client()
        self._login(o_client, 'dup.officer@civic.gov', 'Officer@123')

        self._assert_duplicate_matrix(
            o_client,
            '/officer/workers',
            {
                'action': 'add_worker',
                'full_name': 'Dept Tech',
                'employee_id': 'EMP-DUP-1',
                'designation': 'Technician',
                'password': 'Password@123',
            },
            unique_email='dept.tech.new@civic.gov',
            unique_mobile='9855500004',
        )
        ok_dept_w = o_client.post(
            '/officer/workers',
            data={
                'action': 'add_worker',
                'full_name': 'Dept Tech Inactive',
                'email': 'dept.tech.new@civic.gov',
                'mobile': '9855500004',
                'employee_id': 'EMP-DUP-1',
                'account_status': 'inactive',
                'password': 'Password@123',
            },
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(ok_dept_w.status_code, 200)
        created_worker = Worker.query.filter_by(employee_id='EMP-DUP-1').first()
        self.assertIsNotNone(created_worker)

        # Officer CAN reactivate / toggle status of an inactive worker
        toggle_res = o_client.post(
            '/officer/workers',
            data={'action': 'toggle_status', 'worker_id': created_worker.id},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(toggle_res.status_code, 200)
        self.assertTrue(toggle_res.get_json()['is_active'])

    def test_public_registration_and_integrity_error_race_recovery(self):
        p_client = self.app.test_client()
        self._assert_duplicate_matrix(
            p_client,
            '/auth/register',
            {'full_name': 'Ajax Citizen', 'password': 'Password123', 'confirm_password': 'Password123'},
            unique_email='unique.citizen.ajax@civic.gov',
            unique_mobile='9855500077',
        )

        res_dup = p_client.post('/auth/register', data={
            'full_name': 'Race Citizen',
            'email': 'EXISTING.PERSON@CIVIC.GOV',
            'mobile': '9855555599',
            'password': 'Password123',
            'confirm_password': 'Password123',
        })
        self.assertEqual(res_dup.status_code, 200)
        html_reg = res_dup.get_data(as_text=True)
        self.assertIn(DUP_BOTH_TITLE, html_reg)
        self.assertIn(DUP_BOTH_MSG, html_reg)
        self.assertIn('scfPersistentAlertModal', html_reg)

        # IntegrityError concurrent submission mapping helper
        msg, field = resolve_duplicate_integrity_error(
            IntegrityError('INSERT', {}, Exception('UNIQUE constraint failed: users.email')),
            'existing.person@civic.gov',
            '9899999999',
        )
        self.assertEqual(field, 'email')
        self.assertEqual(msg, DUP_EMAIL_MSG)


if __name__ == '__main__':
    unittest.main()
