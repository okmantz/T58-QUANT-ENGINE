/* ==========================================================================
   T58 first-run guided tour (web)

   A short, skippable walkthrough shown once, the first time someone
   lands on the Dashboard after activating their license. It spotlights the
   real sidebar items ("here is where you add data", "here is where you
   test") and explains the order to do things in.

   - Self-contained: injects its own CSS, reads the app's theme variables
     (--panel-2, --teal, ...) so it follows the light/dark toggle.
   - Shows once, the first time the Dashboard opens after the license is
     activated (the server decides -- see app/web/onboarding.py -- and falls
     back to the localStorage key below). Finishing, skipping, or closing
     it all count as "seen". If localStorage is blocked (some
     desktop WebView shells), a sessionStorage fallback still shows it at
     most once per app session, so nobody gets nagged on every page load
     but a genuine first run is never silently skipped.
   - Quick connect tour: [data-t58-tour-start="connect"] or ?tour=connect (prop firm / MT5 -> live).
   - Replay anytime: any element with [data-t58-tour-start], the URL
     /dashboard?tour=1, or window.T58Tour.start() in the console.
   - No innerHTML anywhere: all text is set via textContent, so step copy
     can never inject markup. "**bold**" in step text renders as <strong>.
   - Keyboard: Right/Left arrows = next/back, Esc = skip.
   ========================================================================== */
(function () {
  "use strict";

  // Key version bumps when the tour's steps materially change, so an
  // updated app shows the (updated) tour once more instead of staying
  // silent forever on a "seen" flag set by an older build. v2
  // (2026-10-06): Owen reinstalled and never saw the tour -- his browser
  // profile still carried the v1 "seen" flag from his first run weeks
  // earlier, and a truly fresh install is exactly when it should pop.
  var STORE_KEY = "t58-tour-v3";
  var Z = 10050;
  var MOBILE_QUERY = "(max-width: 760px)";

  /* ---- helpers to find real sidebar elements by their link ------------- */
  function navLink(href) {
    return document.querySelector('.t58-sidebar a.t58-nav-item[href="' + href + '"]');
  }
  function navGroup(href) {
    var a = navLink(href);
    return a ? a.closest("details.t58-nav-group") : null;
  }
  // A sidebar section by its data-nav key (workspace, strategy-lab, quant-lab, prop-journey, account).
  function sideGroup(key) {
    return document.querySelector('.t58-sidebar details.t58-nav-group[data-nav="' + key + '"]');
  }
  function q(sel) { return document.querySelector(sel); }
  // Targets may be one element or a list of neighbours; the spotlight then covers all of them.
  function asList(t) {
    if (!t) return [];
    return (t.length != null && !t.nodeType ? Array.prototype.slice.call(t) : [t]).filter(Boolean);
  }
  function groupsOf(targets) {
    var out = [];
    asList(targets).forEach(function (n) {
      var d = n.closest ? n.closest("details.t58-nav-group") : null;
      if (d && out.indexOf(d) < 0) out.push(d);
    });
    return out;
  }

  /* ---- the steps ------------------------------------------------------- */
  // target: () => element to spotlight (null/undefined = centered card, no spotlight)
  // group:  () => sidebar <details> that must be open for the target to be visible
  var MAIN_STEPS = [
    {
      title: "Welcome to T58 \uD83D\uDC4B",
      text: [
        "T58 answers one question: **if you trade this strategy under your prop firm's rules, what are your odds of passing the evaluation and reaching a payout?**",
        "This tour points at the real buttons, one stop at a time, so you know exactly where everything lives. It takes about a minute."
      ],
      chips: ["Data", "Create", "Test", "Optimize", "Validate", "Deploy"]
    },
    {
      title: "Add your market data",
      text: [
        "Every test needs price history. **Data Center** (highlighted, inside the **Account** section) is where you import a file (CSV, TSV or Parquet) or fetch data.",
        "It is saved after the first upload. Columns needed: **timestamp, open, high, low, close, volume**."
      ],
      target: function () { return navLink("/data-center"); },
      action: { label: "Open Data Center", href: "/data-center" }
    },
    {
      title: "Strategy Lab: the six steps",
      text: [
        "The **Strategy Lab** section (highlighted) holds the whole journey, top to bottom: **Create, Test, Optimize, Validate, Champion, Deploy**, then the **Strategy Library** where everything you save lives.",
        "Work down the list and you never have to guess what comes next."
      ],
      target: function () { return sideGroup("strategy-lab"); }
    },
    {
      title: "Create a strategy",
      text: [
        "**Create** is where strategies enter. Describe an idea in plain English, paste your own Python, PineScript or MQL5, or let the **Discovery Engine** hunt for candidates for you.",
        "Everything you save lands in the **Strategy Library**."
      ],
      target: function () { return navLink("/start-here/create"); },
      action: { label: "Open Create", href: "/start-here/create" }
    },
    {
      title: "Test it properly",
      text: [
        "**Test** runs the full pipeline: baseline backtest, lookahead-bias check, an out-of-sample search, Monte Carlo, then a plain verdict: **READY, MARGINAL or NOT READY**, with reasons.",
        "Pick your data and strategy, choose your prop-firm rules (FTMO, Apex, TopStep, The5%ers, FundedNext and Lucid are built in) and press run."
      ],
      target: function () { return navLink("/full-pipeline"); },
      action: { label: "Open Test", href: "/full-pipeline" }
    },
    {
      title: "Optimize, Validate, Champion, Deploy",
      text: [
        "Verdict NOT READY? **Optimize** searches for better parameters. **Validate** then tries to break the winner (walk-forward, CPCV, robustness). Survivors reach **Champion**, then **Deploy**: forward test, TradingView webhook, and finally live.",
        "These four neighbours are highlighted together."
      ],
      target: function () { return [navLink("/optimize-simple"), navLink("/validate-simple"), navLink("/champion-simple"), navLink("/forward-test")]; },
      action: { label: "Open Optimize", href: "/optimize-simple" }
    },
    {
      title: "Strategy Library",
      text: [
        "**Strategy Library** is your shelf. Its tabs are **Strategies** (everything you saved), **Research** (the Agent Desk and the Research Ledger), **Graveyard** (what died and why) and a **Trading Bots** section.",
        "Open any card to see its reports, verdicts and next action."
      ],
      target: function () { return navLink("/library"); },
      action: { label: "Open Strategy Library", href: "/library" }
    },
    {
      title: "Prop Journey",
      text: [
        "The **Prop Journey** section (highlighted) is for the evaluation itself: the **First Payout Mission**, the **Evaluation Guardian**, your **Accounts**, and **Buy Challenge**, which compares every firm and plan side by side.",
      ],
      target: function () { return sideGroup("prop-journey"); }
    },
    {
      title: "Quant Lab and Investing",
      text: [
        "**Quant Lab** holds the advanced research tools and the Research Lab. **Investing** is a separate paper-trading portfolio for stocks and ETFs, independent of your prop-firm work."
      ],
      target: function () { return sideGroup("quant-lab"); }
    },
    {
      title: "Your home base: what's next?",
      text: [
        "The Dashboard's focus panel (highlighted) tells you **what you're working on, whether it's working, why, and the exact next step** after every run.",
        "The pipeline below it shows how many strategies have reached each stage."
      ],
      target: function () { return q(".db-focus") || q(".db-kpis") || q(".db-head"); },
      scroll: "start"
    },
    {
      title: "Coach: ask anything",
      text: [
        "The **Coach** button (highlighted, bottom right) is on every page. Ask it about trading, strategy building, prop-firm rules, how to set something up, or where to find a page, and it answers with a button that takes you there.",
        "Try \u201CWhat should I do next?\u201D any time."
      ],
      target: function () { return q("#t58-pc-launcher"); }
    },
    {
      title: "Inbox and your profile",
      text: [
        "The **bell** (highlighted, top right) holds your **Weekly digest**, which is also emailed every Sunday (switch that off in Account settings). Beside it, your profile menu opens **Account settings**."
      ],
      target: function () { return [q("#t58-pnl-chip"), q("#t58-bell"), q("#t58-avatar-btn")]; }
    },
    {
      title: "Learn, then play",
      text: [
        "**University** has the courses and the User Manual. **Playground** has games and puzzles for a break between runs. Both sit in the highlighted **Account** section.",
        "Want this tour again? Use the **60-second tour** button at the top of the Dashboard."
      ],
      target: function () { return [navLink("/education"), navLink("/playground")]; },
      action: { label: "Start my first test \u2192", href: "/start-here/create", primary: true }
    }
  ];


  // Quick guided tour: connect a prop-firm / MT5 account and run a strategy live (start it from [data-t58-tour-start="connect"] or ?tour=connect).
  // It never touches the first-run "seen" flag, so replaying it cannot change whether the main tour auto-starts.
  var CONNECT_STEPS = [
    {
      title: "Run a strategy live in 4 steps",
      text: [
        "This quick tour takes you from **a finished strategy** to **a live or demo account trading it**. It takes about a minute.",
        "Short on time? The **Deploy** button on any champion opens the same path as a guided wizard."
      ],
      chips: ["Mode", "Connect", "Strategy", "Deploy"]
    },
    {
      title: "Pick Demo or Live",
      text: [
        "T58 starts in **Demo** mode: simulated money, nothing real can happen. To connect a real prop-firm or MT5 account, switch to **Live** in **Account settings**.",
        "You can practise on the demo first. It follows the same rules as a real evaluation."
      ],
      target: function () { return document.querySelector('a[href="/settings/account"].t58-nav-item') || navLink("/settings/account"); },
      action: { label: "Open Account settings", href: "/settings/account#account-mode" }
    },
    {
      title: "Connect your account",
      text: [
        "In the guided deploy, choose **Live on MT5** or **Live on a prop firm**, pick your firm and paste the login the firm emailed you.",
        "Press **Test connection**: T58 checks the login, the server name and the firm's automation policy, and lists numbered fixes if anything is off."
      ],
      target: function () { return navLink("/forward-test"); },
      action: { label: "Open guided deploy", href: "/deploy/wizard" }
    },
    {
      title: "Choose the strategy",
      text: [
        "Only a **champion** should trade real money. Promote one on the **Champion** page, then press its **Deploy** button.",
        "No champion yet? Run a strategy through **Test**, **Optimize** and **Validate** first. That is what earns the right to go live."
      ],
      target: function () { return navLink("/champion-simple"); },
      action: { label: "Open Champion board", href: "/champion-simple" }
    },
    {
      title: "Set limits and deploy",
      text: [
        "Pick your firm's rule set and T58 fills in the daily-loss and drawdown limits. Review the safety checks, type **DEPLOY LIVE**, and it starts.",
        "A small **Live P&L** pill on every page shows balance and open trades, and you can stop the session any time."
      ],
      action: { label: "Start deploying \u2192", href: "/deploy/wizard", primary: true }
    }
  ];
  var STEPS = MAIN_STEPS;

  /* ---- state ----------------------------------------------------------- */
  var state = null; // { i, opened:[details], cleanup:[fn], els:{}, prevFocus, openedDrawer }

  function seen() {
    // Desktop WebView shells can block localStorage entirely (it throws
    // on access). The old code read that as "already seen", so the tour
    // NEVER auto-started there -- not even on a genuine first run.
    // Fall back to sessionStorage: still never nagging (at most once
    // per app session), but a fresh install actually gets its tour.
    try { if (localStorage.getItem(STORE_KEY)) return true; } catch (e) {}
    try { return !!sessionStorage.getItem(STORE_KEY); } catch (e) { return false; }
  }
  function markSeen(how) {
    try { localStorage.setItem(STORE_KEY, how || "done"); } catch (e) {}
    try { sessionStorage.setItem(STORE_KEY, how || "done"); } catch (e) {}
    // The server keeps the real "seen" flag (see app/web/onboarding.py), so
    // the tour does not depend on which browser/origin opened the app.
    try {
      fetch("/api/onboarding/tour-seen", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ how: how || "done" }), keepalive: true
      });
    } catch (e) {}
  }
  function isMobile() {
    return !!(window.matchMedia && window.matchMedia(MOBILE_QUERY).matches);
  }

  /* ---- CSS (injected once) --------------------------------------------- */
  function injectCss() {
    if (document.getElementById("t58-tour-css")) return;
    var css = [
      ".t58-tour-block{position:fixed;inset:0;z-index:" + (Z - 2) + ";background:transparent;}",
      ".t58-tour-spot{position:fixed;z-index:" + (Z - 1) + ";pointer-events:none;border-radius:10px;",
      "  box-shadow:0 0 0 9999px rgba(3,6,10,.74),0 0 0 2px var(--teal,#35e0b0),0 0 26px rgba(var(--teal-rgb,53,224,176),.55);",
      "  transition:top .28s ease,left .28s ease,width .28s ease,height .28s ease,opacity .2s ease;}",
      "@keyframes t58-tour-pulse{0%,100%{box-shadow:0 0 0 9999px rgba(3,6,10,.74),0 0 0 2px var(--teal,#35e0b0),0 0 18px rgba(var(--teal-rgb,53,224,176),.45);}",
      "  50%{box-shadow:0 0 0 9999px rgba(3,6,10,.74),0 0 0 3px var(--teal,#35e0b0),0 0 34px rgba(var(--teal-rgb,53,224,176),.85);}}",
      ".t58-tour-spot:not(.t58-tour-nospot){animation:t58-tour-pulse 1.8s ease-in-out infinite;}",
      ".t58-tour-spot.t58-tour-nospot{box-shadow:0 0 0 9999px rgba(3,6,10,.74);width:0;height:0;top:50%;left:50%;}",
      ".t58-tour-card{position:fixed;z-index:" + Z + ";width:min(380px,calc(100vw - 24px));box-sizing:border-box;",
      "  background:var(--pop-bg,#10141c);color:var(--text,#e7ebf2);border:1px solid var(--teal,#35e0b0);",
      "  border-radius:14px;padding:16px 18px 14px;box-shadow:0 18px 50px rgba(0,0,0,.55);",
      "  font-size:13.5px;line-height:1.55;transition:top .28s ease,left .28s ease;}",
      ".t58-tour-card *{box-sizing:border-box;}",
      ".t58-tour-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;}",
      ".t58-tour-step{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--teal,#35e0b0);}",
      ".t58-tour-x{background:none;border:0;color:var(--text-muted,#8a93a6);font-size:20px;line-height:1;cursor:pointer;padding:0 2px;}",
      ".t58-tour-x:hover{color:var(--text,#e7ebf2);}",
      ".t58-tour-title{margin:0 0 8px;font-size:16px;font-weight:700;color:var(--text,#e7ebf2);}",
      ".t58-tour-card p{margin:0 0 9px;color:var(--text,#e7ebf2);}",
      ".t58-tour-card strong{color:var(--teal,#35e0b0);font-weight:700;}",
      ".t58-tour-chips{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:4px 0 10px;}",
      ".t58-tour-chip{padding:4px 10px;border-radius:999px;border:1px solid var(--border-light,#2a3242);",
      "  background:var(--panel-3,#151a24);font-size:12px;font-weight:600;}",
      ".t58-tour-arrow{color:var(--text-muted,#8a93a6);font-size:12px;}",
      ".t58-tour-dots{display:flex;gap:6px;margin:12px 0 12px;}",
      ".t58-tour-dot{width:8px;height:8px;border-radius:50%;padding:0;border:0;cursor:pointer;background:var(--border-light,#2a3242);}",
      ".t58-tour-dot.on{background:var(--teal,#35e0b0);box-shadow:0 0 8px rgba(var(--teal-rgb,53,224,176),.7);}",
      ".t58-tour-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}",
      ".t58-tour-actions .t58-tour-spacer{flex:1;}",
      ".t58-tour-btn{font:inherit;font-size:12.5px;font-weight:700;padding:8px 14px;border-radius:9px;cursor:pointer;",
      "  border:1px solid var(--border-light,#2a3242);background:transparent;color:var(--text,#e7ebf2);text-decoration:none;display:inline-block;}",
      ".t58-tour-btn:hover{border-color:var(--teal,#35e0b0);}",
      ".t58-tour-btn.primary{background:var(--teal,#35e0b0);border-color:var(--teal,#35e0b0);color:#04120e;}",
      ".t58-tour-btn.link{border-color:transparent;color:var(--teal,#35e0b0);padding-left:0;padding-right:6px;}",
      ".t58-tour-btn.quiet{border-color:transparent;color:var(--text-muted,#8a93a6);font-weight:600;padding-left:4px;padding-right:4px;}",
      ".t58-tour-btn:focus-visible,.t58-tour-x:focus-visible,.t58-tour-dot:focus-visible{outline:2px solid var(--teal,#35e0b0);outline-offset:2px;}",
      "@media (max-width:760px){.t58-tour-card{left:10px!important;right:10px;top:auto!important;width:auto;",
      "  bottom:calc(10px + env(safe-area-inset-bottom,0px));padding:14px 16px 12px;max-height:62vh;overflow-y:auto;}}",
      "@media (prefers-reduced-motion:reduce){.t58-tour-spot,.t58-tour-card{transition:none;animation:none!important;}}"
    ].join("\n");
    var style = document.createElement("style");
    style.id = "t58-tour-css";
    style.textContent = css;
    document.head.appendChild(style);
  }

  /* ---- tiny DOM builders (no innerHTML) --------------------------------- */
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  // "plain **bold** plain" -> text nodes + <strong>
  function rich(parent, str) {
    var parts = String(str).split("**");
    for (var k = 0; k < parts.length; k++) {
      if (!parts[k]) continue;
      if (k % 2 === 1) parent.appendChild(el("strong", null, parts[k]));
      else parent.appendChild(document.createTextNode(parts[k]));
    }
    return parent;
  }

  /* ---- sidebar group open/close bookkeeping ---------------------------- */
  function openGroup(details) {
    if (!details) return;
    if (!details.open) {
      details.open = true;
      state.opened.push(details);
    }
  }
  function closeOpenedExcept(keep) {
    var keepList = asList(keep), still = [];
    state.opened.forEach(function (d) {
      if (keepList.indexOf(d) >= 0) { still.push(d); return; }
      d.open = false;
    });
    state.opened = still;
  }

  /* ---- mobile drawer --------------------------------------------------- */
  function drawerParts() {
    return {
      btn: document.getElementById("t58-mobile-menu-btn"),
      sidebar: document.getElementById("t58-sidebar")
    };
  }
  function ensureDrawer(open) {
    var p = drawerParts();
    if (!p.btn || !p.sidebar) return;
    var isOpen = p.sidebar.classList.contains("open");
    if (open && !isOpen) { p.btn.click(); state.openedDrawer = true; }
    if (!open && isOpen && state.openedDrawer) { p.btn.click(); state.openedDrawer = false; }
  }

  /* ---- geometry / positioning ------------------------------------------ */
  // `t` is one element or a list of elements; the result is the box that covers every visible one.
  function targetRect(t) {
    var list = asList(t), box = null;
    list.forEach(function (n) {
      var r = n.getBoundingClientRect();
      if (!r.width && !r.height) return;
      if (!box) { box = { left: r.left, top: r.top, right: r.right, bottom: r.bottom }; return; }
      box.left = Math.min(box.left, r.left); box.top = Math.min(box.top, r.top);
      box.right = Math.max(box.right, r.right); box.bottom = Math.max(box.bottom, r.bottom);
    });
    if (!box) return null;
    box.width = box.right - box.left; box.height = box.bottom - box.top;
    return box;
  }
  function firstEl(t) { return asList(t)[0] || null; }
  function inSidebar(t) {
    return asList(t).some(function (n) { return n.closest && n.closest(".t58-sidebar"); });
  }

  function place() {
    if (!state) return;
    var t = state.target;
    var spot = state.els.spot, card = state.els.card;
    var r = t ? targetRect(t) : null;
    var mobile = isMobile();
    var vw = window.innerWidth, vh = window.innerHeight;
    var cw = card.offsetWidth, ch = card.offsetHeight, gap = 18, m = 12;

    // Where can the card go without covering `rc`? (desktop only)
    function candidates(rc) {
      var cy = rc.top + rc.height / 2 - ch / 2;
      var cx = rc.left + rc.width / 2 - cw / 2;
      return [
        { ok: rc.right + gap + cw <= vw - m, l: rc.right + gap, t: cy },   // right of it
        { ok: rc.bottom + gap + ch <= vh - m, l: cx, t: rc.bottom + gap }, // below it
        { ok: rc.top - gap - ch >= m, l: cx, t: rc.top - gap - ch },       // above it
        { ok: rc.left - gap - cw >= m, l: rc.left - gap - cw, t: cy }      // left of it
      ];
    }
    function firstFit(list) {
      for (var k = 0; k < list.length; k++) if (list[k].ok) return list[k];
      return null;
    }

    var pick = null;
    var box = r; // the region we actually spotlight
    if (r && !mobile) {
      pick = firstFit(candidates(r));
      if (!pick) {
        // Target is too big for the card to sit beside it: spotlight just its top part,
        // leaving room for the card underneath.
        var room = vh - m - ch - gap - r.top;
        if (room >= 60) {
          box = { top: r.top, left: r.left, width: r.width, height: Math.min(r.height, room),
                  right: r.right, bottom: r.top + Math.min(r.height, room) };
          pick = firstFit(candidates(box));
        }
      }
    }

    if (!box) {
      spot.classList.add("t58-tour-nospot");
      spot.style.top = spot.style.left = spot.style.width = spot.style.height = "";
    } else {
      var pad = 5;
      spot.classList.remove("t58-tour-nospot");
      spot.style.top = (box.top - pad) + "px";
      spot.style.left = (box.left - pad) + "px";
      spot.style.width = (box.width + pad * 2) + "px";
      spot.style.height = (box.height + pad * 2) + "px";
    }

    if (mobile) { // CSS pins the card to the bottom-sheet position
      card.style.left = card.style.top = "";
      return;
    }

    var left, top;
    if (pick) { left = pick.l; top = pick.t; }
    else if (!r) { left = (vw - cw) / 2; top = (vh - ch) / 2; }
    else { left = (vw - cw) / 2; top = vh - ch - m; } // last resort: bottom-center
    left = Math.min(Math.max(m, left), Math.max(m, vw - cw - m));
    top = Math.min(Math.max(m, top), Math.max(m, vh - ch - m));
    card.style.left = Math.round(left) + "px";
    card.style.top = Math.round(top) + "px";
  }

  // On phones the card is a bottom sheet; keep the target above it.
  function keepTargetAboveSheet() {
    if (!isMobile() || !state.target) return;
    var r = targetRect(state.target);
    if (!r) return;
    var limit = window.innerHeight - state.els.card.offsetHeight - 24;
    if (r.bottom > limit) {
      var scroller = (firstEl(state.target) && firstEl(state.target).closest(".t58-sidebar")) || document.scrollingElement || document.documentElement;
      scroller.scrollTop += (r.bottom - limit);
    }
  }

  /* ---- rendering a step ------------------------------------------------ */
  function render() {
    var step = STEPS[state.i];
    var last = state.i === STEPS.length - 1;
    var card = state.els.card;
    while (card.firstChild) card.removeChild(card.firstChild);

    var top = el("div", "t58-tour-top");
    top.appendChild(el("span", "t58-tour-step", "Step " + (state.i + 1) + " of " + STEPS.length));
    var x = el("button", "t58-tour-x", "\u00D7");
    x.type = "button";
    x.setAttribute("aria-label", "Close tour");
    x.addEventListener("click", function () { finish("skipped"); });
    top.appendChild(x);
    card.appendChild(top);

    var h = el("h3", "t58-tour-title", step.title);
    h.id = "t58-tour-title";
    card.appendChild(h);

    step.text.forEach(function (p) { card.appendChild(rich(el("p"), p)); });

    if (step.chips) {
      var chips = el("div", "t58-tour-chips");
      step.chips.forEach(function (c, k) {
        if (k) chips.appendChild(el("span", "t58-tour-arrow", "\u2192"));
        chips.appendChild(el("span", "t58-tour-chip", c));
      });
      card.appendChild(chips);
    }

    var dots = el("div", "t58-tour-dots");
    STEPS.forEach(function (_s, k) {
      var d = el("button", "t58-tour-dot" + (k === state.i ? " on" : ""));
      d.type = "button";
      d.setAttribute("aria-label", "Go to step " + (k + 1));
      d.addEventListener("click", function () { go(k); });
      dots.appendChild(d);
    });
    card.appendChild(dots);

    var actions = el("div", "t58-tour-actions");
    if (step.action && !step.action.primary) {
      var a = el("a", "t58-tour-btn link", step.action.label + " \u2197");
      a.href = step.action.href;
      a.addEventListener("click", function () { markSeen("opened-page"); });
      actions.appendChild(a);
    }
    actions.appendChild(el("span", "t58-tour-spacer"));

    if (!last) {
      var skip = el("button", "t58-tour-btn quiet", "Skip");
      skip.type = "button";
      skip.addEventListener("click", function () { finish("skipped"); });
      actions.appendChild(skip);
    }
    if (state.i > 0) {
      var back = el("button", "t58-tour-btn", "Back");
      back.type = "button";
      back.addEventListener("click", function () { go(state.i - 1); });
      actions.appendChild(back);
    }
    if (last) {
      var done = el("button", "t58-tour-btn", "Finish");
      done.type = "button";
      done.addEventListener("click", function () { finish("done"); });
      actions.appendChild(done);
      if (step.action && step.action.primary) {
        var go1 = el("a", "t58-tour-btn primary", step.action.label);
        go1.href = step.action.href;
        go1.addEventListener("click", function () { markSeen("done"); });
        actions.appendChild(go1);
      }
    } else {
      var next = el("button", "t58-tour-btn primary", state.i === 0 ? "Show me around" : "Next");
      next.type = "button";
      next.setAttribute("data-t58-tour-next", "1");
      next.addEventListener("click", function () { go(state.i + 1); });
      actions.appendChild(next);
    }
    card.appendChild(actions);
  }

  function go(i) {
    if (!state) return;
    if (i < 0 || i >= STEPS.length) return;
    state.i = i;
    var step = STEPS[i];

    // Resolve the target first, then open whichever sidebar section(s) hold it. (Every step used to need its own `group`
    // function; steps without one never opened their section, so the item stayed hidden and the tour showed only the card.)
    var tgt = step.target ? step.target() : null;
    var grps = groupsOf(tgt);
    if (step.group) { var g0 = step.group(); if (g0 && grps.indexOf(g0) < 0) grps.push(g0); }
    closeOpenedExcept(grps);
    grps.forEach(openGroup);
    var needsSidebar = inSidebar(tgt);
    if (isMobile()) ensureDrawer(needsSidebar);

    state.target = tgt;
    if (state.target && !targetRect(state.target)) state.target = null; // hidden -> centered card

    render();

    if (state.target) {
      var block = step.scroll || "center";
      var first = firstEl(state.target);
      // Bring the highlighted thing into view: the sidebar scrolls inside itself, the page scrolls for dashboard panels.
      try { first.scrollIntoView({ block: block, inline: "nearest" }); } catch (e) {}
      if (block === "start" && !inSidebar(state.target)) {
        try { window.scrollBy(0, -16); } catch (e) {} // breathing room above the spotlight
      }
    }
    keepTargetAboveSheet();
    place();
    // Layout can shift a frame later (details opening, fonts): re-place once more.
    window.requestAnimationFrame(function () { if (state) { keepTargetAboveSheet(); place(); } });
    // On phones the sidebar slides in as a drawer (a CSS transition): measure again once it has settled, or the
    // spotlight lands where the drawer WAS.
    if (isMobile() && needsSidebar) {
      [140, 360].forEach(function (ms) { window.setTimeout(function () { if (state && state.i === i) { keepTargetAboveSheet(); place(); } }, ms); });
    }

    var nextBtn = state.els.card.querySelector("[data-t58-tour-next]") ||
                  state.els.card.querySelector(".t58-tour-btn.primary");
    if (nextBtn) { try { nextBtn.focus({ preventScroll: true }); } catch (e) {} }
  }

  /* ---- lifecycle -------------------------------------------------------- */
  function onKey(e) {
    if (!state) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); finish("skipped"); }
    else if (e.key === "ArrowRight") { e.preventDefault(); go(Math.min(state.i + 1, STEPS.length - 1)); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); go(Math.max(state.i - 1, 0)); }
    else if (e.key === "Tab") { // keep focus inside the card
      var f = state.els.card.querySelectorAll("a[href],button");
      if (!f.length) return;
      var first = f[0], lastEl = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); lastEl.focus(); }
      else if (!e.shiftKey && document.activeElement === lastEl) { e.preventDefault(); first.focus(); }
      else if (!state.els.card.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
    }
  }
  function onReflow() { if (state) { keepTargetAboveSheet(); place(); } }

  function start(kind) {
    if (state) return;
    kind = (typeof kind === "string") ? kind : "main";
    STEPS = kind === "connect" ? CONNECT_STEPS : MAIN_STEPS;
    injectCss();
    state = {
      kind: kind, i: 0, opened: [], target: null, openedDrawer: false,
      prevFocus: document.activeElement,
      els: { block: el("div", "t58-tour-block"), spot: el("div", "t58-tour-spot t58-tour-nospot"), card: el("div", "t58-tour-card") }
    };
    state.els.card.setAttribute("role", "dialog");
    state.els.card.setAttribute("aria-modal", "true");
    state.els.card.setAttribute("aria-labelledby", "t58-tour-title");
    document.body.appendChild(state.els.block);
    document.body.appendChild(state.els.spot);
    document.body.appendChild(state.els.card);
    // The Coach panel can pop open by itself at the start of a session; it would sit on top of what the tour points at.
    try {
      var pcPanel = document.getElementById("t58-pc-panel"), pcClose = document.getElementById("t58-pc-close");
      if (pcPanel && !pcPanel.hidden && pcClose) pcClose.click();
    } catch (e) {}
    document.addEventListener("keydown", onKey, true);
    window.addEventListener("resize", onReflow);
    window.addEventListener("scroll", onReflow, true);
    go(0);
  }

  function finish(how) {
    if (!state) return;
    if (state.kind !== "connect") markSeen(how);   // the quick connect tour never changes the first-run flag
    document.removeEventListener("keydown", onKey, true);
    window.removeEventListener("resize", onReflow);
    window.removeEventListener("scroll", onReflow, true);
    closeOpenedExcept(null);
    if (isMobile()) ensureDrawer(false);
    ["block", "spot", "card"].forEach(function (k) {
      var n = state.els[k];
      if (n && n.parentNode) n.parentNode.removeChild(n);
    });
    var prev = state.prevFocus;
    state = null;
    if (prev && prev.focus) { try { prev.focus({ preventScroll: true }); } catch (e) {} }
  }

  /* ---- wiring ----------------------------------------------------------- */
  document.addEventListener("click", function (e) {
    var t = e.target && e.target.closest ? e.target.closest("[data-t58-tour-start]") : null;
    if (t) { e.preventDefault(); if (state) finish("done"); start(t.getAttribute("data-t58-tour-start") || "main"); }
  });

  window.T58Tour = {
    start: start,
    stop: function () { finish("skipped"); },
    reset: function () {
      try { localStorage.removeItem(STORE_KEY); } catch (e) {}
      try { sessionStorage.removeItem(STORE_KEY); } catch (e) {}
    },
    _steps: MAIN_STEPS, // exposed for tests
    _connectSteps: CONNECT_STEPS
  };

  function autoStart() {
    var q = "";
    try { q = new URLSearchParams(window.location.search).get("tour"); } catch (e) {}
    if (q === "0") return;
    if (q === "connect") { window.setTimeout(function () { start("connect"); }, 650); return; }
    // The Dashboard renders window.T58_TOUR_AUTOSTART from the server's own
    // first-run flag: true only on the first Dashboard visit after the
    // license is activated. Browser storage is only a fallback for pages
    // that don't set it.
    var serverSays = window.T58_TOUR_AUTOSTART;
    var shouldStart = (typeof serverSays === "boolean") ? serverSays : !seen();
    if (q === "1" || shouldStart) {
      // let the sidebar finish restoring its own open/closed groups first
      window.setTimeout(start, 650);
    }
  }
  if (document.readyState === "complete") autoStart();
  else window.addEventListener("load", autoStart);
})();
