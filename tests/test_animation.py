import unittest
import os
import re

class AnimationSystemTestCase(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_css_animation_tokens_and_keyframes(self):
        css_path = os.path.join(self.base_dir, 'app', 'static', 'css', 'main.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        # Check required timing variables
        self.assertIn('--anim-btn', css)
        self.assertIn('--anim-hover', css)
        self.assertIn('--anim-dropdown', css)
        self.assertIn('--anim-modal', css)
        self.assertIn('--anim-page', css)

        # Check required keyframe animations
        self.assertIn('@keyframes pageFadeInUp', css)
        self.assertIn('@keyframes pulseRing', css)
        self.assertIn('@keyframes inputShake', css)
        self.assertIn('@keyframes badgePulse', css)
        self.assertNotIn('@keyframes btnSpinner', css)
        self.assertIn('@keyframes toastProgress', css)
        self.assertIn('@keyframes tableRowFadeIn', css)
        self.assertIn('@keyframes skeletonShimmer', css)

        # Check reduced motion accessibility
        self.assertIn('@media (prefers-reduced-motion: reduce)', css)

    def test_js_interaction_and_toast_engine(self):
        js_path = os.path.join(self.base_dir, 'app', 'static', 'js', 'main.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            js = f.read()

        # Check number counters
        self.assertIn('initNumberCounters', js)
        self.assertIn('.stat-value', js)

        # Check form loading & double submit prevention
        self.assertIn('btn-loading', js)
        self.assertIn('input-error-shake', js)

        # Check toast notifications
        self.assertIn('window.showToast', js)
        self.assertIn('toastContainer', js)

        # Ensure full-screen / progress loading animations are removed
        self.assertNotIn('startProgressBar', js)
        self.assertNotIn('showGlobalLoader', js)

    def test_notifications_js_enhancements(self):
        notif_path = os.path.join(self.base_dir, 'app', 'static', 'js', 'notifications.js')
        with open(notif_path, 'r', encoding='utf-8') as f:
            js = f.read()

        self.assertIn('badge-pulse', js)
        self.assertIn('showToast', js)

    def test_base_html_animation_elements(self):
        base_path = os.path.join(self.base_dir, 'app', 'templates', 'base.html')
        with open(base_path, 'r', encoding='utf-8') as f:
            html = f.read()

        self.assertNotIn('id="pageProgressBar"', html)
        self.assertIn('id="globalPageLoader"', html)
        self.assertIn('loader.gif', html)
        self.assertIn('id="toastContainer"', html)

    def test_dashboards_stagger_in(self):
        for role in ['admin', 'officer', 'worker', 'citizen']:
            tmpl_path = os.path.join(self.base_dir, 'app', 'templates', role, 'dashboard.html')
            with open(tmpl_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertIn('stat-grid stagger-in', content, f"{role} dashboard should have stat-grid stagger-in")

    def test_workflow_timeline_stagger_in(self):
        templates = [
            os.path.join(self.base_dir, 'app', 'templates', 'public', 'track.html'),
            os.path.join(self.base_dir, 'app', 'templates', 'citizen', 'complaint_detail.html'),
            os.path.join(self.base_dir, 'app', 'templates', 'admin', 'complaint_detail.html'),
            os.path.join(self.base_dir, 'app', 'templates', 'officer', 'complaint_detail.html'),
            os.path.join(self.base_dir, 'app', 'templates', 'worker', 'task_detail.html')
        ]
        for tmpl in templates:
            with open(tmpl, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertIn('timeline stagger-in', content, f"{tmpl} should have timeline stagger-in")

    def test_smooth_page_transition_after_loading(self):
        base_path = os.path.join(self.base_dir, 'app', 'templates', 'base.html')
        css_path = os.path.join(self.base_dir, 'app', 'static', 'css', 'main.css')
        js_path = os.path.join(self.base_dir, 'app', 'static', 'js', 'main.js')

        with open(base_path, 'r', encoding='utf-8') as f:
            base_html = f.read()
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()
        with open(js_path, 'r', encoding='utf-8') as f:
            js = f.read()

        # Pre-paint theme + navigation entering bootstrap in <head> before stylesheets
        self.assertIn("localStorage.getItem('civic_theme')", base_html)
        self.assertIn("sessionStorage.getItem('scf_nav_transition')", base_html)
        self.assertIn("classList.add('scf-page-entering')", base_html)
        self.assertLess(
            base_html.find("localStorage.getItem('civic_theme')"),
            base_html.find('css/main.css'),
            'Theme pre-paint script must run before main.css to prevent light-to-dark flash',
        )

        # Smooth fade-in/fade-out and paused entrance animations until page is ready
        self.assertIn('html.theme-ready body', css)
        self.assertIn('html.scf-page-entering .main-content', css)
        self.assertIn('html.scf-page-entering .global-loader-overlay', css)
        self.assertIn('html.scf-page-entering .dashboard-content', css)
        self.assertIn('.dashboard-content.is-swapping', css)
        self.assertIn('transition: opacity 300ms', css)
        self.assertIn('transition: opacity 280ms', css)

        # JS lifecycle: persist transition flag across navigations & clean double-rAF reveal
        self.assertIn("sessionStorage.setItem('scf_nav_transition', '1')", js)
        self.assertIn('window.ensureDashboardBackBar', js)
        self.assertIn("classList.add('theme-ready')", js)
        self.assertIn("classList.remove('scf-page-entering')", js)

if __name__ == '__main__':
    unittest.main()
