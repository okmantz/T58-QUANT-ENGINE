"""Objective B payout rule: N days of >= $X in any order, wins bigger than losses (owner example, 2026-11-18)."""
import pandas as pd

from app.bots.risk_governor import AccountRulesLite, AccountState
from app.prop.payout_rule import first_eligible_day, payout_progress
from app.prop.presets import get_preset
from app.prop.simulator import PropRules, simulate_account

OWNER_DAYS = [250, -50, 300, -100, 127, 260, -200, 250, -98, 271]


def test_owner_example_becomes_eligible_on_day_ten():
    assert first_eligible_day(OWNER_DAYS) == 10
    p = payout_progress(OWNER_DAYS)
    assert p["qualifying_days"] == 5 and p["net"] == 1010 and p["eligible"]
    assert payout_progress(OWNER_DAYS[:8])["qualifying_days"] == 4        # day 5 ($127) does not count


def test_not_eligible_when_losses_outweigh_wins():
    days = [250, 250, 250, 250, 250, -2000]
    assert payout_progress(days)["qualifying_days"] == 5 and not payout_progress(days)["eligible"]


def test_bot_account_state_pays_on_day_ten_and_starts_a_new_cycle():
    a = AccountState.fresh(AccountRulesLite().with_winning_days_payout(5, 250))
    a.to_funded()
    paid = []
    for i, d in enumerate(OWNER_DAYS, 1):
        a.update(d, f"2024-02-{i:02d}")
        paid.append(a.take_payout())
    assert paid[:9] == [0.0] * 9 and paid[9] == 1010.0
    assert a.cycle_days == {} and a.balance == 50_000.0                   # paid out down to the starting balance, fresh cycle


def test_prop_account_pays_under_the_winning_days_net_positive_rule():
    rules = PropRules(account_size=50_000, evaluation_profit_target_pct=6.0, daily_loss_limit_pct=100, max_drawdown_pct=100, consistency_rule_pct=None,
                      min_trading_days=1, payout_frequency_days=0, winning_days_for_payout=5, min_winning_day_profit=250.0,
                      payout_rule_mode="winning_days_net_positive")
    pnls = [3000] + OWNER_DAYS                                            # day 1 passes the evaluation, then the owner's ten funded days
    dates = [pd.Timestamp("2024-01-01") + pd.Timedelta(days=i) for i in range(len(pnls))]
    res = simulate_account(pnls, dates, rules)
    assert res.passed_evaluation and res.reached_first_payout
    assert len(res.payouts) == 1 and abs(res.payouts[0].amount - 1010.0) < 1e-6


def test_standard_mode_is_unchanged():
    assert PropRules().payout_rule_mode == "standard"
    assert get_preset("lucid_50k").to_prop_rules().payout_rule_mode == "standard"


def test_unknown_mode_rejected():
    import pytest
    with pytest.raises(ValueError):
        PropRules(payout_rule_mode="nope")
