# What moves the needle: pass in 30 days, get paid in 30 days, maximise net profit (2026-11-18)

Reproduce every table below with `python scripts/run_objectives_research.py` (Monte Carlo, Lucid-50K-style rules) and the trade-level harness numbers quoted from the
Evaluation Passer study (train 2020-2023, validation 2024, hold-out 2025-26, hold-out read once).

## 0. The honest answer first

* **Sizing and "adaptivity" cannot create an edge.** On the shipped Evaluation Passer book a grid of 216 governor settings moved P(pass in 30 days) by a few points
  and nothing else. The only controls that helped on train *and* validation were pace-aware sizing (press when ahead of the schedule, ease off behind it) and a larger
  first-third multiplier: train 34.2 -> 39.3 %, validation 57.8 -> 58.7 %, hold-out 28.2 -> 32.7 % (single run, one read). That is what shipped.
* **The shipped book's edge is about 0.10 R per trade at about 1.6 trades a day.** The frontier below says that is a 40-45 % pass machine, and the history agrees
  (train/validation/hold-out 34 / 58 / 28 %, wide because 110-415 start dates overlap). A bot that "consistently" passes needs a different edge, not a different governor.
* **"Under 30 days" is not the binding constraint. Breach is.** Giving the same bot 60 days instead of 30 lifts P(pass) from 44 to 47 %. The other 53 % are not slow, they
  are dead (trailing drawdown) or stalled by the day stop.

## 1. Objective A, pass an evaluation in 30 days

P(pass within 30 trading days), $3,000 target, $2,000 end-of-day trailing floor, 40 % day stop, $500 risk, win rate 45 % (payoff set by the expectancy):

| expectancy (R) | 0.5 trades/day | 1 | 2 | 3 | 5 |
|---:|---:|---:|---:|---:|---:|
| 0.00 | 5 | 17 | 27 | 30 | 33 |
| 0.05 | 10 | 25 | 36 | 39 | 42 |
| 0.10 | 15 | 33 | 44 | 48 | 51 |
| 0.15 | 22 | 41 | 52 | 56 | 59 |
| 0.20 | 35 | 50 | 60 | 62 | 67 |
| 0.30 | 45 | 60 | 70 | 73 | 77 |

Reading it:

1. **Trade count is worth as much as edge up to about 2 a day, then flattens.** Going 1 -> 2 trades a day at 0.10 R is +11 points; 2 -> 5 is +6. Past 3 a day you are paying
   for correlated trades on one index.
2. **To reach 70 % you need 0.30 R per trade at 2 a day.** The shipped strategies have 0.07-0.12 R after costs. Nothing in this repo shows a stable 0.30 R. Plan for 50-60 %, which needs 0.15-0.20 R at 2-3 trades a day.
3. **Risk per trade has a flat top.** At 0.10 R, $300 / $500 / $750 / $1,000 give 33 / 42 / 44 / 45 % pass but 9 / 16 / 21 / 21 % breach. The shipped 0.75 % base ($375)
   with cushion cap, need taper and pace control sits on the knee. More size is more breaches for 1-3 points.
4. **A retry is the cheapest edge.** With p = 0.45 per attempt, P(pass within three attempts) = 1 - 0.55^3 = 83 %, for the cost of two resets. Compare that with the
   cost of finding +0.1 R. The bot should expect to be run as an attempt, and the Trading Bots page should show reset cost against payout (see section 5).

What actually raises the edge (ranked by what I would build first):

| # | Idea | Why it should move the needle | How to test it here |
|---|---|---|---|
| 1 | **More uncorrelated legs, not heavier legs.** The 8 library strategies on NQ and ES share one factor (US index intraday momentum). Add ES/NQ lead-lag, GC, CL, 6E, ZN opening-range legs. | Annual Sharpe of N independent streams rises with sqrt(N); trade count rises, correlation does not. | Generate trades per strategy x instrument (`scripts/gen_trades2.py` pattern), add legs only if they win on train **and** validation. Forward selection on the 14 available legs overfit (validation 58.7 -> 49.1 %), so the bar must be validation-first. |
| 2 | **Regime-gated entries** (volatility, gap size, day-of-week, event days) per leg, learned on train, frozen. | Removes the trades with negative expectancy; edge per trade up, trades down. Net effect on pass probability is positive only if expectancy rises by more than the frequency loss. | Optimize page > "cut worst days and times" per leg, then Validate on the hold-out. |
| 3 | **Event-driven legs** (FOMC / CPI / NFP drift and fade). High R-multiples, 8-24 events a year. | Large moves are where 0.3 R trades live; they are also where the day stop and trailing floor kill you, so they need event-specific size. | New strategies in `strategies/python`; the FOMC overlay result (hold-out 35.2 -> 41.0 %) hints at it. |
| 4 | **Passing-phase target-aware exits.** Once the account is within one trade of the target, stop taking new risk and flatten at the target. | Pass probability is a first-passage problem; locking the last $300 removes the give-back. The need taper already does part of this. | Harness `need_risk_mult` sweep (1.0 / 1.5 / 2.0 gave 28 / 29 / 31 % hold-out, so small). |
| 5 | **Out-of-sample parameter stability gate on every leg** before it enters a bot (Wilson interval on win rate, minimum 150 trades on train+validation). | Kills the leg that makes the book look good on one split. | `app/strategy` champion gates already exist; add a bot-level gate. |

## 2. Objective B, get paid within 30 days of funding

P(5 days of at least $250, cycle net positive, inside 30 trading days), $300 risk, 30 % day stop, a day capped near $400 so no single day dominates:

| expectancy (R) | 0.5/day | 1 | 2 | 3 | 5 |
|---:|---:|---:|---:|---:|---:|
| 0.00 | 44 | 60 | 62 | 63 | 64 |
| 0.05 | 55 | 73 | 77 | 78 | 79 |
| 0.10 | 57 | 76 | 82 | 83 | 85 |
| 0.20 | 60 | 83 | 88 | 91 | 92 |

* Payout is **far easier than the pass** because the funded floor is $2,100 away, the rule asks for small repeatable days, and zero-edge books still get there 60 %
  of the time. At 0.10 R and 2 trades a day it is 82 %. This model leaves out the consistency and payout-request mechanics of a specific firm, so treat it as a ceiling.
* **What matters is the day-level win rate, not the trade-level edge.** Five days of at least $250 needs about 40 % of days to clear $250; a **day profit lock** (stop for the
  day once +$250 to $400 is banked) turns a +$900 outlier into the same one qualifying day and saves the risk of giving it back. This is why `win_day_lock_mult` is on in the
  shipped Payout Hunter.
* **The binding failure is a loss day between qualifying days.** A 30 % day stop and a cushion cap of 25 % keep one bad day from consuming the $2,100 buffer. The
  rest of the work is frequency: a bot that trades twice a day on three uncorrelated legs gets more shots at $250 days than a bot with one great strategy.
* Build for B: low per-trade risk ($200-300), 2-4 trades a day across 3+ legs, a hard day-profit lock, no overnight, no FOMC days, and a payout-request timer that
  stops trading the moment the rule is met.

## 3. Objective NET, "go crazy" with profit on a rule-free account

Median multiple of the account after 250 sessions (5th percentile in brackets), 2 trades a day per stream, win rate 45 %. Streams share one risk budget, so 4 streams also
means 4x the trades:

| expectancy | risk/trade | 1 stream | 4 streams | P(drawdown >= 50 %), 1 / 4 streams |
|---|---:|---:|---:|---:|
| 0.10 R | 1 % | x1.6 (1.0) | x2.6 (1.7) | 0 / 0 % |
| 0.10 R | 2 % | x2.3 (1.0) | x6.3 (2.6) | 5 / 0.2 % |
| 0.20 R | 1 % | x2.6 (1.6) | x7.1 (4.3) | 0 / 0 % |
| 0.20 R | 2 % | x6.1 (2.3) | x45 (17) | 0.8 / 0 % |

* **Compounding is a function of expectancy times trade count times the fraction risked, minus half the variance.** Past about the half-Kelly point extra size lowers the
  median. For 0.10 R and a 1 : 1.4 payoff the growth-optimal risk is near 2 %; the NET bot's 1 % compounding with a 10 % drawdown throttle is already below that.
* **Diversification is worth more than leverage.** At 0.10 R, going from one stream to four lifts the median from x1.6 to x2.6 at the same per-stream risk, and adding a second
  doubling of size on one stream only gets x2.3 with a 5 % chance of a half-account drawdown.
* The numbers are what the model says, not what the history will do: the hold-out for the compounder was 14 months, so read it as an order of magnitude only.
* Build for NET: the widest set of uncorrelated legs (index, metals, energy, rates, FX), volatility-targeted size per leg, the Gate 27 swing basket as the carry
  component, a drawdown throttle at 8-10 %, and pace-aware sizing capped at 1.25x.

## 4. Outside the box

* **Treat a pass as a portfolio of attempts, not one bot.** Run the same objective with two *different* bots (they need not be the best bot, only decorrelated) on two
  accounts. P(at least one passes) rises with decorrelation, whereas copy-trading one bot to ten accounts multiplies the same outcome and the same breach.
* **Start-date selection.** The pass probability is 28-58 % depending on the start window. A volatility and calendar filter on *when to begin the evaluation*
  (avoid the weeks around FOMC, quarter-end rolls) costs nothing and is testable from the 415 historical start dates already in the harness.
* **Spend the cushion in the first third** (shipped: early 1.3x) and **protect it late** (late 0.7x). The first third is where a breach is least likely, and where you can
  afford the variance that makes a quick pass possible.
* **Do not use trailing stops on the trend legs.** The profit-lock ladder clipped Open Drive from $79K to $20K at the typed rungs; this study found no train-and-validation
  agreement for it, so the shipped bots leave it off.
* **Raise trades per day with *more* instruments, not looser entries.** Looser entries lower the expectancy and move you left on the table above.
* **Use the 1-minute bar engine's own slippage model** (already in) and re-measure cost on every new leg: at 0.10 R a one-tick change in slippage is a 20-30 % change in expectancy.

## 5. What shipped from this study

* Pace-aware sizing (`pace_max_mult`, `pace_min_mult`), loss-streak and cold-expectancy damping, a first-third multiplier, and a win-day lock: all capped, all in `app/bots/risk_governor.py`; the three presets use them (`PRESET_REV` 3).
  **Only the Evaluation Passer's settings were selected on train+validation with the hold-out read once. The Payout Hunter and Net Profit Compounder got the same
  controls at conservative values (pace cap 1.3x / 1.25x, streak damping 0.7x) that were not separately grid-searched; treat them as unvalidated until the same
  harness is run on their books.**
* Bug fixes that were costing the existing bots real trades: the demo account never rolled its day (a day stop at -$526 then blocked every later signal for months, the
  "6 trades then nothing" symptom), the leg weight was multiplied *after* the risk caps (a 3x leg could exceed the cushion share), contract sizing ignored slippage, and a bot
  backtested on a full NQ/ES contract rounded to zero contracts (the "12 months, no trades" symptom, now sized in micros like the live bot).
* Bots in the Simulator, Replay, Test, Optimize and Validate dropdowns, and a Bots tab on every strategy-tab page.

## 6. Limits of this paper

* The Monte Carlo is a requirement calculator with i.i.d. trades; real trades cluster and the model understates breach risk.
* All hold-out figures were read once, but there are only 110-135 overlapping start windows in it.
* Nothing here claims the edge exists. It states what edge, frequency and risk a bot needs to pass, and that the current library is a few tenths of a point short.
