/* T58 Mission strip: a slim, glass-style bar at the top of the page showing where you are on the First Payout Mission.
   Click a stage to see exactly what must be met before moving on. Reads /api/journey (cached for a minute).
   It sits at the very top of the page content (where the lifecycle stepper used to be on every page), above the page header. */
(function () {
  'use strict';
  if (window.__t58Journey || /^\/(login|offline|static)/.test(location.pathname)) return;
  window.__t58Journey = true;
  var KEY = 't58-journey-v1';
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function cached() { try { var d = JSON.parse(sessionStorage.getItem(KEY) || 'null'); if (d && Date.now() - d.t < 60000) return d.v; } catch (e) {} return null; }
  function store(v) { try { sessionStorage.setItem(KEY, JSON.stringify({ t: Date.now(), v: v })); } catch (e) {} }
  var css = el('style'); css.textContent =
    '.jt{position:relative;display:flex;align-items:center;gap:16px;margin:0 0 18px;padding:10px 16px 10px 14px;border-radius:16px;max-width:100%;font-size:12px;color:var(--text-muted);' +
      'background:linear-gradient(135deg,rgba(var(--teal-rgb),.10),rgba(var(--teal-rgb),.02) 55%),var(--panel-2);border:1px solid var(--border);box-shadow:0 10px 30px -18px rgba(0,0,0,.6);overflow:visible}' +
    '.jt::before{content:"";position:absolute;left:0;top:12px;bottom:12px;width:3px;border-radius:0 3px 3px 0;background:linear-gradient(var(--teal),var(--neon-cyan,var(--teal)))}' +
    '.jt-id{display:flex;align-items:center;gap:10px;flex:none;padding-left:6px}' +
    '.jt-ico{width:30px;height:30px;border-radius:10px;display:grid;place-items:center;color:var(--teal);background:rgba(var(--teal-rgb),.14);border:1px solid rgba(var(--teal-rgb),.30)}' +
    '.jt-ico svg{width:15px;height:15px}' +
    '.jt-lab{display:block;letter-spacing:.16em;font-weight:800;font-size:10px;color:var(--text);white-space:nowrap}' +
    '.jt-sub{display:block;font-size:11px;color:var(--text-muted);margin-top:1px;white-space:nowrap}' +
    '.jt-track{flex:1;min-width:0;display:flex;align-items:center;gap:0}' +
    '.jt-st{display:flex;align-items:center;gap:7px;background:none;border:0;color:inherit;cursor:pointer;padding:5px 8px;border-radius:999px;font:inherit;font-weight:600;white-space:nowrap;transition:background .15s,color .15s}' +
    '.jt-st:hover{background:rgba(var(--teal-rgb),.10);color:var(--text)}' +
    '.jt-dot{width:9px;height:9px;border-radius:50%;border:1.5px solid var(--border-light);flex:none;background:transparent}' +
    '.jt-st.done{color:var(--text)}.jt-st.done .jt-dot{background:var(--teal);border-color:var(--teal);box-shadow:0 0 8px rgba(var(--teal-rgb),.55)}' +
    '.jt-st.current{color:var(--text)}.jt-st.current .jt-dot{border-color:var(--teal);box-shadow:0 0 0 3px rgba(var(--teal-rgb),.22)}' +
    '.jt-bar{flex:1 1 10px;min-width:8px;max-width:46px;height:2px;border-radius:2px;background:var(--border-light)}.jt-bar.done{background:linear-gradient(90deg,var(--teal),var(--neon-cyan,var(--teal)))}' +
    '.jt-pct{flex:none;font-weight:800;font-size:13px;color:var(--teal);font-variant-numeric:tabular-nums}' +
    '.jt-go{flex:none;font-weight:700;font-size:12px;color:var(--teal);text-decoration:none;white-space:nowrap}.jt-go:hover{text-decoration:underline}' +
    '.jt-pop{position:absolute;top:calc(100% + 8px);left:14px;z-index:9000;width:min(380px,calc(100vw - 32px));background:var(--pop-bg,var(--panel));border:1px solid var(--pop-bd,var(--border-light));border-radius:14px;padding:14px 16px;box-shadow:0 18px 44px rgba(0,0,0,.5);color:var(--text);font-size:12.5px}' +
    '.jt-pop h4{margin:0 0 6px;font-size:13px}.jt-pop .r{display:flex;gap:8px;padding:3px 0}.jt-pop .r i{font-style:normal;width:14px;flex:none}.jt-pop .d{color:var(--text-muted);font-size:11.5px}' +
    '.jt-pop a{color:var(--teal);font-weight:700;text-decoration:none}' +
    '@media(max-width:1100px){.jt-st span.t{display:none}.jt-st.current span.t{display:inline}.jt-sub{display:none}}' +
    '@media(max-width:640px){.jt{gap:10px;padding:9px 12px}.jt-go{display:none}.jt-id .jt-ico{display:none}}';
  document.head.appendChild(css);
  function build(d) {
    var main = document.querySelector('.t58-main'); if (!main || document.getElementById('t58-journey')) return;
    var stages = d.stages || [];
    var total = stages.length || 1, done = stages.filter(function (s) { return s.state === 'done'; }).length;
    var cur = stages.filter(function (s) { return s.state === 'current'; })[0];
    var bar = el('div', 'jt'); bar.id = 't58-journey'; bar.setAttribute('role', 'navigation'); bar.setAttribute('aria-label', 'First Payout Mission progress');
    var id = el('div', 'jt-id');
    var ico = el('span', 'jt-ico'); ico.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 22V4"/><path d="M4 4h13l-2 4 2 4H4"/></svg>';
    var txt = el('div'); txt.appendChild(el('span', 'jt-lab', 'T58 MISSION'));
    txt.appendChild(el('span', 'jt-sub', cur ? 'You are here: ' + cur.label : (done >= total ? 'Mission complete' : 'First payout')));
    id.appendChild(ico); id.appendChild(txt); bar.appendChild(id);
    var track = el('div', 'jt-track'); bar.appendChild(track);
    var pop = null;
    function close() { if (pop) { pop.remove(); pop = null; } }
    stages.forEach(function (s, i) {
      if (i) track.appendChild(el('span', 'jt-bar' + (s.state === 'done' || stages[i - 1].state === 'done' ? ' done' : '')));
      var b = el('button', 'jt-st ' + s.state); b.type = 'button'; b.setAttribute('aria-label', s.label + (s.state === 'current' ? ' (you are here)' : ''));
      b.appendChild(el('span', 'jt-dot')); b.appendChild(el('span', 't', s.label));
      b.addEventListener('click', function (ev) {
        ev.stopPropagation(); var same = pop && pop.dataset.k === s.key; close(); if (same) return;
        pop = el('div', 'jt-pop'); pop.dataset.k = s.key; pop.appendChild(el('h4', null, (i + 1) + '. ' + s.label + (s.state === 'done' ? ' — done' : (s.state === 'current' ? ' — you are here' : ''))));
        pop.appendChild(el('div', 'd', s.state === 'done' ? 'Everything required here is met.' : 'To move past this step:'));
        (s.requirements || []).forEach(function (r) { var row = el('div', 'r'); row.appendChild(el('i', null, r.met === true ? '✓' : (r.met === false ? '○' : '·'))); var t = el('div'); t.appendChild(document.createTextNode(r.label)); if (r.detail) t.appendChild(el('div', 'd', r.detail)); row.appendChild(t); pop.appendChild(row); });
        var more = el('a', null, 'Open this step'); more.href = s.href; var all = el('a', null, 'Full mission'); all.href = '/mission'; all.style.marginLeft = '14px';
        var f = el('div'); f.style.marginTop = '8px'; f.appendChild(more); f.appendChild(all); pop.appendChild(f); bar.appendChild(pop);
      });
      track.appendChild(b);
    });
    bar.appendChild(el('span', 'jt-pct', Math.round(100 * done / total) + '%'));
    var go = el('a', 'jt-go', 'Open mission →'); go.href = '/mission'; bar.appendChild(go);
    document.addEventListener('click', function (e) { if (pop && !bar.contains(e.target)) close(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
    var hdr = main.querySelector('.t58-page-header');
    main.insertBefore(bar, hdr || main.firstChild);
  }
  var c = cached();
  if (c) build(c); else fetch('/api/journey').then(function (r) { return r.json(); }).then(function (d) { if (d && d.ok) { store(d); build(d); } }).catch(function () {});
})();
