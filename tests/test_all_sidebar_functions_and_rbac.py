from datetime import datetime, timedelta
import io
import unittest
from app import create_app, db
from app.models.attachment import ComplaintAttachment
from app.models.category import ComplaintCategory
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.notification import Notification
from app.models.user import User
from app.models.workflow import ComplaintAssignment, ComplaintStatusHistory, Worker


class AllSidebarFunctionsAndRBACTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.dept = Department(name='Public Health & Vector Control', code='HEALTH_ALL', is_active=True)
        self.other_dept = Department(name='Road Works', code='ROADS_ALL', is_active=True)
        db.session.add_all([self.dept, self.other_dept])
        db.session.flush()

        self.cat = ComplaintCategory(
            name='Mosquito Hazard',
            department_id=self.dept.id,
            default_priority='high',
            sla_hours=24,
            is_active=True,
        )
        self.other_cat = ComplaintCategory(
            name='Broken Curb',
            department_id=self.other_dept.id,
            default_priority='medium',
            sla_hours=48,
            is_active=True,
        )
        db.session.add_all([self.cat, self.other_cat])
        db.session.flush()

        self.admin = User(role='admin', full_name='Portal Admin', email='all.admin@civic.gov', mobile_number='9844444401', is_active=True)
        self.admin.set_password('Admin@123')

        self.officer = User(role='officer', department_id=self.dept.id, full_name='Health Officer', email='all.officer@civic.gov', mobile_number='9844444402', is_active=True)
        self.officer.set_password('Officer@123')

        self.other_officer = User(role='officer', department_id=self.other_dept.id, full_name='Roads Officer', email='all.other.officer@civic.gov', mobile_number='9844444403', is_active=True)
        self.other_officer.set_password('Officer@123')

        self.worker_user = User(role='worker', department_id=self.dept.id, full_name='Freaky Worker', email='all.worker@civic.gov', mobile_number='9844444404', is_active=True)
        self.worker_user.set_password('Worker@123')

        self.inactive_worker_user = User(role='worker', department_id=self.dept.id, full_name='Inactive Worker', email='all.inactive.w@civic.gov', mobile_number='9844444405', is_active=False)
        self.inactive_worker_user.set_password('Worker@123')

        self.other_worker_user = User(role='worker', department_id=self.other_dept.id, full_name='Other Dept Worker', email='all.other.w@civic.gov', mobile_number='9844444406', is_active=True)
        self.other_worker_user.set_password('Worker@123')

        self.citizen = User(role='citizen', full_name='Meera Citizen', email='all.citizen@civic.gov', mobile_number='9844444407', city='Chennai', ward_number='12', is_active=True)
        self.citizen.set_password('Citizen@123')

        self.other_citizen = User(role='citizen', full_name='Other Citizen', email='all.other.c@civic.gov', mobile_number='9844444408', city='Chennai', ward_number='14', is_active=True)
        self.other_citizen.set_password('Citizen@123')

        db.session.add_all([
            self.admin, self.officer, self.other_officer,
            self.worker_user, self.inactive_worker_user, self.other_worker_user,
            self.citizen, self.other_citizen,
        ])
        db.session.flush()

        self.worker_profile = Worker(user_id=self.worker_user.id, department_id=self.dept.id, employee_id='EMP-HL-01', designation='Field Inspector', is_available=True)
        self.inactive_worker_profile = Worker(user_id=self.inactive_worker_user.id, department_id=self.dept.id, employee_id='EMP-HL-02', designation='Technician', is_available=True)
        self.other_worker_profile = Worker(user_id=self.other_worker_user.id, department_id=self.other_dept.id, employee_id='EMP-RD-01', designation='Road Crew', is_available=True)
        db.session.add_all([self.worker_profile, self.inactive_worker_profile, self.other_worker_profile])
        db.session.flush()

        self.c_unassigned = Complaint(
            complaint_ref='CMP-ALL-101',
            citizen_id=self.citizen.id,
            department_id=self.dept.id,
            category_id=self.cat.id,
            assigned_officer_id=self.officer.id,
            title='Stagnant water behind Market Lane',
            description='Mosquito breeding hotspot near drainage culvert.',
            priority='high',
            address='12 Market Lane',
            ward_number='12',
            city='Chennai',
            status='Assigned to Department',
            sla_due_date=datetime.utcnow() - timedelta(hours=2),
        )
        self.c_other = Complaint(
            complaint_ref='CMP-ALL-999',
            citizen_id=self.other_citizen.id,
            department_id=self.other_dept.id,
            category_id=self.other_cat.id,
            assigned_officer_id=self.other_officer.id,
            assigned_worker_id=self.other_worker_user.id,
            title='Curb stone broken',
            description='Roads curb repair needed.',
            priority='low',
            status='Assigned to Worker',
        )
        db.session.add_all([self.c_unassigned, self.c_other])
        db.session.flush()

        db.session.add(ComplaintAssignment(
            complaint_id=self.c_other.id,
            assigned_to_user_id=self.other_worker_user.id,
            assigned_by_user_id=self.other_officer.id,
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
        res = client.post('/auth/login', data={'login_id': email, 'password': password}, follow_redirects=False)
        self.assertIn(res.status_code, (200, 302))

    def test_all_sidebar_routes_render_and_worker_officer_workflows_persist(self):
        # 1. Worker empty states first (including /worker/task?status=Work+Completed screenshot URL)
        w_client = self.app.test_client()
        self._login(w_client, 'all.worker@civic.gov', 'Worker@123')

        for path in [
            '/worker/dashboard',
            '/worker/tasks?status=Assigned',
            '/worker/tasks?status=In+Progress',
            '/worker/task?status=Work+Completed',
            '/worker/history',
            '/worker/notifications',
            '/worker/profile',
        ]:
            resp = w_client.get(path)
            self.assertEqual(resp.status_code, 200, f"Worker route {path} failed")

        empty_completed = w_client.get('/worker/task?status=Work+Completed').get_data(as_text=True)
        self.assertIn('No tasks available at the moment.', empty_completed)
        empty_history = w_client.get('/worker/history').get_data(as_text=True)
        self.assertIn('No task history records found.', empty_history)

        # Worker RBAC checks
        self.assertEqual(w_client.get('/admin/dashboard', follow_redirects=False).status_code, 302)
        self.assertEqual(w_client.get('/officer/assignments', follow_redirects=False).status_code, 302)
        # Worker cannot view another worker's task
        other_task_res = w_client.get(f'/worker/task/{self.c_other.id}', follow_redirects=False)
        self.assertEqual(other_task_res.status_code, 302)

        # 2. Officer Worker Assignments & RBAC enforcement
        o_client = self.app.test_client()
        self._login(o_client, 'all.officer@civic.gov', 'Officer@123')

        for path in [
            '/officer/dashboard',
            '/officer/incoming',
            '/officer/complaints',
            '/officer/workers',
            '/officer/assignments',
            '/officer/verification',
            '/officer/escalations',
            '/officer/reports',
            '/officer/notifications',
            '/officer/profile',
        ]:
            resp = o_client.get(path)
            self.assertEqual(resp.status_code, 200, f"Officer route {path} failed")

        assign_page = o_client.get('/officer/assignments').get_data(as_text=True)
        self.assertIn('Freaky Worker', assign_page)
        self.assertIn('Inactive Worker', assign_page)
        self.assertNotIn('Other Dept Worker', assign_page)

        # Officer CANNOT assign to inactive worker or another department's worker
        bad_inactive = o_client.post(
            '/officer/assignments',
            data={'action': 'assign_complaint', 'complaint_id': self.c_unassigned.id, 'worker_id': self.inactive_worker_profile.id},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(bad_inactive.status_code, 400)

        bad_other_dept = o_client.post(
            '/officer/assignments',
            data={'action': 'assign_complaint', 'complaint_id': self.c_unassigned.id, 'worker_id': self.other_worker_profile.id},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(bad_other_dept.status_code, 403)

        # Officer validly assigns complaint to active same-dept worker
        good_assign = o_client.post(
            '/officer/assignments',
            data={
                'action': 'assign_complaint',
                'complaint_id': self.c_unassigned.id,
                'worker_id': self.worker_profile.id,
                'instructions': 'Spray larvicide and clear stagnant drain',
            },
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(good_assign.status_code, 200)
        self.assertTrue(good_assign.get_json()['success'])

        # 3. Worker sees Assigned task with details, notifications, accepts task -> In Progress -> submits proof -> Verification
        assigned_html = w_client.get('/worker/tasks?status=Assigned').get_data(as_text=True)
        self.assertIn('CMP-ALL-101', assigned_html)
        self.assertIn('Public Health &amp; Vector Control', assigned_html)
        self.assertIn('Accept Task', assigned_html)
        self.assertIn('View Details', assigned_html)

        # Notifications API + read flow
        notif_api = w_client.get('/api/notifications').get_json()
        self.assertGreaterEqual(notif_api['unread_count'], 1)
        first_notif_id = notif_api['notifications'][0]['id']
        read_res = w_client.post(f'/api/notifications/{first_notif_id}/read')
        self.assertEqual(read_res.status_code, 200)

        # Worker clicks Accept Task
        acc_res = w_client.post(
            f'/worker/task/{self.c_unassigned.id}',
            data={'action': 'accept_task'},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(acc_res.status_code, 200)
        db.session.refresh(self.c_unassigned)
        self.assertEqual(self.c_unassigned.status, 'In Progress')

        # Appears in In Progress queue
        inprog_html = w_client.get('/worker/tasks?status=In+Progress').get_data(as_text=True)
        self.assertIn('CMP-ALL-101', inprog_html)

        # Worker posts completion + proof photo
        comp_res = w_client.post(
            f'/worker/task/{self.c_unassigned.id}',
            data={
                'action': 'submit_completion',
                'remarks': 'Cleared stagnant drain and completed fogging.',
                'after_image': (io.BytesIO(b'\x89PNG\r\n\x1a\nproofdata'), 'after_work.png'),
            },
            content_type='multipart/form-data',
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(comp_res.status_code, 200)

        # Worker Completed Tasks view shows pending verification task
        comp_list_html = w_client.get('/worker/task?status=Work+Completed').get_data(as_text=True)
        self.assertIn('CMP-ALL-101', comp_list_html)
        self.assertIn('Awaiting Officer Verification', comp_list_html)

        # 4. Officer Work Verification: sees evidence + remarks, rework requires reason, rework notifies worker, approve resolves
        verif_html = o_client.get('/officer/verification').get_data(as_text=True)
        self.assertIn('CMP-ALL-101', verif_html)
        self.assertIn('Freaky Worker', verif_html)
        self.assertIn('Cleared stagnant drain', verif_html)
        self.assertIn('/uploads/proofs/', verif_html)

        missing_reason = o_client.post(
            '/officer/verification',
            data={'action': 'return_rework', 'complaint_id': self.c_unassigned.id, 'rework_reason': ''},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(missing_reason.status_code, 400)

        rework_ok = o_client.post(
            '/officer/verification',
            data={'action': 'return_rework', 'complaint_id': self.c_unassigned.id, 'rework_reason': 'Need wider photo of clean culvert'},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(rework_ok.status_code, 200)
        db.session.refresh(self.c_unassigned)
        self.assertEqual(self.c_unassigned.status, 'Rework Required')

        # Worker resubmits after rework
        resubmit_ok = w_client.post(
            f'/worker/task/{self.c_unassigned.id}',
            data={'action': 'submit_completion', 'remarks': 'Uploaded wide-angle culvert photo.'},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(resubmit_ok.status_code, 200)

        # Officer approves -> Resolved
        approve_ok = o_client.post(
            '/officer/verification',
            data={'action': 'verify_resolve', 'complaint_id': self.c_unassigned.id, 'remarks': 'Site verified satisfactory.'},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(approve_ok.status_code, 200)
        db.session.refresh(self.c_unassigned)
        self.assertEqual(self.c_unassigned.status, 'Resolved')

        # Worker Completed Tasks STILL shows Verified / Resolved task!
        resolved_worker_html = w_client.get('/worker/task?status=Work+Completed').get_data(as_text=True)
        self.assertIn('CMP-ALL-101', resolved_worker_html)
        self.assertIn('Resolved', resolved_worker_html)

        # Worker Task History shows full timeline & remarks
        hist_html = w_client.get('/worker/history').get_data(as_text=True)
        self.assertIn('CMP-ALL-101', hist_html)

        # Worker Profile updates persist while preserving department
        prof_res = w_client.post(
            '/worker/profile',
            data={'full_name': 'Freaky Field Lead'},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(prof_res.status_code, 200)
        db.session.refresh(self.worker_user)
        self.assertEqual(self.worker_user.full_name, 'Freaky Field Lead')
        self.assertEqual(self.worker_user.department_id, self.dept.id)

        # 5. Officer Escalations test (create an active overdue complaint & escalate)
        overdue_c = Complaint(
            complaint_ref='CMP-ALL-ESC',
            citizen_id=self.citizen.id,
            department_id=self.dept.id,
            category_id=self.cat.id,
            assigned_officer_id=self.officer.id,
            title='Overdue chemical waste drain',
            description='Exceeding SLA deadline.',
            priority='urgent',
            status='In Progress',
            sla_due_date=datetime.utcnow() - timedelta(hours=5),
            is_escalated=False,
        )
        db.session.add(overdue_c)
        db.session.commit()

        esc_html = o_client.get('/officer/escalations').get_data(as_text=True)
        self.assertIn('CMP-ALL-ESC', esc_html)
        self.assertIn('Public Health &amp; Vector Control', esc_html)
        self.assertIn('Health Officer', esc_html)

        esc_post = o_client.post(
            '/officer/escalations',
            data={'action': 'escalate_complaint', 'complaint_id': overdue_c.id, 'remarks': 'Urgent SLA breach escalation.'},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        self.assertEqual(esc_post.status_code, 200)
        db.session.refresh(overdue_c)
        self.assertTrue(overdue_c.is_escalated)

        # 6. Admin & Citizen all sidebar routes + RBAC checks
        a_client = self.app.test_client()
        self._login(a_client, 'all.admin@civic.gov', 'Admin@123')
        for path in [
            '/admin/dashboard',
            '/admin/complaints',
            '/admin/citizens',
            '/admin/departments',
            '/admin/officers',
            '/admin/workers',
            '/admin/assignments',
            '/admin/analytics',
            '/admin/notifications',
            '/admin/audit-logs',
            '/admin/settings',
        ]:
            resp = a_client.get(path)
            self.assertEqual(resp.status_code, 200, f"Admin route {path} failed")

        c_client = self.app.test_client()
        self._login(c_client, 'all.citizen@civic.gov', 'Citizen@123')
        for path in [
            '/citizen/dashboard',
            '/citizen/complaints/new',
            '/citizen/complaints',
            '/citizen/track',
            '/citizen/notifications',
            '/citizen/feedback',
            '/citizen/profile',
        ]:
            resp = c_client.get(path)
            self.assertEqual(resp.status_code, 200, f"Citizen route {path} failed")

        # Citizen RBAC: cannot open admin/officer/worker routes or another citizen's complaint
        self.assertEqual(c_client.get('/admin/dashboard', follow_redirects=False).status_code, 302)
        self.assertEqual(c_client.get(f'/citizen/complaints/{self.c_other.id}', follow_redirects=False).status_code, 302)


if __name__ == '__main__':
    unittest.main()
