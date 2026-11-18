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

