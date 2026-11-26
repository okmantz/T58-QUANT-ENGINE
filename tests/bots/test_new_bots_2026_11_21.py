"""2026-11-21: LucidFlex's winning-day payout terms and the evaluation consistency rule in the governor (a LucidFlex evaluation is not passed while the best day
is more than 40% of the profit)."""
from __future__ import annotations

from app.bots.models import AccountLink
from app.bots.risk_governor import CONSISTENCY_PAD, AccountRulesLite, AccountState, GovernorConfig, decide_risk


def _flex() -> AccountRulesLite:
    from app.prop.lifecycle_v2 import V2Rules
    from app.prop.presets import get_preset
    return AccountRulesLite.from_v2(V2Rules.from_prop_rules(get_preset("lucid_flex_50k").to_prop_rules()))


def _pro() -> AccountRulesLite:
    from app.prop.lifecycle_v2 import V2Rules
    from app.prop.presets import get_preset
    return AccountRulesLite.from_v2(V2Rules.from_prop_rules(get_preset("lucid_50k").to_prop_rules()))


def test_flex_rules_carry_consistency_and_the_150_dollar_days():
    f, p = _flex(), _pro()
    assert f.eval_consistency == 0.40 and (f.winning_days, f.winning_day_profit) == (5, 150.0)
    assert p.eval_consistency is None and (p.winning_days, p.winning_day_profit) == (5, 250.0)


def test_objective_b_on_flex_uses_the_accounts_own_payout_days():
    from app.bots.engine import rules_for_account
    rf, _, _ = rules_for_account(AccountLink(venue="paper", account_id="x", size=50_000.0, broker_symbol="MNQ", preset_key="lucid_flex_50k"), objective="B")
    rp, _, _ = rules_for_account(AccountLink(venue="paper", account_id="x", size=50_000.0, broker_symbol="MNQ", preset_key="lucid_50k"), objective="B")
    assert rf.payout_mode == rp.payout_mode == "winning_days_net_positive"
    assert rf.winning_day_profit == 150.0 and rp.winning_day_profit == 250.0


def test_flex_evaluation_is_not_passed_while_one_day_dominates():
    st = AccountState.fresh(_flex())
    st.update(2_000.0, "2026-01-05"); st.update(1_100.0, "2026-01-06")
    assert st.profit >= 3_000 and st.phase == "evaluation"                 # $2,000 is 65% of $3,100: not passed
    assert abs(st.effective_target() - CONSISTENCY_PAD * 2_000 / 0.40) < 1e-6
    st.update(900.0, "2026-01-07"); st.update(1_100.0, "2026-01-08")        # profit $5,100, best day $2,000 = 39%
    assert st.phase == "passed"


def test_pro_evaluation_still_passes_at_the_target():
    st = AccountState.fresh(_pro())
    st.update(2_000.0, "2026-01-05"); st.update(1_100.0, "2026-01-06")
    assert st.phase == "passed" and st.effective_target() == 3_000.0


def test_governor_keeps_trading_toward_the_adjusted_target():
    g = GovernorConfig(objective="A", base_risk_pct=0.75, need_risk_mult=1.0, cushion_risk_frac=0.75)
    st = AccountState.fresh(_flex())
    st.update(2_000.0, "2026-01-05"); st.update(1_000.0, "2026-01-06"); st.roll_day("2026-01-07")
    d = decide_risk(st, g)
    assert d.allow and d.risk_dollars > 300          # at the nominal target the need taper would leave only the minimum risk
    nominal = AccountState.fresh(AccountRulesLite(eval_consistency=None))
    nominal.balance = st.balance - 1.0; nominal.roll_day("2026-01-07")
    assert decide_risk(nominal, g).risk_dollars < d.risk_dollars


def test_state_dict_carries_eval_days():
    st = AccountState.fresh(_flex()); st.update(500.0, "2026-01-05")
    assert st.to_dict()["eval_days"] == {"2026-01-05": 500.0}
