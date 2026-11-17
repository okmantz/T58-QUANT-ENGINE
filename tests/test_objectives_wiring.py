from __future__ import annotations

import importlib

import pytest

from app import objectives as O


def test_normalize_aliases():
    assert O.normalize_objective("pass") == "A" and O.normalize_objective("payout") == "B"
    assert O.normalize_objective("net_profit") == "NET" and O.normalize_objective("") == "BLEND"
    assert O.normalize_objective("zzz", default="A") == "A"


def test_every_objective_maps_to_every_engine():
    for k in O.OBJECTIVES:
        s = O.spec_for(k)
        assert s.lifecycle_mode and s.engine_mode and s.governor in ("A", "B", "NET")
        assert O.lifecycle_mode(k) == s.lifecycle_mode and O.engine_mode(k) == s.engine_mode
    assert not O.spec_for("NET").uses_prop_rules and O.spec_for("A").uses_prop_rules and O.spec_for("B").uses_prop_rules
    assert O.engine_mode("A") == "pass" and O.engine_mode("B") == "payout" and O.engine_mode("NET") == "net_profit"


def _resolve(path: str):
    module, attr = path.split(":")
    obj = importlib.import_module(module)
    for part in attr.split("."):
        if hasattr(obj, part):
            obj = getattr(obj, part)
        elif hasattr(obj, "__dataclass_fields__") and part in obj.__dataclass_fields__:
            obj = obj.__dataclass_fields__[part]
        else:
            raise AssertionError(f"{path}: no attribute {part!r}")
    return obj


def test_engine_wiring_points_at_real_code():
    for name, path in O.ENGINE_WIRING.items():
        assert _resolve(path) is not None, name


def test_engine_config_objects_accept_objective_mode():
    from app.evolution.engine import EvolutionConfig
    from app.orchestration.speed_run import SpeedRunConfig
    from app.portfolio.portfolio import PortfolioConfig
    for cls in (EvolutionConfig, SpeedRunConfig, PortfolioConfig):
        assert "objective_mode" in cls.__dataclass_fields__, cls


def test_engine_modes_and_fitness_per_objective():
    assert O.engine_mode("pass") == "pass" and O.governor_objective("payout") == "B" and O.governor_objective("blend") == "A"
    assert O.evolution_goal_preset("A") == "eval_pass_rate" and O.evolution_goal_preset("NET") == "net_profit"
    assert O.fitness_metric("NET") != O.fitness_metric("A")
    assert O.portfolio_score_metric("NET") != O.portfolio_score_metric("A")


def test_champion_ranking_differs_by_objective():
    fast = {"thirty_day": {"lower_bound": 0.6, "p_pass_30": 0.7, "p_bust_30": 0.3, "p_paid": 0.1, "mean_payout_usd": 100}, "edge_lb_r": 0.05}
    steady = {"thirty_day": {"lower_bound": 0.2, "p_pass_30": 0.3, "p_bust_30": 0.1, "p_paid": 0.6, "mean_payout_usd": 900}, "edge_lb_r": 0.08}
    assert O.champion_rank_key("A", fast) > O.champion_rank_key("A", steady)
    assert O.champion_rank_key("B", steady) > O.champion_rank_key("B", fast)


def test_bot_engine_net_goal_ignores_prop_rules_on_sandbox():
    from app.bots.engine import rules_for_account
    from app.bots.models import AccountLink
    acc = AccountLink(venue="paper", account_id="sandbox", size=50_000.0, preset_key="")
    net, _, _ = rules_for_account(acc, objective="NET")
    a, _, _ = rules_for_account(acc, objective="A")
    assert net.profit_target >= 1e11
    assert a.profit_target < 1e11


def test_discovery_request_takes_the_objective():
    import dataclasses
    from app.discovery_engine.engine import EngineRequest
    assert "objective_mode" in {f.name for f in dataclasses.fields(EngineRequest)}
