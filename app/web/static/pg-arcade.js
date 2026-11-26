/* Playground / Arcade: Chess vs computer, 2048 Quant Edition, Block Stacker (terminal style). Local only. */
(function () {
  var PG = window.PG, CH = PG.chess;
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }

  /* ------------------------------------------------------------------ Chess */
  PG.register('arcade', 'chess', {
    title: 'Chess vs computer', sub: 'Full rules: castling, en passant, promotion, draws. Pick a level, tap a piece, tap a square.',
    mount: function (host) {
      var st, hist, moves, last, level = PG.store.get('chess-level', 2), me = 'w', over = null, thinking = false, dead = false, timer = 0, stack = [];
      var row = PG.el('div', 'pg-row'), left = PG.el('div', 'pg-grow'), side = PG.el('div', 'pg-side'); row.appendChild(left); row.appendChild(side); host.appendChild(row);
      var msg = PG.el('div', 'pg-msg'), list = PG.el('div', 'pg-hint'), rec = PG.el('div', 'pg-hint');
      var bd = PG.mountChessBoard(left, {
        getState: function () { return st; }, flipped: function () { return me === 'b'; }, lastMove: function () { return last; },
        canMove: function () { return !over && !thinking && st.t === me; }, selectable: function () { return !over && !thinking && st.t === me; }, onMove: play
      });
      left.appendChild(msg);
      function newGame(color) {
        clearTimeout(timer); me = color || me; st = CH.start(); hist = [CH.key(st)]; moves = []; last = null; over = null; thinking = false; stack = []; bd.clear(); refresh();
        if (st.t !== me) engine();
      }
      function refresh() {
        bd.render(); var s = CH.status(st, hist);
        if (s.over) {
          if (!over) { var rr = PG.store.get('chess-rec', { w: 0, l: 0, d: 0 }); if (s.winner === me) rr.w++; else if (s.winner) rr.l++; else rr.d++; PG.store.set('chess-rec', rr); }
          over = s; msg.textContent = s.reason === 'checkmate' ? (s.winner === me ? 'Checkmate. You win!' : 'Checkmate. The computer wins.') : 'Draw by ' + (s.reason === 'material' ? 'insufficient material' : s.reason) + '.';
        } else msg.textContent = thinking ? 'Computer is thinking...' : (st.t === me ? (s.check ? 'Check! Your move.' : 'Your move.') : '');
        list.textContent = moves.length ? moves.map(function (m, i) { return (i % 2 ? '' : (i / 2 + 1) + '. ') + m; }).join(' ') : 'No moves yet.';
        var r = PG.store.get('chess-rec', { w: 0, l: 0, d: 0 }); rec.textContent = 'Record vs computer: ' + r.w + ' W / ' + r.d + ' D / ' + r.l + ' L';
      }
      function win() { }
      function play(m) { stack.push({ st: st, hist: hist.slice(), moves: moves.slice(), last: last }); moves.push(CH.san(st, m)); st = CH.apply(st, m); hist.push(CH.key(st)); last = m; refresh(); if (!over && st.t !== me) engine(); }
      function engine() {
        thinking = true; refresh();
        timer = setTimeout(function () {
          if (dead) return; var m = CH.best(st, level); thinking = false; if (!m) { refresh(); return; }
          moves.push(CH.san(st, m)); st = CH.apply(st, m); hist.push(CH.key(st)); last = m; refresh();
        }, 120);
      }
      var bar = PG.el('div', 'pg-bar'); left.appendChild(bar);
      PG.seg(bar, [[1, 'Easy'], [2, 'Casual'], [3, 'Club'], [4, 'Strong']], level, function (v) { level = v; PG.store.set('chess-level', v); });
      PG.button(bar, 'New game (White)', function () { newGame('w'); }, true); PG.button(bar, 'Play Black', function () { newGame('b'); });
      PG.button(bar, 'Undo', function () { if (thinking || !stack.length) return; var k = stack.length > 1 && st.t === me ? 2 : 1; if (st.t !== me) k = 1; var p; while (k-- > 0 && stack.length) p = stack.pop(); if (p) { st = p.st; hist = p.hist; moves = p.moves; last = p.last; over = null; bd.clear(); refresh(); } });
      PG.button(bar, 'Hint', function () { if (over || thinking || st.t !== me) return; var m = CH.best(st, 3, 500); if (m) { last = m; msg.textContent = 'Try ' + CH.san(st, m) + '.'; bd.render(); } });
      side.appendChild(PG.el('div', '', '<b style="color:var(--text)">Moves</b>')); side.appendChild(list); side.appendChild(rec);
      side.appendChild(PG.el('p', 'pg-hint', 'Levels: Easy plays loosely, Casual looks 2 moves ahead, Club about 4, Strong searches up to 5 plies with a time cap.'));
      newGame('w');
      return { destroy: function () { dead = true; clearTimeout(timer); } };
    }
  });

  /* ------------------------------------------------------------------ 2048 Quant Edition */
  var NAMES = { 2: 'Tick', 4: 'Candle', 8: 'Swing', 16: 'Trend', 32: 'Edge', 64: 'Alpha', 128: 'Sharpe', 256: 'Regime', 512: 'Book', 1024: 'Fund', 2048: 'Quant', 4096: 'Legend', 8192: 'Myth' };
  function tileColor(v) { var e = Math.log2(v); return 'hsl(' + (170 + e * 22) % 360 + ' 70% ' + (78 - Math.min(e, 11) * 2.6) + '%)'; }
  PG.register('arcade', '2048', {
    title: '2048 Quant Edition', sub: 'Merge equal tiles up the quant ladder: Tick, Candle, Swing ... Quant. Arrow keys, WASD or swipe.',
    mount: function (host) {
      var box = PG.el('div', 'g48'), grid = PG.el('div', 'g48-grid'), tilesEl = PG.el('div'), over = PG.el('div', 'g48-over');
      for (var i = 0; i < 16; i++) grid.appendChild(PG.el('div', 'g48-cell')); box.appendChild(grid); tilesEl.style.cssText = 'position:absolute;inset:0'; box.appendChild(tilesEl); box.appendChild(over); host.appendChild(box);
      var tiles, score, best = PG.store.get('g48-best', 0), nid = 0, prev = null, won = false, ended = false;
      var bar = PG.el('div', 'pg-bar'); host.appendChild(bar);
      var sc = PG.el('span', 'pg-stat'), bs = PG.el('span', 'pg-stat'); bar.appendChild(sc); bar.appendChild(bs);
      PG.button(bar, 'New game', start, true); PG.button(bar, 'Undo', function () { if (prev) { tiles = prev.t; score = prev.s; prev = null; ended = false; over.classList.remove('on'); draw(); } });
      var msg = PG.el('div', 'pg-msg'); host.appendChild(msg);
      function emptyCells() { var o = []; for (var r = 0; r < 4; r++) for (var c = 0; c < 4; c++) if (!tiles.some(function (t) { return t.r === r && t.c === c; })) o.push([r, c]); return o; }
      function spawn() { var e = emptyCells(); if (!e.length) return; var p = e[Math.floor(Math.random() * e.length)]; tiles.push({ id: ++nid, r: p[0], c: p[1], v: Math.random() < .9 ? 2 : 4, isNew: true }); }
      function start() { tiles = []; score = 0; prev = null; won = false; ended = false; over.classList.remove('on'); msg.textContent = ''; spawn(); spawn(); draw(); }
      function draw() {
        tilesEl.innerHTML = '';
        tiles.forEach(function (t) {
          var d = PG.el('div', 'g48-tile' + (t.v >= 1024 ? ' big' : '') + (t.isNew || t.merged ? ' pop' : ''), '<span>' + t.v + '</span><i>' + (NAMES[t.v] || '') + '</i>');
          d.style.setProperty('--r', t.r); d.style.setProperty('--c', t.c); d.style.background = tileColor(t.v); tilesEl.appendChild(d); t.isNew = false; t.merged = false;
        });
        if (score > best) { best = score; PG.store.set('g48-best', best); }
        sc.innerHTML = 'Score <b>' + score + '</b>'; bs.innerHTML = 'Best <b>' + best + '</b>';
      }
      function move(dir) {   // 0 left 1 up 2 right 3 down
        if (ended) return; var snap = { t: tiles.map(function (t) { return { id: t.id, r: t.r, c: t.c, v: t.v }; }), s: score }, moved = false, gained = 0;
        var grid2 = []; for (var r = 0; r < 4; r++) { grid2.push([null, null, null, null]); } tiles.forEach(function (t) { grid2[t.r][t.c] = t; });
        var out = [];
        for (var line = 0; line < 4; line++) {
          var cells = []; for (var k = 0; k < 4; k++) { var rr = dir === 0 || dir === 2 ? line : (dir === 1 ? k : 3 - k), cc = dir === 1 || dir === 3 ? line : (dir === 0 ? k : 3 - k); cells.push([rr, cc]); }
          var seq = cells.map(function (p) { return grid2[p[0]][p[1]]; }).filter(Boolean), res = [];
          for (var i = 0; i < seq.length; i++) {
            if (i + 1 < seq.length && seq[i].v === seq[i + 1].v) { var m = seq[i]; m.v *= 2; m.merged = true; gained += m.v; res.push(m); i++; } else res.push(seq[i]);
          }
          res.forEach(function (t, idx) { var p = cells[idx]; if (t.r !== p[0] || t.c !== p[1]) moved = true; t.r = p[0]; t.c = p[1]; out.push(t); });
          if (res.length !== seq.length) moved = true;
        }
        if (!moved) return; prev = snap; tiles = out; score += gained; spawn(); draw();
        if (!won && tiles.some(function (t) { return t.v >= 2048; })) { won = true; msg.textContent = 'Quant! You reached 2048. Keep going for Legend.'; }
        if (!emptyCells().length && !canMove()) { ended = true; over.innerHTML = '<div>No more merges<br><small>Score ' + score + '</small></div>'; over.classList.add('on'); }
      }
      function canMove() { var g = {}; tiles.forEach(function (t) { g[t.r + ',' + t.c] = t.v; }); return tiles.some(function (t) { return g[t.r + ',' + (t.c + 1)] === t.v || g[(t.r + 1) + ',' + t.c] === t.v; }); }
      var KEYS = { ArrowLeft: 0, a: 0, ArrowUp: 1, w: 1, ArrowRight: 2, d: 2, ArrowDown: 3, s: 3 };
      var off = PG.keyHandler(function (e) { if (e.ctrlKey || e.metaKey || e.altKey) return; var d = KEYS[e.key]; if (d !== undefined) { e.preventDefault(); move(d); } });
      var sx = 0, sy = 0;
      box.addEventListener('pointerdown', function (e) { sx = e.clientX; sy = e.clientY; });
      box.addEventListener('pointerup', function (e) { var dx = e.clientX - sx, dy = e.clientY - sy; if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) return; if (Math.abs(dx) > Math.abs(dy)) move(dx < 0 ? 0 : 2); else move(dy < 0 ? 1 : 3); });
      start();
      return { destroy: function () { off(); } };
    }
  });

  /* ------------------------------------------------------------------ Block Stacker (terminal) */
  var SH = {
    I: [[0, 1], [1, 1], [2, 1], [3, 1]], O: [[1, 0], [2, 0], [1, 1], [2, 1]], T: [[1, 0], [0, 1], [1, 1], [2, 1]], S: [[1, 0], [2, 0], [0, 1], [1, 1]],
    Z: [[0, 0], [1, 0], [1, 1], [2, 1]], J: [[0, 0], [0, 1], [1, 1], [2, 1]], L: [[2, 0], [0, 1], [1, 1], [2, 1]]
  };
  var CH_OF = { I: '##', O: '[]', T: '<>', S: '()', Z: '{}', J: '%%', L: '&&' };
  function rot(cells, size) { return cells.map(function (c) { return [size - 1 - c[1], c[0]]; }); }
  PG.register('arcade', 'tetris', {
    title: 'Block Stacker', sub: 'Arrows move and rotate, Space hard-drops, C holds, P pauses. On touch screens use the pad.',
    mount: function (host) {
      var W = 10, H = 20, wrap = PG.el('div', 'tt-wrap'), pre = PG.el('pre'), dead = false;
      wrap.appendChild(pre); host.appendChild(wrap);
      var field, cur, next, hold, canHold, bag, score, lines, level, acc, state, best = PG.store.get('tetris-best', { scores: [] }), flash = 0, msg = '';
      function bagNext() { if (!bag || !bag.length) { bag = Object.keys(SH); for (var i = bag.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)), t = bag[i]; bag[i] = bag[j]; bag[j] = t; } } return bag.pop(); }
      function mk(type) { var size = type === 'I' ? 4 : type === 'O' ? 4 : 3; return { t: type, c: SH[type].map(function (p) { return p.slice(); }), size: size, x: type === 'O' ? 3 : 3, y: type === 'I' ? -1 : 0 }; }
      function fits(p, c, x, y) { return c.every(function (q) { var X = x + q[0], Y = y + q[1]; return X >= 0 && X < W && Y < H && (Y < 0 || !field[Y][X]); }); }
      function newGame() { field = []; for (var i = 0; i < H; i++) field.push(new Array(W).fill('')); score = 0; lines = 0; level = 1; acc = 0; hold = null; canHold = true; bag = null; next = bagNext(); state = 'play'; msg = ''; spawn(); }
      function spawn() { cur = mk(next); next = bagNext(); canHold = true; if (!fits(cur, cur.c, cur.x, cur.y)) gameOver(); }
      function gameOver() { state = 'over'; var s = best.scores.concat([score]).sort(function (a, b) { return b - a; }).slice(0, 5); best = { scores: s }; PG.store.set('tetris-best', best); msg = 'GAME OVER'; }
      function lock() {
        cur.c.forEach(function (q) { var Y = cur.y + q[1]; if (Y >= 0) field[Y][cur.x + q[0]] = cur.t; });
        var cl = 0; for (var y = H - 1; y >= 0; y--) { if (field[y].every(Boolean)) { field.splice(y, 1); field.unshift(new Array(W).fill('')); cl++; y++; } }
        if (cl) { lines += cl; score += [0, 100, 300, 500, 800][cl] * level; level = 1 + Math.floor(lines / 10); msg = ['', 'single', 'double', 'triple', 'STACKER!'][cl]; }
        spawn();
      }
      function shift(dx) { if (state !== 'play') return; if (fits(cur, cur.c, cur.x + dx, cur.y)) cur.x += dx; }
      function down() { if (state !== 'play') return false; if (fits(cur, cur.c, cur.x, cur.y + 1)) { cur.y++; return true; } lock(); return false; }
      function rotate(dir) {
        if (state !== 'play' || cur.t === 'O') return; var n = cur.c; for (var k = 0; k < (dir > 0 ? 1 : 3); k++) n = rot(n, cur.size);
        var kicks = [[0, 0], [-1, 0], [1, 0], [0, -1], [-2, 0], [2, 0]]; for (var i = 0; i < kicks.length; i++) if (fits(cur, n, cur.x + kicks[i][0], cur.y + kicks[i][1])) { cur.c = n; cur.x += kicks[i][0]; cur.y += kicks[i][1]; return; }
      }
      function drop() { if (state !== 'play') return; var d = 0; while (fits(cur, cur.c, cur.x, cur.y + 1)) { cur.y++; d++; } score += d * 2; lock(); }
      function doHold() { if (state !== 'play' || !canHold) return; var t = cur.t; if (hold) { cur = mk(hold); } else { cur = mk(next); next = bagNext(); } hold = t; canHold = false; }
      function ghostY() { var y = cur.y; while (fits(cur, cur.c, cur.x, y + 1)) y++; return y; }
      function mini(type) { var g = [['  ', '  ', '  ', '  '], ['  ', '  ', '  ', '  ']]; if (type) SH[type].forEach(function (p) { if (p[1] < 2) g[p[1]][p[0]] = CH_OF[type]; }); return g.map(function (r) { return r.join(''); }); }
      function render() {
        var ghost = {}; if (state === 'play') { var gy = ghostY(); cur.c.forEach(function (q) { ghost[(gy + q[1]) + ',' + (cur.x + q[0])] = 1; }); }
        var live = {}; if (state !== 'over' || true) cur.c.forEach(function (q) { live[(cur.y + q[1]) + ',' + (cur.x + q[0])] = cur.t; });
        var nx = mini(next), hd = mini(hold), out = [], r, c;
        var side = ['  NEXT', '  ' + nx[0], '  ' + nx[1], '', '  HOLD', '  ' + hd[0], '  ' + hd[1], '', '  SCORE', '  ' + score, '', '  LINES ' + lines, '  LEVEL ' + level, '', '  BEST ' + (best.scores[0] || 0), '', '  ' + (state === 'pause' ? 'PAUSED' : msg)];
        for (r = 0; r < H; r++) { var line = '<!'; for (c = 0; c < W; c++) { var t = field[r][c] || live[r + ',' + c]; line += t ? CH_OF[t] : (ghost[r + ',' + c] ? '..' : ' .'); } line += '!>' + (side[r] || ''); out.push(line); }
        out.push('<!' + '====================' + '!>'); out.push('  ' + '\\/'.repeat(10));
        pre.textContent = out.join('\n');
      }
      var pad = PG.el('div', 'tt-pad'); host.appendChild(pad);
      [['◀', function () { shift(-1); }], ['⟳', function () { rotate(1); }], ['▶', function () { shift(1); }], ['▼', function () { down(); }], ['⤓', drop], ['Hold', doHold]].forEach(function (b) { var e = PG.el('button', '', b[0]); e.type = 'button'; e.onclick = b[1]; pad.appendChild(e); });
      var bar = PG.el('div', 'pg-bar'); host.appendChild(bar); PG.button(bar, 'New game', function () { newGame(); }, true); PG.button(bar, 'Pause', function () { if (state === 'play') state = 'pause'; else if (state === 'pause') state = 'play'; });
      var hs = PG.el('span', 'pg-stat'); bar.appendChild(hs);
      function hsr() { hs.innerHTML = 'Top scores: <b>' + (best.scores.length ? best.scores.join(' · ') : 'none yet') + '</b>'; } hsr();
      var off = PG.keyHandler(function (e) {
        if (e.ctrlKey || e.metaKey || e.altKey) return; var k = e.key, used = true;
        if (k === 'ArrowLeft' || k === 'a') shift(-1); else if (k === 'ArrowRight' || k === 'd') shift(1); else if (k === 'ArrowDown' || k === 's') down(); else if (k === 'ArrowUp' || k === 'w' || k === 'x') rotate(1); else if (k === 'z') rotate(-1);
        else if (k === ' ') drop(); else if (k === 'c' || k === 'Shift') doHold(); else if (k === 'p') { state = state === 'play' ? 'pause' : state === 'pause' ? 'play' : state; } else if (k === 'Enter' && state === 'over') newGame(); else used = false;
        if (used) e.preventDefault();
      });
      newGame();
      var prevState = 'play';
      var lp = PG.loop(function (dt) {
        if (dead) return; if (state === 'play') { acc += dt; var spd = Math.max(0.07, 0.8 - (level - 1) * 0.07); while (acc > spd) { acc -= spd; down(); } }
        if (state === 'over' && prevState !== 'over') hsr(); prevState = state; render();
      });
      return { destroy: function () { dead = true; lp.stop(); off(); } };
    }
  });
})();
