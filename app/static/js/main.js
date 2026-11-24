// Smart Civic Complaint System - Master UI & Interaction Engine
// Consistent 60fps transitions, accessible reduced-motion, loading states, and live micro-interactions

document.addEventListener('DOMContentLoaded', () => {
  // 1. Accessibility Motion Preference Detection
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // 2. Chart.js Global Smooth Easing Defaults
  if (window.Chart) {
    Chart.defaults.animation = prefersReducedMotion ? false : {
      duration: 800,
      easing: 'easeOutQuart'
    };
    Chart.defaults.transitions = {
      active: {
        animation: {
          duration: prefersReducedMotion ? 0 : 250
        }
      }
    };
  }

  // 3. Global Theme Manager (Synchronized across all pages, navigation bar, and sidebar)
  const htmlEl = document.documentElement;
  const savedTheme = localStorage.getItem('civic_theme') || 
    (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    
  htmlEl.setAttribute('data-theme', savedTheme);

  function syncThemeUI(theme) {
    const isDark = theme === 'dark';
    document.querySelectorAll('.theme-toggle-btn, #themeToggle').forEach(btn => {
      btn.setAttribute('title', isDark ? 'Switch to Light Theme' : 'Switch to Dark Theme');
      btn.setAttribute('aria-label', isDark ? 'Switch to Light Theme' : 'Switch to Dark Theme');
      
      const icon = btn.querySelector('.theme-icon') || btn.querySelector('i');
      if (icon) {
        icon.setAttribute('data-lucide', isDark ? 'sun' : 'moon');
      } else {
        btn.innerHTML = isDark 
          ? '<i data-lucide="sun" class="icon-sm theme-icon"></i>' 
          : '<i data-lucide="moon" class="icon-sm theme-icon"></i>';
      }

      const label = btn.querySelector('.theme-label-text');
      if (label) {
        label.textContent = isDark ? 'Light Theme' : 'Dark Theme';
      }
    });

    if (window.lucide) {
      lucide.createIcons();
    }
  }

  // Click delegation for any theme toggle button across all pages & sidebars
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.theme-toggle-btn, #themeToggle');
    if (!btn) return;
    
    e.preventDefault();
    const current = htmlEl.getAttribute('data-theme');
    const target = current === 'dark' ? 'light' : 'dark';
    htmlEl.setAttribute('data-theme', target);
    localStorage.setItem('civic_theme', target);
    syncThemeUI(target);
  });

  syncThemeUI(savedTheme);

  // 4. Initialize Lucide Icons
  if (window.lucide) {
    lucide.createIcons();
  }

  // 5. Flash Alert Auto-Dismiss with Smooth Slide-Up
  document.querySelectorAll('.alert').forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 250ms ease, transform 250ms ease';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-8px)';
      setTimeout(() => alert.remove(), 260);
    }, 6000);
  });

  // 6. Smooth KPI Statistic Number Counters
  initNumberCounters();

  function initNumberCounters() {
    const statValues = document.querySelectorAll('.stat-value');
    if (!statValues.length) return;

    if (prefersReducedMotion) return; // Keep instantaneous for accessibility

    statValues.forEach(el => {
      const rawText = el.textContent.trim();
      const targetNum = parseInt(rawText.replace(/[^0-9]/g, ''), 10);
      if (isNaN(targetNum) || targetNum === 0) return;

      const duration = 650; // ms
      const startTime = performance.now();
      const prefix = rawText.match(/^[^0-9]*/)[0] || '';
      const suffix = rawText.match(/[^0-9]*$/)[0] || '';

      el.textContent = `${prefix}0${suffix}`;

      function updateCounter(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // easeOutQuart
        const ease = 1 - Math.pow(1 - progress, 4);
        const currentVal = Math.round(ease * targetNum);

        el.textContent = `${prefix}${currentVal.toLocaleString()}${suffix}`;

        if (progress < 1) {
          requestAnimationFrame(updateCounter);
        } else {
          el.textContent = `${prefix}${targetNum.toLocaleString()}${suffix}`;
        }
      }

      requestAnimationFrame(updateCounter);
    });
  }

  // 7. Form Submission Loading States & Double-Submit Protection
  initFormInteractions();

  function initFormInteractions() {
    document.querySelectorAll('form').forEach(form => {
      form.addEventListener('submit', (e) => {
        // Run native validity check
        if (!form.checkValidity()) {
          // Find first invalid input and apply shake animation
          const firstInvalid = form.querySelector(':invalid');
          if (firstInvalid) {
            firstInvalid.classList.add('input-error-shake');
            firstInvalid.focus();
            setTimeout(() => {
              firstInvalid.classList.remove('input-error-shake');
            }, 400);
          }
          return;
        }

        // Form is valid: start loading animation
        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submitBtn && !submitBtn.disabled) {
          submitBtn.classList.add('btn-loading');
          submitBtn.disabled = true;

          // Start top navigation bar
          startProgressBar();

          // Safety fallback: re-enable after 8.5 seconds in case of slow network or aborted navigation
          setTimeout(() => {
            submitBtn.classList.remove('btn-loading');
            submitBtn.disabled = false;
            finishProgressBar();
          }, 8500);
        }
      });
    });
  }

  // 8. Top Page Progress Bar
  window.startProgressBar = function() {
    let bar = document.getElementById('pageProgressBar');
    if (!bar) {
      bar = document.createElement('div');
      bar.id = 'pageProgressBar';
      document.body.appendChild(bar);
    }
    bar.style.opacity = '1';
    bar.style.width = '0%';
    setTimeout(() => { bar.style.width = '40%'; }, 50);
    setTimeout(() => { bar.style.width = '75%'; }, 200);
  };

  window.finishProgressBar = function() {
    const bar = document.getElementById('pageProgressBar');
    if (!bar) return;
    bar.style.width = '100%';
    setTimeout(() => {
      bar.style.opacity = '0';
      setTimeout(() => { bar.style.width = '0%'; }, 250);
    }, 200);
  };

  // Page Link Click Progress Triggers
  document.querySelectorAll('a[href]:not([target="_blank"]):not([href^="#"]):not([href^="javascript:"])').forEach(link => {
    link.addEventListener('click', (e) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const href = link.getAttribute('href');
      if (href && !href.startsWith('#') && href !== '') {
        startProgressBar();
      }
    });
  });

  // 9. Toast Notification System
  window.showToast = function(message, type = 'info', title = null, duration = 4000) {
    let container = document.getElementById('toastContainer');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toastContainer';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const iconMap = {
      success: 'check-circle',
      error: 'alert-circle',
      warning: 'alert-triangle',
      info: 'info'
    };

    const titleMap = {
      success: 'Operation Successful',
      error: 'Notice Required',
      warning: 'Attention',
      info: 'Notification'
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <div class="toast-icon"><i data-lucide="${iconMap[type] || 'info'}" class="icon-sm"></i></div>
      <div class="toast-content">
        <div class="toast-title">${escapeHtml(title || titleMap[type] || 'Update')}</div>
        <div>${escapeHtml(message)}</div>
      </div>
      <button type="button" class="toast-close-btn" aria-label="Close notification">&times;</button>
      <div class="toast-progress" style="animation-duration: ${duration}ms;"></div>
    `;

    container.appendChild(toast);
    if (window.lucide) {
      lucide.createIcons();
    }

    // Trigger smooth entrance
    requestAnimationFrame(() => {
      toast.classList.add('toast-show');
    });

    const closeBtn = toast.querySelector('.toast-close-btn');
    let timer = setTimeout(dismiss, duration);

    function dismiss() {
      clearTimeout(timer);
      toast.classList.remove('toast-show');
      toast.classList.add('toast-hide');
      setTimeout(() => toast.remove(), 250);
    }

    closeBtn.addEventListener('click', dismiss);
  };

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // 10. Star Rating Interactive Widget
  document.querySelectorAll('.star-rating').forEach(ratingWidget => {
    const input = ratingWidget.querySelector('input[type="hidden"]');
    const stars = ratingWidget.querySelectorAll('.star');

    stars.forEach((star, index) => {
      star.addEventListener('click', () => {
        const value = index + 1;
        if (input) input.value = value;
        updateStars(stars, value);
      });

      star.addEventListener('mouseenter', () => {
        updateStars(stars, index + 1);
      });
    });

    ratingWidget.addEventListener('mouseleave', () => {
      const currentVal = input ? parseInt(input.value) || 0 : 0;
      updateStars(stars, currentVal);
    });
  });

  function updateStars(stars, activeCount) {
    stars.forEach((star, idx) => {
      if (idx < activeCount) {
        star.classList.add('active');
      } else {
        star.classList.remove('active');
      }
    });
  }

  // 11. Mobile Navigation & Drawer
  const mobileToggle = document.getElementById('mobileNavToggle');
  const navLinks = document.querySelector('.nav-links');
  if (mobileToggle) {
    mobileToggle.addEventListener('click', () => {
      const sidebar = document.getElementById('dashboardSidebar');
      if (sidebar) {
        if (window.toggleMobileSidebar) {
          window.toggleMobileSidebar();
        }
      } else if (navLinks) {
        navLinks.classList.toggle('mobile-open');
      }
    });
  }

  // 12. Modal Accessibility & Animation Controller
  window.openModal = function(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.add('modal-overlay');
    modal.classList.add('show');
    modal.style.display = 'flex';
    if (window.lucide) {
      lucide.createIcons();
    }
  };

  window.closeModal = function(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.remove('show');
    setTimeout(() => {
      modal.style.display = 'none';
    }, 220);
  };

  // Close modals on Escape key or backdrop click
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.show, [id$="Modal"]').forEach(m => {
        if (m.classList.contains('show') || m.style.display === 'block' || m.style.display === 'flex') {
          m.classList.remove('show');
          setTimeout(() => { m.style.display = 'none'; }, 220);
        }
      });
    }
  });

  document.querySelectorAll('[id$="Modal"]').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.classList.remove('show');
        setTimeout(() => { modal.style.display = 'none'; }, 220);
      }
    });
  });

  // 13. Two-Sided Sliding Authentication Controller
  const authSliderCard = document.getElementById('authSliderCard');
  if (authSliderCard) {
    const slideSignInBtn = document.getElementById('slideSignInBtn');
    const slideSignUpBtn = document.getElementById('slideSignUpBtn');

    function switchToSignIn(e) {
      if (e) e.preventDefault();
      authSliderCard.classList.add('signin-active');
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, '', '/auth/login');
      }
      document.title = 'Sign In | Smart Civic Complaint Management System';
      if (window.lucide) lucide.createIcons();
    }

    function switchToSignUp(e) {
      if (e) e.preventDefault();
      authSliderCard.classList.remove('signin-active');
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, '', '/auth/register');
      }
      document.title = 'Create Account | Smart Civic Complaint Management System';
      if (window.lucide) lucide.createIcons();
    }

    if (slideSignInBtn) {
      slideSignInBtn.addEventListener('click', switchToSignIn);
    }
    if (slideSignUpBtn) {
      slideSignUpBtn.addEventListener('click', switchToSignUp);
    }

    document.querySelectorAll('.switch-to-signin').forEach(el => {
      el.addEventListener('click', switchToSignIn);
    });
    document.querySelectorAll('.switch-to-signup').forEach(el => {
      el.addEventListener('click', switchToSignUp);
    });

    // Hash & Query param support: e.g. #signup or ?mode=signup
    const urlParams = new URLSearchParams(window.location.search);
    if (window.location.hash === '#signup' || urlParams.get('mode') === 'signup') {
      switchToSignUp();
    } else if (window.location.hash === '#signin' || urlParams.get('mode') === 'signin') {
      switchToSignIn();
    }
  }

  // 14. Password Visibility Toggle
  window.togglePasswordVisibility = function(btn) {
    const wrapper = btn.closest('.auth-input-wrapper, .password-input-wrapper, .form-group') || btn.parentElement;
    if (!wrapper) return;
    const input = wrapper.querySelector('input');
    if (!input) return;

    if (input.type === 'password') {
      input.type = 'text';
      btn.innerHTML = '<svg class="icon-sm" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"></path><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"></path><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"></path><line x1="2" x2="22" y1="2" y2="22"></line></svg>';
      btn.setAttribute('aria-label', 'Hide password');
      btn.setAttribute('title', 'Hide password');
    } else {
      input.type = 'password';
      btn.innerHTML = '<svg class="icon-sm" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
      btn.setAttribute('aria-label', 'Show password');
      btn.setAttribute('title', 'Show password');
    }
    if (window.lucide) {
      lucide.createIcons();
    }
  };

  // 15. Cookie Consent & Preferences Manager
  const COOKIE_STORAGE_KEY = 'civic_cookie_consent';
  const cookieBanner = document.getElementById('cookieConsentBanner');
  const cookieSettingsModal = document.getElementById('cookieSettingsModal');
  const prefFunctional = document.getElementById('prefFunctional');
  const prefAnalytics = document.getElementById('prefAnalytics');

  function getSavedCookiePreferences() {
    try {
      const saved = localStorage.getItem(COOKIE_STORAGE_KEY);
      return saved ? JSON.parse(saved) : null;
    } catch (e) {
      return null;
    }
  }

  function saveCookiePreferences(prefs) {
    try {
      const fullPrefs = {
        essential: true,
        functional: Boolean(prefs.functional),
        analytics: Boolean(prefs.analytics),
        timestamp: new Date().toISOString()
      };
      localStorage.setItem(COOKIE_STORAGE_KEY, JSON.stringify(fullPrefs));
      
      // Also write standard cookie flag
      document.cookie = "civic_cookie_consent=1; path=/; max-age=31536000; SameSite=Lax";
      
      if (cookieBanner) {
        cookieBanner.classList.remove('show');
        setTimeout(() => { cookieBanner.style.display = 'none'; }, 350);
      }
      if (cookieSettingsModal) {
        window.closeModal('cookieSettingsModal');
      }
      return fullPrefs;
    } catch (e) {
      console.warn('Could not save cookie preferences', e);
    }
  }

  window.openCookieSettings = function() {
    const current = getSavedCookiePreferences() || { functional: true, analytics: false };
    if (prefFunctional) prefFunctional.checked = current.functional !== false;
    if (prefAnalytics) prefAnalytics.checked = Boolean(current.analytics);
    window.openModal('cookieSettingsModal');
    if (window.lucide) lucide.createIcons();
  };

  // Initial check on page load: show banner only if consent not yet given
  const existingConsent = getSavedCookiePreferences();
  if (!existingConsent && cookieBanner) {
    cookieBanner.style.display = 'block';
    setTimeout(() => {
      cookieBanner.classList.add('show');
      if (window.lucide) lucide.createIcons();
    }, 450);
  }

  // Bind Cookie Banner Actions
  const btnAcceptAll = document.getElementById('cookieAcceptAll');
  if (btnAcceptAll) {
    btnAcceptAll.addEventListener('click', () => {
      saveCookiePreferences({ functional: true, analytics: true });
      if (window.showToast) {
        showToast('Cookie preferences saved: All cookies accepted.', 'success');
      }
    });
  }

  const btnRejectOptional = document.getElementById('cookieRejectOptional');
  if (btnRejectOptional) {
    btnRejectOptional.addEventListener('click', () => {
      saveCookiePreferences({ functional: false, analytics: false });
      if (window.showToast) {
        showToast('Only essential cookies are enabled.', 'info');
      }
    });
  }

  const btnCustomize = document.getElementById('cookieCustomize');
  if (btnCustomize) {
    btnCustomize.addEventListener('click', () => {
      window.openCookieSettings();
    });
  }

  const btnSaveCustom = document.getElementById('cookieSaveCustom');
  if (btnSaveCustom) {
    btnSaveCustom.addEventListener('click', () => {
      const funcVal = prefFunctional ? prefFunctional.checked : false;
      const analVal = prefAnalytics ? prefAnalytics.checked : false;
      saveCookiePreferences({ functional: funcVal, analytics: analVal });
      if (window.showToast) {
        showToast('Cookie preferences updated successfully.', 'success');
      }
    });
  }

  // 16. Two-State Fixed Dashboard Sidebar & Mobile Drawer Controller
  const sidebar = document.getElementById('dashboardSidebar');
  const sidebarToggleBtn = document.getElementById('sidebarToggleBtn');
  const sidebarTooltip = document.getElementById('sidebarToggleTooltip');
  const sidebarBackdrop = document.getElementById('sidebarBackdrop');

  if (sidebar) {
    document.documentElement.classList.add('has-dashboard');
    document.body.classList.add('has-dashboard');
  }

  function updateSidebarState(isCollapsed) {
    if (!sidebar) return;
    if (isCollapsed) {
      sidebar.classList.add('sidebar-collapsed');
      document.body.classList.add('sidebar-collapsed');
      if (sidebarToggleBtn) {
        sidebarToggleBtn.setAttribute('aria-expanded', 'false');
        sidebarToggleBtn.setAttribute('title', 'Open Menu');
      }
      if (sidebarTooltip) {
        sidebarTooltip.textContent = 'Open Menu';
      }
    } else {
      sidebar.classList.remove('sidebar-collapsed');
      document.body.classList.remove('sidebar-collapsed');
      if (sidebarToggleBtn) {
        sidebarToggleBtn.setAttribute('aria-expanded', 'true');
        sidebarToggleBtn.setAttribute('title', 'Collapse Menu');
      }
      if (sidebarTooltip) {
        sidebarTooltip.textContent = 'Collapse Menu';
      }
    }
    if (window.lucide) {
      lucide.createIcons();
    }
  }

  // Restore saved collapse state from localStorage
  if (sidebar) {
    const savedCollapsed = localStorage.getItem('civic_sidebar_collapsed') === 'true';
    if (savedCollapsed) {
      updateSidebarState(true);
    }

    if (sidebarToggleBtn) {
      sidebarToggleBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const currentlyCollapsed = sidebar.classList.contains('sidebar-collapsed');
        const nextState = !currentlyCollapsed;
        updateSidebarState(nextState);
        localStorage.setItem('civic_sidebar_collapsed', nextState ? 'true' : 'false');
      });
    }
  }

  // Mobile Drawer Toggle
  window.toggleMobileSidebar = function(open) {
    if (!sidebar) return;
    const shouldOpen = (open !== undefined) ? open : !sidebar.classList.contains('mobile-open');
    if (shouldOpen) {
      sidebar.classList.add('mobile-open');
      if (sidebarBackdrop) sidebarBackdrop.classList.add('mobile-open');
      document.body.style.overflow = 'hidden';
    } else {
      sidebar.classList.remove('mobile-open');
      if (sidebarBackdrop) sidebarBackdrop.classList.remove('mobile-open');
      document.body.style.overflow = '';
    }
    if (window.lucide) {
      lucide.createIcons();
    }
  };

  // Close mobile sidebar on backdrop click or Escape key
  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener('click', () => {
      window.toggleMobileSidebar(false);
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (sidebar && sidebar.classList.contains('mobile-open')) {
        window.toggleMobileSidebar(false);
      }
    }
  });

  // 14. Global Form Restrictions: Email format & Mobile Numbers (Only digits 0-9)
  function isMobileInput(el) {
    if (!el || el.tagName !== 'INPUT') return false;
    const name = (el.name || '').toLowerCase();
    const id = (el.id || '').toLowerCase();
    const type = (el.type || '').toLowerCase();
    return type === 'tel' ||
           name === 'mobile' ||
           name === 'phone' ||
           name === 'contact_phone' ||
           name === 'mobile_number' ||
           id.includes('mobile') ||
           id.includes('phone');
  }

  function isEmailInput(el) {
    if (!el || el.tagName !== 'INPUT') return false;
    const name = (el.name || '').toLowerCase();
    const id = (el.id || '').toLowerCase();
    const type = (el.type || '').toLowerCase();
    return type === 'email' || name === 'email' || id.includes('email');
  }

  // Prevent non-numeric characters from being typed in mobile inputs
  document.addEventListener('keypress', (e) => {
    if (isMobileInput(e.target)) {
      if (e.ctrlKey || e.metaKey) return;
      if (!/^\d$/.test(e.key)) {
        e.preventDefault();
      }
    }
    if (isEmailInput(e.target)) {
      // Disallow space bar in email fields
      if (e.key === ' ') {
        e.preventDefault();
      }
    }
  });

  // Filter input value in real-time
  document.addEventListener('input', (e) => {
    if (isMobileInput(e.target)) {
      const orig = e.target.value;
      const filtered = orig.replace(/\D/g, '').slice(0, 10);
      if (orig !== filtered) {
        e.target.value = filtered;
      }
    }
    if (isEmailInput(e.target)) {
      const orig = e.target.value;
      const filtered = orig.replace(/\s+/g, '');
      if (orig !== filtered) {
        e.target.value = filtered;
      }
    }
  });

  // Filter on paste
  document.addEventListener('paste', (e) => {
    if (isMobileInput(e.target)) {
      e.preventDefault();
      const text = (e.clipboardData || window.clipboardData).getData('text') || '';
      const digits = text.replace(/\D/g, '');
      const start = e.target.selectionStart || 0;
      const end = e.target.selectionEnd || 0;
      const current = e.target.value;
      const nextVal = (current.slice(0, start) + digits + current.slice(end)).slice(0, 10);
      e.target.value = nextVal;
      e.target.dispatchEvent(new Event('input', { bubbles: true }));
    }
    if (isEmailInput(e.target)) {
      e.preventDefault();
      const text = (e.clipboardData || window.clipboardData).getData('text') || '';
      const clean = text.replace(/\s+/g, '');
      const start = e.target.selectionStart || 0;
      const end = e.target.selectionEnd || 0;
      const current = e.target.value;
      e.target.value = current.slice(0, start) + clean + current.slice(end);
      e.target.dispatchEvent(new Event('input', { bubbles: true }));
    }
  });

  // Finish top progress bar once DOM is completely rendered
  finishProgressBar();
});
