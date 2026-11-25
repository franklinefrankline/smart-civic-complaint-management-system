// Smart Civic Complaint System - Master UI & Interaction Engine
// Consistent 60fps transitions, accessible reduced-motion, loading states, and live micro-interactions

(function() {
  function getApiBase() {
    const meta = document.querySelector('meta[name="api-base-url"]');
    return meta ? (meta.getAttribute('content') || '').replace(/\/+$/, '') : '';
  }

  window.getApiUrl = function(path) {
    const base = getApiBase();
    if (!base) return path;
    if (/^https?:\/\//i.test(path)) return path;
    return base + (path.startsWith('/') ? path : '/' + path);
  };

  window.apiFetch = function(path, options) {
    const opts = Object.assign({ credentials: 'include' }, options || {});
    return fetch(window.getApiUrl(path), opts);
  };

  // Global Full-Screen Page Loader Controller (#020D1C + Exact Animated GIF)
  let loaderTimeoutId = null;
  let loaderDelayId = null;
  let activeRetryHandler = null;

  function getLoaderEls() {
    return {
      overlay: document.getElementById('globalPageLoader'),
      stage: document.getElementById('globalPageLoaderStage'),
      img: document.getElementById('globalPageLoaderImg'),
      errBox: document.getElementById('globalPageLoaderError'),
      errMsg: document.getElementById('globalPageLoaderErrorText'),
      retryBtn: document.getElementById('globalPageLoaderRetryBtn')
    };
  }

  function clearLoaderTimers() {
    if (loaderDelayId) {
      clearTimeout(loaderDelayId);
      loaderDelayId = null;
    }
    if (loaderTimeoutId) {
      clearTimeout(loaderTimeoutId);
      loaderTimeoutId = null;
    }
    if (window.__loaderFailsafeTimer) {
      clearTimeout(window.__loaderFailsafeTimer);
      window.__loaderFailsafeTimer = null;
    }
  }

  window.showGlobalLoaderError = function(message, retryCallback) {
    const { overlay, stage, img, errBox, errMsg, retryBtn } = getLoaderEls();
    if (!overlay) return;
    clearLoaderTimers();
    activeRetryHandler = typeof retryCallback === 'function' ? retryCallback : function() { window.location.reload(); };
    if (stage) stage.hidden = true;
    if (img) img.hidden = true;
    if (errMsg) errMsg.textContent = message || 'Unable to load page content. Please check your connection and try again.';
    if (errBox) errBox.hidden = false;
    overlay.classList.remove('is-hidden');
    overlay.setAttribute('aria-busy', 'false');
    document.body.classList.add('loader-locked');
    if (retryBtn && !retryBtn.dataset.boundRetry) {
      retryBtn.dataset.boundRetry = '1';
      retryBtn.addEventListener('click', function() {
        const cb = activeRetryHandler || function() { window.location.reload(); };
        window.showGlobalLoader({ timeoutMs: 20000, onRetry: cb });
        cb();
      });
    }
  };

  window.showGlobalLoader = function(options) {
    const opts = options || {};
    const { overlay, stage, img, errBox, retryBtn } = getLoaderEls();
    if (!overlay) return;
    clearLoaderTimers();
    if (stage) stage.hidden = false;
    if (img) img.hidden = false;
    if (errBox) errBox.hidden = true;
    overlay.classList.remove('is-hidden');
    overlay.setAttribute('aria-busy', 'true');
    document.body.classList.add('loader-locked');
    activeRetryHandler = typeof opts.onRetry === 'function' ? opts.onRetry : null;
    if (retryBtn && !retryBtn.dataset.boundRetry) {
      retryBtn.dataset.boundRetry = '1';
      retryBtn.addEventListener('click', function() {
        const cb = activeRetryHandler || function() { window.location.reload(); };
        window.showGlobalLoader({ timeoutMs: 20000, onRetry: cb });
        cb();
      });
    }
    const timeoutMs = typeof opts.timeoutMs === 'number' ? opts.timeoutMs : 20000;
    if (timeoutMs > 0) {
      loaderTimeoutId = setTimeout(function() {
        if (!overlay.classList.contains('is-hidden')) {
          window.showGlobalLoaderError(
            navigator.onLine === false
              ? 'You appear to be offline. Please check your connection and retry.'
              : 'Loading took longer than expected. Please try again.',
            activeRetryHandler || function() { window.location.reload(); }
          );
        }
      }, timeoutMs);
    }
  };

  window.hideGlobalLoader = function() {
    const { overlay, stage, img, errBox } = getLoaderEls();
    if (!overlay) return;
    clearLoaderTimers();
    overlay.classList.add('is-hidden');
    overlay.setAttribute('aria-busy', 'false');
    document.body.classList.remove('loader-locked');
    document.documentElement.classList.remove('loader-locked');
    if (errBox) errBox.hidden = true;
    if (stage) stage.hidden = false;
    if (img) img.hidden = false;
  };

  window.scheduleNavigationLoader = function(options, delayMs) {
    clearLoaderTimers();
    const wait = typeof delayMs === 'number' ? delayMs : 350;
    loaderDelayId = setTimeout(function() {
      loaderDelayId = null;
      window.showGlobalLoader(options || { timeoutMs: 20000 });
    }, wait);
  };

  window.addEventListener('pagehide', clearLoaderTimers);
  window.addEventListener('pageshow', function(e) {
    if (e.persisted || document.readyState === 'complete') {
      window.hideGlobalLoader();
      if (window.finishProgressBar) window.finishProgressBar();
    }
  });

  window.handleSmartBack = function(fallbackUrl) {
    const fallback = fallbackUrl || '/';
    try {
      if (window.history.length > 1 && document.referrer) {
        const refUrl = new URL(document.referrer, window.location.origin);
        if (refUrl.origin === window.location.origin && refUrl.href !== window.location.href) {
          window.showGlobalLoader({ timeoutMs: 20000 });
          window.history.back();
          return;
        }
      }
    } catch (_) {}
    window.showGlobalLoader({ timeoutMs: 20000 });
    window.location.href = fallback;
  };
})();

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

  // 7. Centralized Form Validation (Zero Native Tooltips), Confirmation Delegation & Double-Submit Protection
  initFormInteractions();

  function getFriendlyValidationMessage(el) {
    const labelEl = el.closest('.form-group, .auth-input-group')?.querySelector('label');
    const rawLabel = labelEl ? labelEl.textContent.replace(/\*/g, '').trim() : (el.getAttribute('name') || 'This field');
    const v = el.validity;
    if (v.valueMissing) return `${rawLabel} is required.`;
    if (v.typeMismatch && el.type === 'email') return 'Please enter a valid email address.';
    if (v.tooShort) return `${rawLabel} must be at least ${el.minLength} characters.`;
    if (v.tooLong) return `${rawLabel} must be no more than ${el.maxLength} characters.`;
    if (v.patternMismatch) return `Please enter a valid ${rawLabel.toLowerCase()} format.`;
    if (v.rangeUnderflow) return `${rawLabel} must be at least ${el.min}.`;
    if (v.rangeOverflow) return `${rawLabel} must be at most ${el.max}.`;
    return el.validationMessage || `Please check ${rawLabel}.`;
  }

  function clearFieldValidation(el) {
    el.classList.remove('is-invalid');
    const group = el.closest('.form-group, .auth-input-group') || el.parentElement;
    if (group) {
      const existingErr = group.querySelector('.field-validation-error');
      if (existingErr) existingErr.remove();
    }
  }

  function showFieldValidation(el, message) {
    clearFieldValidation(el);
    el.classList.add('is-invalid', 'input-error-shake');
    setTimeout(() => el.classList.remove('input-error-shake'), 400);

    const group = el.closest('.form-group, .auth-input-group') || el.parentElement;
    if (group) {
      const errDiv = document.createElement('div');
      errDiv.className = 'field-validation-error';
      errDiv.innerHTML = `<i data-lucide="alert-circle" class="icon-xs"></i><span>${escapeHtml(message)}</span>`;
      group.appendChild(errDiv);
      if (window.lucide) lucide.createIcons();
    }
  }

  function isElementVisible(el) {
    return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  }

  function initFormInteractions() {
    // Suppress browser-native validation tooltips on all forms
    document.querySelectorAll('form').forEach(f => {
      f.noValidate = true;
    });

    // Clear validation state as soon as the user updates an input
    document.addEventListener('input', (e) => {
      if (e.target && e.target.classList && e.target.classList.contains('is-invalid')) {
        clearFieldValidation(e.target);
      }
    });
    document.addEventListener('change', (e) => {
      if (e.target && e.target.classList && e.target.classList.contains('is-invalid')) {
        clearFieldValidation(e.target);
      }
    });

    // Suppress any residual native invalid tooltip events globally
    document.addEventListener('invalid', (e) => {
      e.preventDefault();
    }, true);

    // Delegated form submit handler: custom validation -> custom confirm -> loading lock
    document.addEventListener('submit', async (e) => {
      const form = e.target;
      if (!form || form.tagName !== 'FORM') return;
      form.noValidate = true;

      // Skip forms with dedicated custom AJAX validation managers (e.g. addUserForm)
      if (form.id === 'addUserForm') return;

      // 1. Custom in-page validation (no native browser tooltips)
      const controls = Array.from(form.querySelectorAll('input, select, textarea'));
      let firstInvalid = null;
      let firstMsg = null;

      controls.forEach(el => {
        if (el.disabled || el.type === 'hidden') return;
        clearFieldValidation(el);
        if (!el.checkValidity()) {
          const msg = getFriendlyValidationMessage(el);
          if (isElementVisible(el)) {
            showFieldValidation(el, msg);
          }
          if (!firstInvalid) {
            firstInvalid = el;
            firstMsg = msg;
          }
        }
      });

      if (firstInvalid) {
        e.preventDefault();
        e.stopImmediatePropagation();
        if (isElementVisible(firstInvalid)) {
          firstInvalid.focus();
        }
        if (window.showToast && firstMsg) {
          window.showToast(firstMsg, 'warning', 'Please Check Required Fields', 4500);
        }
        return;
      }

      // 2. Dynamic conditional confirmation (e.g. Reject status in admin status override)
      const newStatusSel = form.querySelector('select[name="new_status"]');
      const actionInput = form.querySelector('input[name="action"]');
      let dynamicConfirmMsg = form.getAttribute('data-confirm');
      let dynamicConfirmTitle = form.getAttribute('data-confirm-title') || 'Confirm Action';
      let dynamicConfirmBtn = form.getAttribute('data-confirm-btn') || 'Confirm';
      let dynamicVariant = form.getAttribute('data-confirm-variant') || 'danger';

      if (!dynamicConfirmMsg && actionInput && actionInput.value === 'change_status' && newStatusSel) {
        dynamicConfirmTitle = 'Confirm Status Update';
        dynamicConfirmMsg = `Are you sure you want to change the complaint status to "${newStatusSel.value}"?`;
        dynamicConfirmBtn = 'Update Status';
        dynamicVariant = newStatusSel.value === 'Rejected' ? 'danger' : 'warning';
      }

      if (dynamicConfirmMsg && form.dataset.confirmed !== '1') {
        e.preventDefault();
        e.stopImmediatePropagation();
        const confirmed = await window.showConfirm({
          title: dynamicConfirmTitle,
          message: dynamicConfirmMsg,
          confirmText: dynamicConfirmBtn,
          cancelText: 'Cancel',
          variant: dynamicVariant
        });
        if (!confirmed) return;

        form.dataset.confirmed = '1';
      }

      // 3. Progressive Async Action Submission (Zero full-page reload for dashboard actions & contact form)
      const method = (form.getAttribute('method') || 'GET').toUpperCase();
      const actionAttr = (form.getAttribute('action') || window.location.pathname).trim();
      const lowerAction = actionAttr.toLowerCase();
      const inDashboard = Boolean(form.closest('.dashboard-content'));
      const isExportOrBlank = form.getAttribute('target') === '_blank' ||
        lowerAction.includes('/export') ||
        lowerAction.includes('/download') ||
        form.hasAttribute('data-ajax') ||
        form.hasAttribute('data-full-reload');

      const isAsyncPostAction = method === 'POST' && !isExportOrBlank &&
        !lowerAction.includes('/auth/') &&
        !lowerAction.includes('/clean-demo-data') &&
        !lowerAction.endsWith('/complaints/new') &&
        (inDashboard || lowerAction.endsWith('/contact'));

      const isAsyncGetFilter = method === 'GET' && inDashboard && !isExportOrBlank && !form.hasAttribute('data-no-async');

      const submitBtn = e.submitter || form.querySelector('button[type="submit"], input[type="submit"]');

      if (isAsyncGetFilter) {
        e.preventDefault();
        const params = new URLSearchParams(new FormData(form));
        const basePath = actionAttr.split('?')[0] || window.location.pathname;
        const nextUrl = params.toString() ? `${basePath}?${params.toString()}` : basePath;
        if (submitBtn) {
          submitBtn.classList.add('btn-loading');
          submitBtn.disabled = true;
        }
        startProgressBar();
        try {
          if (window.history && window.history.pushState) {
            window.history.pushState({}, '', nextUrl);
          }
          await window.refreshDashboardContent(nextUrl);
        } catch (err) {
          window.location.href = nextUrl;
        } finally {
          finishProgressBar();
          if (submitBtn) {
            submitBtn.classList.remove('btn-loading');
            submitBtn.disabled = false;
          }
        }
        return;
      }

      if (isAsyncPostAction) {
        e.preventDefault();
        if (submitBtn && submitBtn.disabled) return;
        if (submitBtn) {
          submitBtn.classList.add('btn-loading');
          submitBtn.disabled = true;
        }
        startProgressBar();
        const controller = new AbortController();
        const reqTimeout = setTimeout(() => controller.abort(), 25000);
        try {
          const targetUrl = window.getApiUrl ? window.getApiUrl(actionAttr) : actionAttr;
          const res = await fetch(targetUrl, {
            method: 'POST',
            body: new FormData(form),
            headers: {
              'X-Requested-With': 'XMLHttpRequest',
              'Accept': 'application/json'
            },
            credentials: 'include',
            signal: controller.signal
          });
          clearTimeout(reqTimeout);
          const contentType = res.headers.get('content-type') || '';
          if (!contentType.includes('application/json')) {
            if (res.redirected && res.url) {
              window.location.href = res.url;
              return;
            }
            throw new Error(`Unexpected response (${res.status})`);
          }
          const data = await res.json();
          if (!res.ok || data.success === false) {
            throw new Error(data.message || `Action failed (${res.status})`);
          }

          if (window.showToast && data.message) {
            window.showToast(data.message, 'success');
          }

          // Optimistic instant DOM updates for contact message review & public contact inquiry
          if (lowerAction.includes('/contact-messages/') && lowerAction.endsWith('/read')) {
            const row = form.closest('tr, .contact-inquiry-row, div');
            const badge = document.createElement('span');
            badge.className = 'badge badge-resolved';
            badge.textContent = 'Reviewed';
            form.replaceWith(badge);
            const unreadPill = document.querySelector('#contactInquiriesCard .badge');
            if (unreadPill && typeof data.unread_contact_count === 'number') {
              unreadPill.textContent = data.unread_contact_count > 0 ? `${data.unread_contact_count} Unread` : 'All Reviewed';
            }
          } else if (lowerAction.endsWith('/contact')) {
            form.reset();
          } else if (data.reload_sections && window.refreshDashboardContent) {
            await window.refreshDashboardContent();
          }
          window.dispatchEvent(new Event('focus'));
        } catch (err) {
          clearTimeout(reqTimeout);
          const errMsg = err && err.name === 'AbortError'
            ? 'Request timed out. Please check your connection and try again.'
            : (err && err.message ? err.message : 'Operation failed. Please try again.');
          if (window.showToast) {
            window.showToast(errMsg, 'error');
          }
        } finally {
          form.dataset.confirmed = '';
          finishProgressBar();
          if (submitBtn && submitBtn.isConnected) {
            submitBtn.classList.remove('btn-loading');
            submitBtn.disabled = false;
          }
        }
        return;
      }

      // 4. Full-page navigation submit (login, register, new complaint): protect double submit
      if (e.defaultPrevented) return;
      if (form.dataset.confirmed === '1') {
        if (submitBtn) {
          submitBtn.classList.add('btn-loading');
          submitBtn.disabled = true;
        }
        startProgressBar();
        if (!isExportOrBlank) {
          window.scheduleNavigationLoader({ timeoutMs: 25000 }, 350);
        }
        HTMLFormElement.prototype.submit.call(form);
        return;
      }

      if (submitBtn && !submitBtn.disabled) {
        submitBtn.classList.add('btn-loading');
        submitBtn.disabled = true;
        startProgressBar();
        if (!isExportOrBlank) {
          window.scheduleNavigationLoader({ timeoutMs: 25000 }, 350);
        }
        setTimeout(() => {
          submitBtn.classList.remove('btn-loading');
          submitBtn.disabled = false;
          finishProgressBar();
        }, 12000);
      } else if (!isExportOrBlank) {
        window.scheduleNavigationLoader({ timeoutMs: 25000 }, 350);
      }
    });

    // Delegated custom confirmation for links/buttons (e.g., Sign Out / Logout)
    document.addEventListener('click', async (e) => {
      const target = e.target.closest('a[data-confirm], button[data-confirm]:not([type="submit"])');
      if (!target) return;

      e.preventDefault();
      e.stopPropagation();

      const confirmed = await window.showConfirm({
        title: target.getAttribute('data-confirm-title') || 'Confirm Action',
        message: target.getAttribute('data-confirm'),
        confirmText: target.getAttribute('data-confirm-btn') || 'Confirm',
        cancelText: 'Cancel',
        variant: target.getAttribute('data-confirm-variant') || 'warning'
      });

      if (confirmed) {
        const href = target.getAttribute('href');
        if (href) {
          startProgressBar();
          if (navigator.onLine === false) {
            window.showGlobalLoaderError('You appear to be offline. Please check your connection and retry.', () => {
              window.location.href = href;
            });
            return;
          }
          window.showGlobalLoader({
            timeoutMs: 20000,
            onRetry: () => { window.location.href = href; }
          });
          window.location.href = href;
        }
      }
    });
  }

  // 8. Top Page Progress Bar & Background Dashboard Section Refresh (Zero Full-Page Reload)
  let activeRefreshController = null;
  window.refreshDashboardContent = async function(targetUrl) {
    const dashContent = document.querySelector('.dashboard-content');
    if (!dashContent) {
      window.location.href = targetUrl || window.location.href;
      return;
    }
    if (activeRefreshController) {
      try { activeRefreshController.abort(); } catch (_) {}
    }
    activeRefreshController = new AbortController();
    const fetchUrl = targetUrl || window.location.href;
    const prevScrollTop = dashContent.scrollTop;
    const prevWinY = window.scrollY;
    const res = await fetch(fetchUrl, {
      credentials: 'include',
      headers: { 'X-Async-Partial': '1' },
      signal: activeRefreshController.signal
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const html = await res.text();
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const nextDash = doc.querySelector('.dashboard-content');
    if (!nextDash) {
      window.location.href = fetchUrl;
      return;
    }
    dashContent.innerHTML = nextDash.innerHTML;
    dashContent.querySelectorAll('form').forEach(f => { f.noValidate = true; });
    if (window.initStarRatings) window.initStarRatings(dashContent);
    if (typeof window.filterOfficersByDept === 'function') {
      const deptSel = dashContent.querySelector('#admin_dept_select');
      if (deptSel) window.filterOfficersByDept(deptSel.value);
    }
    if (window.lucide) lucide.createIcons();
    dashContent.scrollTop = prevScrollTop;
    window.scrollTo(0, prevWinY);
  };

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

  // Delegated Async Pagination & Full-Page Navigation Link Click Triggers
  document.addEventListener('click', async (e) => {
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    const pageLink = e.target.closest('a.pagination-link[href]');
    if (pageLink && pageLink.closest('.dashboard-content')) {
      e.preventDefault();
      const nextUrl = pageLink.href;
      startProgressBar();
      try {
        if (window.history && window.history.pushState) {
          window.history.pushState({}, '', nextUrl);
        }
        await window.refreshDashboardContent(nextUrl);
      } catch (_) {
        window.location.href = nextUrl;
      } finally {
        finishProgressBar();
      }
      return;
    }
    const link = e.target.closest('a[href]');
    if (!link) return;
    if (link.hasAttribute('data-confirm') || link.hasAttribute('download') || link.hasAttribute('data-no-loader')) return;
    if (link.getAttribute('target') === '_blank') return;

    const href = (link.getAttribute('href') || '').trim();
    if (!href || href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:') || href.startsWith('tel:')) return;
    const lowerHref = href.toLowerCase();
    if (lowerHref.includes('/export') || lowerHref.includes('/download') || lowerHref.includes('/attachments/') || lowerHref.includes('/proofs/')) return;

    startProgressBar();
    if (navigator.onLine === false) {
      e.preventDefault();
      window.showGlobalLoaderError('You appear to be offline. Please check your connection and retry.', () => {
        window.location.href = href;
      });
      return;
    }

    try {
      const dest = new URL(link.href, window.location.origin);
      if (dest.origin === window.location.origin) {
        window.scheduleNavigationLoader({
          timeoutMs: 20000,
          onRetry: () => { window.location.href = dest.href; }
        }, 350);
      }
    } catch (_) {
      window.scheduleNavigationLoader({ timeoutMs: 20000 }, 350);
    }
  });

  // 9. Centralized Website Notification & Confirmation System
  // Reusable providers/APIs: ToastNotification, ToastContainer, ConfirmDialog, NotificationProvider, useNotification, useConfirmation
  let activeConfirmResolve = null;
  let lastTriggerElement = null;

  window.showConfirm = function(options) {
    const opts = typeof options === 'string' ? { message: options } : (options || {});
    const modal = document.getElementById('sccmtConfirmModal');
    const titleEl = document.getElementById('sccmtConfirmTitle');
    const msgEl = document.getElementById('sccmtConfirmMessage');
    const cancelBtn = document.getElementById('sccmtConfirmCancelBtn');
    const okBtn = document.getElementById('sccmtConfirmOkBtn');
    const iconWrap = document.getElementById('sccmtConfirmIconWrap');

    if (!modal || !titleEl || !msgEl || !cancelBtn || !okBtn) {
      return Promise.resolve(false);
    }

    if (activeConfirmResolve) {
      activeConfirmResolve(false);
      activeConfirmResolve = null;
    }

    lastTriggerElement = document.activeElement;
    const variant = opts.variant || 'danger';
    titleEl.textContent = opts.title || 'Confirm Action';
    msgEl.textContent = opts.message || 'Are you sure you want to proceed?';
    cancelBtn.textContent = opts.cancelText || 'Cancel';
    okBtn.textContent = opts.confirmText || 'Confirm';

    // Reset button & icon classes
    okBtn.className = 'btn btn-sm ' + (
      variant === 'danger' ? 'btn-danger' :
      variant === 'warning' ? 'btn-warning-confirm' :
      'btn-primary'
    );

    if (iconWrap) {
      iconWrap.className = `confirm-modal-icon variant-${variant}`;
      const iconName = variant === 'danger' ? 'alert-triangle' : (variant === 'warning' ? 'alert-circle' : 'help-circle');
      iconWrap.innerHTML = `<i data-lucide="${iconName}" class="icon-md"></i>`;
      if (window.lucide) lucide.createIcons();
    }

    modal.style.display = 'flex';
    requestAnimationFrame(() => {
      modal.classList.add('show');
      cancelBtn.focus();
    });

    return new Promise((resolve) => {
      activeConfirmResolve = resolve;

      function finish(result) {
        if (!activeConfirmResolve) return;
        const cb = activeConfirmResolve;
        activeConfirmResolve = null;

        modal.classList.remove('show');
        setTimeout(() => {
          modal.style.display = 'none';
          if (lastTriggerElement && typeof lastTriggerElement.focus === 'function') {
            lastTriggerElement.focus();
          }
        }, 200);

        cancelBtn.removeEventListener('click', onCancel);
        okBtn.removeEventListener('click', onOk);
        modal.removeEventListener('click', onBackdrop);
        document.removeEventListener('keydown', onKeyDown);
        cb(result);
      }

      function onCancel() { finish(false); }
      function onOk() { finish(true); }
      function onBackdrop(ev) {
        if (ev.target === modal) finish(false);
      }
      function onKeyDown(ev) {
        if (ev.key === 'Escape') {
          ev.preventDefault();
          finish(false);
        }
      }

      cancelBtn.addEventListener('click', onCancel);
      okBtn.addEventListener('click', onOk);
      modal.addEventListener('click', onBackdrop);
      document.addEventListener('keydown', onKeyDown);
    });
  };

  window.showToast = function(message, type = 'info', title = null, duration = null) {
    const normalizedType = type === 'danger' ? 'error' : type;
    const defaultDurations = {
      success: 3600,
      error: 5000,
      warning: 4500,
      info: 4000
    };
    const finalDuration = duration || defaultDurations[normalizedType] || 4000;

    let container = document.getElementById('toastContainer');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toastContainer';
      container.className = 'toast-container';
      container.setAttribute('aria-live', 'polite');
      document.body.appendChild(container);
    }

    const iconMap = {
      success: 'check-circle-2',
      error: 'alert-circle',
      warning: 'alert-triangle',
      info: 'info'
    };

    const titleMap = {
      success: 'Success',
      error: 'Error',
      warning: 'Warning',
      info: 'Information'
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${normalizedType}`;
    toast.setAttribute('role', normalizedType === 'error' ? 'alert' : 'status');
    toast.innerHTML = `
      <div class="toast-icon"><i data-lucide="${iconMap[normalizedType] || 'info'}" class="icon-sm"></i></div>
      <div class="toast-content">
        <div class="toast-title">${escapeHtml(title || titleMap[normalizedType] || 'Update')}</div>
        <div>${escapeHtml(message)}</div>
      </div>
      <button type="button" class="toast-close-btn" aria-label="Close notification">&times;</button>
      <div class="toast-progress" style="animation-duration: ${finalDuration}ms;"></div>
    `;

    container.appendChild(toast);
    if (window.lucide) {
      lucide.createIcons();
    }

    requestAnimationFrame(() => {
      toast.classList.add('toast-show');
    });

    const closeBtn = toast.querySelector('.toast-close-btn');
    let timer = setTimeout(dismiss, finalDuration);

    function dismiss() {
      clearTimeout(timer);
      toast.classList.remove('toast-show');
      toast.classList.add('toast-hide');
      setTimeout(() => toast.remove(), 250);
    }

    closeBtn.addEventListener('click', dismiss);
  };

  window.NotificationProvider = {
    notify: window.showToast,
    success: (msg, title) => window.showToast(msg, 'success', title || 'Success', 3600),
    error: (msg, title) => window.showToast(msg, 'error', title || 'Error', 5000),
    warning: (msg, title) => window.showToast(msg, 'warning', title || 'Warning', 4500),
    info: (msg, title) => window.showToast(msg, 'info', title || 'Information', 4000)
  };
  window.ToastContainer = { show: window.showToast };
  window.ToastNotification = window.NotificationProvider;
  window.ConfirmDialog = { open: window.showConfirm };
  window.useNotification = () => window.NotificationProvider;
  window.useConfirmation = () => window.showConfirm;

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // 10. Star Rating Interactive Widget (Reusable on async content swaps)
  window.initStarRatings = function(rootEl) {
    (rootEl || document).querySelectorAll('.star-rating').forEach(ratingWidget => {
      if (ratingWidget.dataset.boundStars === '1') return;
      ratingWidget.dataset.boundStars = '1';
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
  };
  window.initStarRatings(document);

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
    mobileToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const sidebar = document.getElementById('dashboardSidebar');
      if (sidebar) {
        if (window.toggleMobileSidebar) {
          window.toggleMobileSidebar();
        }
      } else if (navLinks) {
        const isOpen = navLinks.classList.toggle('mobile-open');
        mobileToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      }
    });

    if (navLinks) {
      document.addEventListener('click', (e) => {
        if (navLinks.classList.contains('mobile-open') && !navLinks.contains(e.target) && !mobileToggle.contains(e.target)) {
          navLinks.classList.remove('mobile-open');
          mobileToggle.setAttribute('aria-expanded', 'false');
        }
      });
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && navLinks.classList.contains('mobile-open')) {
          navLinks.classList.remove('mobile-open');
          mobileToggle.setAttribute('aria-expanded', 'false');
        }
      });
    }
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

  // Finish top progress bar & smoothly hide initial global page loader once page content finishes loading
  finishProgressBar();

  // Global Back Navigation Button Handler + Auto Injection for Dashboard Pages Without One
  const dashContent = document.querySelector('.dashboard-content');
  if (dashContent && !dashContent.querySelector('[data-back-nav]')) {
    const hasExistingBackLink = Array.from(dashContent.querySelectorAll('a, button')).some(el => {
      const txt = (el.textContent || '').trim().toLowerCase();
      return txt.startsWith('← back') || txt.includes('back to ');
    });
    if (!hasExistingBackLink) {
      const roleMatch = window.location.pathname.match(/^\/(admin|citizen|officer|worker)\//);
      const fallbackUrl = roleMatch ? `/${roleMatch[1]}/dashboard` : '/';
      const bar = document.createElement('div');
      bar.className = 'page-back-bar';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-secondary btn-sm page-back-btn';
      btn.setAttribute('data-back-nav', '');
      btn.setAttribute('data-fallback-url', fallbackUrl);
      btn.innerHTML = '<i data-lucide="arrow-left" class="icon-xs"></i><span>Back</span>';
      bar.appendChild(btn);
      dashContent.insertBefore(bar, dashContent.firstChild);
      if (window.lucide) lucide.createIcons();
    }
  }

  document.addEventListener('click', (e) => {
    const backBtn = e.target.closest('[data-back-nav]');
    if (!backBtn) return;
    e.preventDefault();
    const fallbackUrl = backBtn.getAttribute('data-fallback-url') || '/';
    window.handleSmartBack(fallbackUrl);
  });

  const initialLoaderImg = document.getElementById('globalPageLoaderImg');
  if (initialLoaderImg) {
    initialLoaderImg.addEventListener('error', () => {
      // Fall back safely without breaking the page if an intermediary drops the GIF asset
      if (navigator.onLine === false) {
        window.showGlobalLoaderError('Unable to load application resources while offline. Please retry.', () => {
          window.location.reload();
        });
      }
    });
  }

  // Dismiss initial #globalPageLoader cleanly once DOM & deferred scripts finish (no multi-second CDN blocking)
  if (typeof requestAnimationFrame === 'function') {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => window.hideGlobalLoader());
    });
  } else {
    window.hideGlobalLoader();
  }
});
