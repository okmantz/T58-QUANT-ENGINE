/* Playground / Daily Puzzles: Infinite Maze, Daily chess puzzle (mate in 1-2, verified by the engine), Chart analyzer. Same set for everyone each day. */
(function () {
  var PG = window.PG, CH = PG.chess;
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function dayNum(s) { var p = s.split('-'); return Math.round(Date.UTC(+p[0], +p[1] - 1, +p[2]) / 864e5); }
  /* a streak counts consecutive days with something solved; key = store key holding {last, n} */
  function bumpStreak(key) {
    var t = PG.today(), s = PG.store.get(key, { last: '', n: 0 }); if (s.last === t) return s;
    s = { last: t, n: s.last && dayNum(t) - dayNum(s.last) === 1 ? s.n + 1 : 1 }; PG.store.set(key, s); return s;
  }
  function streakNow(key) { var s = PG.store.get(key, { last: '', n: 0 }); return s.last && dayNum(PG.today()) - dayNum(s.last) <= 1 ? s.n : 0; }
  /* mate puzzles generated offline by random engine play, then every one re-checked by the rules engine */
var P1 = ["3rkbnr/p4pp1/2n5/qpp4p/4PPb1/P7/1PP1N1PP/RNK2B1R b - - 0 1", "r3k2r/2p2ppp/6n1/pP2b3/2q3P1/2P1Pp1B/1P1K1P2/1RB5 b kq - 0 1", "r6r/p1pknppp/8/3bp3/4p2P/PP2Kn2/4NP2/R1B4q b - - 0 1", "r6r/p2k1p1p/2p5/3bpnP1/4pN2/PP3n2/4KP2/R1B4q b - - 0 1", "r4rk1/p4pp1/R1p3qp/1p1pB3/1PPP4/5P2/1P4PP/4QbK1 b - - 0 1", "rn1kr3/pb3Qp1/2p1p1N1/3pB2p/1b1P4/2p2P2/PP1N1KPP/R4B1R w - - 0 1", "r5nr/1pp1Bpkp/8/p3p3/7N/1P3q2/P1PQ1PPP/1R2KB1R w K - 0 1", "r3k1nr/pp3pp1/1b2p2p/1P6/P3PPq1/1P6/3Q2P1/2B1R2K b kq - 0 1", "1k3b1r/1ppr2pp/5p2/p2q1p2/8/1P2K3/P1P2P1P/5R1R b - - 0 1", "r1b2nk1/1pp3rp/2P4p/p7/P1Pqp2P/3p1P2/RP5K/1N4NR b - - 0 1", "r2qkb1r/2pnp1p1/pp2pn2/3p3p/3P4/2NBP3/PPPB1PPP/R2QK2R w KQkq h6 0 1", "r1b2b1r/pp2k1p1/2p1pn1p/5P2/3p2PK/3Pp2P/PP2q3/R1B2B1R b - - 0 1", "r1b3kr/pp2Bpp1/2p4p/1B1n2P1/8/1Pq1Pp1P/P4P2/R4KR1 b - - 0 1", "r3k2B/p1p5/2b3pp/1p3n1P/3P2P1/1B1KpP2/PPP2q2/R5N1 b - - 0 1", "r1b1kbnr/ppp2ppp/8/3pP3/Pn5q/6PP/1PPPP3/RNBQKBNR b KQkq - 0 1", "r1b1k3/1pn1r3/7p/p2p2p1/P2P1q1P/2PK4/2P2p2/1R3BNR b q - 0 1", "r1b2knr/1pp2ppp/3b4/pB1N4/5nPQ/4KP2/PPPB3P/R5NR w - - 0 1", "r1b1k3/2pn4/p3p1Np/3p1pp1/1KnP4/2P2P2/PP4PP/3q4 b - - 0 1", "r3kb1r/pQ1bpppp/2P4n/8/4P3/p1q5/P2N1PPP/R3KBNR w KQkq - 0 1", "rn2k1nr/ppp2pp1/8/4p2p/4P2q/N2P1b2/P1Pb3P/RQ3BKR b kq - 0 1", "r2qk2r/2pb1ppp/Qp2p3/3p1n2/p2n1P1P/K1P2N2/PP1N1PP1/R4B1R b kq - 0 1", "6kr/1pp2pp1/p1b1r3/3p4/3PqPKp/N1B4R/PPP2P2/R7 b - - 0 1", "6kr/1pp1r1p1/p1b2p2/3p4/3PqPKp/2B5/PPP2P1R/RN6 b - - 0 1", "r2k1r2/p2n3p/1pp2Pp1/P2p1Q2/2NP4/5p1N/1PP3q1/1RB1K1b1 b - - 0 1", "R3b1k1/1pp2ppp/8/1PP1p1B1/8/1K2nN2/1PP2PPP/8 w - - 0 1", "2r1kb1r/p1p1p2p/5p2/1p3n2/1P1nqp2/P4N2/1KP1PPPP/R4B1R b - - 0 1", "r3kb1r/pp3ppp/n7/2P1p3/7q/1PN1p2P/P1P1PP2/R2QKBNR b KQkq - 0 1", "2k2b1r/p1p1pp1p/6pn/1B1Q4/3P4/4P3/PPP2PPP/RNB1K1NR w KQ - 0 1", "rn1k3r/p3bp1p/4q3/1K4pP/2p1p1n1/8/PPPB4/RN6 b - - 0 1", "r1b3kr/1p3ppp/7n/p1B1Q3/6P1/2P1P3/P3KP1P/R4BNR w - - 0 1", "rn2kb1r/pp1b1ppp/2p1p2n/6q1/2pP4/4P2K/PPQ2PPP/RNB2BNR b kq - 0 1", "5k1r/rpp2ppp/2B5/5b1n/pb6/5NPP/PBP1KP2/R2Q1N1R w - - 0 1", "r3k2r/p1p5/7p/1PP1Pp2/3Pp2q/4P3/P1QB4/R4RK1 b - - 0 1", "4qb2/r1pbk1p1/1p2p2r/3p4/3PnPK1/P2Q3P/1PP1N1P1/R4R2 b - - 0 1", "rnb1k1nr/ppp2ppp/4p3/3p4/3b1P1q/1P6/P1PNPNP1/1RBQKB1R b Kkq - 0 1", "r1b2k1r/pp2n1pp/1qp1p1Q1/1B1pNp2/3P4/4P3/PPPB1PPP/R3K2R w KQ - 0 1", "r3kb1r/pppnppp1/8/1B1p1q1p/3PP3/6K1/PPP3PP/RNB3NR b kq - 0 1", "2b2rk1/1pp2pnp/rn1b1qQK/3p2p1/3P3P/2P1P1N1/PP3PP1/R1B4R b - - 0 1", "r1bqk1nr/ppp3pN/8/4p3/1bp1p2P/4P3/PP1BKPP1/R4B1R b kq h3 0 1", "rnb1kbnr/1pp3pp/p7/3pppq1/1P3P2/2N4P/P1PPP1P1/R1BQKB1R b KQkq f3 0 1"];
  var P2 = ["r3kbnr/p4pp1/2n5/qpp4p/4PPb1/P7/1PP1N1PP/RN1K1B1R b - - 0 1", "r1b2nk1/1pp2r1p/2P4p/p7/P1Pqp2P/3p1PK1/RP6/1N4NR b - - 0 1", "r1b1k3/2pn4/p3p1Np/3p1pp1/1K1P4/2P1nP2/PP4PP/3q4 b - - 0 1", "r1b1k3/2pn4/p3p1Np/K2p1pp1/3P4/2P1nP2/PP4PP/3q4 b - - 0 1", "Q1bk3r/p5pp/np1N1p2/2bPP3/3N4/6K1/PP4PP/2R4R w - - 0 1", "r1b1k2r/pp1n1ppp/2n1p3/1Kpp4/3P1P2/NP1BPN2/P1P3PP/R1B4R b kq - 0 1", "3rk2r/2p2p1p/1p2p2p/p3PP2/Pb1Nb1P1/8/2P4P/2RK1B1R b k - 0 1", "r2k3r/pp2qppp/2p1p2n/3p3K/1n1PPP1P/N2P4/PP3P2/R1B3NR b - - 0 1", "4k2N/1pP3pp/4Pp2/p7/2B5/4B3/PP1K1PPP/1N2n3 w - - 0 1", "5k2/1p3p2/7b/pn2p3/4p1r1/8/1PP1nP2/4K3 b - - 0 1", "7B/p3kp1p/2Q3p1/8/1r2p2P/R3K1P1/2P2P2/6NR w - - 0 1", "1rb2b2/Qp1n1kpr/8/2p2K1p/P3PB2/1PN2P1P/2P5/1R3BNR b - - 0 1", "r2k2nr/pp1b1p2/4p1p1/K2p3p/2pPPq2/7P/PPP2PP1/1R1Q1BNR b - - 0 1", "rnb2bnr/1p3pp1/3kp3/1Bp3qp/2KPp3/1P6/P1P2PPP/RN4NR b - - 0 1", "4k1r1/2p1qp2/4b3/3pQ3/2pP4/p1P5/Pr3PPP/1R4KR b - - 0 1"];

  /* ------------------------------------------------------------------ Infinite Maze */
  function makeMaze(n, seed) {
    var R = PG.rng(seed), W = [], i, j; for (i = 0; i < n * n; i++) W.push(15);   // bits: 1 N, 2 E, 4 S, 8 W
    var seen = new Uint8Array(n * n), stack = [0]; seen[0] = 1;
    var D = [[0, -1, 1, 4], [1, 0, 2, 8], [0, 1, 4, 1], [-1, 0, 8, 2]];
    while (stack.length) {
      var c = stack[stack.length - 1], x = c % n, y = (c / n) | 0, opts = [];
      D.forEach(function (d) { var nx = x + d[0], ny = y + d[1]; if (nx >= 0 && ny >= 0 && nx < n && ny < n && !seen[ny * n + nx]) opts.push(d); });
      if (!opts.length) { stack.pop(); continue; }
      var d = opts[Math.floor(R() * opts.length)], nc = (y + d[1]) * n + x + d[0]; W[c] &= ~d[2]; W[nc] &= ~d[3]; seen[nc] = 1; stack.push(nc);
    }
    for (j = 0; j < n * n * 0.04; j++) { var q = Math.floor(R() * n * n), dd = D[Math.floor(R() * 4)], qx = q % n + dd[0], qy = ((q / n) | 0) + dd[1]; if (qx >= 0 && qy >= 0 && qx < n && qy < n) { W[q] &= ~dd[2]; W[qy * n + qx] &= ~dd[3]; } }   // a few loops so it is not a pure tree
    return W;
  }
  PG.register('puzzles', 'maze', {
    title: 'Infinite Maze', sub: 'Reach the glowing exit. Arrow keys or WASD, or tap a spot to walk there. Every level is the same for everyone today and grows bigger.',
    mount: function (host) {
      var wrapEl = PG.el('div'); wrapEl.style.cssText = 'max-width:620px;margin:0 auto'; host.appendChild(wrapEl);
      var cv = PG.canvas(wrapEl, 1), ctx = cv.ctx, dead = false;
      var level = 1, n, W, pos, trail, t0, finished, fog = PG.store.get('maze-fog', false), path = [], moves = 0, walkT = 0, best = PG.store.get('maze-best', { level: 0 });
      var bar = PG.el('div', 'pg-bar'); host.appendChild(bar);
      var info = PG.el('span', 'pg-stat'), strk = PG.el('span', 'pg-stat'); bar.appendChild(info); bar.appendChild(strk);
      PG.seg(bar, [[false, 'Clear view'], [true, 'Fog of war']], fog, function (v) { fog = v; PG.store.set('maze-fog', v); });
      PG.button(bar, 'Restart level', function () { load(level); });
      var next = PG.button(bar, 'Next level', function () { load(level + 1); }, true); next.hidden = true;
      var msg = PG.el('div', 'pg-msg'); host.appendChild(msg);
      function load(l) { level = l; n = Math.min(7 + l * 2, 31); W = makeMaze(n, PG.dailySeed() * 100 + l); pos = 0; trail = { 0: 1 }; t0 = performance.now(); finished = false; path = []; moves = 0; next.hidden = true; msg.textContent = ''; stats(); }
      function stats() { info.innerHTML = 'Level <b>' + level + '</b> · ' + n + '×' + n + (best.level ? ' · best <b>' + best.level + '</b>' : ''); strk.innerHTML = 'Daily streak <b>' + streakNow('maze-streak') + '</b>'; }
      function step(dx, dy) {
        if (finished) return false; var x = pos % n, y = (pos / n) | 0, bit = dx === 1 ? 2 : dx === -1 ? 8 : dy === 1 ? 4 : 1; if (W[pos] & bit) return false;
        pos = (y + dy) * n + x + dx; trail[pos] = 1; moves++; if (pos === n * n - 1) done(); return true;
      }
      function done() {
        finished = true; path = []; var secs = (performance.now() - t0) / 1000; if (level > best.level) { best = { level: level }; PG.store.set('maze-best', best); } bumpStreak('maze-streak');
        msg.textContent = 'Level ' + level + ' cleared in ' + PG.fmtTime(secs) + ' with ' + moves + ' steps. Next one is ' + Math.min(7 + (level + 1) * 2, 31) + '×' + Math.min(7 + (level + 1) * 2, 31) + '.'; next.hidden = false; stats();
      }
      function bfs(to) {
        var prev = new Int32Array(n * n).fill(-1), q = [pos]; prev[pos] = pos;
        while (q.length) { var c = q.shift(); if (c === to) break; var x = c % n, y = (c / n) | 0;[[0, -1, 1], [1, 0, 2], [0, 1, 4], [-1, 0, 8]].forEach(function (d) { if (W[c] & d[2]) return; var nc = (y + d[1]) * n + x + d[0]; if (prev[nc] < 0) { prev[nc] = c; q.push(nc); } }); }
        if (prev[to] < 0) return []; var out = [], c2 = to; while (c2 !== pos) { out.push(c2); c2 = prev[c2]; } return out.reverse();
      }
      cv.cv.addEventListener('pointerdown', function (e) { if (finished) return; var p = cv.pos(e), cs = cv.w / n, c = clamp(Math.floor(p.x / cs), 0, n - 1), r = clamp(Math.floor(p.y / cs), 0, n - 1); path = bfs(r * n + c); });
      var off = PG.keyHandler(function (e) { if (e.ctrlKey || e.metaKey || e.altKey) return; var k = e.key, d = { ArrowUp: [0, -1], w: [0, -1], ArrowDown: [0, 1], s: [0, 1], ArrowLeft: [-1, 0], a: [-1, 0], ArrowRight: [1, 0], d: [1, 0] }[k]; if (d) { e.preventDefault(); path = []; step(d[0], d[1]); } });
      load(1);
      var lp = PG.loop(function (dt, t) {
        walkT += dt; if (path.length && walkT > 0.035) { walkT = 0; var nx = path.shift(), dx = (nx % n) - (pos % n), dy = ((nx / n) | 0) - ((pos / n) | 0); step(dx, dy); }
        var g = ctx, w = cv.w, cs = w / n, px = (pos % n + .5) * cs, py = (((pos / n) | 0) + .5) * cs;
        g.fillStyle = '#05080d'; g.fillRect(0, 0, w, cv.h);
        for (var i = 0; i < n * n; i++) if (trail[i]) { g.fillStyle = 'rgba(53,224,176,.10)'; g.fillRect((i % n) * cs, ((i / n) | 0) * cs, cs, cs); }
        var ex = (n - .5) * cs, pulse = 0.5 + 0.5 * Math.sin(t * 3); var gr = g.createRadialGradient(ex, ex, 1, ex, ex, cs * (1.1 + pulse * .4)); gr.addColorStop(0, 'rgba(245,184,61,.95)'); gr.addColorStop(1, 'rgba(245,184,61,0)'); g.fillStyle = gr; g.fillRect(ex - cs * 2, ex - cs * 2, cs * 4, cs * 4);
        g.strokeStyle = '#5b87a8'; g.lineWidth = Math.max(1.5, cs * .08); g.lineCap = 'round'; g.beginPath();
        for (i = 0; i < n * n; i++) { var x = i % n, y = (i / n) | 0, X = x * cs, Y = y * cs; if (W[i] & 1) { g.moveTo(X, Y); g.lineTo(X + cs, Y); } if (W[i] & 8) { g.moveTo(X, Y); g.lineTo(X, Y + cs); } if (x === n - 1 && (W[i] & 2)) { g.moveTo(X + cs, Y); g.lineTo(X + cs, Y + cs); } if (y === n - 1 && (W[i] & 4)) { g.moveTo(X, Y + cs); g.lineTo(X + cs, Y + cs); } }
        g.stroke();
        var pg = g.createRadialGradient(px, py, 1, px, py, cs * .9); pg.addColorStop(0, 'rgba(53,224,176,.7)'); pg.addColorStop(1, 'rgba(53,224,176,0)'); g.fillStyle = pg; g.fillRect(px - cs, py - cs, cs * 2, cs * 2);
        g.fillStyle = '#35e0b0'; g.beginPath(); g.arc(px, py, cs * .26, 0, 7); g.fill();
        if (fog && !finished) { var fg = g.createRadialGradient(px, py, cs * 1.6, px, py, cs * 4.2); fg.addColorStop(0, 'rgba(5,8,13,0)'); fg.addColorStop(1, 'rgba(5,8,13,.97)'); g.fillStyle = fg; g.fillRect(0, 0, w, cv.h); }
      });
      return { destroy: function () { dead = true; lp.stop(); off(); cv.destroy(); } };
    }
  });

  /* ------------------------------------------------------------------ Daily chess puzzle */
  PG.register('puzzles', 'chess', {
    title: 'Daily chess puzzle', sub: 'Three mating puzzles a day, the same for everyone. Find the move that forces checkmate in the number of moves shown.',
    mount: function (host) {
      var R = PG.rng(PG.dailySeed() * 7 + 3), pick = function (arr, k) { var c = arr.slice(), o = []; while (o.length < k && c.length) o.push(c.splice(Math.floor(R() * c.length), 1)[0]); return o; };
      var set = pick(P1, 2).map(function (f) { return { fen: f, n: 1 }; }).concat(pick(P2, 1).map(function (f) { return { fen: f, n: 2 }; }));
      set = set.filter(function (p) { try { return CH.mateMoves(CH.fromFEN(p.fen), p.n).length > 0; } catch (e) { return false; } });
      var day = PG.store.get('puzzle-day', { date: '', solved: [] }); if (day.date !== PG.today()) day = { date: PG.today(), solved: [] };
      var idx = 0, st, remaining, tries, last = null, locked = false, dead = false, timer = 0;
      var tabs = PG.el('div', 'pg-seg'); host.appendChild(tabs);
      var row = PG.el('div', 'pg-row'); host.appendChild(row); var left = PG.el('div', 'pg-grow'), side = PG.el('div', 'pg-side'); row.appendChild(left); row.appendChild(side);
      var msg = PG.el('div', 'pg-msg'), info = PG.el('div'), strk = PG.el('div', 'pg-stat');
      var bd = PG.mountChessBoard(left, {
        getState: function () { return st; }, flipped: function () { return set[idx] && CH.fromFEN(set[idx].fen).t === 'b'; }, lastMove: function () { return last; },
        canMove: function () { return !locked && !day.solved[idx]; }, selectable: function () { return !locked && !day.solved[idx]; }, onMove: attempt
      });
      left.appendChild(msg); side.appendChild(info); side.appendChild(strk);
      function same(a, b) { return a.from === b.from && a.to === b.to && (a.promo || '') === (b.promo || ''); }
      function load(i) {
        clearTimeout(timer); idx = i; var p = set[i]; st = CH.fromFEN(p.fen); remaining = p.n; tries = 0; last = null; locked = false; bd.clear();
        [].forEach.call(tabs.children, function (b, k) { b.classList.toggle('on', k === i); });
        info.innerHTML = '<b style="color:var(--text)">' + (st.t === 'w' ? 'White' : 'Black') + ' to move: mate in ' + p.n + '</b><p>' + (p.n === 1 ? 'One move ends the game.' : 'Your first move must leave the opponent no defence.') + '</p>';
        msg.textContent = day.solved[i] ? 'Solved today. Nice.' : 'Your move.'; bd.render(); stat();
      }
      function stat() { var n = day.solved.filter(Boolean).length; strk.innerHTML = 'Today <b>' + n + ' / ' + set.length + '</b> · streak <b>' + streakNow('puzzle-streak') + '</b>'; }
      function attempt(m) {
        var sol = CH.mateMoves(st, remaining);
        if (!sol.some(function (s) { return same(s, m); })) { tries++; msg.textContent = tries > 2 ? 'Not that one. Try the Hint button.' : 'That does not force mate. Try again.'; bd.clear(); bd.render(); return; }
        st = CH.apply(st, m); last = m; remaining--;
        if (remaining <= 0 || !CH.legal(st).length) { day.solved[idx] = true; day.date = PG.today(); PG.store.set('puzzle-day', day); bumpStreak('puzzle-streak'); msg.textContent = 'Checkmate! Puzzle solved' + (tries ? ' (after ' + tries + ' miss' + (tries > 1 ? 'es' : '') + ')' : ' first try') + '.'; locked = true; bd.render(); stat(); if (idx + 1 < set.length) { var nb = PG.button(msg, 'Next puzzle', function () { load(idx + 1); }, true); nb.style.marginLeft = '10px'; } return; }
        locked = true; msg.textContent = 'Correct. Opponent replies...'; bd.render();
        timer = setTimeout(function () { if (dead) return; var r = CH.best(st, 2, 300); if (r) { st = CH.apply(st, r); last = r; } locked = false; msg.textContent = 'Now deliver mate.'; bd.render(); }, 450);
      }
      set.forEach(function (p, i) { var b = PG.el('button', '', 'Puzzle ' + (i + 1) + (p.n === 2 ? ' · mate in 2' : '')); b.type = 'button'; b.onclick = function () { load(i); }; tabs.appendChild(b); });
      var bar = PG.el('div', 'pg-bar'); left.appendChild(bar);
      PG.button(bar, 'Hint', function () { if (locked || day.solved[idx]) return; var s = CH.mateMoves(st, remaining)[0]; if (s) msg.textContent = 'Look at the ' + { p: 'pawn', n: 'knight', b: 'bishop', r: 'rook', q: 'queen', k: 'king' }[st.b[s.from].toLowerCase()] + ' on ' + CH.sqName(s.from) + '.'; });
      PG.button(bar, 'Show solution', function () { if (locked || day.solved[idx]) return; var s = CH.mateMoves(st, remaining)[0]; if (s) msg.textContent = 'Solution: ' + CH.san(st, s) + '. Reset the puzzle to try it yourself.'; });
      PG.button(bar, 'Reset', function () { load(idx); });
      side.appendChild(PG.el('p', 'pg-hint', 'The streak counts consecutive days with at least one puzzle solved. Positions are checked by the rules engine, so every listed solution is a true forced mate.'));
      if (!set.length) { host.innerHTML = '<p class="pg-hint">No puzzles available.</p>'; return {}; }
      load(day.solved.length && day.solved.filter(Boolean).length < set.length ? day.solved.findIndex(function (v, k) { return !v; }) : 0);
      return { destroy: function () { dead = true; clearTimeout(timer); } };
    }
  });

  /* ------------------------------------------------------------------ Chart analyzer */
  var REGIMES = [
    { id: 'up', name: 'a steady uptrend', drift: 0.0016 }, { id: 'down', name: 'a steady downtrend', drift: -0.0016 },
    { id: 'range', name: 'a sideways range (mean reverting)', drift: 0 }, { id: 'up', name: 'a quiet breakout higher', drift: 0.0024 }, { id: 'down', name: 'a quiet breakdown lower', drift: -0.0024 }
  ];
  function genSeries(rng, n, drift, sig, revert) {
    var c = [100], i; function gauss() { var u = rng() || 1e-9, v = rng(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
    for (i = 1; i < n; i++) { var p = c[i - 1], r = drift + sig * gauss() - (revert ? revert * Math.log(p / 100) : 0); c.push(p * Math.exp(r)); }
    return c;
  }
  function candles(cl, rng, sig) { return cl.map(function (c, i) { var o = i ? cl[i - 1] : c * (1 + (rng() - .5) * sig), hi = Math.max(o, c) * (1 + rng() * sig * .7), lo = Math.min(o, c) * (1 - rng() * sig * .7); return { o: o, h: hi, l: lo, c: c }; }); }
  PG.register('puzzles', 'chart', {
    title: 'Chart analyzer', sub: 'Five charts a day. Read the last 60 bars, call the next 20: higher, lower or flat. Then see how much was signal and how much was luck.',
    mount: function (host) {
      var cv = PG.canvas(host, 2.1), ctx = cv.ctx, round = 0, score = 0, hist = [], cur, revealed = false, dead = false, today = PG.today();
      var save = PG.store.get('chart-day', { date: '', done: [] }); if (save.date !== today) save = { date: today, done: [] };
      var bar = PG.el('div', 'pg-bar'); host.appendChild(bar); var btns = {};
      [['up', 'Higher'], ['flat', 'Flat'], ['down', 'Lower']].forEach(function (b) { btns[b[0]] = PG.button(bar, b[1], function () { answer(b[0]); }, false); });
      var nextB = PG.button(bar, 'Next chart', function () { go(round + 1); }, true); nextB.hidden = true;
      var info = PG.el('span', 'pg-stat'); bar.appendChild(info);
      var msg = PG.el('div', 'pg-msg'); host.appendChild(msg); var why = PG.el('p', 'pg-hint'); host.appendChild(why);
      function make(i) {
        var R = PG.rng(PG.dailySeed() * 31 + i * 977), rg = REGIMES[Math.floor(R() * REGIMES.length)], sig = 0.0095 + R() * 0.006, past = genSeries(R, 60, rg.drift * (0.4 + R() * .6), sig, rg.id === 'range' ? 0.06 : 0);
        var fut = genSeries(R, 21, rg.drift, sig, rg.id === 'range' ? 0.06 : 0).slice(1).map(function (v) { return v * past[59] / 100; });
        var move = fut[19] / past[59] - 1, thr = sig * Math.sqrt(20) * 0.33, outcome = move > thr ? 'up' : move < -thr ? 'down' : 'flat';
        return { rg: rg, sig: sig, past: past, fut: fut, out: outcome, move: move, C: candles(past.concat(fut), R, sig) };
      }
      function go(i) {
        if (i >= 5) return finish(); round = i; cur = make(i); revealed = false; nextB.hidden = true; why.textContent = ''; msg.textContent = 'Chart ' + (i + 1) + ' of 5. What happens over the next 20 bars?';
        Object.keys(btns).forEach(function (k) { btns[k].disabled = false; }); info.innerHTML = 'Score <b>' + score + ' / ' + i + '</b>';
      }
      function answer(a) {
        if (revealed) return; revealed = true; Object.keys(btns).forEach(function (k) { btns[k].disabled = true; });
        var ok = a === cur.out; if (ok) score++; hist.push(ok);
        msg.textContent = (ok ? 'Right. ' : 'Not this time. ') + 'The next 20 bars went ' + (cur.out === 'flat' ? 'sideways' : cur.out === 'up' ? 'higher' : 'lower') + ' (' + (cur.move * 100 >= 0 ? '+' : '') + (cur.move * 100).toFixed(1) + '%).';
        why.textContent = 'Behind the scenes this chart was ' + cur.rg.name + ', but each bar’s random noise (about ' + (cur.sig * 100).toFixed(1) + '%) was several times larger than the built-in drift. Real markets look like this too, which is why one chart is never evidence.';
        nextB.hidden = false; nextB.textContent = round >= 4 ? 'See result' : 'Next chart'; info.innerHTML = 'Score <b>' + score + ' / ' + (round + 1) + '</b>';
      }
      function finish() {
        Object.keys(btns).forEach(function (k) { btns[k].hidden = true; }); nextB.hidden = true; cur = null;
        if (!save.done.length) { save.done = hist; PG.store.set('chart-day', save); bumpStreak('chart-streak'); }
        msg.textContent = 'Today: ' + score + ' / 5. Guessing at random averages about 1.7. Even skilled traders only edge past a coin flip, so the lesson is sizing and costs, not clairvoyance.';
        why.textContent = 'Daily streak: ' + streakNow('chart-streak') + '. Come back tomorrow for a fresh set. To practise on real data, use Test in the Strategy Lab.';
        var again = PG.button(bar, 'Replay for fun', function () { again.remove(); Object.keys(btns).forEach(function (k) { btns[k].hidden = false; }); score = 0; hist = []; go(0); });
      }
      function draw() {
        var g = ctx, w = cv.w, h = cv.h; g.fillStyle = '#05080d'; g.fillRect(0, 0, w, h); if (!cur) return;
        var show = revealed ? 80 : 60, C = cur.C.slice(0, show), lo = Infinity, hi = -Infinity;
        cur.C.slice(0, 80).forEach(function (c) { lo = Math.min(lo, c.l); hi = Math.max(hi, c.h); }); var pad = (hi - lo) * .08; lo -= pad; hi += pad;
        var padL = 8, padR = 56, X = function (i) { return padL + (i + .5) * (w - padL - padR) / 80; }, Y = function (v) { return h - 12 - (v - lo) / (hi - lo) * (h - 24); }, bw = Math.max(2, (w - padL - padR) / 80 * .66);
        g.strokeStyle = 'rgba(255,255,255,.06)'; g.fillStyle = 'rgba(255,255,255,.45)'; g.font = '10px system-ui'; g.lineWidth = 1;
        for (var k = 0; k <= 4; k++) { var v = lo + (hi - lo) * k / 4, y = Y(v); g.beginPath(); g.moveTo(padL, y); g.lineTo(w - padR + 6, y); g.stroke(); g.fillText(v.toFixed(1), w - padR + 10, y + 3); }
        g.fillStyle = 'rgba(77,144,255,.07)'; g.fillRect(X(59) + bw, 0, w, h); g.strokeStyle = 'rgba(77,144,255,.5)'; g.setLineDash([4, 4]); g.beginPath(); g.moveTo(X(59) + bw, 0); g.lineTo(X(59) + bw, h); g.stroke(); g.setLineDash([]);
        if (!revealed) { g.fillStyle = 'rgba(255,255,255,.55)'; g.font = '600 12px system-ui'; g.fillText('? next 20 bars', X(62), 22); }
        C.forEach(function (c, i) { var up = c.c >= c.o, col = up ? '#35e0b0' : '#ff6b8a'; g.strokeStyle = col; g.fillStyle = col; g.lineWidth = 1; g.beginPath(); g.moveTo(X(i), Y(c.h)); g.lineTo(X(i), Y(c.l)); g.stroke(); var y1 = Y(Math.max(c.o, c.c)), y2 = Y(Math.min(c.o, c.c)); g.fillRect(X(i) - bw / 2, y1, bw, Math.max(1, y2 - y1)); });
      }
      go(save.done.length ? 0 : 0);
      var lp = PG.loop(function () { if (!dead) draw(); });
      return { destroy: function () { dead = true; lp.stop(); cv.destroy(); } };
    }
  });
})();
