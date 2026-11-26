/* Playground / Quantum: Gravity Well, Particle Storm, Orbit Challenge, Signal Path, Light Tunnel. Canvas physics toys, all local. */
(function () {
  var PG = window.PG;
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  var TAU = Math.PI * 2;

  /* ------------------------------------------------------------------ Gravity Well */
  PG.register('quantum', 'well', {
    title: 'Gravity Well', sub: 'Click empty space to drop a well (up to 5), drag a well to move it, double-click one to remove it. Particles fall, whip around and fall again.',
    mount: function (host) {
      var cv = PG.canvas(host, 1.7), ctx = cv.ctx, N = 420, P = [], wells = [], G = 1, drag = null, g0 = 0;
      function U() { return Math.min(cv.w, cv.h); }
      function spawn(p) { var w = wells[0] || { x: cv.w / 2, y: cv.h / 2 }, a = Math.random() * TAU, r = U() * (0.25 + Math.random() * 0.35), v = Math.sqrt(G * 0.064 * Math.pow(U(), 3) / r) * (0.75 + Math.random() * 0.5);
        p.x = w.x + Math.cos(a) * r; p.y = w.y + Math.sin(a) * r; p.vx = -Math.sin(a) * v; p.vy = Math.cos(a) * v; p.age = 0; return p; }
      function init() { wells = [{ x: cv.w / 2, y: cv.h / 2, m: 1 }]; P = []; for (var i = 0; i < N; i++) P.push(spawn({})); ctx.fillStyle = '#05080d'; ctx.fillRect(0, 0, cv.w, cv.h); }
      cv.onresize = function () { ctx.fillStyle = '#05080d'; ctx.fillRect(0, 0, cv.w, cv.h); }; init();
      function hit(p) { for (var i = 0; i < wells.length; i++) if (Math.hypot(wells[i].x - p.x, wells[i].y - p.y) < 22) return i; return -1; }
      PG.drag(cv.cv, {
        down: function (e) { var p = cv.pos(e), i = hit(p); if (i >= 0) drag = i; else if (wells.length < 5) { wells.push({ x: p.x, y: p.y, m: 0.8 }); drag = wells.length - 1; } },
        move: function (e, down) { if (down && drag !== null && wells[drag]) { var p = cv.pos(e); wells[drag].x = p.x; wells[drag].y = p.y; } }, up: function () { drag = null; }
      });
      cv.cv.addEventListener('dblclick', function (e) { var i = hit(cv.pos(e)); if (i >= 0 && wells.length > 1) wells.splice(i, 1); });
      var bar = PG.el('div', 'pg-bar'); host.appendChild(bar);
      bar.appendChild(PG.el('label', '', 'Gravity '));
      var sl = PG.el('input'); sl.type = 'range'; sl.min = 0.3; sl.max = 2.5; sl.step = 0.05; sl.value = 1; sl.setAttribute('aria-label', 'Gravity strength'); sl.oninput = function () { G = +sl.value; }; bar.appendChild(sl);
      PG.button(bar, 'Reset', init); PG.button(bar, 'More particles', function () { for (var i = 0; i < 120; i++) P.push(spawn({})); });
      var lp = PG.loop(function (dt) {
        var g = ctx, w = cv.w, h = cv.h, u = U(), k = G * 0.064 * u * u * u;   // a particle at 0.4u orbits in about 6 seconds
        g.fillStyle = 'rgba(5,8,13,' + (PG.reducedMotion() ? .6 : .1) + ')'; g.fillRect(0, 0, w, h); g.lineWidth = 1.6; g.lineCap = 'round';
        for (var sub = 0; sub < 2; sub++) for (var i = 0; i < P.length; i++) {
          var p = P[i], ax = 0, ay = 0, dead = false, ox = p.x, oy = p.y;
          for (var j = 0; j < wells.length; j++) { var dx = wells[j].x - p.x, dy = wells[j].y - p.y, d2 = dx * dx + dy * dy + 400, inv = wells[j].m * k / (d2 * Math.sqrt(d2)); ax += dx * inv; ay += dy * inv; if (d2 < 520) dead = true; }
          p.vx += ax * dt / 2; p.vy += ay * dt / 2; p.x += p.vx * dt / 2; p.y += p.vy * dt / 2; p.age += dt / 2;
          if (dead || p.x < -50 || p.x > w + 50 || p.y < -50 || p.y > h + 50) { spawn(p); continue; }
          if (sub) { var sp = Math.min(1, Math.hypot(p.vx, p.vy) / (u * 1.1)); g.strokeStyle = 'hsla(' + (215 - sp * 170) + ',95%,' + (58 + sp * 16) + '%,.9)'; g.beginPath(); g.moveTo(ox, oy); g.lineTo(p.x, p.y); g.stroke(); }
        }
        wells.forEach(function (wl, i) {
          var r = 14 + wl.m * 6, gr = g.createRadialGradient(wl.x, wl.y, 1, wl.x, wl.y, r * 3.2); gr.addColorStop(0, 'rgba(155,140,255,.85)'); gr.addColorStop(.35, 'rgba(77,144,255,.25)'); gr.addColorStop(1, 'rgba(77,144,255,0)'); g.fillStyle = gr; g.beginPath(); g.arc(wl.x, wl.y, r * 3.2, 0, TAU); g.fill();
          g.fillStyle = '#05080d'; g.beginPath(); g.arc(wl.x, wl.y, r * .7, 0, TAU); g.fill(); g.strokeStyle = 'rgba(200,190,255,.8)'; g.lineWidth = 1.5; g.stroke();
        });
      });
      return { destroy: function () { lp.stop(); cv.destroy(); } };
    }
  });

  /* ------------------------------------------------------------------ Particle Storm */
  PG.register('quantum', 'storm', {
    title: 'Particle Storm', sub: 'A glowing storm on a swirling flow. Move to carve a vortex, hold to make it a tornado, click to fire a burst.',
    mount: function (host) {
      var cv = PG.canvas(host, 1.7), ctx = cv.ctx, N = 900, P = [], ptr = null, held = false, mode = 'lightning', i;
      function sp(p, burst) { p.x = burst ? burst.x : Math.random() * cv.w; p.y = burst ? burst.y : Math.random() * cv.h; var a = Math.random() * TAU, s = burst ? 120 + Math.random() * 420 : 0; p.vx = Math.cos(a) * s; p.vy = Math.sin(a) * s; p.life = 2 + Math.random() * 5; p.h = Math.random(); return p; }
      for (i = 0; i < N; i++) P.push(sp({}));
      cv.onresize = function () { ctx.fillStyle = '#05080d'; ctx.fillRect(0, 0, cv.w, cv.h); }; ctx.fillStyle = '#05080d'; ctx.fillRect(0, 0, cv.w, cv.h);
      PG.drag(cv.cv, { hover: true, down: function (e) { held = true; ptr = cv.pos(e); for (var k = 0; k < 90; k++) { var q = P[Math.floor(Math.random() * P.length)]; sp(q, ptr); } }, move: function (e) { ptr = cv.pos(e); }, up: function () { held = false; } });
      cv.cv.addEventListener('pointerleave', function () { if (!held) ptr = null; });
      var bar = PG.el('div', 'pg-bar'); host.appendChild(bar);
      PG.seg(bar, [['lightning', 'Lightning'], ['embers', 'Embers'], ['aurora', 'Aurora']], 'lightning', function (m) { mode = m; });
      var lp = PG.loop(function (dt, t) {
        var g = ctx, w = cv.w, h = cv.h; g.globalCompositeOperation = 'source-over'; g.fillStyle = 'rgba(5,8,13,' + (PG.reducedMotion() ? .55 : .14) + ')'; g.fillRect(0, 0, w, h);
        g.globalCompositeOperation = 'lighter'; g.lineWidth = 1.7; g.lineCap = 'round';
        for (i = 0; i < N; i++) {
          var p = P[i], x = p.x / w * 6, y = p.y / h * 4, a = Math.sin(x + t * .5) * Math.cos(y * 1.3 - t * .3) * 2 + Math.sin(y * 2.1 + x * .7 + t * .2) * 1.2, ax = Math.cos(a) * 260, ay = Math.sin(a) * 260;
          if (mode === 'embers') ay -= 150;
          if (ptr) { var dx = ptr.x - p.x, dy = ptr.y - p.y, d = Math.sqrt(dx * dx + dy * dy) + 12, k = Math.min(2.5, 240 / d) * (held ? 2.4 : 1); ax += (-dy / d * 900 + dx / d * (held ? 700 : 200)) * k; ay += (dx / d * 900 + dy / d * (held ? 700 : 200)) * k; }
          p.vx = (p.vx + ax * dt) * .96; p.vy = (p.vy + ay * dt) * .96; var ox = p.x, oy = p.y; p.x += p.vx * dt; p.y += p.vy * dt; p.life -= dt;
          if (p.life <= 0 || p.x < 0 || p.x > w || p.y < 0 || p.y > h) { sp(p); continue; }
          var s = Math.min(1, Math.hypot(p.vx, p.vy) / 380), hue = mode === 'lightning' ? 205 + s * 40 + p.h * 20 : mode === 'embers' ? 8 + s * 40 + p.h * 14 : 130 + s * 130 + p.h * 40;
          g.strokeStyle = 'hsla(' + hue + ',95%,' + (50 + s * 28) + '%,' + (.35 + s * .55) + ')'; g.beginPath(); g.moveTo(ox, oy); g.lineTo(p.x, p.y); g.stroke();
        }
        g.globalCompositeOperation = 'source-over';
      });
      return { destroy: function () { lp.stop(); cv.destroy(); } };
    }
  });

  /* ------------------------------------------------------------------ Orbit Challenge */
  PG.register('quantum', 'orbit', {
    title: 'Orbit Challenge', sub: 'Drag back from the probe like a slingshot, then release. Settle into the glowing band and complete one full lap without leaving it. Gravity is real: faster means higher.',
    mount: function (host) {
      var cv = PG.canvas(host, 1.7), ctx = cv.ctx, GM = 0.135, level = 1, best = PG.store.get('orbit-best', 1), S;
      var LV = [null, { rc: .55, hw: .16, rs: .38, ang: -90 }, { rc: .62, hw: .13, rs: .30, ang: 90 }, { rc: .5, hw: .11, rs: .42, ang: 200 }, { rc: .7, hw: .10, rs: .28, ang: -40 }, { rc: .58, hw: .08, rs: .22, ang: 140 }, { rc: .74, hw: .07, rs: .46, ang: -150 }, { rc: .48, hw: .06, rs: .3, ang: 20 }];
      function lv() { return LV[Math.min(level, LV.length - 1)]; }
      function reset() { S = { phase: 'aim', x: 0, y: 0, vx: 0, vy: 0, acc: 0, last: 0, trail: [], aim: null, t: 0 }; var L = lv(), a = L.ang * Math.PI / 180; S.x = Math.cos(a) * L.rs; S.y = Math.sin(a) * L.rs; msg.textContent = level > LV.length - 1 ? 'Endless mode: the band keeps its tightest width.' : 'Level ' + level + ': get into the band. A pull about ' + Math.round(Math.sqrt(GM / L.rs) / 1.1 / 0.9 * 100) + '% of the way out gives a circular orbit at your height; pull harder to climb.'; stats(); }
      var bar = PG.el('div', 'pg-bar'), st = PG.el('span', 'pg-stat'), msg = PG.el('div', 'pg-msg');
      function stats() { st.innerHTML = 'Level <b>' + level + '</b> · best <b>' + best + '</b>'; }
      var nxt = PG.button(bar, 'Next level', function () { level++; if (level > best) { best = level; PG.store.set('orbit-best', best); } reset(); nxt.hidden = true; }, true); nxt.hidden = true;
      PG.button(bar, 'Retry', function () { reset(); nxt.hidden = true; }); bar.appendChild(st); host.appendChild(bar); host.appendChild(msg);
      function U() { return Math.min(cv.w, cv.h) / 2 * 0.96; }
      function toWorld(p) { return { x: (p.x - cv.w / 2) / U(), y: (p.y - cv.h / 2) / U() }; }
      function launchVel(a) { return { vx: -a.dx * 1.1, vy: -a.dy * 1.1 }; }
      PG.drag(cv.cv, {
        down: function (e) { if (S.phase !== 'aim') return; var w = toWorld(cv.pos(e)); S.aim = { dx: w.x - S.x, dy: w.y - S.y, on: true }; },
        move: function (e, down) { if (down && S.aim && S.phase === 'aim') { var w = toWorld(cv.pos(e)), dx = w.x - S.x, dy = w.y - S.y, m = Math.hypot(dx, dy), cap = 0.9; if (m > cap) { dx *= cap / m; dy *= cap / m; } S.aim.dx = dx; S.aim.dy = dy; } },
        up: function () { if (S.aim && S.phase === 'aim' && Math.hypot(S.aim.dx, S.aim.dy) > 0.02) { var v = launchVel(S.aim); S.vx = v.vx; S.vy = v.vy; S.phase = 'fly'; S.acc = 0; S.last = Math.atan2(S.y, S.x); S.trail = []; msg.textContent = 'Flying...'; } S.aim = null; }
      });
      function stepSim(o, dt) { var r2 = o.x * o.x + o.y * o.y, r = Math.sqrt(r2), a = -GM / (r2 * r + 1e-9); o.vx += o.x * a * dt; o.vy += o.y * a * dt; o.x += o.vx * dt; o.y += o.vy * dt; }
      reset();
      var lp = PG.loop(function (dt) {
        var g = ctx, w = cv.w, h = cv.h, u = U(), cx = w / 2, cy = h / 2, L = lv(), PR = 0.07;
        if (S.phase === 'fly') {
          for (var k = 0; k < 8; k++) {
            stepSim(S, dt / 8); var r = Math.hypot(S.x, S.y);
            if (r < PR) { S.phase = 'lost'; msg.textContent = 'Crashed into the planet. Burn a bit harder sideways next time.'; break; }
            if (r > 1.5) { S.phase = 'lost'; msg.textContent = 'Escaped into deep space. Launch gentler.'; break; }
            var a = Math.atan2(S.y, S.x), da = a - S.last; if (da > Math.PI) da -= TAU; if (da < -Math.PI) da += TAU; S.last = a;
            if (Math.abs(r - L.rc) <= L.hw) { S.acc += Math.abs(da); if (S.acc >= TAU) { S.phase = 'won'; msg.textContent = 'Stable orbit! Level ' + level + ' complete.'; nxt.hidden = false; if (level + 1 > best) { best = level + 1; PG.store.set('orbit-best', best); } stats(); break; } } else S.acc = 0;
          }
          S.trail.push([S.x, S.y]); if (S.trail.length > 700) S.trail.shift();
        }
        g.fillStyle = '#05080d'; g.fillRect(0, 0, w, h);
        for (var s = 0; s < 70; s++) { var sx = (Math.sin(s * 91.7) * .5 + .5) * w, sy = (Math.sin(s * 47.3 + 2) * .5 + .5) * h; g.fillStyle = 'rgba(255,255,255,' + (0.12 + (s % 5) * .05) + ')'; g.fillRect(sx, sy, 1.5, 1.5); }
        g.beginPath(); g.arc(cx, cy, (L.rc + L.hw) * u, 0, TAU); g.arc(cx, cy, (L.rc - L.hw) * u, 0, TAU, true); g.fillStyle = 'rgba(53,224,176,.11)'; g.fill('evenodd');
        g.setLineDash([6, 6]); g.strokeStyle = 'rgba(53,224,176,.55)'; g.lineWidth = 1.2;[L.rc + L.hw, L.rc - L.hw].forEach(function (rr) { g.beginPath(); g.arc(cx, cy, rr * u, 0, TAU); g.stroke(); }); g.setLineDash([]);
        var gr = g.createRadialGradient(cx, cy, 2, cx, cy, PR * u * 2.6); gr.addColorStop(0, 'rgba(77,144,255,.9)'); gr.addColorStop(1, 'rgba(77,144,255,0)'); g.fillStyle = gr; g.beginPath(); g.arc(cx, cy, PR * u * 2.6, 0, TAU); g.fill();
        g.fillStyle = '#4d90ff'; g.beginPath(); g.arc(cx, cy, PR * u, 0, TAU); g.fill();
        if (S.phase === 'aim' && S.aim && Math.hypot(S.aim.dx, S.aim.dy) > .02) {   // preview the first stretch of the path
          var v = launchVel(S.aim), o = { x: S.x, y: S.y, vx: v.vx, vy: v.vy }; g.strokeStyle = 'rgba(245,184,61,.8)'; g.setLineDash([3, 5]); g.beginPath(); g.moveTo(cx + o.x * u, cy + o.y * u);
          for (var q = 0; q < 260; q++) { stepSim(o, 1 / 120); if (q % 4 === 0) g.lineTo(cx + o.x * u, cy + o.y * u); if (Math.hypot(o.x, o.y) < PR) break; } g.stroke(); g.setLineDash([]);
          g.strokeStyle = 'rgba(255,255,255,.5)'; g.beginPath(); g.moveTo(cx + S.x * u, cy + S.y * u); g.lineTo(cx + (S.x + S.aim.dx) * u, cy + (S.y + S.aim.dy) * u); g.stroke();
        }
        if (S.trail.length) { g.strokeStyle = S.phase === 'won' ? 'rgba(53,224,176,.9)' : 'rgba(245,184,61,.75)'; g.lineWidth = 2; g.beginPath(); S.trail.forEach(function (p, i) { if (i) g.lineTo(cx + p[0] * u, cy + p[1] * u); else g.moveTo(cx + p[0] * u, cy + p[1] * u); }); g.stroke(); }
        if (S.phase !== 'lost') { g.fillStyle = '#f5b83d'; g.shadowColor = '#f5b83d'; g.shadowBlur = 12; g.beginPath(); g.arc(cx + S.x * u, cy + S.y * u, 5, 0, TAU); g.fill(); g.shadowBlur = 0; }
        if (S.phase === 'fly') { g.fillStyle = 'rgba(255,255,255,.6)'; g.font = '12px system-ui'; g.fillText('Lap ' + Math.min(100, Math.round(S.acc / TAU * 100)) + '%', 12, 20); }
        if (S.phase === 'lost') { g.fillStyle = 'rgba(255,107,138,.9)'; g.font = '600 14px system-ui'; g.fillText('Press Retry to try again', 12, 22); }
      });
      return { destroy: function () { lp.stop(); cv.destroy(); } };
    }
  });

  /* ------------------------------------------------------------------ Signal Path */
  var DIRS = { E: [1, 0], W: [-1, 0], N: [0, -1], S: [0, 1] };
  var REFL = { '/': { E: 'N', N: 'E', W: 'S', S: 'W' }, '\\': { E: 'S', S: 'E', W: 'N', N: 'W' } };
  function genSignal(level, salt) {
    var cols = Math.min(6 + Math.floor(level / 2), 11), rows = Math.min(4 + Math.floor((level + 1) / 3), 7), tries = 0;
    for (;;) {
      var R = PG.rng(PG.dailySeed() * 131 + level * 17 + (salt || 0) * 7919 + tries++), used = {}, mir = {}, x = 0, y = Math.floor(R() * rows), r0 = y, ok = true, guard = 0;
      used[x + ',' + y] = 1;
      while (x < cols - 1 && guard++ < 40) {
        var nx = Math.min(cols - 1, x + 1 + Math.floor(R() * 3)), free = true, k;
        for (k = x + 1; k <= nx; k++) if (used[k + ',' + y]) free = false; if (!free) { ok = false; break; }
        for (k = x + 1; k <= nx; k++) used[k + ',' + y] = 1;
        if (nx === cols - 1 && (R() < .4 || guard > 8)) { x = nx; break; }
        var up = []; for (k = 1; k <= 3; k++) { if (y - k >= 0) up.push(-k); if (y + k < rows) up.push(k); }
        var dy = up[Math.floor(R() * up.length)]; if (dy === undefined) { ok = false; break; }
        var step = dy > 0 ? 1 : -1, y2 = y + dy; for (k = y + step; k !== y2 + step; k += step) if (used[nx + ',' + k]) free = false; if (!free) { ok = false; break; }
        for (k = y + step; k !== y2 + step; k += step) used[nx + ',' + k] = 1;
        mir[nx + ',' + y] = dy > 0 ? '\\' : '/';     // east -> south uses '\', east -> north uses '/'
        mir[nx + ',' + y2] = dy > 0 ? '\\' : '/';    // south -> east uses '\', north -> east uses '/'
        x = nx; y = y2;
      }
      if (!ok || x !== cols - 1) continue;
      var real = Object.keys(mir), cells = [];
      for (var cx = 0; cx < cols; cx++) for (var cy = 0; cy < rows; cy++) if (!used[cx + ',' + cy]) cells.push(cx + ',' + cy);
      var decoys = Math.min(cells.length, 2 + Math.floor(level * 0.8)), grid = {}; real.forEach(function (c) { grid[c] = { m: mir[c], real: true }; });
      for (var d = 0; d < decoys; d++) { var pi = Math.floor(R() * cells.length), c2 = cells.splice(pi, 1)[0]; grid[c2] = { m: R() < .5 ? '/' : '\\', real: false }; }
      real.forEach(function (c) { if (R() < .65) grid[c].m = grid[c].m === '/' ? '\\' : '/'; });
      var P = { cols: cols, rows: rows, src: r0, dst: y, grid: grid };
      if (trace(P).hit) { real.some(function (c) { grid[c].m = grid[c].m === '/' ? '\\' : '/'; return true; }); }
      if (!trace(P).hit) return P;
    }
  }
  function trace(P) {
    var x = 0, y = P.src, d = 'E', path = [[-1, y]], n = 0;
    while (n++ < 300) {
      var c = P.grid[x + ',' + y]; if (c) { d = REFL[c.m][d]; }
      path.push([x, y]); x += DIRS[d][0]; y += DIRS[d][1];
      if (x < 0 || y < 0 || y >= P.rows) return { path: path, hit: false };
      if (x >= P.cols) { path.push([x, y]); return { path: path, hit: d === 'E' && y === P.dst }; }
    }
    return { path: path, hit: false };
  }
  PG.register('quantum', 'signal', {
    title: 'Signal Path', sub: 'Route the beam from the emitter to the detector. Click a mirror to flip it between / and \\. Grey mirrors are decoys that still bend the light.',
    mount: function (host) {
      var cv = PG.canvas(host, 1.55), ctx = cv.ctx, level = 1, P, flips = 0, won = false, ang = {}, best = PG.store.get('signal-best', 1), t0 = 0;
      var bar = PG.el('div', 'pg-bar'), st = PG.el('span', 'pg-stat'), msg = PG.el('div', 'pg-msg');
      var nx = PG.button(bar, 'Next level', function () { level++; if (level > best) { best = level; PG.store.set('signal-best', best); } load(); }, true); nx.hidden = true;
      PG.button(bar, 'New layout', function () { level = Math.max(1, level); P = genSignal(level, 1 + Math.floor(Math.random() * 9999)); load(true); }); bar.appendChild(st); host.appendChild(bar); host.appendChild(msg);
      function load(alt) { P = alt ? P : genSignal(level); flips = 0; won = false; ang = {}; Object.keys(P.grid).forEach(function (k) { ang[k] = P.grid[k].m === '/' ? -45 : 45; }); nx.hidden = true; msg.textContent = 'Level ' + level + ': route the beam to the detector on the right.'; t0 = performance.now(); stat(); }
      function stat() { st.innerHTML = 'Level <b>' + level + '</b> · flips <b>' + flips + '</b> · best level <b>' + best + '</b>'; }
      function geom() { var mx = 46, cs = Math.min((cv.w - 2 * mx) / P.cols, (cv.h - 20) / P.rows), ox = mx + (cv.w - 2 * mx - cs * P.cols) / 2, oy = (cv.h - cs * P.rows) / 2; return { cs: cs, ox: ox, oy: oy }; }
      cv.cv.addEventListener('pointerdown', function (e) {
        if (won) return; var p = cv.pos(e), G = geom(), x = Math.floor((p.x - G.ox) / G.cs), y = Math.floor((p.y - G.oy) / G.cs), c = P.grid[x + ',' + y];
        if (c) { c.m = c.m === '/' ? '\\' : '/'; flips++; if (trace(P).hit) { won = true; msg.textContent = 'Signal locked in ' + flips + ' flips.'; nx.hidden = false; if (level + 1 > best) { best = level + 1; PG.store.set('signal-best', best); } } stat(); }
      });
      load();
      var lp = PG.loop(function (dt, t) {
        var g = ctx, w = cv.w, h = cv.h, G = geom(), cs = G.cs; g.fillStyle = '#05080d'; g.fillRect(0, 0, w, h);
        g.strokeStyle = 'rgba(255,255,255,.06)'; g.lineWidth = 1; for (var i = 0; i <= P.cols; i++) { g.beginPath(); g.moveTo(G.ox + i * cs, G.oy); g.lineTo(G.ox + i * cs, G.oy + P.rows * cs); g.stroke(); } for (i = 0; i <= P.rows; i++) { g.beginPath(); g.moveTo(G.ox, G.oy + i * cs); g.lineTo(G.ox + P.cols * cs, G.oy + i * cs); g.stroke(); }
        var tr = trace(P), pts = tr.path.map(function (p) { return [G.ox + (p[0] + .5) * cs, G.oy + (p[1] + .5) * cs]; });
        pts[0][0] = G.ox - 22; var last = pts[pts.length - 1]; if (tr.path[tr.path.length - 1][0] >= P.cols) last[0] = G.ox + P.cols * cs + 22;
        var col = won ? '53,224,176' : '255,120,90';
        g.lineJoin = 'round'; g.lineCap = 'round';[[10, .12], [5, .3], [2, 1]].forEach(function (L) { g.strokeStyle = 'rgba(' + col + ',' + L[1] + ')'; g.lineWidth = L[0]; g.beginPath(); pts.forEach(function (p, k) { if (k) g.lineTo(p[0], p[1]); else g.moveTo(p[0], p[1]); }); g.stroke(); });
        Object.keys(P.grid).forEach(function (k) {
          var c = P.grid[k], xy = k.split(','), cx = G.ox + (+xy[0] + .5) * cs, cy = G.oy + (+xy[1] + .5) * cs, target = c.m === '/' ? -45 : 45; ang[k] += (target - ang[k]) * Math.min(1, dt * 16);
          g.save(); g.translate(cx, cy); g.rotate(ang[k] * Math.PI / 180); var L = cs * .34;
                    g.strokeStyle = c.real ? '#9fc4ff' : '#7b8896'; g.lineWidth = 4; g.lineCap = 'round'; g.beginPath(); g.moveTo(-L, 0); g.lineTo(L, 0); g.stroke(); g.restore();
          g.save(); g.translate(cx, cy); g.fillStyle = c.real ? 'rgba(77,144,255,.14)' : 'rgba(255,255,255,.04)'; g.fillRect(-cs * .4, -cs * .4, cs * .8, cs * .8); g.strokeStyle = c.real ? 'rgba(159,196,255,.35)' : 'rgba(123,136,150,.22)'; g.strokeRect(-cs * .4, -cs * .4, cs * .8, cs * .8); g.restore();
        });
        var ey = G.oy + (P.src + .5) * cs; g.fillStyle = '#ff7a5a'; g.beginPath(); g.arc(G.ox - 22, ey, 8, 0, TAU); g.fill(); g.fillStyle = 'rgba(255,255,255,.6)'; g.font = '10px system-ui'; g.fillText('SRC', G.ox - 34, ey + 22);
        var dy = G.oy + (P.dst + .5) * cs, dx = G.ox + P.cols * cs + 28; g.strokeStyle = won ? '#35e0b0' : '#5b87a8'; g.lineWidth = 3; g.beginPath(); g.arc(dx - 6, dy, 11 + (won ? Math.sin(t * 8) * 2 : 0), 0, TAU); g.stroke(); g.fillStyle = won ? '#35e0b0' : 'rgba(91,135,168,.4)'; g.beginPath(); g.arc(dx - 6, dy, 5, 0, TAU); g.fill();
      });
      return { destroy: function () { lp.stop(); cv.destroy(); } };
    }
  });

  /* ------------------------------------------------------------------ Light Tunnel */
  function hash(n) { n = Math.imul(n ^ (n >>> 15), 2246822519); n = Math.imul(n ^ (n >>> 13), 3266489917); return ((n ^ (n >>> 16)) >>> 0) / 4294967296; }
  function pathAt(d) { return [Math.sin(d * .11) * .9 + Math.sin(d * .047 + 2) * .7, Math.cos(d * .083) * .55 + Math.sin(d * .031) * .4]; }
  PG.register('quantum', 'tunnel', {
    title: 'Light Tunnel', sub: 'Drift through a winding tunnel of light. Steer with the pointer or arrow keys and glide through the glowing orbs. No crashes, just flow.',
    mount: function (host) {
      var cv = PG.canvas(host, 1.7), ctx = cv.ctx, dist = 0, speed = 3, px = 0, py = 0, tx = 0, ty = 0, orbs = 0, best = PG.store.get('tunnel-best', 0), keys = {}, combo = 0, pulse = 0, got = {};
      var bar = PG.el('div', 'pg-bar'), st = PG.el('span', 'pg-stat'); host.appendChild(bar); bar.appendChild(st); PG.button(bar, 'Restart', function () { dist = 0; speed = 3; orbs = 0; combo = 0; got = {}; });
      PG.drag(cv.cv, { hover: true, down: function (e) { var p = cv.pos(e); tx = clamp((p.x - cv.w / 2) / (cv.h * .42), -1, 1); ty = clamp((p.y - cv.h / 2) / (cv.h * .42), -1, 1); }, move: function (e) { var p = cv.pos(e); tx = clamp((p.x - cv.w / 2) / (cv.h * .42), -1, 1); ty = clamp((p.y - cv.h / 2) / (cv.h * .42), -1, 1); } });
      var off = PG.keyHandler(function (e) { if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'a', 'd', 'w', 's'].indexOf(e.key) >= 0) { keys[e.key] = e.type; e.preventDefault(); } });
      function kd(e) { keys[e.key] = 1; } function ku(e) { keys[e.key] = 0; } window.addEventListener('keydown', kd); window.addEventListener('keyup', ku);
      function stat() { st.innerHTML = 'Distance <b>' + Math.floor(dist) + '</b> · orbs <b>' + orbs + '</b> · best <b>' + Math.floor(best) + '</b>'; }
      var lp = PG.loop(function (dt, t) {
        var g = ctx, w = cv.w, h = cv.h, cx = w / 2, cy = h / 2, R0 = h * .42, N = 34, hue = (dist * 2.2) % 360;
        if (keys.ArrowLeft || keys.a) tx -= dt * 1.6; if (keys.ArrowRight || keys.d) tx += dt * 1.6; if (keys.ArrowUp || keys.w) ty -= dt * 1.6; if (keys.ArrowDown || keys.s) ty += dt * 1.6;
        var m = Math.hypot(tx, ty); if (m > 1) { tx /= m; ty /= m; }
        px += (tx - px) * Math.min(1, dt * 5); py += (ty - py) * Math.min(1, dt * 5);
        speed = Math.min(9, 3 + dist / 260); dist += speed * dt; if (dist > best) { best = dist; PG.store.set('tunnel-best', Math.floor(best)); }
        var base = pathAt(dist), k0 = Math.floor(dist);
        g.fillStyle = '#05080d'; g.fillRect(0, 0, w, h);
        var bg = g.createRadialGradient(cx, cy, 5, cx, cy, h); bg.addColorStop(0, 'hsla(' + hue + ',80%,30%,.35)'); bg.addColorStop(1, 'rgba(5,8,13,0)'); g.fillStyle = bg; g.fillRect(0, 0, w, h);
        var prev = null;
        for (var k = k0 + N; k >= k0; k--) {
          var d = k - dist, s = 1 / (1 + d * .2), pa = pathAt(k), ccx = cx + (pa[0] - base[0]) * R0 * s * .9 - px * R0 * .25 * (1 - s) * .5, ccy = cy + (pa[1] - base[1]) * R0 * s * .9 - py * R0 * .25 * (1 - s) * .5, r = R0 * s, a = Math.max(0, Math.min(1, s * 1.6));
          g.strokeStyle = 'hsla(' + ((hue + k * 4) % 360) + ',90%,' + (45 + s * 25) + '%,' + a + ')'; g.lineWidth = 1 + s * 4; g.beginPath(); g.arc(ccx, ccy, r, 0, TAU); g.stroke();
          if (prev) { g.lineWidth = 1; g.strokeStyle = 'hsla(' + hue + ',80%,55%,' + a * .35 + ')'; g.beginPath(); for (var q = 0; q < 8; q++) { var an = q / 8 * TAU + k * .02; g.moveTo(ccx + Math.cos(an) * r, ccy + Math.sin(an) * r); g.lineTo(prev.x + Math.cos(an) * prev.r, prev.y + Math.sin(an) * prev.r); } g.stroke(); }
          prev = { x: ccx, y: ccy, r: r };
          if (hash(k * 7 + 3) < .3) {
            var ox = (hash(k * 13 + 1) - .5) * 1.5, oy = (hash(k * 29 + 5) - .5) * 1.3, fx = ccx + ox * r, fy = ccy + oy * r, size = 4 + s * 18;
            if (d < .12 && !got[k]) { var ddx = ox - px * .62, ddy = oy - py * .62; if (Math.hypot(ddx, ddy) < .36) { got[k] = 1; orbs++; combo++; pulse = 1; dist += .8; } else if (d < .05) got[k] = 1; }
            if (!got[k] || d > .12) { var og = g.createRadialGradient(fx, fy, 0, fx, fy, size * 2); og.addColorStop(0, 'rgba(255,255,255,' + a + ')'); og.addColorStop(.35, 'hsla(' + ((hue + 150) % 360) + ',95%,65%,' + a * .8 + ')'); og.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = og; g.beginPath(); g.arc(fx, fy, size * 2, 0, TAU); g.fill(); }
          }
        }
        pulse = Math.max(0, pulse - dt * 2.5);
        var rx = cx + px * R0 * .62, ry = cy + py * R0 * .62; g.strokeStyle = 'rgba(255,255,255,.85)'; g.lineWidth = 2; g.beginPath(); g.arc(rx, ry, 16 + pulse * 18, 0, TAU); g.stroke(); g.beginPath(); g.moveTo(rx - 6, ry); g.lineTo(rx + 6, ry); g.moveTo(rx, ry - 6); g.lineTo(rx, ry + 6); g.stroke();
        stat();
      });
      return { destroy: function () { lp.stop(); off(); window.removeEventListener('keydown', kd); window.removeEventListener('keyup', ku); cv.destroy(); } };
    }
  });
})();
