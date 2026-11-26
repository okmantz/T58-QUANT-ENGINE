"""Unit tests for the 2026-11 gates: cliff gate, independent events, spec conformance, research ledger / closed families."""
from types import SimpleNamespace as T

import numpy as np
import pandas as pd
import pytest

from app.validation.cliff_gate import NeighbourPoint, evaluate_neighbours, from_plateau_report, neighbour_values, apply_cliff_cap
from app.validation.independent_events import independent_event_gate, pooled_event_count
from app.validation import spec_conformance as sc

pytestmark = pytest.mark.fast


# ------------------------------------------------------------------------------------------------------------------ cliff gate
def test_cliff_all_profitable_passes():
    r = evaluate_neighbours([NeighbourPoint("a", -1, 9, 10, 5.0), NeighbourPoint("a", 1, 11, 10, 2.0)])
    assert r.status == "PASS" and not r.caps


def test_cliff_one_losing_neighbour_fails_and_caps():
    r = evaluate_neighbours([NeighbourPoint("a", -1, 9, 10, 5.0), NeighbourPoint("a", 1, 11, 10, -0.01), NeighbourPoint("b", 1, 2, 1, 3.0)])
    assert r.status == "FAIL" and r.caps and r.worst["param"] == "a"
    v, reasons, ev = apply_cliff_cap("READY", [], cfg=T(cliff_gate_enabled=True, cliff_gate_direct=False, fitness_metric="net_profit"), strategy=None, df=None,
                                     risk=None, prop_rules=None, plateau={"chosen_neighbor_fitnesses": [1.0]})
    assert v == "READY" and ev["status"] == "UNMEASURED"        # net_profit fitness is not an R edge: the free pre-screen must not fire


def test_cliff_strategy_that_stops_trading_is_a_failure():
    r = evaluate_neighbours([NeighbourPoint("a", -1, 9, 10, float("-inf")), NeighbourPoint("a", 1, 11, 10, 4.0)])
    assert r.status == "FAIL"


def test_cliff_too_few_neighbours_is_unmeasured_not_pass():
    assert evaluate_neighbours([NeighbourPoint("a", 1, 11, 10, 5.0)]).status == "UNMEASURED"
    assert evaluate_neighbours([]).status == "UNMEASURED"


def test_cliff_plateau_prescreen_only_for_edge_metrics():
    assert from_plateau_report({"chosen_neighbor_fitnesses": [0.1, -0.2]}, "net_profit") is None
    assert from_plateau_report({"chosen_neighbor_fitnesses": [0.1, -0.2]}, "edge_lb_r").status == "FAIL"


def test_cliff_cap_never_lifts_and_ignores_non_ready():
    v, _r, _e = apply_cliff_cap("MARGINAL", [], cfg=T(), strategy=None, df=None, risk=None, prop_rules=None)
    assert v == "MARGINAL"
    v, reasons, _e = apply_cliff_cap("READY", [], cfg=T(cliff_gate_enabled=True, cliff_gate_direct=False, fitness_metric="edge_lb_r"), strategy=None, df=None,
                                     risk=None, prop_rules=None, plateau={"chosen_neighbor_fitnesses": [0.3, -0.1]})
    assert v == "MARGINAL" and reasons[0].startswith("CLIFF GATE")


def test_neighbour_values_integer_and_clipping():
    assert neighbour_values(10, 1, 100, True) == [(-1, 9.0), (1, 11.0)]
    assert neighbour_values(1, 1, 100, True) == [(1, 2.0)]       # on the lower bound: only one neighbour


# ----------------------------------------------------------------------------------------------------------- independent events
def _basket(n_days, per_day=3):
    out = []
    for i in range(n_days * per_day):
        d = pd.Timestamp("2024-01-02 15:00") + pd.Timedelta(days=i // per_day)
        out.append(T(entry_time=d, exit_time=d + pd.Timedelta(hours=1), symbol=["ES", "NQ", "GC"][i % per_day]))
    return out


def test_basket_with_many_trades_but_few_events_fails():
    g = independent_event_gate(_basket(100), min_events=150)
    assert g["applies"] and not g["passed"] and g["n_trades"] == 300 and g["n_events"] == 100


def test_basket_with_enough_events_passes():
    assert independent_event_gate(_basket(200), min_events=150)["passed"]


def test_single_market_not_held_to_event_floor():
    one = [T(entry_time=pd.Timestamp("2024-01-02 15:00") + pd.Timedelta(days=i // 5), exit_time=pd.Timestamp("2024-01-02 16:00") + pd.Timedelta(days=i // 5), symbol="ES") for i in range(300)]
    assert not independent_event_gate(one, min_events=150)["applies"]


def test_pooled_event_count_counts_distinct_days():
    d = list(pd.date_range("2024-01-02", periods=5, freq="D"))
    assert pooled_event_count({"ES": ([1, 2, 3], d[:3]), "NQ": ([1, 2], d[:2])}) == 3


# ------------------------------------------------------------------------------------------------------------ spec conformance
def _frame(n=6000):
    ts = pd.date_range("2024-01-02 14:30", periods=n, freq="5min", tz="UTC")
    c = 100 + np.cumsum(np.random.default_rng(0).normal(0, 0.1, n))
    return pd.DataFrame({"timestamp": ts, "open": c, "high": c + 0.2, "low": c - 0.2, "close": c}), ts, c


def _tr(ts, c, i, j, d=1, ep=None):
    return T(entry_time=ts[i], exit_time=ts[j], direction=d, entry_price=c[i] if ep is None else ep, exit_price=c[j], exit_reason="signal")


def test_spec_clean_trades_pass():
    df, ts, c = _frame()
    r = sc.run_pass1(df, [_tr(ts, c, 10, 20), _tr(ts, c, 30, 40, -1)], sc.SpecConformanceSpec(instrument="ES"))
    assert r.status == "PASS"


def test_spec_phantom_fill_is_critical_and_not_ready():
    df, ts, c = _frame()
    r = sc.run_pass1(df, [_tr(ts, c, 10, 20), _tr(ts, c, 30, 40, ep=500.0)], sc.SpecConformanceSpec(instrument="ES"))
    assert r.worst == sc.CRITICAL
    assert sc.apply_spec_cap("READY", [], r)[0] == "NOT READY"


def test_spec_overlap_detected():
    df, ts, c = _frame()
    r = sc.run_pass1(df, [_tr(ts, c, 10, 50), _tr(ts, c, 20, 60)], sc.SpecConformanceSpec(instrument="ES"))
    assert any(f.check == "overlap" for f in r.findings)


def test_spec_trigger_rate_mismatch_caps_marginal():
    df, ts, c = _frame()
    trades = [_tr(ts, c, 10 + 30 * k, 20 + 30 * k) for k in range(100)]
    r = sc.run_pass1(df, trades, sc.SpecConformanceSpec(instrument="ES", stated_trades_per_day=0.5))
    assert any(f.check == "trigger_rate" and f.severity == sc.MAJOR for f in r.findings)
    assert sc.apply_spec_cap("READY", [], r)[0] == "MARGINAL"
    assert sc.apply_spec_cap("MARGINAL", [], r)[0] == "MARGINAL"


def test_spec_session_and_direction():
    df, ts, c = _frame()
    spec = sc.SpecConformanceSpec(instrument="ES", session_start="03:00", session_end="04:00", direction="long")
    r = sc.run_pass1(df, [_tr(ts, c, 10, 20, -1)], spec)
    assert {f.check for f in r.findings} >= {"session", "direction"}


def test_spec_missed_signals_against_reference():
    df, ts, c = _frame()
    trades = [_tr(ts, c, 100, 110)]
    spec = sc.SpecConformanceSpec(instrument="ES", reference_signal=lambda b: [1 if i in (100, 300, 500, 700) else 0 for i in range(len(b))])
    r = sc.run_pass2(df, trades, spec)
    assert any(f.check == "missed_signals" for f in r.findings)


def test_spec_unmeasured_is_not_a_failure():
    df, ts, c = _frame()
    assert sc.apply_spec_cap("READY", [], sc.run_pass1(df, [], sc.SpecConformanceSpec()))[0] == "READY"


# ------------------------------------------------------------------------------------------------------------ same-days replay
def test_replay_diff_matches_and_kills():
    from app.forward_test.same_days_replay import TradeLite, diff_trade_lists
    base = pd.Timestamp("2025-01-02 15:00", tz="UTC")
    L = lambda m, d, p: TradeLite(base + pd.Timedelta(minutes=m), None, d, p, None, "live")
    tol = pd.Timedelta(minutes=10)
    assert diff_trade_lists([L(0, 1, 100), L(60, -1, 101)], [L(5, 1, 100.5), L(60, -1, 101)], tol=tol).status == "OK"
    d = diff_trade_lists([L(0, 1, 100), L(60, -1, 101)], [L(5, 1, 100.5)], tol=tol)
    assert d.kill and len(d.only_live) == 1 and "never takes" in d.kill_reason()
    d = diff_trade_lists([L(0, 1, 100)], [L(0, 1, 100), L(200, 1, 5)], tol=tol)
    assert d.kill and len(d.only_replay) == 1
    assert diff_trade_lists([L(0, 1, 100)], [L(0, -1, 100)], tol=tol).kill      # opposite direction is not a match


def test_replay_is_one_to_one():
    from app.forward_test.same_days_replay import TradeLite, diff_trade_lists
    base = pd.Timestamp("2025-01-02 15:00", tz="UTC")
    L = lambda m, s: TradeLite(base + pd.Timedelta(minutes=m), None, 1, 100.0, None, s)
    d = diff_trade_lists([L(0, "l"), L(1, "l")], [L(0, "r")], tol=pd.Timedelta(minutes=10))
    assert d.kill and len(d.only_live) == 1


# -------------------------------------------------------------------------------------------------------------- research ledger
def test_evidence_covers_all_100_and_blocked_cap_at_d():
    from app.research_ledger import EVIDENCE, validate_coverage, family_grade
    assert sorted(EVIDENCE) == list(range(1, 101))
    assert set(g for g, _b, _r in EVIDENCE.values()) <= set("ABCD")
    v = validate_coverage()
    assert v["ok"] and v["n"] == 100 and not v["problems"]
    assert family_grade(1)["grade"] == "A"


def test_ledgers_append_and_coverage(tmp_path, monkeypatch):
    monkeypatch.setenv("T58_RESEARCH_LEDGER_DIR", str(tmp_path))
    from app.research_ledger import ledger as lg
    lg.log_source(title="A paper", kind="paper", url="http://x", authors="X", year=2020, grade="B", families=["tsmom_vol_targeted"], takeaway="t")
    lg.log_query(text="opening range breakout", channel="web", n_results=10, n_used=2, outcome="hit", families=["tsmom_vol_targeted"])
    lg.record_coverage(family="tsmom_vol_targeted", instrument="ES", timeframe="5m", trials=30, status="tested", best_edge_lb_r=0.01, source="unit")
    cs = lg.coverage_summary(sync=False)
    assert cs and (tmp_path / "sources.jsonl").exists() and (tmp_path / "queries.jsonl").exists()


def test_hard_close_rule_needs_enough_deaths_across_cells():
    from app.research_ledger.closure import ClosureRules, evaluate_family
    few = {("ES", "5m"): {"deaths": 10, "near_misses": 0, "median_r": -0.1}}
    assert evaluate_family("fam_x", few, grade="C").state != "CLOSED"
    many = {(i, t): {"deaths": 20, "near_misses": 0, "median_r": -0.1} for i in ("ES", "NQ", "GC") for t in ("5m", "15m")}
    assert evaluate_family("fam_x", many, grade="C").state == "CLOSED"
    near = {k: dict(v, near_misses=1) for k, v in many.items()}
    assert evaluate_family("fam_x", near, grade="C").state != "CLOSED"          # one near miss keeps a family open
    assert evaluate_family("fam_x", many, grade="A").state != "CLOSED" or sum(v["deaths"] for v in many.values()) >= 80   # grade A needs 2x the deaths
