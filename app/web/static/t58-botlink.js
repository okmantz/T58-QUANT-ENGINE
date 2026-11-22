/* "Your bot is trading" strip: on the Deploy pages, one row per running Trading Bot with a button straight to that bot's page
   (live trade log, stats and CSV export). Mount point: any element with the data-bot-active attribute.
   Reads GET /trading-bots/api/active every 15 s while the tab is visible. Escapes all text; works without storage. */
(function () {
  'use strict';
  var slot = document.querySelector('[data-bot-active]');
  if (!slot || slot.__t58BotLink) return;
  slot.__t58BotLink = true;
  var st = document.createElement('style');
  st.textContent =
    '.bl-wrap{display:grid;gap:8px;margin:0 0 14px}.bl-wrap:empty{display:none}' +
    '.bl-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:11px 14px;border-radius:14px;border:1px solid rgba(var(--teal-rgb),.45);' +
    'background:linear-gradient(135deg,rgba(var(--teal-rgb),.14),rgba(var(--teal-rgb),.03) 70%),var(--panel-2)}' +
    '.bl-dot{width:9px;height:9px;border-radius:50%;background:var(--teal);box-shadow:0 0 0 0 rgba(var(--teal-rgb),.6);animation:bl-pulse 1.8s infinite}' +
    '@keyframes bl-pulse{70%{box-shadow:0 0 0 8px rgba(var(--teal-rgb),0)}100%{box-shadow:0 0 0 0 rgba(var(--teal-rgb),0)}}' +
    '@media(prefers-reduced-motion:reduce){.bl-dot{animation:none}}' +
    '.bl-txt{flex:1 1 240px;min-width:0;font-size:13px;color:var(--text-muted);line-height:1.45}.bl-txt b{color:var(--text)}' +
    '.bl-pnl{font-variant-numeric:tabular-nums;font-weight:700}.bl-pnl.up{color:var(--lm-up,#3ed685)}.bl-pnl.down{color:var(--lm-down,#f0596a)}' +
    '.bl-go{flex:none;display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:10px;background:var(--teal);color:var(--on-teal,#04120c);' +
    'font-weight:700;font-size:12.5px;text-decoration:none;white-space:nowrap}.bl-go:hover{filter:brightness(1.08)}';
  document.head.appendChild(st);
  var box = document.createElement('div');
  box.className = 'bl-wrap';
  box.setAttribute('role', 'status');
  box.setAttribute('aria-live', 'polite');
  slot.appendChild(box);
  function money(v) { var s = Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); return (v < 0 ? '-$' : '+$') + s; }
  function venue(v) { return v === 'broker' ? 'a connected account' : (v === 'paper' ? 'its sandbox' : 'the T58 demo account'); }
  function render(bots) {
    box.textContent = '';
    (bots || []).forEach(function (b) {
      var row = document.createElement('div'); row.className = 'bl-row';
      var dot = document.createElement('span'); dot.className = 'bl-dot'; row.appendChild(dot);
      var txt = document.createElement('div'); txt.className = 'bl-txt';
      var nm = document.createElement('b'); nm.textContent = b.name || 'Your bot';
      txt.appendChild(nm);
      txt.appendChild(document.createTextNode(' is trading on ' + venue(b.venue) + ' · ' + (b.n_trades || 0) + ' trade' + (b.n_trades === 1 ? '' : 's') + ' so far · '));
      var pn = document.createElement('span'); pn.className = 'bl-pnl ' + (b.net_pnl > 0 ? 'up' : (b.net_pnl < 0 ? 'down' : '')); pn.textContent = money(b.net_pnl || 0);
      txt.appendChild(pn);
      row.appendChild(txt);
      var a = document.createElement('a'); a.className = 'bl-go'; a.target = '_top';
      a.href = b.url || '/trading-bots'; a.textContent = 'Open bot page →'; row.appendChild(a);
      box.appendChild(row);
    });
  }
  function load() {
    if (document.visibilityState === 'hidden') return;
    fetch('/trading-bots/api/active', { headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(function (r) { return r.json(); })
      .then(function (d) { if (d && d.ok) render(d.bots); }).catch(function () {});
  }
  window.T58BotLink = { refresh: load };
  load();
  setInterval(load, 15000);
})();
