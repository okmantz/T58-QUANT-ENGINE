from __future__ import annotations

from app.bots.risk_governor import AccountRulesLite, AccountState, GovernorConfig, contracts_for_risk, decide_risk


def _state():
    return AccountState.fresh(AccountRulesLite.lucid_50k())


def test_fresh_account_risks_base_amount():
    d = decide_risk(_state(), GovernorConfig(objective="A", base_risk_pct=1.0))
    assert d.allow and abs(d.risk_dollars - 500.0) < 1e-6


def test_progress_ladder_trims_late_risk():
    cfg = GovernorConfig(objective="A", late_mult=0.5)
    s = _state()
    s.update(2_400.0, 'd1')  # 80% of a $3,000 target
    assert decide_risk(s, cfg).risk_dollars < 500.0


def test_day_stop_blocks_new_trades():
    s = _state()
    s.update(-600.0, 'd1')
    d = decide_risk(s, GovernorConfig(objective="A", day_stop_frac=0.4))
    assert not d.allow and "day stop" in d.reason


def test_cushion_cap_limits_risk():
    cfg = GovernorConfig(objective="B", base_risk_pct=1.0, cushion_risk_frac=0.1)
    d = decide_risk(_state(), cfg)
    assert d.allow and d.risk_dollars <= 0.1 * _state().cushion + 1e-6


def test_net_objective_throttles_in_drawdown():
    cfg = GovernorConfig(objective="NET", base_risk_pct=1.0, min_risk_dollars=1.0, dd_throttle_tol_pct=10.0)
    s = _state()
    s.update(1_000.0, 'd1')
    s.roll_day('d2')
    top = decide_risk(s, cfg).risk_dollars
    s.update(-800.0, 'd2')
    s.roll_day('d3')
    assert decide_risk(s, cfg).risk_dollars < top


def test_finished_accounts_do_not_trade():
    s = _state()
    s.phase = "breached"
    assert not decide_risk(s, GovernorConfig()).allow


def test_contract_sizing_never_exceeds_risk():
    kind, n = contracts_for_risk(500.0, 10.0, 20.0, 2.0, 5, 50)
    assert (kind, n) == ("mini", 2)                    # 10 pts x $20 = $200 per mini -> 2 fit in $500
    kind, n = contracts_for_risk(150.0, 10.0, 20.0, 2.0, 5, 50)
    assert (kind, n) == ("micro", 7)                   # a mini would risk $200 > $150, so micros ($20 each)
    assert contracts_for_risk(5.0, 10.0, 20.0, 2.0, 5, 50)[1] == 0
