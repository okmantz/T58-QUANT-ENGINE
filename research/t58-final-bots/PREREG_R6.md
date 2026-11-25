# Round 6 pre-registration (written 2026-11-25 ~04:00Z, before any round-6 bot or filter score was looked at)

Owen's round-6 asks (2026-11-25 03:27Z): explore GEX, news filters, VIX level, overnight gap size, market internals (TICK), volume profile /
footprint; score on Lucid Pro 50K and Pro 100K; add the CL and NG 1m data he attached as legs; no sim account yet; the repo's two bots
(= the round-4 picks, checked against origin/main 1f761d7) are the starting point. Rules unchanged and never relaxed: cost model,
lookahead protection, sealed holdout touched once per finalist, finalist must beat baseline on every metric or the shortfall is reported.

Disclosure on order: the energy leg screen (code/screen_r6.py -> strategy_ledger_r6.csv) was launched a few minutes before this file was
written. It uses the round-1 leg admission rule unchanged (legs.py docstring) and its results were not opened before this file was saved.

## 1. Data and splits
- ES / NQ / GC 2016-11-24 .. 2026-11-20: every day already read in rounds 1-5. Every ES/NQ/GC number in round 6 is IN-SAMPLE.
- CL / NG (Owen's parquet, 1m, unadjusted front month): research 2021-01-04 .. 2024-07-15, validation 2024-07-16 .. 2026-01-04,
  H6 2026-01-05 .. 2026-11-23 SEALED (data_r6/SEAL.sha256, data_r6/seal_info.json; only the time column was read to cut it).
- Energy session mats: 18:00 ET session days like the other markets; day session 09:00 ET sits at mat column 930; flat 16:15 ET (30 min
  before Lucid's 16:45, conservative). Sessions that open on a roll (18:00 open vs prior close jump > 4x its 60-session median, > 1%,
  15th of the month or later) take no family trades: prior-day levels there belong to another contract. F9 gap is not screened on CL/NG,
  and trend-only variants not on NG (they read prior closes across rolls).
- Bot windows: W1 = 2021-01-04 .. 2024-07-16, W2 = 2024-07-16 .. 2026-01-05 (every market present, nothing sealed), H6 =
  2026-01-05 .. 2026-11-21. The round-5 windows (h3, research 2020-23, validation 2024-01 .. 2026-11-20) are reported for bots with no
  energy legs, for continuity.

## 2. Costs [ASM where marked]
Unchanged for ES/NQ/GC. MCL / MNG: commission base $1.62 a round trip [fee report], stress $2.14 (= base x 1.32, the ES/NQ stress ratio,
above CME's $1.72 after Oct 1 2026); slippage 1 tick a side base, 1.5 ticks stress ($1 a tick on both micros). Lucid allowing energy
products is [ASM] (not on the Lucid pages read 2026-11-23). Decisions are made at stress cost; base cost is reported.

## 3. Plans
- Pro 50K: as rounds 1-5 (fee $172, reset $120).
- Pro 100K: target $6,000, MLL $3,000, DLL $1,800 (soft), cap 60 micros, payout goal $750, payout caps $2,500 / $3,000, buffer $103,100,
  split 90/10 [Lucid pages 2026-11-23]; fee $268 and reset $188 [ASM: 100K price not verified; straight line between the verified
  50K $172 / $120 and 150K $365 / $255].
- Our bots on Pro 100K: every dollar knob of the policy x 1.5 (= 3,000 / 2,000 MLL); no other change. Baselines on Pro 100K: the repo
  governor with AccountRulesLite set to the 100K numbers above.
- Owen now names Pro 50K / 100K, so BOT-B is scored on Pro (round 1-5 scored it on Flex 50K; Flex numbers are reported for continuity).

## 4. New inputs (all causal: known before the session's first entry; prior-day values unless stated)
| input | source | definition |
|---|---|---|
| VIX level | TradingView CBOE:VIX daily | prior close; expanding percentile (>= 250 prior days) |
| VIX term | VIX / VIX3M daily | prior-close ratio (> 1 = backwardation) |
| VIX change | VIX daily | prior close / close 5 sessions earlier |
| NYSE TICK | TradingView USI:TICK daily | prior session close and high-low range |
| FOMC | TradingView calendar, 79 decisions 2016-2026 | decision day flag; block entries from 13:30 ET on decision days |
| NFP | rule: first Friday of the month [ASM: approximation, misses the few shifted releases] | day flag |
| overnight gap | 1m data | (09:30 open - prior RTH close) / ATR14; energies: 09:00 open - prior 14:30 close, roll sessions excluded |
| overnight range | 1m data | (18:00 .. 09:29 high-low) / ATR14, known at 09:30 (09:00 energies) |
| volume profile | 1m data | prior RTH session POC and 70% value area from 1m volume at bar closes; today's open inside / above / below it |
Unavailable (said so, carried on): GEX history (no free history found; SqueezeMetrics files not reachable), intraday TICK (TradingView
keeps about 6 months of 5m bars, too short), footprint / bid-ask volume (no tick or order-flow data). CPI calendar not pulled
(TradingView quota hit); skipped unless the quota frees before the search starts.

## 5. Filter admission (per leg, decided before bot search)
For each leg of the round-4 bots and each admitted energy leg: thresholds = terciles of the input over that leg's research trades only
(ES/NQ/GC: 2020-2023; energies: W1). A filter "skip the low (or high) tercile" (or "skip FOMC after 13:30", "skip NFP day") is admitted
only if the removed trades' mean net R at stress is below the leg's own mean in EVERY period: ES/NQ/GC h3, research, validation;
energies research and validation. Every tried (leg, input, side) is a counted trial (research/filter_trials_r6.csv).

## 6. Energy legs
Admission: round-1 rule: positive at stress in research (HAC t >= 1.5) and in validation (t >= 1), favouring plateaus (a one-step
neighbour also passes). At most 3 legs per instrument enter the bot search.

## 7. Search and pick rule
Start from the round-4 picks. Moves: add admitted energy legs at weight 0.25 / 0.5 / 1; add admitted filters; max_open +1 if energy
legs are added. Budget <= 1,500 configs per bot, every config logged. Scored at stress on W1 and W2, Pro 50K and Pro 100K (4 cells).
- Bars (unchanged): BOT-A = PREREG_R4 bar vs baseline_A in the same cell; BOT-B = beat or tie baseline_B on every metric including the
  sustained block, same cell.
- A round-6 candidate replaces the round-4 bot only if (a) it has fewer shortfall cells vs baseline than the round-4 bot over the 4 cells,
  (b) its primary metrics (A: p_pass, ev; B: f90_paid, p_payout, ev) are at least the round-4 bot's in at least 3 of the 4 cells,
  (c) picking on W1 alone would have picked it or a config within one shortfall cell of it on W2 (rotation), and (d) at least half of
  its one-step neighbours are within one shortfall cell (plateau). Fail any -> round-4 bot stays and the candidate is documented.
- Plan choice per bot: the plan with the higher stress ev in both W1 and W2; if they split, Pro 50K (cheaper fee).

## 8. H6 read
After research/FROZEN_PICKS_R6.md is written and hashed: one read of H6 per finalist and per baseline (stress and base). The ES/NQ/GC
part of H6 is in-sample; only the CL/NG trades are clean. Also reported once: each admitted energy leg's own H6 net R (one micro),
which is the clean test of whether the energy edge held. No change after the read.

## Addendum 1 (2026-11-25 ~04:10Z, after the screen result: 0 of 1,134 energy variants pass; best research t 0.73 at stress)
One energy-specific family is added before anything else is looked at, because the generic families are equity-session designs:
report breakout = opening range of the k minutes after 10:30 ET on the weekly inventory day (CL: Wednesday EIA petroleum; NG: Thursday EIA
storage; holiday-shifted weeks are not corrected [ASM]), entry on the first close beyond it within ``cut`` minutes, stop opp / mid,
target R. Grid: k in (5, 15), stop in (opp, mid), R in (1.5, 2, 3, none), cut in (60, 180): 32 per market. Same admission rule. If none
passes, round 6 has no energy legs and H6 stays sealed except for the reads in section 8 that still apply (none for energy legs).

## Addendum 2 (2026-11-25 ~04:45Z, after scoring only the baselines and the round-4 picks on Pro 50K / 100K, research/r6_base_s2.csv)
Seen: BOT-B-R4 (a Flex design: $300 risk, Flex day caps) barely passes a Pro evaluation (p_pass .03 / .12 on Pro 50K W1 / W2), and on
Pro 100K the x1.5 knob scaling leaves BOT-A-R4's ev negative. So, before any search score:
- BOT-B on Pro is searched as a Pro design: leg mixes from the round-4 A and B legs, Pro-style eval knobs (r_eval 600 / 800 / 1000,
  cons_k 0.55, cush_a 0.5, prog_b -0.3, as BOT-A-R4) x funded knobs (r_fund 250 / 300 / 400, fund_day_cap 400 / 500 / 700,
  fund_day_stop 300 / 400 / 600, fund_f_cush 0.2 / 0.3 / 0.4) x max_open 2 / 3 / 4, plus admitted filters. Same B bar vs baseline_B on
  the same Pro plan and window. Flex 50K numbers stay in the report for continuity.
- Pro 100K dollar-knob multiplier is a searched knob in (1.5, 1.75, 2.0) for both bots (still capped by the 60-micro size cap and every
  firm rule); the pick rule in section 7 is unchanged.
