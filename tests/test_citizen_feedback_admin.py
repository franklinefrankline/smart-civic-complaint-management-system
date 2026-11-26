import unittest
from app import create_app, db
from app.models.user import User
from app.models.department import Department
from app.models.category import ComplaintCategory
from app.models.complaint import Complaint
from app.models.notification import Notification


class CitizenFeedbackAdminVisibilityTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.dept = Department(name='Street Lighting', code='LIGHT_FB', is_active=True)
        db.session.add(self.dept)
        db.session.flush()

        self.cat = ComplaintCategory(
            name='Streetlight Defect',
            department_id=self.dept.id,
            default_priority='medium',
            sla_hours=72,
            is_active=True,
        )
        db.session.add(self.cat)
        db.session.flush()

        self.admin = User(
            role='admin',
            full_name='Feedback Admin',
            email='fb.admin@civic.gov',
            mobile_number='9822222201',
            is_active=True,
        )
        self.admin.set_password('Admin@123')

        self.citizen = User(
            role='citizen',
            full_name='Priya Feedback Citizen',
            email='fb.citizen@civic.gov',
            mobile_number='9822222202',
            is_active=True,
        )
        self.citizen.set_password('Citizen@123')
        db.session.add_all([self.admin, self.citizen])
        db.session.flush()

        self.complaint = Complaint(
            complaint_ref='CMP-FB-1001',
            citizen_id=self.citizen.id,
            department_id=self.dept.id,
            category_id=self.cat.id,
            title='LED Pole Repaired on 2nd Avenue',
            description='Streetlights repaired cleanly and verified.',
            priority='medium',
            status='Resolved',
        )
        db.session.add(self.complaint)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_submitted_citizen_feedback_appears_on_admin_dashboard_and_detail(self):
        c_client = self.app.test_client()
        login_c = c_client.post('/auth/login', data={'login_id': 'fb.citizen@civic.gov', 'password': 'Citizen@123'})
        self.assertEqual(login_c.status_code, 302)

        sub = c_client.post(
            f'/citizen/complaints/{self.complaint.id}/feedback',
            data={
                'rating': '5',
                'response_speed_rating': '5',
                'work_quality_rating': '4',
                'comment': 'Fast repair and courteous municipal team!',
            },
            follow_redirects=False,
        )
        self.assertEqual(sub.status_code, 302)

        admin_notif = Notification.query.filter_by(user_id=self.admin.id, complaint_id=self.complaint.id).first()
        self.assertIsNotNone(admin_notif)
        self.assertIn('5/5', admin_notif.title)

        a_client = self.app.test_client()
        login_a = a_client.post('/auth/login', data={'login_id': 'fb.admin@civic.gov', 'password': 'Admin@123'})
        self.assertEqual(login_a.status_code, 302)

        dash = a_client.get('/admin/dashboard')
        self.assertEqual(dash.status_code, 200)
        dash_html = dash.get_data(as_text=True)
        self.assertIn('id="citizenFeedbackCard"', dash_html)
        self.assertIn('CMP-FB-1001', dash_html)
        self.assertIn('Priya Feedback Citizen', dash_html)
        self.assertIn('Fast repair and courteous municipal team!', dash_html)
        self.assertIn('Avg 5.0 / 5.0', dash_html)

        detail = a_client.get(f'/admin/complaints/{self.complaint.id}')
        self.assertEqual(detail.status_code, 200)
        detail_html = detail.get_data(as_text=True)
        self.assertIn('Citizen Resolution Feedback', detail_html)
        self.assertIn('Fast repair and courteous municipal team!', detail_html)


if __name__ == '__main__':
    unittest.main()
