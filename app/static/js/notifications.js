// Smart Civic Complaint System - Real-Time Notification Center (SSE + Authenticated Fallback Polling)

document.addEventListener('DOMContentLoaded', () => {
  const notifToggleBtn = document.getElementById('notifToggleBtn');
  const notifMenu = document.getElementById('notifMenu');
  const notifBadge = document.getElementById('notifBadge');
  const notifList = document.getElementById('notifList');
  const markAllReadBtn = document.getElementById('markAllReadBtn');
  const isDashboard = Boolean(document.getElementById('dashboardSidebar') || document.querySelector('.dashboard-layout'));
  const hasAuthSession = Boolean(notifToggleBtn || document.querySelector('.sidebar-user-card a[href*="logout"], a[href*="/auth/logout"]'));

  let lastUnreadCount = 0;
  let lastNotifId = 0;
  let lastFingerprint = null;
  let initialized = false;
  let pollInFlight = false;
  let lastPollTs = 0;
  let eventSource = null;
  let fallbackInterval = null;
  let sseErrorCount = 0;
  const seenNotifIds = new Set();

  const getUrl = (path) => (window.getApiUrl ? window.getApiUrl(path) : path);
  const requestFn = (path, opts) => {
    if (window.apiFetch) return window.apiFetch(path, opts);
    return fetch(getUrl(path), Object.assign({ credentials: 'include' }, opts || {}));
  };

  // 1. Notification Bell Dropdown Controller (Works on both Navbar & Dashboard Sidebar)
  if (notifToggleBtn && notifMenu) {
    notifToggleBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isShowing = notifMenu.classList.contains('show');
      if (isShowing) {
        notifMenu.classList.remove('show');
      } else {
        notifMenu.classList.add('show');
        loadNotifications(false);
      }
    });

    document.addEventListener('click', (e) => {
      if (!notifMenu.contains(e.target) && !notifToggleBtn.contains(e.target)) {
        notifMenu.classList.remove('show');
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && notifMenu.classList.contains('show')) {
        notifMenu.classList.remove('show');
      }
    });

    if (markAllReadBtn) {
      markAllReadBtn.addEventListener('click', (e) => {
        e.preventDefault();
        requestFn('/api/notifications/read-all', { method: 'POST' })
          .then(res => {
            if (!res.ok) throw new Error('Unable to mark notifications as read.');
            return res.json();
          })
          .then(data => {
            if (data.success) {
              updateBadge(0);
              if (notifList) {
                notifList.querySelectorAll('.notif-item.unread').forEach(item => {
                  item.style.transition = 'background-color 200ms ease, border-left-color 200ms ease';
                  item.classList.remove('unread');
                });
              }
              if (window.showToast) {
                window.showToast('All notifications marked as read.', 'success');
              }
            }
          })
          .catch(err => {
            console.error('Error marking all read:', err);
            if (window.showToast) window.showToast(err.message || 'Failed to update notifications.', 'error');
          });
      });
    }
  }

  // Expose helper for individual mark-as-read buttons on notifications history pages
  window.markSingleNotificationRead = function(id, btnEl) {
    if (!id) return;
    requestFn(`/api/notifications/${id}/read`, { method: 'POST' })
      .then(res => {
        if (!res.ok) throw new Error('Unable to mark notification as read.');
        return res.json();
      })
      .then(data => {
        if (data.success) {
          const card = btnEl ? btnEl.closest('[data-notif-card]') : null;
          if (card) {
            card.style.background = 'var(--bg-surface)';
            card.style.borderLeftColor = 'var(--border-color)';
          }
          if (btnEl) btnEl.remove();
          const nextCount = Math.max(0, lastUnreadCount - 1);
          lastUnreadCount = nextCount;
          updateBadge(nextCount);
        }
      })
      .catch(err => {
        if (window.showToast) window.showToast(err.message || 'Failed to update notification.', 'error');
      });
  };

  function loadNotifications(isBackgroundPoll = false) {
    requestFn('/api/notifications')
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch notifications.');
        return res.json();
      })
      .then(data => {
        const count = data.unread_count || 0;
        const list = data.notifications || [];
        list.forEach(n => seenNotifIds.add(n.id));
        if (list.length > 0 && list[0].id > lastNotifId) {
          lastNotifId = list[0].id;
        }
        lastUnreadCount = count;
        updateBadge(count);
        if (notifList) renderList(list);
      })
      .catch(err => {
        console.error('Failed to load notifications:', err);
        if (!isBackgroundPoll && notifList) {
          notifList.innerHTML = '<div style="padding: 1.25rem; text-align: center; color: var(--status-rejected); font-size: 0.82rem;"><div>Unable to load notifications right now.</div><button type="button" id="retryNotifBtn" class="btn btn-secondary btn-sm" style="margin-top: 0.5rem;">Retry</button></div>';
          const retryBtn = document.getElementById('retryNotifBtn');
          if (retryBtn) {
            retryBtn.addEventListener('click', (e) => {
              e.stopPropagation();
              loadNotifications(false);
            });
          }
        }
      });
  }

  function updateSidebarBadge(count) {
    const notifLink = document.querySelector('#dashboardSidebar a[href*="/notifications"]');
    if (!notifLink) return;
    let badge = notifLink.querySelector('.sidebar-notif-badge');
    if (count > 0) {
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'sidebar-notif-badge';
        badge.style.cssText = 'margin-left: auto; background: #ef4444; color: #fff; font-size: 0.68rem; font-weight: 700; min-width: 18px; height: 18px; padding: 0 5px; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center;';
        notifLink.appendChild(badge);
      }
      badge.textContent = count > 99 ? '99+' : String(count);
      badge.style.display = 'inline-flex';
    } else if (badge) {
      badge.style.display = 'none';
    }
  }

  function updateBadge(count) {
    if (notifBadge) {
      if (count > 0) {
        notifBadge.textContent = count > 99 ? '99+' : String(count);
        notifBadge.style.display = 'inline-flex';
        notifBadge.classList.add('badge-pulse');
      } else {
        notifBadge.style.display = 'none';
        notifBadge.classList.remove('badge-pulse');
      }
    }
    updateSidebarBadge(count);
  }

  function renderList(notifications) {
    if (!notifList) return;
    if (!notifications || notifications.length === 0) {
      notifList.innerHTML = '<div style="padding: 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.85rem;">No notifications at this time</div>';
      return;
    }

    notifList.innerHTML = notifications.map((n, idx) => `
      <a href="${n.link || '#'}" class="notif-item ${n.is_read ? '' : 'unread'}" data-id="${n.id}" style="animation: pageFadeInUp 200ms ease-out forwards; animation-delay: ${idx * 35}ms;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem;">
          <strong style="color: var(--text-primary); font-size: 0.84rem;">${escapeHtml(n.title)}</strong>
          <span style="font-size: 0.72rem; color: var(--text-muted); white-space: nowrap;">${escapeHtml(n.time_ago || '')}</span>
        </div>
        <p style="margin-top: 0.25rem; font-size: 0.8rem; color: var(--text-secondary); line-height: 1.35;">${escapeHtml(n.message)}</p>
      </a>
    `).join('');

    notifList.querySelectorAll('.notif-item').forEach(item => {
      item.addEventListener('click', () => {
        const id = item.getAttribute('data-id');
        if (id && item.classList.contains('unread')) {
          item.classList.remove('unread');
          requestFn(`/api/notifications/${id}/read`, { method: 'POST' });
          const newCount = Math.max(0, lastUnreadCount - 1);
          lastUnreadCount = newCount;
          updateBadge(newCount);
        }
      });
    });
  }

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function shouldAutoRefreshLiveSections() {
    if (!isDashboard) return false;
    if (document.querySelector('.modal-overlay.show')) return false;
    const active = document.activeElement;
    if (active && ['INPUT', 'TEXTAREA', 'SELECT'].includes(active.tagName)) return false;

    const p = window.location.pathname;
    return /^\/(admin|officer|worker|citizen)\/(dashboard|complaints|complaint|tasks|task|incoming|verification|escalations|assignments|notifications|analytics|reports)(\/\d+)?\/?$/.test(p);
  }

  async function refreshDashboardSectionsInPlace() {
    if (!shouldAutoRefreshLiveSections()) return;
    if (typeof window.refreshAdminAnalytics === 'function') {
      await window.refreshAdminAnalytics();
      return;
    }
    try {
      const resp = await fetch(window.location.href, {
        credentials: 'include',
        headers: { 'X-Live-Refresh': '1' }
      });
      if (!resp.ok || resp.redirected) return;
      const html = await resp.text();
      const doc = new DOMParser().parseFromString(html, 'text/html');

      const selectors = [
        '.stat-grid',
        '#newComplaintsQueueCard',
        '#recentComplaintsCard',
        '#auditStreamCard',
        '#contactInquiriesCard',
        '#citizenFeedbackCard',
        '.timeline'
      ];

      let updatedAny = false;
      selectors.forEach(sel => {
        const currentEl = document.querySelector(sel);
        const freshEl = doc.querySelector(sel);
        if (currentEl && freshEl && currentEl.innerHTML !== freshEl.innerHTML) {
          currentEl.innerHTML = freshEl.innerHTML;
          currentEl.querySelectorAll('tbody tr').forEach(tr => tr.classList.add('live-row-highlight'));
          updatedAny = true;
        }
      });

      // Update status badge on detail pages when status changes in real time
      const currentHeaderBadges = document.querySelector('.dashboard-content > div:first-child .badge');
      const freshHeaderBadges = doc.querySelector('.dashboard-content > div:first-child .badge');
      if (currentHeaderBadges && freshHeaderBadges && currentHeaderBadges.outerHTML !== freshHeaderBadges.outerHTML) {
        currentHeaderBadges.outerHTML = freshHeaderBadges.outerHTML;
        updatedAny = true;
      }

      // On queue/list/notifications pages (without Chart.js canvas), swap table or notification cards
      if (!document.getElementById('deptChart')) {
        const currentTables = document.querySelectorAll('.dashboard-content .table-responsive');
        const freshTables = doc.querySelectorAll('.dashboard-content .table-responsive');
        if (currentTables.length === freshTables.length && currentTables.length > 0) {
          currentTables.forEach((tbl, idx) => {
            if (tbl.innerHTML !== freshTables[idx].innerHTML) {
              tbl.innerHTML = freshTables[idx].innerHTML;
              tbl.querySelectorAll('tbody tr').forEach(tr => tr.classList.add('live-row-highlight'));
              updatedAny = true;
            }
          });
        } else {
          const curCards = document.querySelectorAll('.dashboard-content > .card');
          const newCards = doc.querySelectorAll('.dashboard-content > .card');
          if (curCards.length === newCards.length && curCards.length > 0) {
            const lastIdx = curCards.length - 1;
            if (curCards[lastIdx].innerHTML !== newCards[lastIdx].innerHTML) {
              curCards[lastIdx].innerHTML = newCards[lastIdx].innerHTML;
              updatedAny = true;
            }
          }
        }
      }

      if (updatedAny && window.lucide) {
        lucide.createIcons();
      }
      if (updatedAny && window.formatLocalTimes) {
        window.formatLocalTimes(document);
      }
    } catch (e) {
      console.error('Live dashboard update failed:', e);
    }
  }

  async function processSyncPayload(data) {
    if (!data || typeof data !== 'object') return;

    const count = data.unread_notifications || 0;
    const latestNotif = data.latest_notification;
    const missedList = Array.isArray(data.new_notifications) ? data.new_notifications : [];

    if (!initialized) {
      if (latestNotif) {
        lastNotifId = latestNotif.id;
        seenNotifIds.add(latestNotif.id);
      }
      if (data.latest_notif_id && data.latest_notif_id > lastNotifId) {
        lastNotifId = data.latest_notif_id;
      }
      lastUnreadCount = count;
      lastFingerprint = data.fingerprint;
      initialized = true;
      updateBadge(count);
      return;
    }

    // Emit toast alerts only for unseen notifications (strict deduplication)
    const toAnnounce = [];
    if (missedList.length > 0) {
      missedList.forEach(n => {
        if (!seenNotifIds.has(n.id)) {
          seenNotifIds.add(n.id);
          toAnnounce.push(n);
        }
      });
    } else if (latestNotif && !seenNotifIds.has(latestNotif.id) && latestNotif.id > lastNotifId) {
      seenNotifIds.add(latestNotif.id);
      toAnnounce.push(latestNotif);
    }

    if (toAnnounce.length > 0 && window.showToast) {
      toAnnounce.slice(-2).forEach(n => {
        const toastType = (n.notification_type === 'rework_required') ? 'warning' : 'info';
        window.showToast(n.message || n.title, toastType, n.title || 'New Update', 5500);
      });
    }

    if (data.latest_notif_id && data.latest_notif_id > lastNotifId) {
      lastNotifId = data.latest_notif_id;
    } else if (latestNotif && latestNotif.id > lastNotifId) {
      lastNotifId = latestNotif.id;
    }

    lastUnreadCount = count;
    updateBadge(count);

    // Refresh open dropdown panel automatically if visible
    if (notifMenu && notifMenu.classList.contains('show')) {
      loadNotifications(true);
    }

    if (lastFingerprint !== null && data.fingerprint !== lastFingerprint) {
      lastFingerprint = data.fingerprint;
      if (Date.now() >= (window.__sccmtPauseLiveSyncUntil || 0)) {
        await refreshDashboardSectionsInPlace();
      }
    } else {
      lastFingerprint = data.fingerprint;
    }
  }

  async function pollLiveUpdatesOnce(force) {
    if (!hasAuthSession) return;
    if (pollInFlight) return;
    const now = Date.now();
    if (!force && now - lastPollTs < 4000) return;
    lastPollTs = now;
    pollInFlight = true;
    const controller = new AbortController();
    const pollTimer = setTimeout(() => controller.abort(), 15000);
    try {
      const res = await requestFn(`/api/live-updates?since_id=${lastNotifId || 0}`, {
        signal: controller.signal
      });
      if (!res.ok) return;
      const data = await res.json();
      await processSyncPayload(data);
    } catch (e) {
      // Quietly ignore transient offline/timeout errors; next poll/reconnect recovers missed IDs
    } finally {
      clearTimeout(pollTimer);
      pollInFlight = false;
    }
  }

  const isVercelProxied = (() => {
    const meta = document.querySelector('meta[name="api-base-url"]');
    const apiBase = meta ? (meta.getAttribute('content') || '').trim() : '';
    return !apiBase && window.location.hostname.endsWith('.vercel.app');
  })();

  function startFallbackPolling() {
    if (fallbackInterval) return;
    fallbackInterval = setInterval(() => {
      if (!document.hidden) {
        pollLiveUpdatesOnce(false);
      }
    }, isVercelProxied ? 30000 : 12000);
  }

  function stopFallbackPolling() {
    if (fallbackInterval) {
      clearInterval(fallbackInterval);
      fallbackInterval = null;
    }
  }

  function connectSSE() {
    if (!hasAuthSession || isVercelProxied || typeof window.EventSource === 'undefined') {
      startFallbackPolling();
      return;
    }
    if (eventSource) {
      try { eventSource.close(); } catch (e) {}
      eventSource = null;
    }

    const streamUrl = getUrl(`/api/stream?since_id=${lastNotifId || 0}`);
    try {
      eventSource = new EventSource(streamUrl, { withCredentials: true });

      eventSource.addEventListener('sync', (ev) => {
        sseErrorCount = 0;
        stopFallbackPolling();
        try {
          const payload = JSON.parse(ev.data);
          processSyncPayload(payload);
        } catch (err) {
          console.error('SSE payload parse error:', err);
        }
      });

      eventSource.addEventListener('heartbeat', () => {
        sseErrorCount = 0;
      });

      eventSource.onerror = () => {
        sseErrorCount += 1;
        // Close flaky/buffered proxy SSE streams promptly after 2 errors so only lightweight polling runs
        startFallbackPolling();
        if (sseErrorCount >= 2) {
          try { eventSource.close(); } catch (e) {}
          eventSource = null;
        }
      };
    } catch (e) {
      startFallbackPolling();
    }
  }

  if (hasAuthSession) {
    window.refreshLiveNotifications = () => pollLiveUpdatesOnce(true);
    // Defer initial background live-sync so initial page load & interactions never queue behind it
    setTimeout(() => {
      pollLiveUpdatesOnce(true).then(() => {
        connectSSE();
      });
    }, 2500);

    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) {
        pollLiveUpdatesOnce(false);
        if (!eventSource && !fallbackInterval) {
          sseErrorCount = 0;
          connectSSE();
        }
      }
    });

    window.addEventListener('sccmt:action-synced', () => {
      pollLiveUpdatesOnce(true);
    });

    window.addEventListener('focus', () => {
      pollLiveUpdatesOnce(false);
    });

    window.addEventListener('online', () => {
      sseErrorCount = 0;
      pollLiveUpdatesOnce(true);
      connectSSE();
    });

    window.addEventListener('beforeunload', () => {
      if (eventSource) {
        try { eventSource.close(); } catch (e) {}
      }
    });
  }
});
