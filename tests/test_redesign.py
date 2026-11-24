import unittest
from app import create_app, db
from app.models.user import User
from app.models.complaint import Complaint
from app.models.category import ComplaintCategory
from app.models.department import Department
from app.models.workflow import Worker, ComplaintAssignment

class RedesignEnterpriseTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Department & Category
        self.dept = Department(name="Electricity Board", code="ELEC", is_active=True)
        db.session.add(self.dept)
        db.session.flush()

        self.cat = ComplaintCategory(name="Streetlight Outage", department_id=self.dept.id, default_priority="medium", is_active=True)
        db.session.add(self.cat)
        db.session.flush()

        # Users
        self.admin = User(role='admin', full_name='Super Admin', email='admin@city.gov', mobile_number='9800000001', is_active=True)
        self.admin.set_password('Admin@123')

        self.officer = User(role='officer', full_name='Electrical Officer', email='officer@city.gov', mobile_number='9800000002', department_id=self.dept.id, is_active=True)
        self.officer.set_password('Officer@123')

        self.worker = User(role='worker', full_name='Lineman tech', email='worker@city.gov', mobile_number='9800000003', department_id=self.dept.id, is_active=True)
        self.worker.set_password('Worker@123')

        self.citizen = User(role='citizen', full_name='Local Citizen', email='citizen@city.gov', mobile_number='9800000004', is_active=True, ward_number='4', city='Chennai')
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

    def test_structured_address_complaint_submission(self):
        """Verify complaint registers and saves structured address fields without any map"""
        self.login('citizen@city.gov', 'Citizen@123')
        res = self.client.post('/citizen/complaints/new', data={
            'title': 'High mast streetlight failure at junction',
            'category_id': self.cat.id,
            'department_id': self.dept.id,
            'description': 'Dark intersection causing public hazard for pedestrians and vehicles.',
            'priority': 'high',
            'state': 'Tamil Nadu',
            'district': 'Chennai',
            'city': 'Greater Chennai Corporation',
            'ward_number': '4',
            'street_name': 'Mount Road Junction',
            'locality': 'Anna Salai',
            'landmark': 'Opposite Metro Station',
            'pincode': '600002'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Complaint registered successfully", res.data)

        # Inspect database record
        complaint = Complaint.query.filter_by(citizen_id=self.citizen.id).first()
        self.assertIsNotNone(complaint)
        self.assertEqual(complaint.state, 'Tamil Nadu')
        self.assertEqual(complaint.district, 'Chennai')
        self.assertEqual(complaint.street_name, 'Mount Road Junction')
        self.assertEqual(complaint.locality, 'Anna Salai')
        self.assertEqual(complaint.landmark, 'Opposite Metro Station')
        self.assertEqual(complaint.pincode, '600002')
        self.assertIn("Mount Road Junction", complaint.full_address)
        self.assertIn("Anna Salai", complaint.full_address)

    def test_new_admin_role_routes(self):
        """Verify all new admin management views load successfully"""
        self.login('admin@city.gov', 'Admin@123')
        for route in ['/admin/citizens', '/admin/officers', '/admin/assignments', '/admin/settings', '/admin/notifications']:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Route {route} failed")

    def test_new_officer_role_routes(self):
        """Verify all new officer management views load successfully"""
        self.login('officer@city.gov', 'Officer@123')
        for route in ['/officer/incoming', '/officer/verification', '/officer/escalations', '/officer/notifications', '/officer/profile']:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Route {route} failed")

    def test_new_worker_role_routes(self):
        """Verify all new worker management views load successfully"""
        self.login('worker@city.gov', 'Worker@123')
        for route in ['/worker/notifications', '/worker/profile']:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Route {route} failed")

    def test_new_citizen_role_routes(self):
        """Verify all new citizen views load successfully"""
        self.login('citizen@city.gov', 'Citizen@123')
        for route in ['/citizen/notifications', '/citizen/feedback']:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Route {route} failed")

    def test_no_leaflet_in_rendered_html(self):
        """Verify that Leaflet map links and scripts are completely absent from key pages"""
        for url in ['/', '/about', '/how-it-works', '/track']:
            res = self.client.get(url)
            self.assertNotIn(b"leaflet.css", res.data)
            self.assertNotIn(b"leaflet.js", res.data)
            self.assertNotIn(b"brand-emblem", res.data)

if __name__ == '__main__':
    unittest.main()
