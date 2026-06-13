// ── Dark / Light mode (runs before first paint) ───────────────
(function () {
  const stored = localStorage.getItem('theme');
  const preferred = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  const theme = stored || preferred;
  if (theme === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
})();

// ── Global utility ────────────────────────────────────────────
function toggleNav() {
  const nav = document.getElementById('nav-links');
  if (nav) nav.classList.toggle('open');
}

async function postJSON(url, body) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await resp.json().catch(() => ({}));
  return { ok: resp.ok, data };
}

// Auto-dismiss flash messages
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => el.remove(), 5000);
});

// ── Theme toggle ──────────────────────────────────────────────
function toggleTheme() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const next   = isDark ? 'light' : 'dark';
  if (next === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
  localStorage.setItem('theme', next);
}

// ── Notifications ─────────────────────────────────────────────
const ICON_SVG = {
  green:  '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>',
  orange: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
  blue:   '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
  red:    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
};

let _notifLoaded  = false;
let _notifUnread  = 0;

function _renderNotifItems(items) {
  const list  = document.getElementById('notif-list');
  const empty = document.getElementById('notif-empty');
  if (!list) return;

  list.querySelectorAll('.notif-item').forEach(el => el.remove());

  if (!items || items.length === 0) {
    if (empty) empty.style.display = '';
    return;
  }
  if (empty) empty.style.display = 'none';

  items.forEach(item => {
    const a = document.createElement('a');
    a.className = 'notif-item';
    a.href      = item.url || '#';
    a.innerHTML = `
      <div class="notif-item-icon ${item.icon || 'green'}">${ICON_SVG[item.icon] || ICON_SVG.green}</div>
      <div class="notif-item-body">
        <div class="notif-item-msg">${item.msg}</div>
        <div class="notif-item-time">${item.time || ''}</div>
      </div>`;
    list.insertBefore(a, empty || null);
  });
}

function _updateBadge(count) {
  const badge = document.getElementById('notif-badge');
  if (!badge) return;
  _notifUnread = count;
  if (count > 0) {
    badge.textContent = count > 99 ? '99+' : String(count);
    badge.classList.remove('hidden');
    badge.classList.add('pop');
    setTimeout(() => badge.classList.remove('pop'), 400);
  } else {
    badge.classList.add('hidden');
  }
}

async function _fetchNotifications() {
  const url = window._NOTIF_URL;
  if (!url) return;
  try {
    const resp = await fetch(url, { credentials: 'same-origin' });
    if (!resp.ok) return;
    const data = await resp.json();
    _renderNotifItems(data.items || []);
    _updateBadge(data.unread || 0);
    // Update "View all" link
    const allLink = document.getElementById('notif-all-link');
    if (allLink && window._NOTIF_ALL) allLink.href = window._NOTIF_ALL;
    _notifLoaded = true;
  } catch (_) { /* network error — fail silently */ }
}

function toggleNotifDropdown() {
  const dd = document.getElementById('notif-dropdown');
  if (!dd) return;
  const isOpen = dd.classList.toggle('open');
  if (isOpen) {
    if (!_notifLoaded) _fetchNotifications();
  }
}

function markAllRead() {
  document.querySelectorAll('.notif-item.unread').forEach(el => el.classList.remove('unread'));
  _updateBadge(0);
}

// Close notification dropdown on outside click
document.addEventListener('click', function (e) {
  const wrap = document.querySelector('.notif-wrap');
  if (!wrap || wrap.contains(e.target)) return;
  const dd = document.getElementById('notif-dropdown');
  if (dd) dd.classList.remove('open');
});

// Poll notifications every 90 seconds while the page is open (only when URL is defined)
document.addEventListener('DOMContentLoaded', function () {
  if (!window._NOTIF_URL) return;
  _fetchNotifications();
  setInterval(_fetchNotifications, 90_000);
});
