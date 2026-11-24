import unittest
from app import create_app, db
from app.models.user import User
from app.models.department import Department
import os

class SidebarRedesignTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        # Seed Department
        self.dept = Department(name='Public Works & Sanitation', code='PWS', is_active=True)
        db.session.add(self.dept)
        db.session.commit()

        # Seed Users for all 4 roles
        self.admin = User(role='admin', full_name='Admin Commander', email='admin.sb@test.gov', mobile_number='9999000001', is_active=True)
        self.admin.set_password('Admin@123')

        self.officer = User(role='officer', full_name='Officer Sarah', email='officer.sb@test.gov', mobile_number='9999000002', department_id=self.dept.id, is_active=True)
        self.officer.set_password('Officer@123')

        self.worker = User(role='worker', full_name='Technician John', email='worker.sb@test.gov', mobile_number='9999000003', department_id=self.dept.id, is_active=True)
        self.worker.set_password('Worker@123')

        self.citizen = User(role='citizen', full_name='Citizen Jane', email='citizen.sb@test.gov', mobile_number='9999000004', city='Metro City', is_active=True)
        self.citizen.set_password('Citizen@123')

        db.session.add_all([self.admin, self.officer, self.worker, self.citizen])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_admin_sidebar_structure_and_menu(self):
        self.client.post('/auth/login', data={'login_id': 'admin.sb@test.gov', 'password': 'Admin@123'})
        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 200)

        # Check core sidebar structure
        self.assertIn(b'id="dashboardSidebar"', res.data)
        self.assertIn(b'id="sidebarToggleBtn"', res.data)
        self.assertIn(b'class="sidebar-toggle-btn"', res.data)
        self.assertIn(b'class="toggle-icon-expanded"', res.data)
        self.assertIn(b'class="toggle-icon-collapsed"', res.data)
        self.assertIn(b'id="sidebarToggleTooltip"', res.data)
        self.assertIn(b'Collapse Menu', res.data)
        self.assertIn(b'class="sidebar-brand-header"', res.data)
        self.assertIn(b'class="sidebar-nav-container"', res.data)
        self.assertIn(b'class="sidebar-profile-footer"', res.data)
        self.assertIn(b'id="sidebarBackdrop"', res.data)

        # Check Admin menu items
        self.assertIn(b'Administration', res.data)
        self.assertIn(b'Complaint Management', res.data)
        self.assertIn(b'Citizen Management', res.data)
        self.assertIn(b'Department Management', res.data)
        self.assertIn(b'Officer Management', res.data)
        self.assertIn(b'Worker Management', res.data)
        self.assertIn(b'Assignments', res.data)
        self.assertIn(b'Reports and Analytics', res.data)
        self.assertIn(b'Audit Logs', res.data)
        self.assertIn(b'Settings', res.data)

        # Check user info at bottom
        self.assertIn(b'Admin Commander', res.data)
        self.assertIn(b'Public Portal', res.data)
        self.assertIn(b'Sign Out', res.data)

    def test_officer_sidebar_structure_and_menu(self):
        self.client.post('/auth/login', data={'login_id': 'officer.sb@test.gov', 'password': 'Officer@123'})
        res = self.client.get('/officer/dashboard')
        self.assertEqual(res.status_code, 200)

        # Check core sidebar structure
        self.assertIn(b'id="dashboardSidebar"', res.data)
        self.assertIn(b'id="sidebarToggleBtn"', res.data)
        self.assertIn(b'class="sidebar-nav-container"', res.data)
        self.assertIn(b'class="sidebar-profile-footer"', res.data)

        # Check Officer menu items
        self.assertIn(b'Department Operations', res.data)
        self.assertIn(b'Incoming Complaints', res.data)
        self.assertIn(b'Department Complaints', res.data)
        self.assertIn(b'Worker Assignments', res.data)
        self.assertIn(b'Work Verification', res.data)
        self.assertIn(b'Escalations', res.data)
        self.assertIn(b'Reports', res.data)

        # Check profile display
        self.assertIn(b'Officer Sarah', res.data)
        self.assertIn(b'Public Works &amp; Sanitation', res.data)

    def test_worker_sidebar_structure_and_menu(self):
        self.client.post('/auth/login', data={'login_id': 'worker.sb@test.gov', 'password': 'Worker@123'})
        res = self.client.get('/worker/dashboard')
        self.assertEqual(res.status_code, 200)

        # Check core sidebar structure
        self.assertIn(b'id="dashboardSidebar"', res.data)
        self.assertIn(b'id="sidebarToggleBtn"', res.data)

        # Check Worker menu items
        self.assertIn(b'Field Technician Work', res.data)
        self.assertIn(b'Assigned Tasks', res.data)
        self.assertIn(b'In Progress', res.data)
        self.assertIn(b'Completed Tasks', res.data)
        self.assertIn(b'Task History', res.data)
        self.assertIn(b'Notifications', res.data)

        # Check profile display
        self.assertIn(b'Technician John', res.data)

    def test_citizen_sidebar_structure_and_menu(self):
        self.client.post('/auth/login', data={'login_id': 'citizen.sb@test.gov', 'password': 'Citizen@123'})
        res = self.client.get('/citizen/dashboard')
        self.assertEqual(res.status_code, 200)

        # Check core sidebar structure
        self.assertIn(b'id="dashboardSidebar"', res.data)
        self.assertIn(b'id="sidebarToggleBtn"', res.data)

        # Check Citizen menu items
        self.assertIn(b'Citizen Services', res.data)
        self.assertIn(b'My Dashboard', res.data)
        self.assertIn(b'Register Complaint', res.data)
        self.assertIn(b'My Complaints', res.data)
        self.assertIn(b'Track Complaint', res.data)
        self.assertIn(b'Feedback', res.data)
        self.assertIn(b'My Profile', res.data)

        # Check profile display
        self.assertIn(b'Citizen Jane', res.data)

    def test_sidebar_css_fixed_scrolling_and_toggle_button(self):
        css_path = os.path.join(self.app.root_path, 'static', 'css', 'main.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Fixed Sidebar layout tests
        self.assertIn('.dashboard-sidebar {', css_content)
        self.assertIn('position: fixed;', css_content)
        self.assertIn('--sidebar-expanded-width: 260px;', css_content)
        self.assertIn('--sidebar-collapsed-width: 76px;', css_content)

        # Floating circular blue toggle button outside at exact vertical center
        self.assertIn('.sidebar-toggle-btn {', css_content)
        self.assertIn('position: absolute;', css_content)
        self.assertIn('top: 50%;', css_content)
        self.assertIn('transform: translateY(-50%);', css_content)
        self.assertIn('right: -15px;', css_content)
        self.assertIn('border-radius: 50%;', css_content)

        # Independent middle navigation scroll
        self.assertIn('.sidebar-nav-container {', css_content)
        self.assertIn('overflow-y: auto;', css_content)

        # Independent main content scroll
        self.assertIn('.dashboard-content {', css_content)
        self.assertIn('margin-left: var(--sidebar-expanded-width);', css_content)
        self.assertIn('overflow-y: auto;', css_content)

        # Collapsed sidebar styles and tooltips
        self.assertIn('.dashboard-sidebar.sidebar-collapsed', css_content)
        self.assertIn('body.sidebar-collapsed', css_content)
        self.assertIn('.sidebar-label', css_content)

        # Mobile drawer rules
        self.assertIn('@media (max-width: 900px)', css_content)
        self.assertIn('.sidebar-backdrop', css_content)
        self.assertIn('.mobile-open', css_content)

    def test_sidebar_js_toggle_and_persistence(self):
        js_path = os.path.join(self.app.root_path, 'static', 'js', 'main.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # JS Controller tests
        self.assertIn('civic_sidebar_collapsed', js_content)
        self.assertIn('updateSidebarState', js_content)
        self.assertIn('sidebar-collapsed', js_content)
        self.assertIn('toggleMobileSidebar', js_content)
        self.assertIn('sidebarToggleBtn', js_content)
        self.assertIn('Open Menu', js_content)
        self.assertIn('Collapse Menu', js_content)
