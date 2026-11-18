# The three objectives

Generated from `app/objectives.py` (`DIRECTIVES`, `ENGINE_DIRECTIVE`). Edit the code, not this file.

## OBJECTIVE A: EVALUATION PASSER

**Mission:** Pass a prop-firm evaluation as quickly and efficiently as possible. Optimize strategy portfolios for the highest probability of reaching the profit target within 30 days, with 60 days as the maximum acceptable horizon, while minimizing the probability of breaching drawdown rules before passing.

- Prioritize probability of passing, speed to target, and capital efficiency.
- Accept higher variance and more aggressive risk than Objective B, provided drawdown survival remains statistically viable.
- Optimize position sizing, trade frequency, strategy combinations, and risk dynamically as the account approaches its profit target or drawdown limit.
- Maximize the probability of reaching the profit target before violating any account rules.

**Primary metric:** Probability of passing within 30/60 days.
**Secondary metrics:** Median days to pass, breach probability, profit-target efficiency, risk of ruin.

**The goal is to pass—not to preserve the account long-term.**

- Risk posture: aggressive: more variance than B, as long as survival to the target stays statistically viable
- Sizing: dynamic: full size while the floor is far, trimmed as the target or the floor comes near; ends at the pass
- Markets: intraday futures inside the firm's rules (flat at the close, news and consistency rules respected)
- Overnight holds: not allowed

## OBJECTIVE B: PAYOUT HUNTER

**Mission:** Secure a funded account, preserve it, and extract payouts as quickly and consistently as possible. Optimize for the highest probability of generating a payout while minimizing the risk of losing the funded account.

- Prioritize survivability, capital preservation, consistency, and sustainable payout generation.
- Use conservative risk sizing and reduce exposure as drawdown increases or the account's safety buffer shrinks.
- Favor robust strategies, low drawdown, shorter losing streaks, consistency-rule compliance, and uncorrelated portfolio exposure.
- Optimize for reaching payout thresholds efficiently without jeopardizing the account.
- Avoid unnecessary risk after achieving payout eligibility or daily profit objectives.

**Primary metric:** Probability of reaching a payout without breaching account rules.
**Secondary metrics:** Time to first payout, payout expectancy, account survival, drawdown, consistency compliance, repeat payout probability.

**The goal is to get paid and keep the account alive—not to pass aggressively or maximize raw trading profits.**

- Risk posture: conservative: low variance, small drawdowns, short losing streaks, no single day carrying the profit
- Sizing: shrinks with drawdown and with the safety buffer; eased back once payout-eligible or after a good day
- Markets: intraday futures inside the firm's rules, diversified across uncorrelated sleeves
- Overnight holds: not allowed

## OBJECTIVE C: NET PROFIT COMPOUNDER

**Mission:** Maximize long-term risk-adjusted net profit on unrestricted live accounts. Optimize for sustainable wealth generation and account growth after all trading costs, with no prop-firm restrictions.

- Maximize long-term net profit and compound growth.
- Optimize risk-adjusted returns, expectancy, drawdown efficiency, and capital utilization.
- Trade any suitable market: forex, stocks, indices, futures, commodities, etc.
- Permit overnight, swing, position, and longer-term trades where statistically advantageous.
- Allow flexible leverage, sizing, holding periods, portfolio allocation, and compounding based on validated risk controls.
- Prioritize durable out-of-sample edges over short-term performance or artificial trading-frequency constraints.

**Primary metric:** Long-term net profit and compounded growth.
**Secondary metrics:** Risk-adjusted return, Calmar ratio, expectancy, maximum drawdown, return on capital, robustness across market regimes.

**The goal is to grow capital and maximize net wealth—not pass evaluations or satisfy payout rules.**

- Risk posture: growth: as much volatility as the validated drawdown budget allows, throttled as drawdown deepens
- Sizing: compounds with equity; falls to a floor multiple as drawdown from the equity peak deepens
- Markets: any liquid market: futures, indices, commodities, FX, equities; overnight, swing and position holds allowed
- Overnight holds: allowed

## ENGINE DIRECTIVE

Each objective must have its own independent strategy discovery, optimization, portfolio construction, position-sizing logic, risk governor, scoring system, and selection criteria. Never optimize a strategy for one objective using another objective's priorities. A strategy that is excellent at passing an evaluation may be unsuitable for payouts or live compounding. Strategies must be judged exclusively by how effectively they accomplish their assigned mission.


# Statistics and mathematics of the optimal combination

## 1. Setting and notation

A strategy book emits a daily P&L stream; a trade i has net dollars r_i after commission and slippage, sized in whole contracts. The simulator maps a start date s and the trade list to an account path E_s(t). All three objectives are functionals of the distribution of these paths over start dates s, so each objective is a different functional of the same underlying law, and the optimal book for one is generally not optimal for the others.

## 2. Objective A: maximise P(pass within H days)

Let T be the first day the path reaches the profit target Π (Lucid 50K: Π = 3,000) and B the first day it breaches the trailing / daily loss rule. The primary metric is p_H = P(T ≤ H, T < B) with H = 30 (60 as the acceptable maximum). Secondary: median(T | pass), breach probability P(B ≤ H), risk of ruin P(B < ∞), profit-target efficiency, and the pass-per-breach ratio p_H / P(B ≤ H).

Estimator. Over K rolling starts, p̂_H = (1/K) Σ 1[pass_s]. Starts overlapping by less than H days are positively correlated, so the effective sample is n_eff = (window days)/H, not K. The reported lower bound is the Wilson interval at n_eff:

  lo = ( p̂ + z²/2n − z·sqrt( p̂(1−p̂)/n + z²/4n² ) ) / (1 + z²/n),  z = 1.96, n = n_eff.

Gambler's-ruin intuition for the optimum. For a book with per-day mean μ and volatility σ, with an absorbing target Π and an absorbing floor D below the start (D the loss allowance), the probability of hitting Π first is approximately
  P(hit Π before −D) ≈ (1 − e^{−2μD/σ²}) / (1 − e^{−2μ(Π+D)/σ²}),
and the expected time is ≈ Π/μ. Raising size scales μ and σ together (μ→kμ, σ→kσ), leaving the exponent 2μD/σ² scaled by 1/k, so more size always shortens the time but lowers the pass probability once the floor is binding. The A optimum is therefore an interior size where d p_30/dk = 0 within the 30-day constraint, which is why A accepts more risk than B but not unlimited risk, and why the governor de-risks as the account approaches Π (locking the gain costs less than the extra variance adds).

Combination. For books with daily P&L covariance Σ and weights w, μ_p = wᵀμ and σ_p² = wᵀΣw. Pass probability rises with the ratio μ_p/σ_p², so diversification (low off-diagonal Σ) is rewarded directly: the optimum maximises wᵀμ / wᵀΣw subject to the contract grid and the one-position limit, which is the choice made on the train split and confirmed on validation.

## 3. Objective B: maximise P(payout without breach)

Let U be the first day the funded path satisfies the payout rule (profit buffer above the threshold, a minimum number of winning days, and the consistency rule: the best day share ≤ c of total profit) and B the breach time. Primary: P(U ≤ 365, U < B). Secondary: median(U), expected payout E[paid] = Σ payouts, survival P(no breach to day 365), repeat payout probability P(second payout | first), consistency compliance, and the max drawdown in dollars.

Consistency is a constraint on the concentration of profit: with day profits g_d, require max_d g_d ≤ c·Σ g_d. A book whose edge comes from few large days fails it even with a high win rate, so B favours low skew, smooth equity and a lower σ than A. The relevant optimum maximises a Sharpe-like ratio over the 365-day horizon with a loss floor: P(U<B) is increasing in μ/σ for a fixed floor, and the size is set so that the drawdown stays well inside the trailing buffer rather than being pushed to the edge, which is the opposite of A.

Estimator caveat. The window needs 365 forward days from each start, so the number of independent starts is n_eff = (window days)/365, which is 1-5 in the splits used here. Wilson bounds at this n_eff are wide (see the tables), and the 2025-2026 test window has 2-13 valid starts. The B conclusion therefore rests on train+validation consistency and on structural properties (survival, drawdown, low consistency risk); the test column cannot confirm or refute it.

## 4. Objective C: maximise compounded net wealth

For an equity path E(t) over Y years: CAGR = (E_end/E_0)^{1/Y} − 1, max drawdown MDD = max_t (peak_t − E_t)/peak_t, Calmar = CAGR / MDD, expectancy = mean net dollars per trade, return on capital = (E_end − E_0)/E_0.

The growth-optimal sizing result (Kelly) for a return with mean μ and variance σ² per period is f* = μ/σ², giving long-run log growth g(f) = fμ − f²σ²/2, maximal at f* with g(f*) = μ²/2σ². Growth falls on either side of f*, and beyond 2f* it is negative, so the practical rule is fractional Kelly (typically f*/2) which keeps 75% of the growth and cuts the drawdown roughly in half. Estimation error in μ makes the true f* lower than the estimated one, which is why C uses the drawdown-throttled governor: the size multiplier falls to a floor as the drawdown from the equity peak deepens.

Compounding is capped at $250K of sizing equity (`SIZE_CAP_DEFAULT`) because a futures account cannot add contracts without bound; ignoring the cap produced unrealistic multi-million curves in testing, which is why reported train and validation CAGRs should be read as regime evidence rather than forecasts.

Diversification. For sleeves with correlation ρ_ij, the portfolio variance is Σ_i w_i²σ_i² + 2Σ_{i<j} w_i w_j ρ_ij σ_i σ_j. Adding Gate27 (daily bars, overnight, multi-asset) at low ρ to the intraday NQ/ES sleeves lowers the variance for the same mean, raising μ²/2σ² and Calmar; that is the mechanism the combined-book table measures.

## 5. Out-of-sample robustness (mandatory for all three)

Selection uses train only; confirmation uses validation, ranking by the lower of train and validation scores (the minimum is the conservative estimate); the test split is read once. A candidate whose validation score is far below train (e.g. greedy-2 for B: train 73.7, validation 14.3) is rejected as overfit even though its train score is the highest. For A the shipped book has validation P(pass≤60) above train and a test P(pass≤30) lower bound that remains positive; the gap between train and test is itself a measured regime effect, reported rather than hidden.

## 6. What the optimal attainable combination looks like

- A: high-frequency, positively skewed intraday sleeves on NQ with moderate-to-high contract multipliers, at most one position, a combined daily cap, and a governor that sizes up early and locks in as the target nears; the binding constraint is the breach floor, not the number of signals.
- B: fewer, smoother sleeves at roughly 1x, no sleeve whose profit is concentrated in a few days, with the whole book sized so that the worst historical drawdown is a fraction of the trailing buffer.
- C: the largest sleeve set that keeps pairwise correlation low, including a slow overnight sleeve (Gate27), sized by drawdown-throttled fractional Kelly with the equity cap.

## 7. Using this for new strategy creation

A new candidate is worth building only if it raises the objective's functional for the existing book, not if it merely has a good standalone profit factor:
- For A: it must raise wᵀμ/wᵀΣw, which means a positive mean and low correlation with the current A sleeves, and the ability to produce winners within 30 days.
- For B: it must lower the best-day share and the dollar drawdown at the same mean.
- For C: it must raise CAGR/MDD of the combined book, usually by being uncorrelated and carried overnight.
Screen at profit factor ≥ 1.1 and at least 60 trades on train+validation, rank by the lower of the two, read test once.
