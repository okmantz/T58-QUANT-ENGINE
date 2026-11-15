# Engines

The discovery engine and the global-events layer. Data coverage lives in `DATA_COVERAGE.md` because `app/data/data_manifest.py` parses it.

---

## Discovery engine


Search Lab, Evolution Lab, Forge (the deep gauntlet preset), Speed Run and the hypothesis layer are ONE engine with presets (the Create page now exposes only the engine; the classic pages remain under "More tools") (`app/discovery_engine`).
One objective (`edge_lb_r`), one entry floor (100+ trades, mean-R t >= 1, cost < 0.15R), one lifetime trial ledger clustered to
effective trials, one sealed slice read once, one promotion sequence:
reproduction -> sequence-deflated Sharpe -> random-timing null gate -> pooled cross-market edge -> sealed slice.
A passing champion is a forward-test candidate, never a "winner".

## Run
    python -m scripts.bootstrap_data                      # which pooled markets do you actually have? (needs >= 8)
    python -m scripts.run_surrogate_study --null-runs 60  # false-discovery rate on no-edge data + power on planted +0.10..0.30R edges
    python -m scripts.run_discovery_engine --preset search_lab --data data/raw/NQ_5m.csv --symbol NQ --pool ES=... --retest
    python -m scripts.run_preregistered_families NQ=... ES=... --v13-batch=1

The 100 report indicators are in `app/strategy/indicators_v13*.py`; the 100 families (92 runnable, 8 blocked with reasons) in
`app/search/families_v13.py`, pre-registered with kill conditions in `app/discovery/hypothesis.py`.
New family batches stay CLOSED until `reports/surrogate_gate.json` (written by the surrogate study, valid 90 days, bound to the
current engine code) shows < 5% false discoveries over >= 60 null runs and >= 50% power on +0.20/+0.30R plants measured on >= 10 runs per planted-edge size.
Requires `numba` for speed (pure-Python fallback is ~100x slower for the HMM/analog indicators).

## Known limits
- Surrogate FDR on your real data has not been measured; the shipped gate is closed.
- Ext feeds (VIX term, COT, skew, ...) need your CSV drop-ins; those families are `needs_data`.
- Pooled test needs >= 8 markets and fails closed with fewer.
- Blocked families: 6, 95 (scale-in), 18 (calendar spread), 39 (closing imbalance), 45 (roll calendar), 56, 57, 59 (tick/book).
- No Johansen test (PC-spread + AR(1) gate instead); family 29 uses OLS lines, not Theil-Sen.

## Fast Lab v2 (the default method)

- **Budgets:** Quick 5,200 / Standard 10,400 / Deep 15,600 evaluated configurations (shown in the app as 5,000+ / 10,000+ / 15,000+). Every configuration is optimized the same way (random search, evolution, local refinement) and the count of distinct signal sets tried feeds the luck bar below. Known-dead neighbourhoods from the Strategy Graveyard are skipped, not re-tested.
- **Search:** 30 strategy families (trend, reversion, breakout, session, momentum, plus an any-indicator family that turns about 300 indicators into trend, revert or slope rules), each with optional side / trend / hours / volatility filters, stop, target and hold-time variants. Random search, then evolution, then local refinement - all scored on the training slice only.
- **Splits:** train 60% / validate 20% / sealed test 20%, then neighbour robustness and a 2x-cost stress test. Confidence labels deflate by the number of distinct ideas tried.
- **No leaks:** the average-daily-range indicator now uses only completed days (a lookahead was fixed), and a test (`tests/backtest/test_prefix_invariance_all_kinds.py`) checks that every indicator kind gives the same value on a bar with or without later bars. Saved strategies are causal (the position is carried bar by bar; an unresolved trade stays open at the end of data). Every finalist is re-run in the real backtester, including the same lookahead test Full Pipeline uses, before it can be called a winner.
- **Full history:** the Lab uses all loaded bars (resampled to the bar sizes where costs are small versus risk) instead of a 400k-bar tail.
- A winner is still a lead: run it through Full Pipeline and Validate.

---

## Global events


Sidebar page (`/events/`) directly under **AI Assistant**: a cache-first world-events monitor.

- **Architecture:** a background poller (started lazily on first page visit; sleeps after ~20 min unseen; never started under pytest or when `T58_GLOBAL_EVENTS_POLLER=0`) fetches RSS/GDELT-style feeds, USGS, NASA EONET, GDACS, Stooq quotes and the economic calendar, classifies headlines, and writes to SQLite (WAL). Every HTTP endpoint is a read-only query of that cache, so page loads never wait on the network.
- **Endpoints:** `/events/api/bootstrap` (ETag), `headlines`, `events`, `geo`, `health`, `intel` (ETag; market intelligence below), `POST refresh` (rate-limited), `POST brief`, `snapshot`.
- **Map:** offline canvas using Natural Earth land (public domain, `static/global-events/land.json`); cached land layer, rAF-coalesced redraws, DPR-aware.
- **X (Twitter) section:** add usernames in the page; the latest posts for each are fetched with the Bearer token saved under API Keys → X (`app/global_events/x_feed.py`, endpoints `/events/api/x`, `/events/api/x/accounts`, `/events/api/x/accounts/remove`). Reading posts needs a paid X API plan; with no/invalid token the section shows a message and the rest of the page is unaffected. Posts are cached and rate-limited; rendered via `textContent`.
- **Safety:** all DOM written via `textContent` (no `innerHTML`); feed failures never raise.
- **Config:** `T58_GLOBAL_EVENTS_DB` overrides the DB path (default `data/global_events/global_events.db`).
- **Theater Heat** shows "calibrating" until ~4 days of history exist.
- **Caveats:** feed URLs are catalogued in `app/global_events/sources.py` and should be checked against provider terms before commercial distribution (notably Stooq quotes).

## Market intelligence (`/events/api/intel`, `app/global_events/intel.py`)

Computed locally from stored **daily bars** (Stooq CSV, fetched by the poller every 6 hours into `ge_daily`, up to 400 sessions per symbol), the economic calendar and the
theater scores. Nothing is a prediction or a signal, and every label is printed with the rule and numbers that produced it.

| Panel | What it is |
|---|---|
| Market Regime Intelligence | Per instrument (ES, NQ, YM, RTY, GC, CL, DXY). Priority order: **Event-driven** (a high-impact release for that instrument within the next 24 h or the last 3 h) > **High-vol** (20-day realised vol at or above the 80th percentile of its own past year) > **Trending up/down** (Kaufman efficiency ratio over 20 days >= 0.35) > **Range-bound** (efficiency ratio <= 0.20 and vol percentile <= 60) > **Mixed**. Fewer than 25 bars: Unknown. Thresholds live in `intel.RULES`. |
| Calendar and releases | CPI, PPI, jobs, GDP, PCE, retail sales, ISM and central-bank events from the live calendar feed (current week), grouped Inflation / Jobs / Growth / Central banks. |
| Central banks | Next decision date for the Fed, ECB, BoE and BoJ from each bank's published 2026 schedule (`intel.CENTRAL_BANKS`) with a link to the bank's page; a live-calendar match adds forecast and previous. The list ends in December 2026 and must be extended from the banks' pages. |
| Sessions | Tokyo, London, New York cash and CME Globex, in each market's own time zone (DST-correct; needs the `tzdata` package on Windows). |
| Futures stats | Last, 1/5/20-day change, position in the 20-day range, 20-day realised vol, ATR14 as % of price. |
| Volatility regime | VIX bucket (calm < 15, normal 15-20, elevated 20-30, stress 30+), VIX year percentile, ES realised vol and the implied-minus-realised gap. |
| Cross-asset monitor | 1/5/20-day moves, a 1-day z-score against the last 60 days (>= 2 flagged), and a Risk-on / Risk-off tone: one point each over 5 days for S&P up, Nasdaq up, Russell up, VIX down, Dollar down; +3 or more Risk-on, -3 or less Risk-off. |
| Correlations | Pearson correlation of daily log returns over the last 60 sessions (blank below 30 shared days). |
| Geopolitics | The five hottest theaters, the instruments they touch and their lead headline. |

Until the first daily fetch completes the panels say so instead of showing blanks. Stooq terms apply (see Caveats).
