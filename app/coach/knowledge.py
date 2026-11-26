"""Coach knowledge base: plain data, no AI.

Each entry is a dict:
    id        unique slug
    cat       category label (used for the "browse topics" chips)
    title     short question-style title (also matched against)
    kw        trigger phrases; a phrase matches when all its words appear in the question (stemmed)
    answer    the reply text. Blank line = new paragraph; lines starting with "- " render as bullets.
    links     [(label, href)] buttons shown under the answer
    related   ids offered as follow-up chips

Keep answers factual about the app and standard trading practice. Nothing here is financial advice.
"""

from __future__ import annotations

CATEGORIES = [
    ("start", "Getting started"),
    ("app", "Where things are"),
    ("flow", "The strategy workflow"),
    ("dev", "Developing strategies"),
    ("concept", "Trading concepts"),
    ("prop", "Prop firms and payouts"),
    ("setup", "Setup and settings"),
    ("help", "Troubleshooting"),
]

ENTRIES = [
    # ------------------------------------------------------------------ getting started
    dict(id="what_is_t58", cat="start", title="What is T58 Quant Engine?",
         kw=["what is t58", "what does this app do", "what is this app", "what can i do here", "overview", "about the app", "explain the app"],
         answer="T58 is a research lab for trading strategies, built around one goal: get you a payout from a prop firm without fooling yourself on the way.\n\n"
                "You create or import a strategy, test it on historical data, optimize it, stress-test it, promote the survivors to Champion, practise on a demo account and only then go live.\n\n"
                "Everything runs on your own computer. The sidebar groups the tools: Workspace, Strategy Lab, Quant Lab, Prop Journey and Account.",
         links=[("Open the dashboard", "/dashboard"), ("First Payout Mission", "/mission")], related=["next_step", "workflow", "sidebar"]),
    dict(id="next_step", cat="start", title="What should I do next?",
         kw=["what should i do next", "what next", "what now", "next step", "where do i start", "where to start", "how do i start", "get started", "getting started", "i am new", "new here", "first time", "begin", "what do i do"],
         answer="Follow the ladder. Each rung earns the next one:\n\n"
                "- 1. Get data into the Data Center (the app ships with some).\n"
                "- 2. Create or pick a strategy.\n"
                "- 3. Test it properly.\n"
                "- 4. Optimize it, then check it will not fall apart (Validate).\n"
                "- 5. Promote it on the Champion board.\n"
                "- 6. Practise on the demo account in Deploy.\n"
                "- 7. Buy an evaluation, pass it, collect your first payout.\n\n"
                "The First Payout Mission page tracks where you are and always names the single next action, so if in doubt open it.",
         links=[("First Payout Mission", "/mission"), ("Create a strategy", "/start-here/create"), ("Data Center", "/data-center")], related=["workflow", "create", "data_import"]),
    dict(id="mission", cat="start", title="What is the First Payout Mission?",
         kw=["first payout mission", "mission", "payout mission", "seven steps", "7 steps", "progress tracker"],
         answer="The Mission is a seven-step guided path: test a strategy, optimize or validate it, promote it to Champion, complete forward testing, purchase the evaluation, pass it and receive your first payout.\n\n"
                "It updates itself as you hit milestones and tells you the one thing to do next. The thin bar at the top of most pages is the same tracker.",
         links=[("Open the Mission", "/mission")], related=["next_step", "workflow"]),
    dict(id="tour", cat="start", title="How do I take the guided tour again?",
         kw=["tour", "walkthrough", "guided tour", "60 second", "show me around", "replay tour", "restart tour", "tutorial", "onboarding"],
         answer="Open your profile menu (the round avatar, top right) and choose the guided tour, or open the Help area. The tour highlights each part of the sidebar and the dashboard in turn so you can see exactly where everything lives.\n\n"
                "You can leave it at any time with Esc.",
         links=[("Open Help and Support", "/support")], related=["sidebar", "next_step"]),
    dict(id="sidebar", cat="app", title="Where is everything? (the sidebar)",
         kw=["where is", "where can i find", "where do i find", "sidebar", "menu", "navigation", "navigate", "find a page", "site map", "all pages", "all features", "what pages"],
         answer="The left sidebar has five sections:\n\n"
                "- Workspace: Dashboard, AI Assistant, Global Events, Trading Journal, Runs, Mobile Access.\n"
                "- Strategy Lab: Create, Test, Optimize, Validate, Champion, Deploy, Strategy Library.\n"
                "- Quant Lab: deeper research tools, plus Investing.\n"
                "- Prop Journey: First Payout Mission, Evaluation Guardian, Research Integrity, Accounts, Buy Challenge.\n"
                "- Account: Settings, Data Center, University, Playground and the Library of books and papers.\n\n"
                "Tip: press Ctrl+K (Cmd+K on Mac) to jump to any page by typing its name. Ask me 'where is X' for a specific page.",
         links=[("Dashboard", "/dashboard"), ("Quant Lab", "/quant-lab")], related=["jump_anywhere", "workflow"]),
    dict(id="jump_anywhere", cat="app", title="Is there a quick way to jump to a page?",
         kw=["ctrl k", "command palette", "jump anywhere", "quick search", "search the app", "keyboard shortcut", "shortcut", "search strategies datasets"],
         answer="Yes. Press Ctrl+K (Cmd+K on a Mac) anywhere in the app, type part of a page, strategy or dataset name and press Enter. The search box at the top of the sidebar does the same thing.",
         related=["sidebar"]),
    # ------------------------------------------------------------------ where things are
    dict(id="where_data", cat="app", title="Where do I manage data and import files?",
         kw=["data center", "where is data", "datasets", "import data", "upload data", "add data", "csv", "parquet", "bring my own data", "historical data", "data coverage", "gaps in data"],
         answer="The Data Center (Account section) shows every dataset: coverage, timeframes, gaps, duplicates, sessions and bar counts. It is also where you import new CSV or parquet files.\n\n"
                "To import: open the Data Center, use the import area, pick your file, tell it the instrument and timeframe, then confirm. A good file has timestamp, open, high, low, close and (optionally) volume columns.\n\n"
                "Check the coverage view afterwards. Gaps or duplicate bars quietly distort backtests.",
         links=[("Open the Data Center", "/data-center")], related=["data_quality", "create"]),
    dict(id="data_import", cat="setup", title="How do I import my own data?",
         kw=["import my own data", "how do i import", "load data", "data format", "what format", "timestamp column", "add a dataset", "new dataset"],
         answer="Go to Data Center, use the import section and choose a CSV or parquet file. Columns needed: time/date, open, high, low, close; volume is optional.\n\n"
                "Pick the right instrument name and timeframe when asked, and keep timezone consistent (the Data Center shows what it detected). After importing, scan the coverage and gap report before you test anything on it.",
         links=[("Data Center", "/data-center")], related=["where_data", "data_quality"]),
    dict(id="data_quality", cat="dev", title="How much data do I need, and what makes data good?",
         kw=["how much data", "enough data", "data quality", "how many years", "how many trades", "sample size", "bar count", "bad data", "dirty data", "survivorship"],
         answer="Rules of thumb:\n\n"
                "- Aim for at least 100 to 200 trades in a backtest. Below ~30 trades the result is mostly noise.\n"
                "- Cover more than one market regime: a trending stretch, a choppy stretch, a crash or spike.\n"
                "- Keep a slice the strategy never sees (out-of-sample or holdout). T58 does this for you in Test.\n"
                "- Watch for gaps, duplicate bars and wrong timezones; they are the commonest silent bug.\n\n"
                "More years is not always better: a strategy tuned to a market that no longer exists will not carry over.",
         links=[("Data Center", "/data-center"), ("Test a strategy", "/full-pipeline")], related=["oos", "overfitting"]),
    dict(id="where_library", cat="app", title="Where are my strategies?",
         kw=["strategy library", "my strategies", "saved strategies", "where are my strategies", "find a strategy", "list of strategies", "view code", "strategy code"],
         answer="The Strategy Library lists every strategy (Manual, Python, PineScript and MQL5). Click one to view its code, run a backtest or optimization, see results, deploy it or manage settings.\n\n"
                "It has tabs: Strategies, Research (the Agent Desk and Research Ledger together) and Graveyard. The Trading Bots section sits at the top of the Strategies tab.",
         links=[("Open the Library", "/library")], related=["graveyard", "research_tab", "bots"]),
    dict(id="research_tab", cat="app", title="Where is the Agent Desk and Research Ledger?",
         kw=["agent desk", "research ledger", "research tab", "desk", "ledger", "scout", "research agents", "where is the research"],
         answer="Both now live in one place: Strategy Library, Research tab (between Strategies and Graveyard). Use the switch at the top to flip between the Agent Desk (the research agents and their board) and the Research Ledger (what has been tried, covered and closed).\n\n"
                "The old addresses /desk and /research-ledger redirect there automatically.",
         links=[("Open Research", "/library/research"), ("Agent Desk", "/library/research?view=desk"), ("Research Ledger", "/library/research?view=ledger")], related=["where_library", "graveyard"]),
    dict(id="graveyard", cat="app", title="What is the Graveyard?",
         kw=["graveyard", "dead strategies", "failed strategies", "rejected strategies", "archive", "why was a strategy rejected", "retired strategies"],
         answer="The Graveyard keeps strategies that failed a check, with the reason, so you never rebuild the same dead idea twice. Failure is information: a pattern of reasons (for example 'fails out-of-sample') tells you what to fix in your next idea.\n\n"
                "Find it as a tab in the Strategy Library.",
         links=[("Open the Graveyard", "/graveyard")], related=["where_library", "overfitting"]),
    dict(id="bots", cat="app", title="Where are the trading bots?",
         kw=["trading bots", "bots", "bot", "where are the bots", "automated trading", "auto trade", "autopilot", "run a bot", "configure a bot", "bot settings"],
         answer="Trading Bots appear in two places: the Dashboard and the top of the Strategy Library (the Trading Bots section). There are three bots, each tuned for one goal. They size every trade from your account size, rules, P&L, drawdown and progress, and explain in plain words why they are or are not trading.\n\n"
                "They start on the T58 demo account. Moving to a prop firm or live account is one step in Settings, and nothing touches real money until you do that on purpose.\n\n"
                "To configure one: open its card, choose Configure, set the account size and risk, then switch it on.",
         links=[("Open Trading Bots", "/trading-bots"), ("Strategy Library", "/library")], related=["deploy", "guardian"]),
    dict(id="runs", cat="app", title="Where do I see running or finished jobs?",
         kw=["runs", "running jobs", "job status", "background job", "where is my run", "finished run", "compare runs", "stop a run", "cancel run", "progress of my test"],
         answer="The Runs page lists every run, running or recently finished. Leaving a run's page never stops it. Tap a row to jump back in, or tick two finished runs to compare them side by side.",
         links=[("Open Runs", "/runs")], related=["slow_backtest"]),
    dict(id="journal", cat="app", title="What is the Trading Journal?",
         kw=["journal", "trading journal", "log a trade", "playbook", "tag trades", "trade log", "review my trades", "which setups make money"],
         answer="The Journal is where you log every real trade against your playbook, tag it, and see which setups, time windows and instruments actually make or lose money. A starter playbook and tag list are preloaded and fully editable. Data stays on your computer.\n\n"
                "Habit that pays: log the trade, the reason, and whether you followed your rules. Review it weekly.",
         links=[("Open the Journal", "/journal")], related=["weekly_digest"]),
    dict(id="events", cat="app", title="What are Global Events?",
         kw=["global events", "news", "economic calendar", "events", "fomc", "cpi", "nfp", "high impact news", "news filter"],
         answer="Global Events shows scheduled market-moving events. Prop firms often restrict trading around high-impact news, and the Evaluation Guardian can watch for it. Check it before you plan a session.",
         links=[("Open Global Events", "/events/"), ("Evaluation Guardian", "/guardian")], related=["guardian"]),
    dict(id="quant_lab", cat="app", title="What is the Quant Lab?",
         kw=["quant lab", "advanced tools", "research tools", "walk forward", "cpcv", "pbo", "monte carlo tool", "regime matrix", "advanced research"],
         answer="The Quant Lab is the toolbox behind the simple pages: walk-forward optimization, CPCV, probability of backtest overfitting (PBO), parameter robustness, regime matrix, family diversity and more. Use it when a strategy has passed the basics and you want harder evidence.\n\n"
                "Rule of thumb: Strategy Lab to build and promote, Quant Lab to interrogate.",
         links=[("Open the Quant Lab", "/quant-lab")], related=["overfitting", "validate"]),
    dict(id="investing", cat="app", title="What is the Investing tab?",
         kw=["investing", "invest", "stocks", "portfolio", "paper trading", "paper money", "long term portfolio", "sec filings", "crypto", "reset portfolio", "10000"],
         answer="Investing lets you search any stock, index or crypto, read the SEC filings behind it and invest yourself or let an algo tuned to you do it. It starts in paper mode with $10,000 of practice money.\n\n"
                "Reinstalling the app with your master license key now resets this portfolio too, so you always start clean.",
         links=[("Open Investing", "/investing")], related=["settings"]),
    dict(id="mobile", cat="setup", title="How do I use T58 on my phone?",
         kw=["phone", "mobile", "ipad", "tablet", "mobile access", "qr code", "scan", "use on my phone", "iphone", "android"],
         answer="Open Mobile Access, scan the QR code with your phone's camera and the exact same app opens on the phone. Nothing to install. Your computer needs to stay on and on the same network. The page always shows the current address.",
         links=[("Mobile Access", "/mobile-access")], related=["troubleshoot_login"]),
    dict(id="university", cat="app", title="Where can I learn trading and quant concepts?",
         kw=["university", "learn", "course", "education", "lessons", "teach me", "learn trading", "study", "training", "tutorial videos"],
         answer="The University (Account section) has structured lessons on strategy design, testing, risk and prop firms. The Library inside Playground holds books, research papers and a focus timer for quieter study.\n\n"
                "Ask me directly too: I can explain drawdown, Sharpe, overfitting, walk-forward and most terms in plain words.",
         links=[("Open the University", "/education"), ("Books and papers", "/playground/library")], related=["glossary_hub"]),
    dict(id="playground", cat="app", title="What is the Playground?",
         kw=["playground", "games", "game", "fidget", "relax", "break", "fun", "chess", "2048", "puzzle", "tetris", "maze"],
         answer="The Playground is a calm corner for breaks: fidgets (a twisting cube with secrets, liquid light, particles), arcade games (chess against the computer, 2048 Quant Edition, a block stacker), daily puzzles (maze, chess puzzles, chart analyzer) and physics toys. All of it runs locally and never touches your strategies.",
         links=[("Open the Playground", "/playground")], related=["university"]),
    # ------------------------------------------------------------------ workflow
    dict(id="workflow", cat="flow", title="What is the strategy workflow?",
         kw=["workflow", "process", "pipeline", "how does it work", "steps", "lifecycle", "stages", "from idea to", "how do i go from", "evidence ladder", "reject lead forward"],
         answer="Strategies move up an evidence ladder: Reject, Lead, Forward-Test Candidate, Evaluate, Funded.\n\n"
                "- Create: describe or import the idea.\n- Test: the full check (baseline, preflight, search, Monte Carlo, out-of-sample, holdout) ending in a verdict.\n"
                "- Optimize: try variations, keep the best, with a plain explanation.\n- Validate: stress tests only, nothing gets tuned.\n"
                "- Champion: promote one stage at a time once it has earned it.\n- Deploy: demo account, then forward test, then live.\n\n"
                "Never skip Validate. A strategy that has only been optimized has only been fitted.",
         links=[("Create", "/start-here/create"), ("Test", "/full-pipeline"), ("Champion board", "/champion-simple")], related=["create", "test", "optimize", "validate", "champion", "deploy"]),
    dict(id="create", cat="flow", title="How do I create a strategy?",
         kw=["create a strategy", "make a strategy", "new strategy", "build a strategy", "write a strategy", "add a strategy", "import a strategy", "pinescript", "mql5", "python strategy", "generate strategies", "strategy idea"],
         answer="Open Create (Strategy Lab). You can start from a ready-made template, generate candidates automatically, or bring your own: Python, PineScript or MQL5 code, or a manual rule set.\n\n"
                "Good first strategy: one entry idea, one stop, one target, one instrument, one timeframe. Complexity is how overfitting sneaks in.\n\n"
                "After saving, it appears in the Strategy Library, ready for Test.",
         links=[("Create a strategy", "/start-here/create"), ("Strategy Library", "/library")], related=["strategy_design", "test"]),
    dict(id="test", cat="flow", title="How do I test a strategy properly?",
         kw=["test a strategy", "backtest", "back test", "run a test", "test my strategy", "full pipeline", "verdict", "how do i backtest", "run backtest", "test it properly"],
         answer="Open Test. Pick the strategy, the data and the prop-firm rules to judge it against, then start. The full check runs: baseline, preflight, walk-forward-aware search, re-validated Monte Carlo, out-of-sample and holdout, then gives a verdict on the evidence ladder (Reject, Lead, Forward-Test Candidate, Evaluate, Funded).\n\n"
                "Read the verdict and the reasons, not just the profit number. A big profit with a Reject verdict means the profit is probably luck.",
         links=[("Open Test", "/full-pipeline"), ("Runs", "/runs")], related=["optimize", "verdict", "slow_backtest"]),
    dict(id="verdict", cat="flow", title="How do I read the verdict?",
         kw=["verdict", "reject", "lead", "forward test candidate", "what does reject mean", "what does lead mean", "evaluate verdict", "funded verdict", "my strategy was rejected", "why rejected"],
         answer="The verdict is where your strategy sits on the evidence ladder:\n\n"
                "- Reject: the evidence says no edge or an unacceptable risk. Check the reasons, fix or bury it.\n- Lead: something interesting, not enough proof. Keep researching.\n"
                "- Forward-Test Candidate: passes the offline checks. Time to practise on demo.\n- Evaluate: worth paying for a prop-firm evaluation.\n- Funded: has the track record to be trusted with a funded account.\n\n"
                "Each verdict lists why. Fix the named weakness and re-run; do not just re-tune until it flips.",
         links=[("Open Test", "/full-pipeline"), ("Graveyard", "/graveyard")], related=["overfitting", "optimize"]),
    dict(id="optimize", cat="flow", title="How do I optimize a strategy?",
         kw=["optimize", "optimise", "optimization", "improve my strategy", "tune", "parameters", "better results", "improve", "tweak", "parameter search", "genetic"],
         answer="Open Optimize. Choose the strategy, the data and the firm, then say what you want to improve (profit, safer drawdown, pass rate). T58 tries variations, keeps the best, and tells you plainly what changed and what to do next.\n\n"
                "Rules that save you pain:\n- Optimize a few parameters, not twenty.\n- Prefer a wide plateau of good settings over one sharp peak.\n- Always follow with Validate. Optimization is the step that creates overfitting, so Validate is the step that catches it.",
         links=[("Open Optimize", "/optimize-simple"), ("Validate", "/validate-simple")], related=["validate", "overfitting", "robustness"]),
    dict(id="validate", cat="flow", title="What does Validate do?",
         kw=["validate", "validation", "stress test", "will it fall apart", "robustness check", "check it will not fall apart", "monte carlo", "stress tests"],
         answer="Validate runs stress tests only. Nothing is tuned or changed. You tick the checks you want and they all run against the same risk setup so the numbers compare. Each finished check is saved on the strategy, so the Champion page knows what has been proven.\n\n"
                "Typical checks: Monte Carlo reshuffles, parameter nudges, higher costs and slippage, different time windows. If a small push breaks it, it was never robust.",
         links=[("Open Validate", "/validate-simple")], related=["champion", "monte_carlo", "robustness"]),
    dict(id="champion", cat="flow", title="How do I promote a strategy to Champion?",
         kw=["champion", "promote", "promotion", "champion board", "rank strategies", "what does it still need", "promote a strategy", "best strategy"],
         answer="The Champion board ranks every saved strategy by how far it has earned its way up. Pick one, see exactly what it still needs (for example a Validate check or a longer forward test), and promote it one stage at a time. You cannot skip stages; that is the point.",
         links=[("Open Champion", "/champion-simple")], related=["validate", "deploy"]),
    dict(id="deploy", cat="flow", title="How do I deploy (demo, forward test, live)?",
         kw=["deploy", "go live", "live trading", "demo account", "forward test", "forward testing", "paper trade a strategy", "connect broker", "metatrader", "start trading", "arm deploy live", "deploy live"],
         answer="Deploy goes in three guarded steps: the T58 demo account (simulated money with real prop-firm rules), then a forward test on a live terminal, then live. Nothing touches real money until you deliberately arm Deploy Live.\n\n"
                "Do the demo and forward test for long enough to see a normal losing streak. If live results drift far from the backtest, stop and investigate before adding size.",
         links=[("Open Deploy", "/forward-test"), ("Demo account", "/demo-account")], related=["guardian", "bots", "forward_vs_backtest"]),
    dict(id="forward_vs_backtest", cat="dev", title="Why do live results differ from the backtest?",
         kw=["live results different", "backtest vs live", "why is live worse", "live is worse than backtest", "slippage", "spread", "execution", "forward test different", "performance drop live"],
         answer="Common causes, in order of how often they bite:\n\n"
                "- Costs: spread, commission and slippage were too low in the test.\n- Overfitting: the backtest was tuned to the past.\n- Execution: fills, latency, requotes, news spikes.\n"
                "- Regime change: the market behaves differently now.\n- Rule drift: you (or a bot) deviated from the plan.\n\n"
                "Test with pessimistic costs on purpose. Use Validate's higher-cost checks.",
         links=[("Validate", "/validate-simple")], related=["overfitting", "validate"]),
    # ------------------------------------------------------------------ developing strategies
    dict(id="strategy_design", cat="dev", title="How do I design a strategy that might actually work?",
         kw=["strategy design", "design a strategy", "strategy development", "develop a strategy", "how to build a good strategy", "good strategy", "find an edge", "edge", "trading idea", "ideas", "what makes a strategy work", "entry exit", "rules"],
         answer="Start from a reason the edge should exist (a behaviour, a structural flow, a risk premium) rather than from a pattern you noticed on a chart.\n\n"
                "- Write the rules in one paragraph: entry, stop, target, position size, session.\n- Keep parameters few (3 to 5).\n- Choose a timeframe and instrument that suit the prop firm rules you will face.\n"
                "- Test costs-in from the first run.\n- Predict in advance what result would make you drop it.\n\n"
                "Then run Test. A Reject is a cheap lesson; a lucky pass is an expensive one.",
         links=[("Create a strategy", "/start-here/create"), ("University", "/education")], related=["overfitting", "stops", "position_sizing"]),
    dict(id="overfitting", cat="concept", title="What is overfitting and how do I avoid it?",
         kw=["overfitting", "overfit", "curve fitting", "curve fit", "over optimized", "too good to be true", "data mining", "backtest too perfect", "pbo", "probability of backtest overfitting"],
         answer="Overfitting is when a strategy learns the noise of the past instead of a repeatable edge. It looks great in the backtest and fails live.\n\n"
                "Defences built into T58: out-of-sample and holdout data, walk-forward search, Monte Carlo, parameter-nudge checks and PBO in the Quant Lab.\n\n"
                "Defences you control: fewer parameters, wide plateaus not sharp peaks, a reason for the edge, and never re-tuning after you have seen the holdout.",
         links=[("Validate", "/validate-simple"), ("Quant Lab", "/quant-lab")], related=["oos", "robustness", "walk_forward"]),
    dict(id="oos", cat="concept", title="What are in-sample, out-of-sample and holdout data?",
         kw=["out of sample", "in sample", "oos", "holdout", "train test", "test data", "unseen data", "split data"],
         answer="In-sample is the data you tune on. Out-of-sample is data the tuning never saw; if performance survives there, the edge is more believable. Holdout is a final slice you touch once, at the end. If you peek and re-tune, it stops being a holdout.\n\nTest handles the splits for you.",
         links=[("Open Test", "/full-pipeline")], related=["overfitting", "walk_forward"]),
    dict(id="walk_forward", cat="concept", title="What is walk-forward testing?",
         kw=["walk forward", "walk-forward", "rolling optimization", "wfo", "walk forward optimization"],
         answer="Walk-forward repeatedly optimizes on a window of past data, then tests on the period right after it, and rolls forward. Stitching the test periods together gives a result that mimics how you would really have traded: re-tuning as you go and only judged on unseen data.\n\nThe Quant Lab has dedicated walk-forward tools.",
         links=[("Quant Lab", "/quant-lab")], related=["oos", "overfitting"]),
    dict(id="robustness", cat="concept", title="How do I know if a strategy is robust?",
         kw=["robust", "robustness", "parameter robustness", "sensitivity", "stable", "plateau", "fragile", "nudge parameters"],
         answer="A robust strategy still works when you nudge the settings, add costs, shift the start date or reshuffle the trade order. Look for a broad plateau of good parameters rather than a single spike. Validate and the Quant Lab's parameter-robustness and sensitivity tools test exactly this.",
         links=[("Validate", "/validate-simple"), ("Quant Lab", "/quant-lab")], related=["overfitting", "monte_carlo"]),
    dict(id="monte_carlo", cat="concept", title="What is Monte Carlo?",
         kw=["monte carlo", "reshuffle", "simulation", "randomize trades", "worst case", "luck vs skill", "simulate"],
         answer="Monte Carlo reshuffles or resamples your historical trades thousands of times to show the range of outcomes you could have had with the same edge. It answers: how bad could the drawdown get, and how often would I pass an evaluation, if the order of wins and losses had been different?\n\nFocus on the bad tail (the 5th percentile), not the average.",
         related=["drawdown", "pass_rate"]),
    dict(id="drawdown", cat="concept", title="What is drawdown?",
         kw=["drawdown", "dd", "max drawdown", "peak to trough", "trailing drawdown", "max dd", "equity drop"],
         answer="Drawdown is the fall from an equity peak to the next low. Max drawdown is the worst one. Prop firms cap it, so it is the number that most often ends an evaluation.\n\n"
                "Trailing drawdown moves up with your best equity and never moves back down, so it is stricter than a fixed limit. Know which kind your firm uses before you size trades.",
         links=[("Evaluation Guardian", "/guardian")], related=["eod_vs_intraday", "position_sizing", "daily_loss"]),
    dict(id="eod_vs_intraday", cat="prop", title="What is end-of-day versus intraday trailing drawdown?",
         kw=["eod drawdown", "intraday drawdown", "end of day trailing", "eod vs intraday", "trailing type", "balance based", "equity based", "static drawdown"],
         answer="Intraday (equity) trailing updates on every tick, including unrealised profit, so a trade that runs up and gives it back can still raise your floor. End-of-day trailing only updates when the day closes, which is gentler. Static drawdown never moves.\n\nBuy Challenge lists each plan's type, so compare them before you buy.",
         links=[("Buy Challenge", "/buy-challenge")], related=["drawdown", "buy_challenge"]),
    dict(id="daily_loss", cat="prop", title="What is the daily loss limit?",
         kw=["daily loss", "daily loss limit", "daily drawdown", "dll", "max loss per day", "daily limit"],
         answer="A hard cap on how much you can lose in one trading day, set by the firm. Break it and the account is usually closed. The Evaluation Guardian watches it live and acts before you cross it. A good habit is a personal daily stop at roughly half the firm's limit.",
         links=[("Evaluation Guardian", "/guardian")], related=["drawdown", "guardian"]),
    dict(id="sharpe", cat="concept", title="What are Sharpe, Sortino and profit factor?",
         kw=["sharpe", "sortino", "profit factor", "ratio", "risk adjusted", "calmar", "metrics", "what does sharpe mean", "performance metrics", "expectancy"],
         answer="- Sharpe: return divided by volatility. Higher is steadier. Above 1 is decent, above 2 is excellent but suspicious in a short sample.\n- Sortino: like Sharpe but only penalises downside swings.\n- Profit factor: gross profit divided by gross loss. 1.0 is break-even; 1.3 to 2.0 is healthy; above 3 on a small sample usually means luck or overfitting.\n- Expectancy: average profit per trade, ideally in R (multiples of your risk).\n\nNever judge one metric alone: pair it with drawdown and the number of trades.",
         related=["drawdown", "win_rate", "r_multiple"]),
    dict(id="win_rate", cat="concept", title="Does win rate matter?",
         kw=["win rate", "winning percentage", "hit rate", "percent winners", "how often do i win", "reward to risk", "risk reward", "rr", "rrr"],
         answer="Win rate only means something together with reward-to-risk. A 40% win rate with 2:1 winners is profitable (expectancy +0.2R per trade); a 70% win rate with 0.3:1 winners loses money.\n\nExpectancy = win rate x average win minus loss rate x average loss.",
         related=["r_multiple", "sharpe"]),
    dict(id="r_multiple", cat="concept", title="What is an R-multiple?",
         kw=["r multiple", "r-multiple", "risk unit", "1r", "2r", "in r"],
         answer="R is the amount you risk on a trade (entry to stop). A trade that makes twice its risk is +2R; a full stop-out is -1R. Measuring everything in R lets you compare strategies, accounts and instruments fairly, and makes expectancy easy: average R per trade.",
         related=["win_rate", "position_sizing"]),
    dict(id="position_sizing", cat="dev", title="How should I size my positions?",
         kw=["position sizing", "position size", "lot size", "how many contracts", "risk per trade", "how much to risk", "size my trades", "contract size", "risk percent", "kelly"],
         answer="Size from the stop, not the other way round: contracts = (dollars you are willing to risk) divided by (stop distance in dollars per contract).\n\n"
                "For prop accounts, risk a small fraction of the drawdown limit per trade (many traders use 0.25% to 1% of the account, and far less than the daily limit). Smaller size survives the inevitable losing streak; oversizing is the number one reason evaluations fail.\n\n"
                "The Trading Bots size this automatically from your rules and drawdown.",
         links=[("Trading Bots", "/trading-bots"), ("Evaluation Guardian", "/guardian")], related=["drawdown", "risk_of_ruin", "stops"]),
    dict(id="risk_of_ruin", cat="concept", title="What is risk of ruin?",
         kw=["risk of ruin", "blow up", "blow the account", "probability of failing", "chance of failing", "how likely to fail"],
         answer="The probability of hitting your drawdown limit before reaching your goal. It falls fast as you cut position size or raise expectancy. Run Monte Carlo on your trades with your firm's limits to estimate it; the pass-rate numbers in Test and Buy Challenge come from this kind of simulation.",
         related=["monte_carlo", "position_sizing", "pass_rate"]),
    dict(id="stops", cat="dev", title="How do I choose stops and targets?",
         kw=["stop loss", "stop", "take profit", "target", "trailing stop", "break even", "where to put stop", "atr stop", "exit rules", "exits"],
         answer="Anchor stops to market volatility (for example a multiple of ATR) rather than a fixed dollar figure, so they scale when markets move more or less. Place them where the idea is proven wrong, not where the loss feels tolerable.\n\n"
                "Test several stop and target combos in Optimize but expect a plateau, not a magic number. Fixed 1:2 or 1:3 targets are a clean baseline.",
         links=[("Optimize", "/optimize-simple")], related=["position_sizing", "r_multiple"]),
    dict(id="regime", cat="concept", title="What are market regimes?",
         kw=["regime", "regimes", "trending vs ranging", "market conditions", "choppy", "volatility regime", "regime matrix", "market state"],
         answer="Markets alternate between trends, ranges and high or low volatility. Most strategies work in one regime and bleed in another. The Quant Lab's Regime Matrix shows how a strategy behaves in each. Aim to know when yours should be switched off, and prefer a mix of uncorrelated strategies.",
         links=[("Quant Lab", "/quant-lab")], related=["diversification"]),
    dict(id="diversification", cat="concept", title="Should I run more than one strategy?",
         kw=["diversification", "diversify", "multiple strategies", "portfolio of strategies", "correlation", "family diversity", "correlated"],
         answer="Yes, once each one stands alone. Two uncorrelated strategies smooth the equity curve and cut drawdown. Check correlation first: three variations of one idea are one strategy in three costumes. The Quant Lab's family-diversity and family-map tools show how related your strategies are.",
         links=[("Quant Lab", "/quant-lab")], related=["regime"]),
    dict(id="slippage", cat="concept", title="How should I handle costs, spread and slippage?",
         kw=["costs", "commission", "spread", "slippage", "fees", "transaction costs", "realistic costs"],
         answer="Always backtest with costs, and be a little pessimistic: wider spread, an extra tick of slippage, full commissions. If a strategy only works at zero cost it does not work. Scalping strategies are the most cost-sensitive; check them with Validate's higher-cost stress test.",
         links=[("Validate", "/validate-simple")], related=["forward_vs_backtest"]),
    dict(id="glossary_hub", cat="concept", title="Can you explain a trading term?",
         kw=["glossary", "define", "what does mean", "explain term", "terminology", "jargon", "what is a"],
         answer="Ask me by name and I will explain it. I know: drawdown, trailing drawdown, Sharpe, Sortino, profit factor, expectancy, R-multiple, win rate, overfitting, out-of-sample, holdout, walk-forward, Monte Carlo, regime, correlation, slippage, spread, risk of ruin, position sizing, consistency rule, profit split, evaluation, funded account and more.",
         related=["drawdown", "overfitting", "sharpe"]),
    # ------------------------------------------------------------------ prop firms
    dict(id="prop_how", cat="prop", title="How do prop firm evaluations work?",
         kw=["prop firm", "prop firms", "evaluation", "challenge", "how do evaluations work", "funded account", "how does prop trading work", "profit target", "get funded", "phase 1"],
         answer="You pay a fee for an evaluation account (simulated money). Hit the profit target without breaking the rules (daily loss, max drawdown, minimum days, sometimes a consistency rule) and you are passed to a funded account where you keep a share of profits, typically 70% to 90%.\n\n"
                "The fee is the real cost, so the maths is: expected payout minus the cost of the attempts it takes to pass. The Accounts page and Buy Challenge both show that cost.",
         links=[("Buy Challenge", "/buy-challenge"), ("Accounts", "/accounts")], related=["pass_rate", "consistency", "buy_challenge", "payouts"]),
    dict(id="pass_rate", cat="prop", title="What is the pass rate and expected cost to pass?",
         kw=["pass rate", "expected cost to pass", "chance of passing", "probability of passing", "how likely to pass", "payout probability"],
         answer="Pass rate is the simulated chance your strategy passes a given plan's rules. Expected cost to pass is the plan's fee divided by that chance, plus reset fees along the way. Buy Challenge shows both for each plan against your strategy, so you can pick the plan that is cheapest for you, not just cheapest on the shelf.",
         links=[("Buy Challenge", "/buy-challenge")], related=["buy_challenge", "monte_carlo"]),
    dict(id="consistency", cat="prop", title="What is a consistency rule?",
         kw=["consistency rule", "consistency", "best day", "one big day", "30 percent rule", "40 percent rule"],
         answer="Some firms require that no single day exceeds a set percentage of your total profit (commonly 30% to 50%). It stops one lucky day from passing the account. Steady, similar-sized days satisfy it; one giant winner does not. Buy Challenge lists each plan's consistency percentage.",
         links=[("Buy Challenge", "/buy-challenge")], related=["prop_how"]),
    dict(id="buy_challenge", cat="prop", title="How do I buy an evaluation (and compare plans)?",
         kw=["buy challenge", "buy an evaluation", "purchase evaluation", "compare plans", "compare firms", "which firm", "which prop firm", "cheapest", "discount code", "coupon", "promo code", "plan comparison", "side by side"],
         answer="Open Buy Challenge. Firms are on top: pick one with 'View plans' to filter the table below, or browse every plan. Tick two to four plans and a side-by-side comparison pops up, with the best value in each row highlighted, a 'differences only' switch, and a share link.\n\n"
                "When you choose, 'Buy at firm' opens the firm's own checkout (T58 never takes payment) and 'I bought this' logs the fee in My Attempts. Always confirm price, rules and discount code at the firm's checkout, because they change them often.",
         links=[("Open Buy Challenge", "/buy-challenge"), ("Accounts", "/accounts")], related=["pass_rate", "eod_vs_intraday", "prop_how"]),
    dict(id="guardian", cat="prop", title="What does the Evaluation Guardian do?",
         kw=["guardian", "evaluation guardian", "rule watcher", "protect my account", "limits watcher", "stop me breaking rules", "account protection", "news lockout", "trading hours"],
         answer="The Guardian watches every limit on your account (daily loss, drawdown, target, consistency, days, contracts, exposure, news and trading hours) and acts before one is broken. Set your firm's numbers once, then let it be the safety net. It is the single best defence against a careless trade ending an evaluation.",
         links=[("Open the Guardian", "/guardian")], related=["drawdown", "daily_loss", "bots"]),
    dict(id="accounts", cat="prop", title="How do I track my accounts and payouts?",
         kw=["accounts", "my accounts", "payouts", "payout", "payout calendar", "payout planner", "withdraw", "track spending", "money spent", "funded accounts", "attempts", "resets"],
         answer="Accounts holds every evaluation and funded account: status, payouts, the payout calendar and planner, the prop firm recommender, what you have spent and strategy health. After you buy a plan, 'I bought this' in Buy Challenge adds it here as an attempt.",
         links=[("Open Accounts", "/accounts")], related=["buy_challenge", "payouts"]),
    dict(id="payouts", cat="prop", title="How do payouts work?",
         kw=["how do payouts work", "get paid", "first payout", "withdrawal", "profit split", "payout rules", "when do i get paid", "payout schedule"],
         answer="After you pass, the funded account earns profit that you can withdraw after the firm's waiting period and minimum-profit rules, splitting it (often 80% to 90% yours). The exact schedule differs by firm, so read the firm's payout page. The payout planner in Accounts helps you time withdrawals around your drawdown cushion.",
         links=[("Accounts", "/accounts"), ("First Payout Mission", "/mission")], related=["prop_how", "mission"]),
    dict(id="research_integrity", cat="prop", title="What is Research Integrity?",
         kw=["research integrity", "integrity", "false positives", "is the lab honest", "planted edge", "null test"],
         answer="Research Integrity checks the lab itself: does it hand out good-looking strategies when there is nothing to find, and does it find an edge when one is planted? Those checks gate new strategy families, so a green result here means the lab's verdicts are trustworthy.",
         links=[("Open Research Integrity", "/research-integrity")], related=["verdict"]),
    # ------------------------------------------------------------------ setup / settings
    dict(id="settings", cat="setup", title="Where are my settings?",
         kw=["settings", "account settings", "profile", "change password", "profile picture", "avatar", "security", "subscription", "preferences", "personalize", "change theme", "dark mode", "light mode", "theme"],
         answer="Click your avatar (top right) and choose Account settings. Sections: Account mode, Profile, Security (password), Research profile, Personalize (theme and looks), Subscription, Saved runs and account, and App. There is also a dark/light theme toggle at the bottom of the sidebar.",
         links=[("Account settings", "/settings/account")], related=["weekly_digest", "api_keys", "notifications"]),
    dict(id="weekly_digest", cat="setup", title="How does the weekly digest email work?",
         kw=["weekly digest", "digest", "weekly email", "weekly report", "email summary", "newsletter", "unsubscribe", "opt out", "stop emails", "turn off emails", "weekly summary", "sunday email"],
         answer="Every Sunday T58 emails a short, clean summary of your week (strategies, tests, accounts, progress and what to do next) to the address you log in with. It is on by default.\n\n"
                "To opt out or back in: Account settings, Notifications tab, then the Weekly digest switch. There is also a 'Send me a test' button to preview the email right now.\n\n"
                "The app needs to be running on Sunday (or the next time it opens) to send it.",
         links=[("Weekly digest settings", "/settings/account?tab=notifications")], related=["notifications", "settings"]),
    dict(id="notifications", cat="setup", title="How do I manage notifications?",
         kw=["notifications", "alerts", "bell", "notify me", "push", "email alerts", "briefing", "daily briefing", "morning briefing"],
         answer="The bell icon (top right) holds in-app notifications. Notification and briefing preferences live in Account settings, Notifications tab. Choose what you want to hear about and how; the weekly digest has its own on/off switch there.",
         links=[("Notification settings", "/settings/account?tab=notifications")], related=["weekly_digest"]),
    dict(id="api_keys", cat="setup", title="Where do I add API keys and broker connections?",
         kw=["api key", "api keys", "broker", "connect a broker", "alpaca", "data provider", "add key", "integration", "connect account", "broker connection"],
         answer="Open Settings, API Keys. There are sections for trading, data and brokers: paste the key, save, then use Test to confirm it works. Keys are stored on your computer. Start with a paper or demo key before any live one.",
         links=[("API Keys", "/settings/api-keys")], related=["deploy", "settings"]),
    dict(id="license", cat="setup", title="How does my license work?",
         kw=["license", "licence", "license key", "activate", "activation", "master key", "reinstall", "redownload", "reset everything", "fresh start", "new computer", "move to another computer", "subscription key"],
         answer="You log in with the email on your license. If you delete and reinstall the app with the master license key, everything resets cleanly to a fresh start: your previous data is moved to a dated backup folder rather than destroyed, and the Investing portfolio now resets too.\n\nFor a new computer, install, log in with the same email and key.",
         links=[("Account settings", "/settings/account"), ("Help and Support", "/support")], related=["troubleshoot_login", "backup"]),
    dict(id="backup", cat="setup", title="How do I back up or restore my work?",
         kw=["backup", "back up", "restore", "export", "save my work", "move my data", "saved runs", "vault", "cloud backup"],
         answer="Your work lives on your computer. Account settings has a Saved runs and account section for exports. After a master-key fresh start, the previous state is kept in a dated backup folder next to the app data, so you can recover it if you need to.",
         links=[("Account settings", "/settings/account")], related=["license"]),
    dict(id="user_manual", cat="help", title="Is there a manual or support page?",
         kw=["manual", "user manual", "documentation", "docs", "support", "contact support", "help page", "contact", "bug report", "report a problem", "feedback"],
         answer="Yes: the User Manual covers every page in detail, and Help and Support has contact options and common fixes.",
         links=[("User Manual", "/user-manual"), ("Help and Support", "/support")], related=["troubleshoot_login"]),
    # ------------------------------------------------------------------ troubleshooting
    dict(id="slow_backtest", cat="help", title="Why is my test slow or stuck?",
         kw=["backtest stuck", "test stuck", "run stuck", "run slow", "test slow", "slow", "stuck", "frozen", "taking forever", "backtest slow", "not finishing", "hang", "hangs", "never ends", "long time", "progress not moving"],
         answer="Big searches on lots of data take time. Try:\n\n- Check the Runs page: if it shows running, it is working. Leaving the page never stops it.\n- Use a shorter date range or a higher timeframe for a first pass.\n- Reduce parameters or search size in Optimize.\n- Close other heavy apps; runs use your CPU.\n\nIf a run shows failed, open it for the reason shown.",
         links=[("Runs", "/runs")], related=["runs", "no_trades"]),
    dict(id="no_trades", cat="help", title="My backtest shows zero trades or odd results",
         kw=["no trades", "zero trades", "0 trades", "nothing happened", "empty results", "weird results", "results look wrong", "too many trades", "error running", "failed", "error"],
         answer="Check, in order:\n\n- The dataset covers the date range you chose (Data Center coverage view).\n- The timeframe matches the one the strategy expects.\n- Session or time filters are not excluding everything.\n- Entry conditions can actually occur on that instrument (price scale, tick size).\n- Open the run on the Runs page for the exact error message.\n\nIf results look too good, assume a bug (look-ahead, missing costs) before assuming genius.",
         links=[("Data Center", "/data-center"), ("Runs", "/runs")], related=["data_quality", "slow_backtest"]),
    dict(id="troubleshoot_login", cat="help", title="I cannot log in or reach the app",
         kw=["cannot log in", "can't log in", "login", "log in", "forgot password", "reset password", "locked out", "license invalid", "not activating", "can't open", "page will not load", "blank page"],
         answer="- Use the email your license was issued to. Passwords are changed in Account settings, Security.\n- If activation fails, check your internet connection once; the license check needs it occasionally.\n- Refresh the page (Ctrl+F5). If a page is blank after an update, clear the browser cache for this site.\n- On the phone, use Mobile Access to get the current address.\n\nStill stuck? Help and Support has contact options.",
         links=[("Help and Support", "/support"), ("Mobile Access", "/mobile-access")], related=["license", "mobile"]),
    dict(id="dont_know", cat="help", title="What can you help me with?",
         kw=["help", "what can you do", "what can you help with", "what do you know", "commands", "how do i use coach", "coach", "ask you"],
         answer="I can answer questions about the app, trading and strategy development without any AI service, using built-in knowledge:\n\n- Where to find anything and how to set it up.\n- What to do next, based on the page you are on.\n- How to build, test, optimize and validate a strategy.\n- Trading terms and risk concepts.\n- Prop firms, evaluations, payouts, Buy Challenge.\n- Troubleshooting.\n\nTry: 'How do I optimize without overfitting?' or 'Where do I import data?'",
         related=["next_step", "sidebar", "glossary_hub"]),
]

# What each page is, and the sensible next action there. Keys are URL paths (longest prefix wins).
PAGES = {
    "/dashboard": ("Dashboard", "your status at a glance: mission progress, recent runs, bots and quick links.", "Open the First Payout Mission and do the step it names, or start a Test if you have not yet."),
    "/start-here/create": ("Create", "where strategies begin: templates, generators or your own code.", "Save one simple strategy, then open Test."),
    "/full-pipeline": ("Test", "the full check that ends in a verdict on the evidence ladder.", "Pick a strategy, data and firm and press start. Read the verdict reasons when it finishes."),
    "/optimize-simple": ("Optimize", "tries variations of a strategy and keeps the best.", "Choose what to improve, run it, then go straight to Validate."),
    "/validate-simple": ("Validate", "stress tests only; nothing is tuned.", "Tick the checks, run them, then promote on the Champion board."),
    "/champion-simple": ("Champion board", "ranks strategies by how far they have earned their way up.", "Pick one, read what it still needs, then promote or go fix it."),
    "/forward-test": ("Deploy", "demo account, forward test, then live.", "Start on the demo account and let it run long enough to see a losing streak."),
    "/library/research": ("Research", "the Agent Desk and Research Ledger together.", "Switch between Desk and Ledger at the top; use the Desk to start a scouting run."),
    "/library": ("Strategy Library", "every strategy plus the Trading Bots section.", "Open a strategy to run it, or configure a bot from the Trading Bots section."),
    "/graveyard": ("Graveyard", "rejected strategies and why.", "Read the reasons to avoid rebuilding the same idea."),
    "/quant-lab": ("Quant Lab", "advanced research tools.", "Pick a tool for the doubt you have (overfitting, regimes, robustness)."),
    "/investing": ("Investing", "paper-money portfolio and stock, index and crypto research.", "Search an asset, read the filings, place a paper trade."),
    "/mission": ("First Payout Mission", "the seven-step path to a payout.", "Do the one step highlighted at the top."),
    "/guardian": ("Evaluation Guardian", "watches your account limits.", "Enter your firm's limits so it can protect you."),
    "/research-integrity": ("Research Integrity", "checks that the lab itself is honest.", "Just read it; green is good."),
    "/accounts": ("Accounts", "evaluations, funded accounts, payouts and spending.", "Add the account you hold, or check the payout planner."),
    "/buy-challenge": ("Buy Challenge", "firms first, then plans, with a side-by-side comparison.", "Pick a firm, tick 2 to 4 plans to compare, then buy at the firm."),
    "/data-center": ("Data Center", "datasets, coverage and imports.", "Check coverage for your instrument, or import a file."),
    "/education": ("University", "lessons on strategy, testing, risk and prop firms.", "Pick the lesson that matches your next step."),
    "/playground": ("Playground", "games and toys for a break.", "Pick anything and relax for five minutes."),
    "/journal": ("Trading Journal", "log and review real trades.", "Log your last trade with its tags."),
    "/runs": ("Runs", "every running and finished job.", "Open the latest run or compare two."),
    "/settings/account": ("Account settings", "profile, security, theme, weekly digest.", "Check that your weekly digest is the way you want it."),
    "/trading-bots": ("Trading Bots", "three bots tuned to different goals.", "Open a bot, review its plain-English status, configure it."),
    "/mobile-access": ("Mobile Access", "open the app on your phone.", "Scan the code."),
    "/events": ("Global Events", "scheduled market-moving events.", "Check today's high-impact events before trading."),
}

GREETINGS = ("hi", "hello", "hey", "yo", "good morning", "good afternoon", "good evening", "howdy", "sup")
THANKS = ("thanks", "thank you", "thx", "ty", "cheers", "appreciate")
