"""Audit A-R1 / B-4: one explicit cost policy, applied by every path."""
from __future__ import annotations

import pandas as pd
import pytest

from app.backtest import cost_policy as cp
from app.backtest.risk import RiskConfig
from app.data.instrument_specs import apply_instrument_spec, get_instrument_spec
from app.prop import fee_schedule as fs
from app.search.instrument_risk import resolve_leg_risk, resolve_run_costs


@pytest.fixture(autouse=True)
def _reset_profile():
    cp.set_active_profile(None)
    yield
    cp.set_active_profile(None)


def test_default_profile_is_realistic():
    assert cp.active_profile() == "realistic"


@pytest.mark.parametrize("sym,expected", [("ES", 28.50), ("NQ", 13.50), ("GC", 24.60), ("MES", 3.50), ("MNQ", 2.00), ("MGC", 3.60)])
def test_realistic_round_trip_dollars(sym, expected):
    # spec section 2.3 base: commission + 2 x (1 tick slippage); the spread is folded into the slippage (no double count)
    spec = get_instrument_spec(sym)
    assert spec.round_trip_cost_dollars() == pytest.approx(expected, abs=1e-6)


@pytest.mark.parametrize("sym,expected", [("ES", 54.78), ("NQ", 24.78), ("GC", 45.22), ("MES", 6.32), ("MNQ", 3.32), ("MGC", 5.82)])
def test_stress_round_trip_dollars(sym, expected):
    # methodology 6.9: stress commissions (Alpha all-in) and 2x slippage
    cp.set_active_profile("stress")
    assert get_instrument_spec(sym).round_trip_cost_dollars() == pytest.approx(expected, abs=1e-6)


def test_stress_is_always_costlier_than_realistic():
    for sym in ("ES", "NQ", "GC", "MES", "MNQ", "MGC", "CL", "ZN"):
        spec = get_instrument_spec(sym)
        assert cp.costs_for(spec, "stress").round_trip_dollars(spec.tick_value) > cp.costs_for(spec, "realistic").round_trip_dollars(spec.tick_value)


def test_legacy_profile_reproduces_the_old_convention():
    spec = get_instrument_spec("ES")
    c = cp.costs_for(spec, "legacy")
    assert (c.spread_ticks, c.slippage_ticks) == (1.0, 1.0)


def test_every_resolution_path_charges_the_same_friction():
    for sym in ("ES", "NQ", "MGC"):
        spec = get_instrument_spec(sym)
        base = RiskConfig(pip_size=spec.pip_size)
        a = apply_instrument_spec(base, sym)
        b, _ = resolve_leg_risk(base, pd.DataFrame({"close": [1.0]}), sym)
        c, _ = resolve_run_costs(RiskConfig(pip_size=spec.pip_size, contract_size=spec.contract_size), sym)
        for r in (a, b, c):
            assert r.commission_per_contract == pytest.approx(spec.effective_commission_round_turn)
            assert float(r.slippage_pips) == pytest.approx(spec.default_slippage_pips)
            assert float(r.spread_pips) == pytest.approx(spec.default_spread_pips)


def test_a_typed_value_is_never_overwritten():
    base = RiskConfig(pip_size=1.0, spread_pips=2.0, slippage_pips=0.5, commission_per_trade=9.0, commission_per_contract=1.11)
    out = apply_instrument_spec(base, "ES")
    assert out.spread_pips == 2.0 and out.slippage_pips == 0.5 and out.commission_per_contract == 1.11


def test_fx_spread_is_charged_once_per_round_trip_under_realistic():
    from app.data.instrument_specs import CROSS_MARKET_INSTRUMENTS
    spec = next(iter(CROSS_MARKET_INSTRUMENTS.values()))
    real, stress = cp.costs_for(spec, "realistic"), cp.costs_for(spec, "stress")
    assert real.spread_ticks == pytest.approx(spec.default_spread_ticks / 2.0)
    assert stress.spread_ticks == pytest.approx(spec.default_spread_ticks)


def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError):
        cp.set_active_profile("cheap")


# ---- fee schedule (the structured fees report) -------------------------------------------------------------------------------
def test_fee_schedule_matches_the_report_for_the_headline_firms():
    assert fs.commission_rt("ES", profile="stress") == 4.78 and fs.commission_rt("MGC", profile="stress") == 1.82
    assert fs.commission_rt("ES", firm="topstep", platform="topstepx") == 3.78
    assert fs.commission_rt("GC", firm="apex", platform="rithmic") == 4.62
    assert fs.commission_rt("MNQ", firm="apex", platform="wealthcharts") is None        # unverified: never guessed
    assert fs.commission_rt("ES", firm="leeloo") is None
    lucid50 = fs.plan_fees("lucid", "pro", 50_000)[0]
    assert (lucid50.price, lucid50.reset, lucid50.activation, lucid50.monthly) == (172, 120, 0.0, False)
    assert fs.plan_fees("lucid", "pro", 100_000)[0].tier == fs.ASSUMPTION            # the report lists 100K as UNVERIFIED


def test_cost_per_funded_account_formulas():
    out = fs.cost_per_funded_account(172, 0.60, reset=120)
    assert out["buy_new"] == pytest.approx(286.67, abs=0.01) and out["reset_route"] == pytest.approx(252.0, abs=0.01)
    assert fs.cost_per_funded_account(None, 0.5)["buy_new"] is None
    assert fs.cost_per_funded_account(172, 0.0)["buy_new"] is None
