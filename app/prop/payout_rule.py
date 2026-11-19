"""The Objective B payout rule as a pure function: N days of at least $X, in any order, with wins bigger than losses.

    day 1 +250, day 2 -50, day 3 +300, day 4 -100, day 5 +127, day 6 +260, day 7 -200, day 8 +250, day 9 -98, day 10 +271
    -> five days at or above $250 (1, 3, 6, 8, 10; day 5 made only $127, so it does not count), the days need not be consecutive, and the
       cycle is net +$1,010 (wins outweigh losses) -> payout eligible on day 10.

The same rule is enforced by ``PropRules.payout_rule_mode = "winning_days_net_positive"`` (scalar PropAccount) and by
``AccountRulesLite.with_winning_days_payout`` (the bot account model); this module is the readable reference and what the UI explains with.
"""
from __future__ import annotations

from typing import Sequence

DEFAULT_WINNING_DAYS = 5
DEFAULT_WINNING_DAY_PROFIT = 250.0


def payout_progress(day_pnls: Sequence[float], *, winning_days: int = DEFAULT_WINNING_DAYS, day_profit: float = DEFAULT_WINNING_DAY_PROFIT) -> dict:
    """Where a payout cycle stands after ``day_pnls`` (one realised P&L per trading day since the last payout)."""
    qualifying = sum(1 for p in day_pnls if p >= day_profit)
    wins = sum(p for p in day_pnls if p > 0)
    losses = -sum(p for p in day_pnls if p < 0)
    net = wins - losses
    return {"qualifying_days": qualifying, "days_needed": int(winning_days), "wins": wins, "losses": losses, "net": net,
            "wins_exceed_losses": net > 0, "eligible": qualifying >= winning_days and net > 0}


def first_eligible_day(day_pnls: Sequence[float], *, winning_days: int = DEFAULT_WINNING_DAYS, day_profit: float = DEFAULT_WINNING_DAY_PROFIT) -> int | None:
    """1-based day on which the cycle first becomes payout-eligible, or None."""
    for i in range(1, len(day_pnls) + 1):
        if payout_progress(day_pnls[:i], winning_days=winning_days, day_profit=day_profit)["eligible"]:
            return i
    return None


def objective_b_rules(rules, days: int = DEFAULT_WINNING_DAYS, day_profit: float = DEFAULT_WINNING_DAY_PROFIT):
    """``rules`` (a PropRules) re-expressed under the Objective B payout rule. The $250 day is for a 50K account and scales with account size.
    Rules that already choose a payout mode are returned unchanged."""
    from dataclasses import replace
    if getattr(rules, "payout_rule_mode", "standard") != "standard":
        return rules
    return replace(rules, payout_rule_mode="winning_days_net_positive", winning_days_for_payout=int(days),
                   min_winning_day_profit=float(day_profit) * float(rules.account_size) / 50_000.0)
