"""Objective A (pass) and Objective B (sustainable payouts) are separate numbers; the modes route to the right fitness."""
import types

import pytest

from app.optimize.refinement import fitness_for_objective_mode
from app.prop import objectives as ob
from app.prop.lifecycle import FundedStage, LifecycleResult, EvaluationStage, normalize_objective_mode


def _lc(*, surv90=80.0, gross=1500.0, p_funded=60.0):
    ev = EvaluationStage(n_simulations=100, p_reach_target_before_breach=70.0, p_pass=65.0, p_pass_ci=(55.0, 74.0), p_daily_loss_violation=4.0,
                         p_fail_daily_loss=1.0, p_fail_max_drawdown=20.0, p_fail_time_limit=3.0, p_fail_other=0.0, p_unresolved=2.0,
                         p_consistency_ok_given_target=90.0, p_blocked_by_rules_after_target=5.0,
                         time_to_target={"calendar": {"p50": 12.0}, "trading": {"p50": 9.0}}, p_pass_within_days={30: 50.0, 60: 60.0},
                         windows_covered={30: True, 60: True, 90: False})
    fu = FundedStage(n_funded=60, p_funded=p_funded, p_survive_given_funded={30: 95.0, 60: 88.0, 90: surv90}, survival_at_risk={30: 60, 60: 50, 90: 40},
                     p_fail_funded_daily_loss=3.0, p_fail_funded_drawdown=17.0, p_first_payout_given_funded=70.0, p_second_payout_given_funded=40.0,
                     p_third_payout_given_funded=20.0, expected_gross_payout_per_funded=gross, median_payout_amount=900.0, time_to_first_payout={})
    return LifecycleResult(evaluation=ev, funded=fu, p_pass_and_first_payout=42.0, p_pass_and_first_payout_ci=(30.0, 50.0),
                           expected_gross_payout_per_attempt=900.0, expected_net_per_attempt=520.0, expected_fees_per_first_payout=None,
                           expected_attempts_to_first_payout=None, objective_mode="prop_lifecycle", objective_value=0.0, n_trades=300,
                           history_calendar_days=400)


def test_objective_a_is_pass_within_horizon_and_refuses_unmeasurable_horizons():
    lc = _lc()
    assert ob.objective_pass(lc, 30) == 50.0 and ob.objective_pass(lc) == 65.0
    with pytest.raises(ValueError):
        ob.objective_pass(lc, 90)              # history too short: not measurable, never silently 0
    with pytest.raises(ValueError):
        ob.objective_pass(lc, 14)              # not simulated
    a = ob.objective_a_report(lc, 30)
    assert a["primary_pct"] == 50.0 and a["daily_loss"]["survival_pct"] == 96.0


def test_objective_b_counts_withdrawals_only_above_the_survival_floor():
    ok = ob.sustainable_withdrawals(_lc(surv90=80.0), 80.0)
    assert ok["feasible"] and ok["score"] == pytest.approx(1200.0)
    bad = ob.sustainable_withdrawals(_lc(surv90=40.0, gross=9000.0), 80.0)      # big payouts bought with a likely blow-up
    assert not bad["feasible"] and bad["score"] == 0.0 and "floor" in bad["why"]


def test_payout_objective_composes_funded_share_payout_count_and_survival():
    lc = _lc()
    assert ob.objective_payout(lc, 1) == pytest.approx(60.0 * 0.70)
    assert ob.objective_payout(lc, 2, 90) == pytest.approx(60.0 * 0.40 * 0.80)
    with pytest.raises(ValueError):
        ob.objective_payout(lc, 4)


def test_modes_and_fitness_routing():
    assert normalize_objective_mode("objective_a") == "pass" and normalize_objective_mode("Funded") == "payout"
    assert normalize_objective_mode("net") == "net_profit"          # legacy meaning (live account) is preserved
    assert normalize_objective_mode("prop net") == "prop_net" and normalize_objective_mode("") == "prop_lifecycle"
    assert fitness_for_objective_mode("pass") == "pass_gradient" and fitness_for_objective_mode("payout") == "lifecycle_gradient"
    assert fitness_for_objective_mode("pass", "edge_lb_r_dd") == "edge_lb_r_dd"
    lc = _lc()
    assert ob.objective_value(lc, "prop_net") == 520.0 and ob.objective_value(lc, "pass") == 50.0


def test_stage_view_is_derived_from_the_preset():
    from app.prop.stages import firm_rules
    f = firm_rules("lucid_50k")
    assert f.evaluation.trailing_lock and f.payout.cap_dollars == 2000.0 and f.payout.buffer_pct == 4.2
    assert f.fees.purchase is not None and f.payout.split_pct > 0


def test_run_staged_two_step_then_funded():
    import pandas as pd
    from types import SimpleNamespace as T
    from app.prop.stages import phase_plan, run_staged
    assert [n for n, _ in phase_plan("ftmo_100k")] == ["phase_1", "phase_2", "funded"]
    assert [n for n, _ in phase_plan("topstep_50k")] == ["phase_1", "funded"]
    ts = pd.date_range("2024-01-02 10:00", periods=200, freq="1D")
    tr = [T(entry_time=t, pnl=600.0 if i % 3 else -200.0) for i, t in enumerate(ts)]
    r = run_staged(tr, "ftmo_100k")
    assert [p.name for p in r.phases] == ["phase_1", "phase_2", "funded"] and r.passed_all_evaluation and r.funded_reached
    bust = run_staged([T(entry_time=t, pnl=-9000.0) for t in ts[:5]], "ftmo_100k")
    assert bust.phases[0].failed and not bust.funded_reached
