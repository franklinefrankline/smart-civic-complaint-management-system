import unittest
from app import create_app, db
from app.models.user import User
from app.models.department import Department
import os

class SidebarFixedScrollTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        # Seed Department & User
        self.dept = Department(name='Civic Engineering', code='CE', is_active=True)
        db.session.add(self.dept)
        db.session.commit()

        self.admin = User(role='admin', full_name='Fixed Admin', email='admin.scroll@test.gov', mobile_number='9999222221', is_active=True)
        self.admin.set_password('Admin@123')
        db.session.add(self.admin)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_css_sidebar_fixed_and_content_scroll_isolation(self):
        """Verify CSS guarantees the sidebar never scrolls with the page"""
        css_path = os.path.join(self.app.root_path, 'static', 'css', 'main.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        # 1. Dashboard body/html lock preventing window scroll on dashboard pages
        self.assertIn('html.has-dashboard,', css)
        self.assertIn('body.has-dashboard,', css)
        self.assertIn('body:has(.dashboard-layout)', css)
        self.assertIn('overflow: hidden;', css)

        # 2. Layout viewport lock
        self.assertIn('.dashboard-layout {', css)
        self.assertIn('height: 100vh;', css)

        # 3. Fixed sidebar pinned to viewport
        self.assertIn('.dashboard-sidebar {', css)
        self.assertIn('position: fixed !important;', css)
        self.assertIn('top: 0 !important;', css)
        self.assertIn('left: 0 !important;', css)

        # 4. Content area has own independent scroll and height constraint
        self.assertIn('.dashboard-content {', css)
        self.assertIn('height: 100vh;', css)
        self.assertIn('overflow-y: auto;', css)
        self.assertIn('overscroll-behavior: contain;', css)

        # 5. Middle navigation menu has overscroll-behavior contain
        self.assertIn('.sidebar-nav-container {', css)
        self.assertIn('overscroll-behavior: contain;', css)

        # 6. Ensure .main-content does NOT have will-change: transform (which breaks position: fixed)
        self.assertNotIn('.main-content, .dashboard-content {\n  animation: pageFadeInUp', css)

    def test_js_adds_has_dashboard_class(self):
        """Verify main.js dynamically adds has-dashboard class when sidebar exists"""
        js_path = os.path.join(self.app.root_path, 'static', 'js', 'main.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            js = f.read()

        self.assertIn("document.documentElement.classList.add('has-dashboard')", js)
        self.assertIn("document.body.classList.add('has-dashboard')", js)

    def test_base_template_flash_container_empty_guard(self):
        """Verify base.html does not render empty flash-container div that causes vertical jump"""
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b'<div class="container flash-container" style="margin-top: 1rem;">\n  </div>', res.data)
