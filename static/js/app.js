/* RSA shared front-end helpers (no framework, no build step). */
(function () {
  'use strict';

  const csrf = () => (document.querySelector('meta[name="csrf-token"]') || {}).content || '';

  /** HTML-escape any value before putting it into innerHTML. */
  function esc(value) {
    return String(value === null || value === undefined ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  /** POST/GET JSON with the CSRF token. Always resolves to {ok, status, data}. */
  async function api(url, options) {
    const opts = Object.assign({ method: 'GET', headers: {} }, options || {});
    opts.headers = Object.assign({ 'Accept': 'application/json' }, opts.headers);
    if (opts.method !== 'GET') opts.headers['X-CSRF-Token'] = csrf();
    if (opts.form) { opts.body = opts.form instanceof FormData ? opts.form : toForm(opts.form); delete opts.form; }
    opts.credentials = 'same-origin';
    try {
      const response = await fetch(url, opts);
      let data = {};
      try { data = await response.json(); } catch (e) { data = { success: false, message: 'Unexpected server response.' }; }
      if (response.status === 401) { window.location = '/login?next=' + encodeURIComponent(location.pathname); }
      return { ok: response.ok && data.success !== false, status: response.status, data };
    } catch (e) {
      return { ok: false, status: 0, data: { success: false, message: 'Network error. Check your connection and try again.' } };
    }
  }

  function toForm(object) {
    const fd = new FormData();
    Object.entries(object).forEach(([k, v]) => { if (v !== undefined && v !== null) fd.append(k, v); });
    return fd;
  }

  /** Small toast messages (role=status for screen readers). */
  function toast(message, kind) {
    let stack = document.querySelector('.flash-stack');
    if (!stack) { stack = document.createElement('div'); stack.className = 'flash-stack'; stack.setAttribute('role', 'status'); document.body.appendChild(stack); }
    const el = document.createElement('div');
    el.className = 'flash ' + (kind || 'success');
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(() => el.remove(), 5000);
  }

  /** Convert <time class="ts" datetime="...Z"> to the viewer's local time. */
  function localTimes(root) {
    (root || document).querySelectorAll('time.ts[datetime]').forEach((el) => {
      const d = new Date(el.getAttribute('datetime'));
      if (!isNaN(d)) { el.textContent = d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }); el.title = el.getAttribute('datetime'); }
    });
  }

  function timeHtml(utcString) {
    if (!utcString) return '';
    const iso = String(utcString).replace(' ', 'T') + (String(utcString).endsWith('Z') ? '' : 'Z');
    const d = new Date(iso);
    if (isNaN(d)) return esc(utcString);
    return '<time class="ts" datetime="' + esc(iso) + '" title="' + esc(iso) + '">' + esc(d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })) + '</time>';
  }

  /** Confirmation for any form/button with data-confirm. */
  document.addEventListener('submit', (event) => {
    if (event.defaultPrevented) return; // handled by page script
    const form = event.target;
    const message = form.getAttribute('data-confirm');
    if (message && !window.confirm(message)) { event.preventDefault(); return; }
    form.querySelectorAll('button[type="submit"]').forEach((b) => { b.disabled = true; b.classList.add('loading'); });
  });

  /** Notification badge polling (only when signed in). */
  async function pollNotifications() {
    const badge = document.querySelector('[data-notification-count]');
    if (!badge || document.hidden) return;
    const res = await api('/api/notifications');
    if (res.ok) {
      const n = res.data.unread || 0;
      badge.textContent = n > 99 ? '99+' : String(n);
      badge.hidden = n === 0;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    localTimes();
    document.querySelectorAll('.flash-stack .flash').forEach((x) => setTimeout(() => x.remove(), 6000));
    if (document.querySelector('[data-notification-count]')) setInterval(pollNotifications, 20000);
  });

  window.RSA = { api, esc, toast, localTimes, timeHtml, toForm };
})();
