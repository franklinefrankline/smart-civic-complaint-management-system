from datetime import datetime, timedelta
import unittest
from app import create_app, db
from app.models.user import User
from app.models.department import Department
from app.models.category import ComplaintCategory
from app.models.complaint import Complaint


class OfficerQueueRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.dept = Department(name='Water Supply', code='WATER_Q', is_active=True)
        self.other_dept = Department(name='Roads', code='ROADS_Q', is_active=True)
        db.session.add_all([self.dept, self.other_dept])
        db.session.flush()

        self.cat = ComplaintCategory(
            name='Pipe Leak',
            department_id=self.dept.id,
            default_priority='high',
            sla_hours=24,
            is_active=True,
        )
        self.other_cat = ComplaintCategory(
            name='Pothole',
            department_id=self.other_dept.id,
            default_priority='medium',
            sla_hours=48,
            is_active=True,
        )
        db.session.add_all([self.cat, self.other_cat])
        db.session.flush()

        self.citizen = User(
            role='citizen',
            full_name='Queue Citizen',
            email='queue.citizen@civic.gov',
            mobile_number='9811111111',
            is_active=True,
        )
        self.citizen.set_password('Citizen@123')

        self.officer = User(
            role='officer',
            full_name='Queue Water Officer',
            email='queue.officer@civic.gov',
            mobile_number='9811111112',
            department_id=self.dept.id,
            is_active=True,
        )
        self.officer.set_password('Officer@123')
        db.session.add_all([self.citizen, self.officer])
        db.session.commit()

        login_res = self.client.post(
            '/auth/login',
            data={'login_id': 'queue.officer@civic.gov', 'password': 'Officer@123'},
        )
        self.assertEqual(login_res.status_code, 302)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_empty_queues_render_clear_titles_and_empty_states(self):
        verif = self.client.get('/officer/verification')
        self.assertEqual(verif.status_code, 200)
        verif_html = verif.get_data(as_text=True)
        self.assertIn('Work Verification Queue', verif_html)
        self.assertIn('No completed tasks are currently awaiting work verification.', verif_html)

        esc = self.client.get('/officer/escalations')
        self.assertEqual(esc.status_code, 200)
        esc_html = esc.get_data(as_text=True)
        self.assertIn('Escalated Department Complaints', esc_html)
        self.assertIn('No escalated or overdue complaints in your department right now.', esc_html)

    def test_verification_shows_both_verification_pending_and_work_completed(self):
        c1 = Complaint(
            complaint_ref='CMP-VERIF-01',
            citizen_id=self.citizen.id,
            department_id=self.dept.id,
            assigned_officer_id=self.officer.id,
            category_id=self.cat.id,
            title='Verification Pending Valve Fix',
            description='Completed valve repair awaiting verification',
            priority='high',
            status='Verification Pending',
        )
        c2 = Complaint(
            complaint_ref='CMP-VERIF-02',
            citizen_id=self.citizen.id,
            department_id=self.dept.id,
            assigned_officer_id=None,
            category_id=self.cat.id,
            title='Legacy Work Completed Pipe Fix',
            description='Legacy Work Completed status should also show up',
            priority='medium',
            status='Work Completed',
        )
        c_other = Complaint(
            complaint_ref='CMP-VERIF-99',
            citizen_id=self.citizen.id,
            department_id=self.other_dept.id,
            category_id=self.other_cat.id,
            title='Other Dept Completed Task',
            description='Must remain isolated from water officer',
            priority='low',
            status='Verification Pending',
        )
        db.session.add_all([c1, c2, c_other])
        db.session.commit()

        res = self.client.get('/officer/verification')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('CMP-VERIF-01', html)
        self.assertIn('CMP-VERIF-02', html)
        self.assertNotIn('CMP-VERIF-99', html)

    def test_escalations_auto_sweeps_overdue_and_shows_escalated_records(self):
        overdue_active = Complaint(
            complaint_ref='CMP-ESC-01',
            citizen_id=self.citizen.id,
            department_id=self.dept.id,
            assigned_officer_id=self.officer.id,
            category_id=self.cat.id,
            title='Overdue Active Water Main',
            description='Past SLA deadline without manual sweep yet',
            priority='urgent',
            status='In Progress',
            sla_due_date=datetime.utcnow() - timedelta(hours=3),
            is_escalated=False,
        )
        manual_escalated = Complaint(
            complaint_ref='CMP-ESC-02',
            citizen_id=self.citizen.id,
            department_id=self.dept.id,
            assigned_officer_id=None,
            category_id=self.cat.id,
            title='Manually Escalated Leak',
            description='Explicit Escalated status',
            priority='high',
            status='Escalated',
            is_escalated=True,
        )
        resolved_old = Complaint(
            complaint_ref='CMP-ESC-DONE',
            citizen_id=self.citizen.id,
            department_id=self.dept.id,
            category_id=self.cat.id,
            title='Resolved Old Complaint',
            description='Closed before escalation',
            priority='low',
            status='Resolved',
            sla_due_date=datetime.utcnow() - timedelta(days=2),
            is_escalated=False,
        )
        db.session.add_all([overdue_active, manual_escalated, resolved_old])
        db.session.commit()

        res = self.client.get('/officer/escalations')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('CMP-ESC-01', html)
        self.assertIn('CMP-ESC-02', html)
        self.assertNotIn('CMP-ESC-DONE', html)

        db.session.refresh(overdue_active)
        self.assertTrue(overdue_active.is_escalated)

        filter_res = self.client.get('/officer/complaints?status=Escalated')
        self.assertEqual(filter_res.status_code, 200)
        filter_html = filter_res.get_data(as_text=True)
        self.assertIn('CMP-ESC-01', filter_html)
        self.assertIn('CMP-ESC-02', filter_html)


if __name__ == '__main__':
    unittest.main()
