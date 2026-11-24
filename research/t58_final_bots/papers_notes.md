# Research papers: what each one gives the search (round 2)

Source: RESEARCH PAPERS folder in Drive (unzipped by Owen, Nov 23). Read with the Drive connector, read-only.
Batch 1 of 4 (validation and optimal trading rules) is below. Claims are the papers' own; where a paper is
single-author, unreviewed or internally inconsistent it is noted, and its numbers are treated as hypotheses.

## Batch 1: validation, overfitting, optimal trading rules, MNQ-specific

| Paper | Usable for us | How we use it |
|---|---|---|
| Carr & Lopez de Prado, Optimal Trading Rules | Exit calibration without backtest grid search: fit AR(1)/OU to trade P&L paths, simulate, pick target/stop by Sharpe. Short half-life + no drift: small target, wide stop. Positive drift: target 3-6 sigma, stop 4-10 sigma. No clear optimum region means a random walk and any backtest-chosen exit is overfit. | Hypothesis H-OTR: re-derive each leg's target/stop from its own research-split trade paths (no validation data), capped by the day stop. Test as a new variant per leg. |
| Mroziewicz & Slepaczuk, walk-forward double OOS | Smoothed ("robust") Sharpe = 0.5 cell + 0.5 mean of neighbours; walk-forward window lengths as parameters; holdout once. 1-10 min EMA rules all negative after costs. | Already use plateau checks; adopt neighbour-smoothed scoring for the bot-level grid. Confirms: skip fast crossover families. |
| Mesfin, Structural limits of OHLCV signals in MNQ (5-min, 2021-25) | 14 families fail after 2 pt round-trip cost; ORB long held 15 bars T=1.5; Asia expansion bars reverse; holds of 12-15 bars beat 1-6 bars. Gate: OOS T>=2, >=30 trades, same sign every year, permutation p<.05. Single author, unreviewed. | Our cost (MNQ $1 + 1 tick a side = 1.5 pt round trip at stress ~1.9 pt) is in line. Add "same sign every year" as a reported check on finalist legs. Confirms our survivors are rare. |
| Bailey et al., PBO (CSCV) | S=16 blocks, 12,870 splits, PBO = share with logit<=0; reject PBO > .05. | Already in factory (PBO via CSCV); keep S=16. |
| Bailey & Lopez de Prado, DSR | SR0 formula with N effective trials; DSR > .95; log every trial. | Already in factory; N counts every ledger trial (1,825+). |
| Mesfin, VVG classifier (MNQ) | VVG day = |r(09:30->09:55)|, |gap|, first-5-min volume z all above expanding 66.7th pct (prior days only); fires ~4.4% of days; 78% of VVG days give back from the intraday peak; no directional rule passed. Paper's day counts are inconsistent. | Hypothesis H-VVG: use VVG as a block filter (no new entries after 10:00 on VVG days) on both bots; aimed at A's worst day and B's max DD. |
| Wijesinghe, simple rules vs costs | Intraday SPY ORB and RSI(2) fail after costs; only daily Donchian 20 + 50/200 filter survives. | Hypothesis H-TREND: daily Donchian-20/50-200 state as a direction filter for intraday legs. |
| Bailey et al., Backtest overfitting | MinBTL: few variations per year of data; holdout alone does not cure overfitting. | Disclosure: the holdout window is reused in round 2; report that plainly. |

Pending: batch 2 (momentum and mean reversion), batch 3 (ML, RL, gold), batch 4 (prop economics, Kelly, order flow).

## Batch 4: prop economics, Kelly, order flow

| Paper | Usable for us | How we use it |
|---|---|---|
| Lim (2026), Price of a Funded Account (actuarial) | Closed form P(+a before -b) = (1-e^(theta b))/(e^(-theta a)-e^(theta b)), theta = 2mu/sigma^2; zero edge gives b/(a+b). Time limit costs more pass probability than the daily rule. Interior optimum daily sigma near b/5; below it accounts time out, above it they breach. Costs drag Sharpe by k*sqrt(252). Static barriers only; trailing floor and consistency not modelled. | Hypothesis H-SIG: for LucidPro, b=$2,000 gives target daily sigma about $400 (b/5) to $600 (time-scaled). Measure BOT-A's daily P&L sigma during evals and test r_eval values that put it in $300-700/day. Our firm.py simulator already handles the trailing floor and consistency, so it, not the closed form, scores the grid. |
| Levine, Day Trading Adapting to Change | Student paper-trading project: ES 08:00-08:15 range, breakout before 09:30, enter on pullback to range mid; $300 max risk; stop to breakeven past halfway to target. No costs, no trade counts. | Hypothesis H-PREORB: pre-RTH 08:00-08:15 ES/NQ range breakout with mid-range pullback entry, 08:15-09:30 window. Weak evidence; one family, small grid. |
| Rotando & Thorp (1992), Kelly (papers 3 and 4 are the same article) | f* = (bp-q)/b; ruin above roughly 2 f*. Kelly maximises log growth with no floor. | Use Kelly only as an upper cap on per-trade risk (check that r_eval stays well under f* times cushion). Not the objective: the barrier model is. |
| Gerig thesis; Berger et al. (EBS); Evans & Lyons | Order-flow results need exchange-signed trades; the link to price is contemporaneous; at 1 minute, flow predicts flow for a few minutes, not returns. | No OHLCV proxy from these papers. A close-location-value volume proxy may be tried as a filter only; low prior. |

## Batch 2: momentum, trend following, mean reversion

| Paper | Usable for us | How we use it |
|---|---|---|
| Urquhart & Zhang, momentum and reversal in commodity futures | Momentum works, reversal never did (0 of 189 windows); edge weaker since 1998. | Don't fade multi-month GC trends. |
| Baltas & Kosowski, futures momentum and CTAs | Position = sign(past return) x target / sigma(60-day Yang-Zhang). 1-day/1-day continuation died after 1995. | Hypothesis H-VOLSZ: scale per-trade risk by 1/sigma60 relative to its median (bounded 0.5-1.5x). |
| Clare et al., trend following and risk parity | Long only above 7-12 month MA halves vol, cuts max DD to a third. Survives costs. | Hypothesis H-TREND: intraday longs only when close > 7-month (147-session) SMA; shorts only below. Aimed at max DD and PF. |
| Daniel & Moskowitz, Momentum crashes | Trend bets crash in rebounds when 24-month return < 0 and 126-day vol is high. | Hypothesis H-CRASH: halve risk when 24-month return < 0 and 126-day realized vol is above its median. |
| Hurst, Ooi & Pedersen, Century of trend following | 12-month signal most robust; 1-month dead after 2010. | Use 12-month return sign (252 sessions) as an alternative trend filter in H-TREND. |
| Jashnani, Bollinger mean reversion (stocks, daily) | BB 20/2 fade with OU screen; screen worsened risk metrics; gross of costs. | Low prior; not added. |
| Long & Bhattacharyya, QuantConnect mean reversion (ES 1-min) | MACD-fade on ES 1-min, 2023 only, in-sample, tolerance looks overfit. | Low prior; not added. |
| Babayev et al., mean reversion and black swans | Per-stock optimised, no split, no costs; code actually trades breakouts. | Not added. |
| Arda, breakout vs mean reversion (BTC 1-min) | Both lose on 1-5 min after fees; breakout more robust in bear/choppy; pullback only in strong bull. | Supports trend-gated pullbacks (VWPB already does this). |

## Batch 3: machine learning, RL, gold

| Paper | Usable for us | How we use it |
|---|---|---|
| Huber, MaxAI RL+GA (NQ 1-min) | Chaikin Money Flow(20) on 1-min, long >= +0.25, short <= -0.25, next-bar fill, $900/$1,500 stop/target per NQ (45/75 pts), RTH, flat by close. PF 1.07 over 4,014 trades after costs, test overlaps training. | Hypothesis H-CMF: family fam_cmf on NQ/ES/GC, stop:target 0.6:1 in ATR terms, first signal after 10:00, one trade a day. Low prior (PF 1.07). |
| Waldow et al., ML in futures (60 futures) | Short-term (1-5 day) reversal drives the edge; signal on 09:30-10:30 VWAP, entry 10:31-11:31. | Hypothesis H-REV: fade the prior day's RTH return after 10:30 when the first hour agrees with the fade. |
| Zhang, Zohren & Roberts, DRL for trading (daily futures) | Vol targeting with 60-day EWMA sigma; on equity indices long-only beat both DQN and TSMOM. | Supports H-VOLSZ and a long bias filter on ES/NQ. |
| Hirsa et al., DRL multi-asset (ES daily) | Real-data DQN lost to buy and hold. | Nothing usable. |
| Thophet, TwinAlgo (XAUUSD spot, LLM) | Regime rules (ATR > 85th pct = volatile; block if ATR > 2x average); R:R >= 1.5. Only result is a 40% win rate, no backtest. | Hypothesis H-ATRX: block new entries when today's first-hour range > 2x its 20-day average (all bots). |
| Kakushadze, 101 Formulaic Alphas | Cross-sectional daily equity formulas; few adapt to one instrument. | Not added. |
| Pillai et al., Hybrid AI; Han, crypto adaptive limits | Daily stocks and hourly crypto; bull-run or loses to buy and hold. | Not added. |

## Verdict on the papers

None of the 32 papers shows an out-of-sample, cost-adjusted intraday edge on ES, NQ or GC that is stronger than the legs we already have; the two MNQ papers report that nearly every OHLCV family fails after costs, which matches our ledger. What they add is (1) regime filters (long-horizon trend, crash state, VVG and ATR-expansion blocks), (2) a sizing target (eval daily sigma near $400-600 for a $2,000 drawdown), (3) exit calibration from trade paths, and (4) three new low-prior entry families (CMF, pre-RTH range, prior-day reversal). Each is pre-registered here and logged in the ledger when run.
