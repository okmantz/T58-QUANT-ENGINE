/* Playground / Fidgets: Infinity Cube (a 2x2x2 you can twist, with six secret combos), Liquid Playground, Particle Field.
   All canvas, all local, no network. Each mount() returns {destroy()}. */
(function () {
  var PG = window.PG;
  function TAU() { return Math.PI * 2; }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }

  /* ------------------------------------------------------------------ Infinity Cube */
  var FACE_COL = ['#35e0b0', '#4d90ff', '#9b8cff', '#f5b83d', '#ff6b8a', '#e8eef5'];
  var SECRETS = [
    { id: 'circle', name: 'Full circle', hint: 'Turn one face four times in a row.' },
    { id: 'trigger', name: 'The trigger', hint: 'A famous four-move shortcut: R U R′ U′.' },
    { id: 'wiggle', name: 'Wiggle', hint: 'Turn the top face back and forth twice.' },
    { id: 'stairs', name: 'Staircase', hint: 'Climb it: U R F U R F.' },
    { id: 'dizzy', name: 'Dizzy', hint: 'Spin the whole cube with the mouse until it makes you dizzy.' },
    { id: 'rewind', name: 'Rewind', hint: 'Scramble it, then undo every single move.' }
  ];
  /* integer rotation matrix about axis a (0 x, 1 y, 2 z) by k quarter turns (k = +1 / -1) */
  function qrot(a, k) {
    var c = 0, s = k, M = [[1, 0, 0], [0, 1, 0], [0, 0, 1]], i = (a + 1) % 3, j = (a + 2) % 3;
    M[i][i] = c; M[i][j] = -s; M[j][i] = s; M[j][j] = c; return M;
  }
  function frot(a, th) {
    var c = Math.cos(th), s = Math.sin(th), M = [[1, 0, 0], [0, 1, 0], [0, 0, 1]], i = (a + 1) % 3, j = (a + 2) % 3;
    M[i][i] = c; M[i][j] = -s; M[j][i] = s; M[j][j] = c; return M;
  }
  function mm(A, B) { var R = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]; for (var i = 0; i < 3; i++) for (var j = 0; j < 3; j++) R[i][j] = A[i][0] * B[0][j] + A[i][1] * B[1][j] + A[i][2] * B[2][j]; return R; }
  function mv(A, v) { return [A[0][0] * v[0] + A[0][1] * v[1] + A[0][2] * v[2], A[1][0] * v[0] + A[1][1] * v[1] + A[1][2] * v[2], A[2][0] * v[0] + A[2][1] * v[1] + A[2][2] * v[2]]; }
  function rnd3(M) { return M.map(function (r) { return r.map(Math.round); }); }
  var MOVES = { U: [1, -1, 1], D: [1, 1, -1], L: [0, -1, -1], R: [0, 1, 1], F: [2, -1, -1], B: [2, 1, 1] };   // axis, layer, direction

  PG.register('fidgets', 'cube', {
    title: 'Infinity Cube', sub: 'Drag to spin it. Twist a layer with the buttons (or U D L R F B on the keyboard, Shift for the reverse). Six secret combos are hidden in it.',
    mount: function (host) {
      var cv = PG.canvas(host, 1.7), ctx = cv.ctx, dead = false;
      var yaw = -0.7, pitch = 0.5, vyaw = 0.004, hist = [], queue = [], anim = null, scrambled = 0, spun = 0;
      var found = PG.store.get('cube-secrets', []), cubies = [];
      function reset() { cubies = []; for (var x = -1; x <= 1; x += 2) for (var y = -1; y <= 1; y += 2) for (var z = -1; z <= 1; z += 2) cubies.push({ p: [x, y, z], m: [[1, 0, 0], [0, 1, 0], [0, 0, 1]], o: [x, y, z] }); hist = []; queue = []; anim = null; scrambled = 0; trail(); }
      var FACES = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]];
      function view() { return mm(frot(0, pitch), frot(1, yaw)); }
      function draw() {
        var w = cv.w, h = cv.h, g = ctx; g.clearRect(0, 0, w, h);
        var bg = g.createRadialGradient(w / 2, h / 2, 10, w / 2, h / 2, Math.max(w, h) * .6); bg.addColorStop(0, '#0f1c2b'); bg.addColorStop(1, '#05080d'); g.fillStyle = bg; g.fillRect(0, 0, w, h);
        var V = view(), sc = Math.min(w, h) * 0.2, polys = [], A = null;
        if (anim) { var e = anim.t < .5 ? 2 * anim.t * anim.t : 1 - Math.pow(-2 * anim.t + 2, 2) / 2; A = frot(anim.mv[0], anim.mv[2] * Math.PI / 2 * e); }
        cubies.forEach(function (cb) {
          var moving = anim && cb.p[anim.mv[0]] === anim.mv[1];
          FACES.forEach(function (n, fi) {
            var outer = cb.o[0] === n[0] && n[0] || cb.o[1] === n[1] && n[1] || cb.o[2] === n[2] && n[2];
            var u = n[0] ? [0, 1, 0] : [1, 0, 0], v = n[2] ? [0, 1, 0] : [0, 0, 1], pts = [], k;
            [[-1, -1], [1, -1], [1, 1], [-1, 1]].forEach(function (q) {
              var l = [n[0] * .46 + u[0] * q[0] * .46 + v[0] * q[1] * .46, n[1] * .46 + u[1] * q[0] * .46 + v[1] * q[1] * .46, n[2] * .46 + u[2] * q[0] * .46 + v[2] * q[1] * .46];
              var wv = mv(cb.m, l); wv = [wv[0] + cb.p[0] * .5, wv[1] + cb.p[1] * .5, wv[2] + cb.p[2] * .5];
              if (moving) wv = mv(A, wv); pts.push(mv(V, wv));
            });
            var nw = mv(cb.m, n); if (moving) nw = mv(A, nw); nw = mv(V, nw);
            if (nw[2] > 0.02) return;
            var cz = (pts[0][2] + pts[1][2] + pts[2][2] + pts[3][2]) / 4;
            polys.push({ pts: pts, z: cz, n: nw, col: outer ? FACE_COL[fi] : '#18222e' });
          });
        });
        polys.sort(function (a, b) { return b.z - a.z; });
        var cam = 6.2;
        polys.forEach(function (p) {
          g.beginPath(); p.pts.forEach(function (q, i) { var f = cam / (cam + q[2]), X = w / 2 + q[0] * sc * f, Y = h / 2 + q[1] * sc * f; if (i) g.lineTo(X, Y); else g.moveTo(X, Y); }); g.closePath();
          var lit = clamp(0.9 - p.n[1] * 0.14 - p.n[0] * 0.1, 0.66, 1); g.fillStyle = p.col; g.fill();
          g.fillStyle = 'rgba(0,0,0,' + (1 - lit) * 0.9 + ')'; g.fill();
          g.lineJoin = 'round'; g.lineWidth = 1.2; g.strokeStyle = 'rgba(2,6,10,.9)'; g.stroke();
        });
      }
      PG.drag(cv.cv, {
        down: function (e) { cv.cv._lx = e.clientX; cv.cv._ly = e.clientY; vyaw = 0; },
        move: function (e, down) { if (!down) return; var dx = e.clientX - cv.cv._lx, dy = e.clientY - cv.cv._ly; cv.cv._lx = e.clientX; cv.cv._ly = e.clientY; yaw += dx * .01; pitch = clamp(pitch + dy * .01, -1.4, 1.4); spun += Math.abs(dx) * .01 + Math.abs(dy) * .01; if (spun > 40) unlock('dizzy'); },
        up: function () { vyaw = 0.003; }
      });
      var msg = PG.el('div', 'pg-msg'), trailEl = PG.el('div', 'cube-trail'), secEl = PG.el('div', 'cube-secrets');
      function trail() { trailEl.innerHTML = hist.length ? '<span>Moves:</span>' : '<span>Make a move to start your trail.</span>'; hist.slice(-16).forEach(function (m) { trailEl.appendChild(PG.el('i', '', m)); }); }
      function chips() {
        secEl.innerHTML = '<div class="hd"><b>Secrets <span style="color:var(--text-muted);font-weight:500">' + found.length + ' / ' + SECRETS.length + '</span></b></div><div class="chips"></div>';
        var c = secEl.querySelector('.chips'); SECRETS.forEach(function (s) { var ok = found.indexOf(s.id) >= 0, d = PG.el('div', 'chip' + (ok ? ' ok' : ''), '<b>' + (ok ? s.name : '???') + '</b><small>' + (ok ? 'Found. ' : '') + s.hint + '</small>'); c.appendChild(d); });
      }
      function unlock(id) { if (found.indexOf(id) >= 0) return; found.push(id); PG.store.set('cube-secrets', found); var s = SECRETS.filter(function (x) { return x.id === id; })[0]; msg.textContent = 'Secret found: ' + s.name + '!'; chips(); }
      function check() {
        var n = hist.length, last = function (k) { return hist.slice(-k).join(' '); };
        if (n >= 4 && hist.slice(-4).every(function (m) { return m === hist[n - 1]; })) unlock('circle');
        if (last(4) === "R U R' U'") unlock('trigger'); if (last(4) === "U U' U U'" || last(4) === "U' U U' U") unlock('wiggle'); if (last(6) === 'U R F U R F') unlock('stairs');
      }
      function name(k, dir) { return k + (dir < 0 ? "'" : ''); }
      function inv(m) { return m.slice(-1) === "'" ? m[0] : m + "'"; }
      function doMove(k, dir, silent) {
        var mvd = MOVES[k]; queue.push({ mv: [mvd[0], mvd[1], mvd[2] * dir], nm: name(k, dir), silent: silent });
      }
      function step(dt) {
        if (!anim && queue.length) { anim = queue.shift(); anim.t = 0; }
        if (anim) {
          anim.t += dt / (anim.fast ? .09 : .24);
          if (anim.t >= 1) {
            var R = qrot(anim.mv[0], anim.mv[2]); cubies.forEach(function (cb) { if (cb.p[anim.mv[0]] === anim.mv[1]) { cb.p = mv(R, cb.p).map(Math.round); cb.m = rnd3(mm(R, cb.m)); } });
            if (!anim.silent) { hist.push(anim.nm); if (hist.length > 200) hist.shift(); trail(); check(); } anim = null;
          }
        }
      }
      var bar = PG.el('div', 'pg-bar'); host.appendChild(bar);
      Object.keys(MOVES).forEach(function (k) {
        var grp = PG.el('div', 'pg-seg'); [[k, 1], [k + "'", -1]].forEach(function (d) { var b = PG.el('button', '', d[0].replace("'", '′')); b.type = 'button'; b.setAttribute('aria-label', 'Turn ' + d[0]); b.onclick = function () { scrambled = Math.max(0, scrambled); doMove(k, d[1]); }; grp.appendChild(b); }); bar.appendChild(grp);
      });
      var bar2 = PG.el('div', 'pg-bar'); host.appendChild(bar2);
      PG.button(bar2, 'Scramble', function () {
        var ks = Object.keys(MOVES), prev = ''; for (var i = 0; i < 10; i++) { var k; do { k = ks[Math.floor(Math.random() * 6)]; } while (k === prev); prev = k; var d = Math.random() < .5 ? 1 : -1; var a = { mv: [MOVES[k][0], MOVES[k][1], MOVES[k][2] * d], nm: name(k, d), fast: true }; queue.push(a); }
        scrambled = 10; msg.textContent = 'Scrambled. Now undo it however you like.';
      });
      PG.button(bar2, 'Undo move', function () { if (!hist.length || queue.length || anim) return; var m = hist.pop(); var k = m[0], d = m.slice(-1) === "'" ? 1 : -1; queue.push({ mv: [MOVES[k][0], MOVES[k][1], MOVES[k][2] * d], nm: m, silent: true }); trail(); if (!hist.length && scrambled >= 8) { unlock('rewind'); } });
      PG.button(bar2, 'Undo all', function () {
        if (queue.length || anim) return; var n = hist.length; var had = scrambled >= 8 && n >= 8;
        hist.slice().reverse().forEach(function (m) { var k = m[0], d = m.slice(-1) === "'" ? 1 : -1; queue.push({ mv: [MOVES[k][0], MOVES[k][1], MOVES[k][2] * d], nm: m, silent: true, fast: true }); });
        hist = []; trail(); if (had) setTimeout(function () { unlock('rewind'); }, n * 90 + 100);
      });
      PG.button(bar2, 'Reset', function () { reset(); msg.textContent = ''; });
      host.appendChild(msg); host.appendChild(trailEl); host.appendChild(secEl); chips(); reset();
      var off = PG.keyHandler(function (e) { var k = e.key.toUpperCase(); if (MOVES[k] && !e.ctrlKey && !e.metaKey && !e.altKey) { doMove(k, e.shiftKey ? -1 : 1); e.preventDefault(); } });
      var lp = PG.loop(function (dt) { if (!dead) { step(dt); if (!PG.reducedMotion()) yaw += vyaw; draw(); } });
      return { destroy: function () { dead = true; lp.stop(); off(); cv.destroy(); } };
    }
  });

  /* ------------------------------------------------------------------ Liquid Playground */
  PG.register('fidgets', 'liquid', {
    title: 'Liquid Playground', sub: 'A ring of liquid light. Push it with the pointer, click for a ripple, hold to stir.',
    mount: function (host) {
      var cv = PG.canvas(host, 1.7), ctx = cv.ctx, N = 180, r = new Float32Array(N), v = new Float32Array(N), ptr = null, held = false, hue = 160, mode = 'light';
      function ang(i) { return i / N * TAU(); }
      PG.drag(cv.cv, {
        hover: true,
        down: function (e) { held = true; ptr = cv.pos(e); ripple(ptr); }, move: function (e) { ptr = cv.pos(e); }, up: function () { held = false; }
      });
      cv.cv.addEventListener('pointerleave', function () { if (!held) ptr = null; });
      function ripple(p) { var cx = cv.w / 2, cy = cv.h / 2, a = Math.atan2(p.y - cy, p.x - cx), i0 = Math.round((a < 0 ? a + TAU() : a) / TAU() * N); for (var k = -10; k <= 10; k++) v[(i0 + k + N) % N] += 260 * Math.exp(-k * k / 20) * (Math.hypot(p.x - cx, p.y - cy) < Math.min(cv.w, cv.h) * .3 ? -1 : 1); }
      function bar() { var b = PG.el('div', 'pg-bar'); host.appendChild(b); PG.seg(b, [['light', 'Light'], ['ink', 'Ink'], ['ember', 'Ember']], 'light', function (m) { mode = m; }); PG.button(b, 'Splash', function () { for (var i = 0; i < N; i++) v[i] += (Math.random() - .5) * 700; }); }
      bar();
      var lp = PG.loop(function (dt, t) {
        var w = cv.w, h = cv.h, cx = w / 2, cy = h / 2, R = Math.min(w, h) * .3, g = ctx, i;
        for (i = 0; i < N; i++) {
          var l = r[(i + N - 1) % N], rr = r[(i + 1) % N], a = ang(i), f = -60 * r[i] + 900 * (l + rr - 2 * r[i]) - 3.2 * v[i];
          f += Math.sin(a * 3 + t * 1.3) * 26 + Math.sin(a * 5 - t * .9) * 14;   // slow idle breathing so it is never still
          if (ptr) { var px = cx + Math.cos(a) * (R + r[i]), py = cy + Math.sin(a) * (R + r[i]), dx = px - ptr.x, dy = py - ptr.y, d2 = dx * dx + dy * dy, s = Math.max(30, R * .35); if (d2 < s * s * 4) { var k = Math.exp(-d2 / (s * s)); f += (held ? -1 : 1) * 2200 * k * (Math.cos(a) * dx + Math.sin(a) * dy) / (Math.sqrt(d2) + 1); } }
          v[i] += f * dt;
        }
        for (i = 0; i < N; i++) { r[i] = clamp(r[i] + v[i] * dt, -R * .7, R * .7); }
        hue = (hue + dt * 18) % 360;
        g.globalCompositeOperation = 'source-over'; g.fillStyle = mode === 'ink' ? 'rgba(244,240,230,1)' : '#05080d'; g.fillRect(0, 0, w, h);
        g.globalCompositeOperation = mode === 'ink' ? 'multiply' : 'lighter'; g.lineCap = 'round';
        var pal = mode === 'ember' ? [10, 55] : mode === 'ink' ? [215, 240] : [hue, hue + 120];
        [[16, .09], [8, .18], [3, .95]].forEach(function (L) {
          for (i = 0; i < N; i++) {
            var j = (i + 1) % N, a1 = ang(i), a2 = ang(j), p1 = R + r[i], p2 = R + r[j];
            g.beginPath(); g.moveTo(cx + Math.cos(a1) * p1, cy + Math.sin(a1) * p1); g.lineTo(cx + Math.cos(a2) * p2, cy + Math.sin(a2) * p2);
            var hh = pal[0] + (pal[1] - pal[0]) * (0.5 + 0.5 * Math.sin(a1 * 2 + t * .6)) + Math.abs(v[i]) * .04;
            g.strokeStyle = mode === 'ink' ? 'hsla(' + hh + ',55%,22%,' + L[1] + ')' : 'hsla(' + hh + ',95%,' + (L[0] === 3 ? 72 : 58) + '%,' + L[1] + ')'; g.lineWidth = L[0] + Math.abs(v[i]) * .01; g.stroke();
          }
        });
        g.globalCompositeOperation = 'source-over';
      });
      return { destroy: function () { lp.stop(); cv.destroy(); } };
    }
  });

  /* ------------------------------------------------------------------ Particle Field */
  PG.register('fidgets', 'field', {
    title: 'Particle Field', sub: 'A few hundred particles drifting on a flow. Your pointer attracts, repels or swirls them.',
    mount: function (host) {
      var cv = PG.canvas(host, 1.7), ctx = cv.ctx, N = 520, P = [], ptr = null, mode = 'attract', down = false, i;
      function seed() { P = []; for (i = 0; i < N; i++) P.push({ x: Math.random() * cv.w, y: Math.random() * cv.h, vx: 0, vy: 0, h: Math.random() * 60 }); }
      seed(); cv.onresize = function () { ctx.fillStyle = '#05080d'; ctx.fillRect(0, 0, cv.w, cv.h); };
      PG.drag(cv.cv, { hover: true, down: function (e) { down = true; ptr = cv.pos(e); }, move: function (e) { ptr = cv.pos(e); }, up: function () { down = false; } });
      cv.cv.addEventListener('pointerleave', function () { if (!down) ptr = null; });
      var b = PG.el('div', 'pg-bar'); host.appendChild(b);
      PG.seg(b, [['attract', 'Attract'], ['repel', 'Repel'], ['swirl', 'Swirl']], 'attract', function (m) { mode = m; });
      PG.button(b, 'Scatter', function () { P.forEach(function (p) { p.vx += (Math.random() - .5) * 600; p.vy += (Math.random() - .5) * 600; }); });
      ctx.fillStyle = '#05080d'; ctx.fillRect(0, 0, cv.w, cv.h);
      var lp = PG.loop(function (dt, t) {
        var g = ctx, w = cv.w, h = cv.h; g.fillStyle = 'rgba(5,8,13,' + (PG.reducedMotion() ? .5 : .08) + ')'; g.fillRect(0, 0, w, h); g.lineWidth = 2; g.lineCap = 'round';
        for (i = 0; i < N; i++) {
          var p = P[i], fa = Math.sin(p.x * .008 + t * .25) * 3 + Math.cos(p.y * .009 - t * .2) * 3, ax = Math.cos(fa) * 120, ay = Math.sin(fa) * 120;
          if (ptr) { var dx = ptr.x - p.x, dy = ptr.y - p.y, d = Math.sqrt(dx * dx + dy * dy) + 8, k = Math.min(1, 160 / d) * (down ? 2.6 : 1), nx = dx / d, ny = dy / d;
            if (mode === 'attract') { ax += nx * 900 * k; ay += ny * 900 * k; } else if (mode === 'repel') { ax -= nx * 1100 * k; ay -= ny * 1100 * k; } else { ax += -ny * 1000 * k + nx * 180 * k; ay += nx * 1000 * k + ny * 180 * k; } }
          p.vx = (p.vx + ax * dt) * .975; p.vy = (p.vy + ay * dt) * .975;
          var ox = p.x, oy = p.y; p.x += p.vx * dt; p.y += p.vy * dt;
          if (p.x < 0) p.x += w; else if (p.x > w) p.x -= w; if (p.y < 0) p.y += h; else if (p.y > h) p.y -= h;
          if (Math.abs(p.x - ox) > w / 2 || Math.abs(p.y - oy) > h / 2) continue;
          var sp = Math.min(1, Math.sqrt(p.vx * p.vx + p.vy * p.vy) / 420);
          g.strokeStyle = 'hsla(' + (165 + sp * 130 + p.h) + ',95%,' + (60 + sp * 20) + '%,' + (.6 + sp * .4) + ')'; g.beginPath(); g.moveTo(ox, oy); g.lineTo(p.x, p.y); g.stroke();
        }
      });
      return { destroy: function () { lp.stop(); cv.destroy(); } };
    }
  });
})();
