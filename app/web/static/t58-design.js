/* T58 design layer: command palette (Ctrl/Cmd+K), heartbeat for the lifecycle watchdog, toast, Quit. No dependencies, no polling while hidden. */
(function () {
  'use strict';
  var ready = function (fn) { document.readyState !== 'loading' ? fn() : document.addEventListener('DOMContentLoaded', fn); };

  /* -------- heartbeat: tells the app a page is open (see app/lifecycle.py); paused while the tab is hidden -------- */
  function beat() { if (!document.hidden) { try { fetch('/api/heartbeat', { cache: 'no-store' }).catch(function () {}); } catch (e) {} } }
  beat(); setInterval(beat, 30000);
  document.addEventListener('visibilitychange', beat);

  /* -------- toast -------- */
  function toast(msg) {
    var t = document.getElementById('ds-toast');
    if (!t) { t = document.createElement('div'); t.id = 'ds-toast'; document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('show');
    clearTimeout(toast._t); toast._t = setTimeout(function () { t.classList.remove('show'); }, 2600);
  }
  window.t58Toast = toast;

  /* -------- quit -------- */
  function csrf() { return window.__T58_CSRF || ((document.getElementById('t58-profile') || {}).dataset || {}).csrf || ''; }
  function quitApp() {
    if (!confirm('Close T58 completely? Running jobs will stop.')) return;
    fetch('/api/quit', { method: 'POST', headers: { 'X-CSRF-Token': csrf() } })
      .then(function (r) { return r.json(); })
      .then(function (j) { toast(j.message || j.error || 'Closing…'); if (j.ok) setTimeout(function () { document.body.innerHTML = '<div style="display:grid;place-items:center;height:100vh;font:15px system-ui;color:#9ba6ba">T58 has closed. You can close this tab.</div>'; }, 700); })
      .catch(function () { toast('Could not reach the app.'); });
  }
  window.t58Quit = quitApp;

  /* -------- command palette: every sidebar link + actions, fuzzy filtered -------- */
  ready(function () {
    var items = [];
    document.querySelectorAll('.t58-sidebar a.t58-nav-item').forEach(function (a) {
      var label = (a.querySelector('.label') || a).textContent.trim();
      var group = a.closest('details.t58-nav-group'); var g = group ? (group.querySelector('summary').textContent || '').trim().replace(/\s+/g, ' ') : '';
      if (label) items.push({ label: label, hint: g, run: function () { location.href = a.getAttribute('href'); } });
    });
    items.push({ label: 'Toggle light / dark', hint: 'Appearance', run: function () { var b = document.getElementById('t58-theme-toggle') || document.querySelector('[data-theme-toggle]'); if (b) b.click(); } });
    items.push({ label: 'Quit T58', hint: 'Close the app completely', run: quitApp });

    var el = document.createElement('div'); el.id = 'ds-palette'; el.setAttribute('role', 'dialog'); el.setAttribute('aria-label', 'Command palette');
    el.innerHTML = '<div class="box"><input type="text" placeholder="Go to a page or run a command…" aria-label="Command" autocomplete="off"><ul role="listbox"></ul><div class="foot"><span><kbd>↑</kbd> <kbd>↓</kbd> move</span><span><kbd>Enter</kbd> open</span><span><kbd>Esc</kbd> close</span></div></div>';
    document.body.appendChild(el);
    var input = el.querySelector('input'), list = el.querySelector('ul'), sel = 0, shown = [];

    function score(q, s) { q = q.toLowerCase(); s = s.toLowerCase(); if (!q) return 1; var i = s.indexOf(q); if (i >= 0) return 100 - i; var j = 0; for (var k = 0; k < s.length && j < q.length; k++) if (s[k] === q[j]) j++; return j === q.length ? 10 : 0; }
    function render() {
      var q = input.value.trim();
      shown = items.map(function (it) { return { it: it, s: Math.max(score(q, it.label), score(q, it.hint) / 2) }; }).filter(function (x) { return x.s > 0; }).sort(function (a, b) { return b.s - a.s; }).slice(0, 12).map(function (x) { return x.it; });
      sel = Math.min(sel, Math.max(shown.length - 1, 0));
      list.innerHTML = '';
      shown.forEach(function (it, i) {
        var li = document.createElement('li'); li.setAttribute('role', 'option'); li.setAttribute('aria-selected', i === sel ? 'true' : 'false');
        li.innerHTML = '<span></span><small></small>'; li.firstChild.textContent = it.label; li.lastChild.textContent = it.hint;
        li.addEventListener('mousedown', function (e) { e.preventDefault(); go(i); }); list.appendChild(li);
      });
      if (!shown.length) list.innerHTML = '<li style="cursor:default;color:var(--text-dim)">Nothing matches</li>';
    }
    function go(i) { var it = shown[i]; if (it) { close(); it.run(); } }
    function open() { el.classList.add('open'); input.value = ''; sel = 0; render(); setTimeout(function () { input.focus(); }, 0); }
    function close() { el.classList.remove('open'); }
    input.addEventListener('input', function () { sel = 0; render(); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { sel = Math.min(sel + 1, shown.length - 1); render(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { sel = Math.max(sel - 1, 0); render(); e.preventDefault(); }
      else if (e.key === 'Enter') { go(sel); e.preventDefault(); }
    });
    el.addEventListener('mousedown', function (e) { if (e.target === el) close(); });
    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); el.classList.contains('open') ? close() : open(); }
      else if (e.key === 'Escape' && el.classList.contains('open')) close();
    });
    if (!document.querySelector('.ds-kbd-hint') && !/[?&]embed=/.test(location.search)) {
      var h = document.createElement('div'); h.className = 'ds-kbd-hint'; h.innerHTML = '<kbd>' + (navigator.platform.indexOf('Mac') >= 0 ? '⌘' : 'Ctrl') + '</kbd> <kbd>K</kbd> jump anywhere'; document.body.appendChild(h);
    }
  });
})();
