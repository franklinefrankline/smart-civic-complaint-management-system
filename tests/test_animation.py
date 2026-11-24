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
        self.assertIn('@keyframes btnSpinner', css)
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

        # Check progress bar
        self.assertIn('startProgressBar', js)
        self.assertIn('finishProgressBar', js)

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

        self.assertIn('id="pageProgressBar"', html)
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

if __name__ == '__main__':
    unittest.main()
