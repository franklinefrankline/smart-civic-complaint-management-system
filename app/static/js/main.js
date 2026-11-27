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

  window.handleSmartBack = function(fallbackUrl) {
    const fallback = fallbackUrl || '/';
    try {
      if (window.history.length > 1 && document.referrer) {
        const refUrl = new URL(document.referrer, window.location.origin);
        if (refUrl.origin === window.location.origin && refUrl.href !== window.location.href) {
          window.history.back();
          return;
        }
      }
    } catch (_) {}
    window.location.href = fallback;
  };

  // Sync browser timezone offset cookie so server-rendered timestamps match local time immediately
  try {
    document.cookie = 'sccmt_tz_offset=' + new Date().getTimezoneOffset() + '; path=/; max-age=2592000; SameSite=Lax';
  } catch (_) {}

  const SHORT_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const FULL_MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const pad2 = (n) => (n < 10 ? '0' + n : String(n));

  function formatDateWithPattern(date, fmt) {
    const YYYY = date.getFullYear();
    const MM = pad2(date.getMonth() + 1);
    const dd = pad2(date.getDate());
    const HH24 = date.getHours();
    const HH = pad2(HH24);
    const h12 = HH24 % 12 || 12;
    const II = pad2(h12);
    const min = pad2(date.getMinutes());
    const sec = pad2(date.getSeconds());
    const ampm = HH24 >= 12 ? 'PM' : 'AM';
    const b = SHORT_MONTHS[date.getMonth()];
    const B = FULL_MONTHS[date.getMonth()];

    return fmt
      .replace(/%Y/g, YYYY)
      .replace(/%m/g, MM)
      .replace(/%d/g, dd)
      .replace(/%B/g, B)
      .replace(/%b/g, b)
      .replace(/%H/g, HH)
      .replace(/%I/g, II)
      .replace(/%M/g, min)
      .replace(/%S/g, sec)
      .replace(/%p/g, ampm);
  }

  window.formatLocalTimes = function(root) {
    const scope = root || document;
    scope.querySelectorAll('time[data-utc]').forEach(el => {
      const utcStr = el.getAttribute('data-utc');
      if (!utcStr) return;
      const d = new Date(utcStr);
      if (isNaN(d.getTime())) return;
      const fmt = el.getAttribute('data-fmt') || '%d %b %Y, %I:%M %p';
      el.textContent = formatDateWithPattern(d, fmt);
    });
  };

  // Modal & Persistent Alert Popup Controllers (Exposed synchronously so template DOMContentLoaded listeners always see them)
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

  let persistentAlertOnClose = null;
  let persistentAlertPrevFocus = null;

  window.closePersistentAlertPopup = function() {
    const modal = document.getElementById('scfPersistentAlertModal');
    if (!modal || (!modal.classList.contains('show') && modal.style.display === 'none')) return;

    const cb = persistentAlertOnClose;
    const prevFocus = persistentAlertPrevFocus;
    persistentAlertOnClose = null;
    persistentAlertPrevFocus = null;

    modal.classList.remove('show');
    setTimeout(() => {
      modal.style.display = 'none';
      if (typeof cb === 'function') {
        try { cb(); } catch (_) {}
      } else if (prevFocus && typeof prevFocus.focus === 'function') {
        try { prevFocus.focus(); } catch (_) {}
      }
    }, 180);
  };

  window.showPersistentAlertPopup = function(options) {
    const opts = typeof options === 'string' ? { message: options } : (options || {});
    const modal = document.getElementById('scfPersistentAlertModal');
    const titleEl = document.getElementById('scfPersistentAlertTitle');
    const msgEl = document.getElementById('scfPersistentAlertMessage');
    const iconWrap = document.getElementById('scfPersistentAlertIconWrap');
    const closeBtn = document.getElementById('scfPersistentAlertCloseBtn');
    const footerBtn = document.getElementById('scfPersistentAlertFooterBtn');

    // Suppress any top-right flash/toast alert so only the single center popup is visible
    const flashWrap = document.getElementById('flashToastContainer');
    if (flashWrap) flashWrap.remove();
    const toastWrap = document.getElementById('toastContainer');
    if (toastWrap) toastWrap.innerHTML = '';

    if (!modal || !titleEl || !msgEl) {
      if (window.showToast && opts.message) {
        window.showToast(opts.message, opts.variant === 'success' ? 'success' : 'error', opts.title);
      }
      return;
    }

    if (!modal.dataset.boundPersistentAlert) {
      modal.dataset.boundPersistentAlert = '1';
      if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          window.closePersistentAlertPopup();
        });
      }
      if (footerBtn) {
        footerBtn.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          window.closePersistentAlertPopup();
        });
      }
    }

    persistentAlertPrevFocus = document.activeElement;
    persistentAlertOnClose = typeof opts.onClose === 'function' ? opts.onClose : null;

    const variant = opts.variant || 'danger';
    titleEl.textContent = opts.title || (variant === 'success' ? 'Success' : 'Validation Alert');
    msgEl.textContent = opts.message || '';

    if (footerBtn) {
      footerBtn.textContent = opts.closeText || 'Close';
      footerBtn.className = 'btn btn-sm ' + (variant === 'success' ? 'btn-primary' : 'btn-danger');
    }

    if (iconWrap) {
      iconWrap.className = `confirm-modal-icon variant-${variant}`;
      const iconName = variant === 'success'
        ? 'check-circle-2'
        : (variant === 'warning' ? 'alert-triangle' : 'alert-octagon');
      iconWrap.innerHTML = `<i data-lucide="${iconName}" class="icon-md"></i>`;
      if (window.lucide) lucide.createIcons();
    }

    modal.style.display = 'flex';
    requestAnimationFrame(() => {
      modal.classList.add('show');
      if (closeBtn) closeBtn.focus();
    });
  };

  window.__userModalConfigs = window.__userModalConfigs || {};
  window.rebindUserCreateModalForms = function() {
    Object.values(window.__userModalConfigs).forEach((savedCfg) => {
      if (savedCfg && document.getElementById(savedCfg.formId)) {
        window.bindUserCreateModalForm(savedCfg);
      }
    });
  };

  window.bindUserCreateModalForm = function(cfg) {
    if (!cfg || !cfg.formId) return;
    window.__userModalConfigs[cfg.formId] = cfg;

    const form = document.getElementById(cfg.formId);
    if (!form || form.dataset.userModalBound === '1') return;
    form.dataset.userModalBound = '1';

    const emailMsgDup = 'This email address is already associated with an existing account. Please enter a different email address.';
    const mobileMsgDup = 'This phone number is already associated with an existing account. Please enter a different phone number.';

    const getAlert = () => (cfg.alertId ? document.getElementById(cfg.alertId) : null);
    const getAlertMsg = () => (cfg.messageId ? document.getElementById(cfg.messageId) : null);
    const getField = (name) => form.querySelector(`[name="${name}"]`);

    function setFieldError(el, hintText) {
      if (!el) return;
      el.classList.add('is-invalid');
      el.style.borderColor = '#ef4444';
      el.style.boxShadow = '0 0 0 2px rgba(239, 68, 68, 0.2)';
      const group = el.closest('.form-group, .auth-input-group') || el.parentElement;
      if (group && hintText) {
        let hint = group.querySelector('.modal-field-hint');
        if (!hint) {
          hint = document.createElement('span');
          hint.className = 'form-hint modal-field-hint';
          hint.style.cssText = 'color: #ef4444; display: block; font-size: 0.8rem; margin-top: 0.3rem; font-weight: 500;';
          group.appendChild(hint);
        }
        hint.textContent = hintText;
        hint.style.display = 'block';
      }
    }

    function clearFieldError(el) {
      if (!el) return;
      el.classList.remove('is-invalid');
      el.style.borderColor = '';
      el.style.boxShadow = '';
      const group = el.closest('.form-group, .auth-input-group') || el.parentElement;
      const hint = group ? group.querySelector('.modal-field-hint') : null;
      if (hint) {
        hint.style.display = 'none';
        hint.textContent = '';
      }
    }

    function clearAllErrors() {
      const alertEl = getAlert();
      if (alertEl) alertEl.style.display = 'none';
      form.querySelectorAll('input, select, textarea').forEach(clearFieldError);
      if (cfg.emailHintId) {
        const eh = document.getElementById(cfg.emailHintId);
        if (eh) { eh.style.display = 'none'; eh.textContent = ''; }
      }
      if (cfg.mobileHintId) {
        const mh = document.getElementById(cfg.mobileHintId);
        if (mh) { mh.style.display = 'none'; mh.textContent = ''; }
      }
    }

    function resolvePopupTitle(field, backendTitle) {
      if (backendTitle) return backendTitle;
      if (field === 'both') return 'Account Details Already Exist!';
      if (field === 'email') return 'Email Already Registered!';
      if (field === 'mobile') return 'Phone Number Already Registered!';
      return 'Validation Error';
    }

    function highlightAndFocusField(field, message) {
      const emailEl = getField('email');
      const mobileEl = getField('mobile');
      let focusTarget = null;

      if (field === 'both') {
        setFieldError(emailEl, emailMsgDup);
        setFieldError(mobileEl, mobileMsgDup);
        focusTarget = emailEl;
      } else if (field === 'dept_both') {
        const nameEl = getField('name');
        const codeEl = getField('code');
        setFieldError(nameEl, 'Department name already exists.');
        setFieldError(codeEl, 'Department code already exists.');
        focusTarget = nameEl || codeEl;
      } else if (field === 'email') {
        setFieldError(emailEl, message);
        focusTarget = emailEl;
      } else if (field === 'mobile') {
        setFieldError(mobileEl, message);
        focusTarget = mobileEl;
      } else if (field) {
        const targetField = getField(field);
        setFieldError(targetField, message);
        focusTarget = targetField;
      }
      return focusTarget;
    }

    form.addEventListener('input', (e) => {
      if (e.target) clearFieldError(e.target);
    });
    form.addEventListener('change', (e) => {
      if (e.target) clearFieldError(e.target);
    });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (form.dataset.submitting === '1') return;
      clearAllErrors();

      if (typeof cfg.beforeSubmit === 'function') {
        const clientErr = cfg.beforeSubmit(form);
        if (clientErr && clientErr.message) {
          const alertEl = getAlert();
          const alertMsg = getAlertMsg();
          if (alertEl && alertMsg) {
            alertMsg.textContent = clientErr.message;
            alertEl.style.display = 'flex';
          }
          const focusEl = highlightAndFocusField(clientErr.field, clientErr.message);
          if (window.showPersistentAlertPopup) {
            window.showPersistentAlertPopup({
              title: clientErr.title || 'Validation Alert',
              message: clientErr.message,
              variant: 'danger',
              closeText: 'Close',
              onClose: () => { if (focusEl) focusEl.focus(); }
            });
          } else if (focusEl) {
            focusEl.focus();
          }
          return;
        }
      }

      form.dataset.submitting = '1';
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
      if (window.showPageLoader) window.showPageLoader('Saving...');

      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 25000);
      try {
        const rawAction = form.getAttribute('action') || window.location.pathname;
        const targetUrl = window.getApiUrl ? window.getApiUrl(rawAction) : rawAction;
        const res = await fetch(targetUrl, {
          method: 'POST',
          body: new FormData(form),
          credentials: 'include',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json'
          },
          signal: controller.signal
        });
        clearTimeout(timer);
        const data = await res.json().catch(() => null);

        if (res.ok && data && data.success) {
          window.__sccmtPauseLiveSyncUntil = Date.now() + 8000;
          if (window.hidePageLoader) window.hidePageLoader();

          if (cfg.isRegistration) {
            const redirectUrl = data.redirect || '/auth/login';
            if (window.showPersistentAlertPopup) {
              window.showPersistentAlertPopup({
                title: 'Account Created Successfully',
                message: data.message || 'Your account has been created. Please sign in to continue.',
                variant: 'success',
                closeText: 'Continue to Sign In',
                onClose: () => { window.location.href = redirectUrl; }
              });
            } else {
              window.location.href = redirectUrl;
            }
            return;
          }

          if (window.closeModal && cfg.modalId) window.closeModal(cfg.modalId);
          form.reset();
          if (typeof cfg.onAfterReset === 'function') {
            try { cfg.onAfterReset(form); } catch (_) {}
          }
          if (window.refreshDashboardContent) {
            await window.refreshDashboardContent();
          }
          if (window.showPersistentAlertPopup) {
            window.showPersistentAlertPopup({
              title: cfg.successTitle || 'Account Created Successfully',
              message: data.message || 'Changes have been saved successfully.',
              variant: 'success',
              closeText: 'Close'
            });
          }
          return;
        }

        const message = (data && data.message) ? data.message : 'Unable to save user details.';
        const field = data ? data.field : null;
        const title = resolvePopupTitle(field, data ? data.title : null);

        const alertEl = getAlert();
        const alertMsg = getAlertMsg();
        if (alertEl && alertMsg) {
          alertMsg.textContent = message;
          alertEl.style.display = 'flex';
          if (window.lucide) lucide.createIcons();
        }

        const focusTarget = highlightAndFocusField(field, message);

        if (window.showPersistentAlertPopup) {
          window.showPersistentAlertPopup({
            title: title,
            message: message,
            variant: 'danger',
            closeText: 'Close',
            onClose: () => {
              if (focusTarget) {
                focusTarget.focus();
                if (typeof focusTarget.select === 'function') focusTarget.select();
              }
            }
          });
        }
      } catch (err) {
        clearTimeout(timer);
        const msg = (err && err.name === 'AbortError')
          ? 'Server took too long to respond. Please try again.'
          : 'Network error while communicating with server.';
        const alertEl = getAlert();
        const alertMsg = getAlertMsg();
        if (alertEl && alertMsg) {
          alertMsg.textContent = msg;
          alertEl.style.display = 'flex';
        }
        if (window.showPersistentAlertPopup) {
          window.showPersistentAlertPopup({
            title: 'Request Error',
            message: msg,
            variant: 'danger',
            closeText: 'Close'
          });
        }
      } finally {
        delete form.dataset.submitting;
        if (window.hidePageLoader) window.hidePageLoader();
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  };
})();

document.addEventListener('DOMContentLoaded', () => {
  if (window.formatLocalTimes) window.formatLocalTimes(document);
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
  requestAnimationFrame(() => htmlEl.classList.add('theme-ready'));

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
      if (form.id === 'addUserForm' || form.hasAttribute('data-custom-ajax')) return;

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
        if (window.showPageLoader) window.showPageLoader('Filtering records...');
        try {
          if (window.history && window.history.pushState) {
            window.history.pushState({}, '', nextUrl);
          }
          await window.refreshDashboardContent(nextUrl);
        } catch (err) {
          if (!err || err.name !== 'AbortError') {
            window.location.href = nextUrl;
          }
        } finally {
          if (window.hidePageLoader) window.hidePageLoader();
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
        if (window.showPageLoader) window.showPageLoader('Processing request...');
        const controller = new AbortController();
        const reqTimeout = setTimeout(() => controller.abort(), 55000);
        let actionSucceeded = false;
        let responseData = null;
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
            if (res.status === 502 || res.status === 503 || res.status === 504) {
              throw new Error(`Server is waking up or busy (HTTP ${res.status}). Please retry in a few seconds.`);
            }
            throw new Error(`Unexpected response (${res.status}). Please try again.`);
          }
          const data = await res.json();
          if (!res.ok || data.success === false) {
            throw new Error(data.message || data.error || `Action failed (${res.status})`);
          }

          actionSucceeded = true;
          responseData = data;
          window.__sccmtPauseLiveSyncUntil = Date.now() + (data.reload_sections ? 10000 : 3500);

          if (window.showToast && data.message) {
            window.showToast(data.message, 'success');
          }

          // Optimistic instant DOM updates without extra round-trips where safe
          if (lowerAction.includes('/contact-messages/') && lowerAction.endsWith('/read')) {
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
          } else if (data.priority && !data.reload_sections) {
            document.querySelectorAll('.badge[class*="badge-priority-"]').forEach(el => {
              el.className = `badge badge-priority-${data.priority}`;
              el.textContent = String(data.priority).toUpperCase();
            });
          } else if (data.reload_sections && window.refreshDashboardContent) {
            // Unlock UI & hide loader right after POST succeeds so actions feel instant
            if (window.hidePageLoader) window.hidePageLoader();
            if (submitBtn && submitBtn.isConnected) {
              submitBtn.classList.remove('btn-loading');
              submitBtn.disabled = false;
            }
            try {
              await window.refreshDashboardContent();
            } catch (refreshErr) {
              if (!refreshErr || refreshErr.name !== 'AbortError') {
                window.location.reload();
                return;
              }
            }
          }
        } catch (err) {
          clearTimeout(reqTimeout);
          if (!actionSucceeded) {
            const errMsg = err && err.name === 'AbortError'
              ? 'Server took too long to respond. Please wait a moment and try again.'
              : (err && err.message ? err.message : 'Operation failed. Please try again.');
            if (window.showToast) {
              window.showToast(errMsg, 'error');
            }
          }
        } finally {
          if (window.hidePageLoader) window.hidePageLoader();
          form.dataset.confirmed = '';
          if (submitBtn && submitBtn.isConnected) {
            submitBtn.classList.remove('btn-loading');
            submitBtn.disabled = false;
          }
          if (actionSucceeded && responseData && !responseData.reload_sections) {
            window.dispatchEvent(new CustomEvent('sccmt:action-synced', { detail: responseData }));
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
        if (window.showPageLoader && !isExportOrBlank && !form.hasAttribute('data-no-loader')) {
          window.showPageLoader('Submitting...', 0, true);
        }
        HTMLFormElement.prototype.submit.call(form);
        return;
      }

      if (window.showPageLoader && !isExportOrBlank && !form.hasAttribute('data-no-loader')) {
        window.showPageLoader('Submitting...', 0, true);
      }
      if (submitBtn && !submitBtn.disabled) {
        submitBtn.classList.add('btn-loading');
        submitBtn.disabled = true;
        setTimeout(() => {
          submitBtn.classList.remove('btn-loading');
          submitBtn.disabled = false;
        }, 45000);
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
          if (navigator.onLine === false) {
            if (window.showToast) {
              window.showToast('You appear to be offline. Please check your connection and retry.', 'error');
            }
            return;
          }
          if (window.showPageLoader && !target.hasAttribute('data-no-loader')) {
            window.showPageLoader('Loading...', undefined, true);
          }
          window.location.href = href;
        }
      }
    });
  }

  // 8. Global Loader & Smooth Page Transition + Background Dashboard Refresh
  let loaderDelayTimer = null;
  let loaderAutoHideTimer = null;
  window.showPageLoader = function(message, delayMs, isNavTransition) {
    if (isNavTransition) {
      try { sessionStorage.setItem('scf_nav_transition', '1'); } catch (_) {}
    }
    const loader = document.getElementById('globalPageLoader');
    if (!loader) return;
    const textEl = document.getElementById('globalLoaderText');
    if (textEl) textEl.textContent = message || 'Loading...';

    const activate = () => {
      loader.classList.add('is-active');
      loader.setAttribute('aria-hidden', 'false');
      clearTimeout(loaderAutoHideTimer);
      loaderAutoHideTimer = setTimeout(() => {
        if (window.hidePageLoader) window.hidePageLoader();
      }, 25000);
    };

    clearTimeout(loaderDelayTimer);
    const delay = typeof delayMs === 'number' ? delayMs : 150;
    if (delay > 0) {
      loaderDelayTimer = setTimeout(activate, delay);
    } else {
      activate();
    }
  };

  window.hidePageLoader = function() {
    clearTimeout(loaderDelayTimer);
    clearTimeout(loaderAutoHideTimer);
    try { sessionStorage.removeItem('scf_nav_transition'); } catch (_) {}
    document.documentElement.classList.remove('scf-page-entering');
    const loader = document.getElementById('globalPageLoader');
    if (!loader) return;
    loader.classList.remove('is-active');
    loader.setAttribute('aria-hidden', 'true');
  };

  // Warm-cache loader.gif quietly after initial page paint so it never blocks first render
  window.addEventListener('load', () => {
    setTimeout(() => {
      const loaderImg = document.querySelector('#globalPageLoader img.global-loader-gif');
      if (loaderImg && loaderImg.src) {
        const pre = new Image();
        pre.src = loaderImg.src;
      }
    }, 600);
  }, { once: true });
  let activeRefreshController = null;
  let activeRefreshSuperseded = false;
  window.refreshDashboardContent = async function(targetUrl) {
    const dashContent = document.querySelector('.dashboard-content');
    if (!dashContent) {
      window.location.href = targetUrl || window.location.href;
      return;
    }
    if (activeRefreshController) {
      activeRefreshSuperseded = true;
      try { activeRefreshController.abort(); } catch (_) {}
    }
    const controller = new AbortController();
    activeRefreshController = controller;
    activeRefreshSuperseded = false;
    const timeoutId = setTimeout(() => controller.abort(), 15000);
    const fetchUrl = targetUrl || window.location.href;
    const prevScrollTop = dashContent.scrollTop;
    const prevWinY = window.scrollY;
    try {
      const res = await fetch(fetchUrl, {
        credentials: 'include',
        headers: { 'X-Async-Partial': '1' },
        signal: controller.signal
      });
      clearTimeout(timeoutId);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const existingErr = dashContent.querySelector('.scf-api-retry-banner');
      if (existingErr) existingErr.remove();
      const html = await res.text();
      const doc = new DOMParser().parseFromString(html, 'text/html');
      const nextDash = doc.querySelector('.dashboard-content');
      if (!nextDash) {
        window.location.href = fetchUrl;
        return;
      }
      dashContent.classList.add('is-swapping');
      dashContent.innerHTML = nextDash.innerHTML;
      dashContent.querySelectorAll('form').forEach(f => { f.noValidate = true; });
      if (window.ensureDashboardBackBar) window.ensureDashboardBackBar();
      if (window.initStarRatings) window.initStarRatings(dashContent);
      if (typeof window.filterOfficersByDept === 'function') {
        const deptSel = dashContent.querySelector('#admin_dept_select');
        if (deptSel) window.filterOfficersByDept(deptSel.value);
      }
      if (window.lucide) lucide.createIcons();
      if (window.formatLocalTimes) window.formatLocalTimes(dashContent);
      if (window.rebindUserCreateModalForms) window.rebindUserCreateModalForms();
      dashContent.scrollTop = prevScrollTop;
      window.scrollTo(0, prevWinY);
      requestAnimationFrame(() => dashContent.classList.remove('is-swapping'));
    } catch (err) {
      dashContent.classList.remove('is-swapping');
      clearTimeout(timeoutId);
      if (err && err.name === 'AbortError' && activeRefreshSuperseded) {
        return;
      }
      if (!dashContent.querySelector('.scf-api-retry-banner')) {
        const banner = document.createElement('div');
        banner.className = 'alert alert-danger scf-api-retry-banner';
        banner.style.cssText = 'display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1rem;';
        banner.innerHTML = '<span>Unable to refresh data from the server. Please check your connection and try again.</span><button type="button" class="btn btn-secondary btn-sm">Retry</button>';
        const retryBtn = banner.querySelector('button');
        if (retryBtn) {
          retryBtn.addEventListener('click', () => {
            banner.remove();
            window.refreshDashboardContent(fetchUrl).catch(() => {});
          });
        }
        dashContent.insertBefore(banner, dashContent.firstChild);
      }
      throw err;
    } finally {
      if (activeRefreshController === controller) {
        activeRefreshController = null;
      }
    }
  };

  // Delegated Async Pagination & Navigation Loader + Offline Guard
  document.addEventListener('click', async (e) => {
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    const pageLink = e.target.closest('a.pagination-link[href]');
    if (pageLink && pageLink.closest('.dashboard-content')) {
      e.preventDefault();
      const nextUrl = pageLink.href;
      if (window.showPageLoader) window.showPageLoader('Loading page...');
      try {
        if (window.history && window.history.pushState) {
          window.history.pushState({}, '', nextUrl);
        }
        await window.refreshDashboardContent(nextUrl);
      } catch (err) {
        if (!err || err.name !== 'AbortError') {
          window.location.href = nextUrl;
        }
      } finally {
        if (window.hidePageLoader) window.hidePageLoader();
      }
      return;
    }
    const link = e.target.closest('a[href]');
    if (!link) return;
    if (link.hasAttribute('data-confirm') || link.hasAttribute('download')) return;
    if (link.getAttribute('target') === '_blank') return;

    const href = (link.getAttribute('href') || '').trim();
    if (!href || href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:') || href.startsWith('tel:')) return;

    if (navigator.onLine === false) {
      e.preventDefault();
      if (window.showToast) {
        window.showToast('You appear to be offline. Please check your connection and retry.', 'error');
      }
      return;
    }

    const lowerHref = href.toLowerCase();
    const isDownloadRoute = lowerHref.includes('/export') || lowerHref.includes('/download') || lowerHref.includes('/backup');
    if (!link.hasAttribute('data-no-loader') && !isDownloadRoute && link.href && link.href.startsWith(window.location.origin)) {
      if (window.showPageLoader) window.showPageLoader('Loading...', undefined, true);
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

  // 12. Auto-bind all modal and registration forms so ALL forms share consistent validation, persistent center popups, and close-button-only dismissal
  document.querySelectorAll('form[action*="/auth/register"]').forEach((regForm, idx) => {
    if (!regForm.id) regForm.id = `scfRegisterForm${idx + 1}`;
    regForm.dataset.customAjax = '1';
    regForm.noValidate = true;
    window.bindUserCreateModalForm({
      formId: regForm.id,
      isRegistration: true
    });
  });

  [
    {
      formId: 'adminCreateDeptForm',
      modalId: 'createDeptModal',
      alertId: 'createDeptErrorAlert',
      messageId: 'createDeptErrorMessage',
      successTitle: 'Department Created Successfully'
    },
    {
      formId: 'adminDispatchForm',
      modalId: 'dispatchModal',
      alertId: 'dispatchErrorAlert',
      messageId: 'dispatchErrorMessage',
      successTitle: 'Work Order Dispatched'
    },
    {
      formId: 'adminAddWorkerForm',
      modalId: 'addWorkerModal',
      alertId: 'adminAddWorkerErrorAlert',
      messageId: 'adminAddWorkerErrorMessage'
    },
    {
      formId: 'addOfficerForm',
      modalId: 'addOfficerModal',
      alertId: 'addOfficerErrorAlert',
      messageId: 'addOfficerErrorMessage'
    }
  ].forEach((stdCfg) => {
    if (document.getElementById(stdCfg.formId)) {
      window.bindUserCreateModalForm(stdCfg);
    }
  });

  // Safety rebind for standard admin/officer modal forms inside DOMContentLoaded
  if (window.rebindUserCreateModalForms) {
    window.rebindUserCreateModalForms();
  }

  // Only close non-form informational modals via Escape/backdrop; NEVER close form modals or persistent alerts when clicking outside or pressing Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const persistentAlert = document.getElementById('scfPersistentAlertModal');
      if (persistentAlert && persistentAlert.classList.contains('show')) {
        return;
      }
      document.querySelectorAll('.modal-overlay.show, [id$="Modal"]').forEach(m => {
        if (m.id === 'scfPersistentAlertModal' || m.id === 'sccmtConfirmModal' || m.querySelector('form')) return;
        if (m.classList.contains('show') || m.style.display === 'block' || m.style.display === 'flex') {
          m.classList.remove('show');
          setTimeout(() => { m.style.display = 'none'; }, 220);
        }
      });
    }
  });

  // Never close form modals or persistent alerts when clicking outside (backdrop); only close explicit buttons
  document.querySelectorAll('[id$="Modal"]').forEach(modal => {
    if (modal.id === 'scfPersistentAlertModal' || modal.id === 'sccmtConfirmModal' || modal.querySelector('form')) return;
    modal.addEventListener('click', (e) => {
      const persistentAlert = document.getElementById('scfPersistentAlertModal');
      if (persistentAlert && persistentAlert.classList.contains('show')) return;
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
    if (!btn) return;
    const wrapper = btn.closest('.auth-input-wrapper, .password-input-wrapper, .form-group') || btn.parentElement;
    if (!wrapper) return;
    const input = wrapper.querySelector('input');
    if (!input) return;

    if (input.type === 'password') {
      input.type = 'text';
      btn.innerHTML = '<svg class="icon-sm" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"></path><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"></path><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"></path><line x1="2" x2="22" y1="2" y2="22"></line></svg>';
      btn.setAttribute('aria-label', 'Hide password');
      btn.setAttribute('title', 'Hide password');
      btn.setAttribute('aria-pressed', 'true');
    } else {
      input.type = 'password';
      btn.innerHTML = '<svg class="icon-sm" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
      btn.setAttribute('aria-label', 'Show password');
      btn.setAttribute('title', 'Show password');
      btn.setAttribute('aria-pressed', 'false');
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

  // Global Back Navigation Button Handler + Auto Injection for Dashboard Pages Without One
  window.ensureDashboardBackBar = function() {
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
  };
  window.ensureDashboardBackBar();

  // Smooth destination page reveal AFTER layout, Back bar, theme, and icons are completely ready
  if (document.documentElement.classList.contains('scf-page-entering')) {
    const loaderEl = document.getElementById('globalPageLoader');
    if (loaderEl) {
      loaderEl.classList.add('is-active');
      loaderEl.setAttribute('aria-hidden', 'false');
    }
    try { sessionStorage.removeItem('scf_nav_transition'); } catch (_) {}
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        document.documentElement.classList.remove('scf-page-entering');
        if (loaderEl) {
          loaderEl.classList.remove('is-active');
          loaderEl.setAttribute('aria-hidden', 'true');
        }
      });
    });
  }

  document.addEventListener('click', (e) => {
    const backBtn = e.target.closest('[data-back-nav]');
    if (!backBtn) return;
    e.preventDefault();
    const fallbackUrl = backBtn.getAttribute('data-fallback-url') || '/';
    window.handleSmartBack(fallbackUrl);
  });

  // Restore button & loader states cleanly when returning via browser history (bfcache)
  window.addEventListener('pageshow', () => {
    if (window.hidePageLoader) window.hidePageLoader();
    document.documentElement.classList.remove('scf-page-entering');
    document.querySelectorAll('button.btn-loading, input.btn-loading').forEach(btn => {
      btn.classList.remove('btn-loading');
      btn.disabled = false;
    });
  });

  // Cloud Cold-Start Keep-Warm Ping & Safe Hover Prefetch
  const host = window.location.hostname;
  const isLocalHost = host === 'localhost' || host === '127.0.0.1' || host.endsWith('.local');
  if (!isLocalHost) {
    let warmInFlight = false;
    const pingWarm = (force) => {
      if (warmInFlight || navigator.onLine === false) return;
      try {
        const now = Date.now();
        const last = Number(sessionStorage.getItem('sccmt_last_warm_ts') || '0');
        if (!force && now - last < 180000) return;
        sessionStorage.setItem('sccmt_last_warm_ts', String(now));
      } catch (_) {}
      warmInFlight = true;
      fetch(window.getApiUrl ? window.getApiUrl('/health') : '/health', {
        method: 'GET',
        credentials: 'omit',
        cache: 'no-store'
      }).catch(() => {}).finally(() => { warmInFlight = false; });
    };
    setTimeout(() => pingWarm(false), 1500);
    setInterval(() => {
      if (document.visibilityState === 'visible') pingWarm(true);
    }, 240000);

    const prefetchedUrls = new Set();
    let hoverTimer = null;
    document.addEventListener('pointerenter', (e) => {
      const link = e.target && e.target.closest ? e.target.closest('a.sidebar-link[href], a.nav-link[href]') : null;
      if (!link || link.hasAttribute('data-confirm') || link.hasAttribute('download') || link.getAttribute('target') === '_blank') return;
      const href = link.href || '';
      if (!href || !href.startsWith(window.location.origin)) return;
      const lowerHref = href.toLowerCase();
      if (lowerHref.includes('/logout') || lowerHref.includes('/export') || lowerHref.includes('/download') || lowerHref.includes('#')) return;
      if (prefetchedUrls.has(href) || prefetchedUrls.size >= 12) return;
      clearTimeout(hoverTimer);
      hoverTimer = setTimeout(() => {
        if (prefetchedUrls.has(href)) return;
        prefetchedUrls.add(href);
        const pf = document.createElement('link');
        pf.rel = 'prefetch';
        pf.as = 'document';
        pf.href = href;
        document.head.appendChild(pf);
      }, 90);
    }, true);
    document.addEventListener('pointerleave', (e) => {
      if (e.target && e.target.closest && e.target.closest('a.sidebar-link[href], a.nav-link[href]')) {
        clearTimeout(hoverTimer);
      }
    }, true);
  }
});
