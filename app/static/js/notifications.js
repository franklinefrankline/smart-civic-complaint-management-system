// Smart Civic Complaint System - Notification Center & Live Alerts Engine

document.addEventListener('DOMContentLoaded', () => {
  const notifToggleBtn = document.getElementById('notifToggleBtn');
  const notifMenu = document.getElementById('notifMenu');
  const notifBadge = document.getElementById('notifBadge');
  const notifList = document.getElementById('notifList');
  const markAllReadBtn = document.getElementById('markAllReadBtn');

  let lastUnreadCount = 0;

  if (!notifToggleBtn || !notifMenu) return;

  // Toggle notification menu with smooth scale-fade transition
  notifToggleBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    const isShowing = notifMenu.classList.contains('show');
    if (isShowing) {
      notifMenu.classList.remove('show');
    } else {
      notifMenu.classList.add('show');
      loadNotifications();
    }
  });

  // Close when clicking outside
  document.addEventListener('click', (e) => {
    if (!notifMenu.contains(e.target) && e.target !== notifToggleBtn) {
      notifMenu.classList.remove('show');
    }
  });

  // Mark all notifications as read
  if (markAllReadBtn) {
    markAllReadBtn.addEventListener('click', (e) => {
      e.preventDefault();
      fetch('/api/notifications/read-all', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            updateBadge(0);
            // Smoothly remove unread highlights
            notifList.querySelectorAll('.notif-item.unread').forEach(item => {
              item.style.transition = 'background-color 200ms ease, border-left-color 200ms ease';
              item.classList.remove('unread');
            });
            if (window.showToast) {
              window.showToast('All notifications marked as read.', 'success');
            }
          }
        })
        .catch(err => console.error('Error marking all read:', err));
    });
  }

  function loadNotifications(isBackgroundPoll = false) {
    fetch('/api/notifications')
      .then(res => res.json())
      .then(data => {
        const count = data.unread_count || 0;

        // If a new notification arrived in the background, trigger a toast alert!
        if (isBackgroundPoll && count > lastUnreadCount && data.notifications.length > 0) {
          const newest = data.notifications[0];
          if (window.showToast) {
            window.showToast(newest.message || newest.title, 'info', 'Civic Update');
          }
        }

        lastUnreadCount = count;
        updateBadge(count);
        renderList(data.notifications);
      })
      .catch(err => console.error('Failed to load notifications:', err));
  }

  function updateBadge(count) {
    if (!notifBadge) return;
    if (count > 0) {
      notifBadge.textContent = count > 99 ? '99+' : count;
      notifBadge.style.display = 'inline-flex';
      notifBadge.classList.add('badge-pulse');
    } else {
      notifBadge.style.display = 'none';
      notifBadge.classList.remove('badge-pulse');
    }
  }

  function renderList(notifications) {
    if (!notifList) return;
    if (!notifications || notifications.length === 0) {
      notifList.innerHTML = '<div style="padding: 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.85rem;">No notifications at this time</div>';
      return;
    }

    notifList.innerHTML = notifications.map((n, idx) => `
      <a href="${n.link || '#'}" class="notif-item ${n.is_read ? '' : 'unread'}" data-id="${n.id}" style="animation: pageFadeInUp 200ms ease-out forwards; animation-delay: ${idx * 40}ms;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
          <strong style="color: var(--text-primary); font-size: 0.85rem;">${escapeHtml(n.title)}</strong>
          <span style="font-size: 0.72rem; color: var(--text-muted);">${n.time_ago || ''}</span>
        </div>
        <p style="margin-top: 0.25rem; font-size: 0.8rem; color: var(--text-secondary); line-height: 1.3;">${escapeHtml(n.message)}</p>
      </a>
    `).join('');

    // Attach click listeners to mark individually read
    notifList.querySelectorAll('.notif-item').forEach(item => {
      item.addEventListener('click', () => {
        const id = item.getAttribute('data-id');
        if (id && item.classList.contains('unread')) {
          item.classList.remove('unread');
          fetch(`/api/notifications/${id}/read`, { method: 'POST' });
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

  // Periodic poll every 45 seconds for background updates
  setInterval(() => {
    loadNotifications(true);
  }, 45000);
});
