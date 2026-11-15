# T58 Strategy Discovery — November 2026

Three executable strategies, all loading and running in the T58 engine, with Objective A (evaluation) and Objective B (funded) account configurations.
Status of every strategy: **forward-test candidate**. None is deployment-approved, and the sealed-window read below is the reason.

## 1. Result in one table

| # | Strategy (file in `strategies/python/`) | Mandate | Trades/mo | Dev 2020–Aug 2025: mean R, win, PF | Every year positive? | Sealed Sep 2025+: mean R (n) | T58 ladder |
|---|---|---|---|---|---|---|---|
| 01 | NQ Open-Drive Continuation 5m | Trend continuation (intraday momentum) | ~16 | +0.158 R, 48.8%, 1.35 | 6/6 | +0.018 R (102) | LEAD, EV = FORWARD-TEST CANDIDATE |
| 02 | NQ Liquidity Sweep Reclaim 5m | Liquidity failure / reversal | ~16 | +0.107 R, 32.8%, 1.16 | 6/6 | −0.024 R (90) | REJECT (EV test) |
| 04 | ES Compression ORB 5m | Volatility expansion / breakout | ~6 | +0.154 R, 47.6%, 1.33 | 6/6 | +0.167 R (53) | REJECT (EV test) |

Costs: engine default policy (1 tick slippage per side + commission). Edges hold at 2× costs (+0.150, +0.093, +0.112 R in dev).

**Not delivered, on purpose** — no defensible edge was found for these, so no strategy was fabricated:
- 03 Mean reversion / VWAP: VWAP-deviation fades, stretch fades, failed-opening-range fades and gap fades were all negative or noise on ES, NQ and GC (≈190 configs). On these markets momentum dominates.
- 05 Market-specific edge: NQ is the only market where own-drive momentum works (ES and GC own-drive fail or are fragile). That finding is Strategy 01 itself. GC produced nothing stable.
- 06 Unrestricted discovery: (a) ML trade selection (gradient boosting, walk-forward by year) showed no reliable lift — correlation with realised R ≈ 0.05, sign flips year to year (NQ Open-Drive filtered was *worse* in 2025); not adopted. (b) Cross-market lead-lag: ES traded in the direction of NQ's opening drive gives +0.09/+0.17 R, but it is the same bet as Strategy 01 (highly correlated), so it is not counted as a separate strategy.
- EURUSD and BTC: no data in the bundle (ES, NQ, GC only), so those mandates could not be tested.

## 2. What the evidence supports, honestly

- **NQ Open-Drive Continuation** is the only candidate that survives a multiple-testing correction in development: day-clustered t = 4.1 vs ≈3.4 expected for the best of ~1,600 noise trials; 100% of 36 neighbouring parameter sets are positive (median +0.09 R). In the 6-month sealed NQ window it was flat (+0.018 R; the 5% lower bound is −0.15 R). That is consistent with both "edge decayed" and "6 months of noise" — it cannot tell them apart.
- **NQ Sweep Reclaim** (t = 2.1) and **ES Compression ORB** (t = 2.4) do not clear the correction. Their neighbourhoods are positive (100% and 85%) but the headline numbers are selection-inflated. Treat as hypotheses.
- Selection history: ≈1,600 configurations were examined (scan1 444, scan2 828, scan3 147, cross-market 24, plateau 135). Discovery used 2020–2023, validation 2024–Aug 2025, and the sealed window (Sep 2025+) was read **once**, after parameters were frozen. Nothing was re-tuned after seeing it. The repo notes earlier experiments already read that window, so it is not a certified-clean holdout.
- A causality bug was caught by T58's own Full Pipeline lookahead gate (ES ORB was rejected by it) and fixed: session-completeness filtering and loop bounds let a signal depend on how many bars its day would end up with. The harness numbers did not change with the fix; the three files now pass the engine lookahead check and all Full Pipeline results here are from the fixed files.

## 3. Account configurations (`deploy/strategy_discovery_2026_11/*.json`)

Account rules: repo preset `lucid_50k` (target $3,000; EOD trailing max loss $2,000 locking at $50,100; $1,200 daily soft limit; 40 micros; flat by 15:45 CT). Secondary-source verified — **re-check lucidtrading.com and get written confirmation that automation is allowed before paying**.

Sizing rule: risk per trade = clip(frac × cushion, lo, hi) where cushion = balance − current trailing floor; contracts = round(risk ÷ stop$ per micro), at least 1; skip a trade whose single micro risks more than 1.7× the budget. This makes size shrink as the account nears the floor and grow with a profit cushion. T58 strategy files cannot see account state, so apply it in the order-routing layer or by hand from the table.

**Objective A — evaluation** (all three strategies, frac 0.14, $100–$400):

| Replay | Pass ≤ 21 days | ≤ 42 days | ≤ 63 days | Breach | Median days to pass |
|---|---|---|---|---|---|
| Dev 2020–Aug 2025 (optimistic: selected on it) | 26% | 41% | 53% | 30% | 23 |
| Full 2020–2026 | 24% | 37% | 48% | 29% | 22 |
| Sealed window only (~97 overlapping starts) | 6% | 9% | 9% | 28% | 14 |

T58's own Monte Carlo for NQ Open-Drive alone at $400 planned risk: 55% pass, 30% pass-and-paid, 52% 90-day ruin.

**Objective B — funded** (payout terms in the simulation are the repo's *unsourced* assumptions — replace with Lucid's real ones):

| Config | Strategies | Sizing | 90-day survival | P(≥1 payout in 90d) | Expected withdrawals per account per 90d | Sealed-window 60d withdrawals |
|---|---|---|---|---|---|---|
| B1 conservative | Open-Drive + ORB | 0.08, $80–$200, $1,000 buffer | 100% | 52% | ≈$650 | ≈$55 |
| B2 more payouts | all three | 0.06, $60–$150, $1,000 buffer | 94% | 64% | ≈$940 | ≈$150 |

**Income reality check:** at this edge size a single $50K account yields roughly $200–$300 a month in the development replay and less in the sealed window. $5K/month needs on the order of 15–20 such accounts, each with its own fees and its own failure risk, or a strategy with several times the edge. These strategies do not get there alone.

## 4. Gate calibration (`config/gate_profile_pragmatic.json`)

Thresholds relaxed (no code changed — all are `FullPipelineConfig` fields): `risk_of_ruin_cap` 20→50, `min_per_attempt_pass_pct` 70→35, `min_per_attempt_paid_pct` 35→15, `funded_breach_cap_pct` 35→50; also `skip_optimization` on (lock parameters), adaptive-risk throttle off (the cushion rule replaces it), and for the NQ Sweep run only `preflight_enforce` off (preflight sized the full-size NQ contract and flagged 29% of signals; a direct micro-contract run skipped 0.3%).

Left alone on purpose: lookahead gate, data/sealed-slice ledger, EV-after-fee test, 300-trade floor, edge lower bound, 2× cost retention, random-entry null, deflated Sharpe. Relaxing thresholds did not turn any LEAD or REJECT into READY: what binds is the EV test and the edge lower bound, which are evidence, not strictness. ES ORB's verdict reasons were: edge lower bound −0.024 R on 206 out-of-sample trades, deflated Sharpe 0.65, per-attempt pass lower bound 29.7%. Under T58's default $400-planned sizing the engine caps position size on ~97% of trades, which makes ORB/Sweep reach the target slowly and drives the EV test negative; the cushion sizing above is what lifts them in my replay.

## 5. Forward-test plan (proposed, not yet run)

1. Run all three on a demo/sim account through the T58 webhook relay for 8–12 weeks (≈40–60 trades on NQ Open-Drive).
2. Continue if the combined R is ≥ 0 with at least 30 trades per NQ strategy; stop and re-open research if the combined drawdown exceeds 10 R.
3. Only then buy one evaluation at the Objective A config. If a strategy's rolling 60-trade mean R falls below −0.05, switch it off.

## 6. Limitations

- Own simulator (`research/.../prop.py`, `prop2.py`) for the account replays; intraday floating risk uses each trade's worst excursion and ignores partial overlaps between concurrent legs. T58's PropAccount was used only through the Full Pipeline runs, not for the cushion-sizing replays.
- ES/NQ/GC 1-minute data from the bundle, roll-adjusted with the repo's own back-adjustment; ~55 roll events detected on ES vs ~27 expected, so some adjustments may be false positives. Gap-based features were avoided for that reason.
- NQ data ends March 2026, so the NQ sealed window is ~6 months.
- No Pine/MQL5 export was produced or parity-tested.
- Prop-firm rules and payout terms are assumptions; real fees, payout cycles and consistency rules decide the economics.

## 7. Reproduce

`research/strategy_discovery_2026_11/`: `prep.py` (5m bars), `h.py`/`fam.py` (harness and event generators), `scan*.py` (trial grids), `cands.py` (frozen candidates), `prop.py`/`prop2.py` (account replays), `t58run.py` and `fp.py` (T58 engine and Full Pipeline runs), `results/` (all scan outputs), `t58_pipeline_reports/` (Full Pipeline JSON/HTML).
