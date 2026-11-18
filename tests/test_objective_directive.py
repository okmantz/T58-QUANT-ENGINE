"""The three objectives are standing directives, not labels: the numbers, the isolation and the generated docs must agree with the code."""
from __future__ import annotations

from pathlib import Path

import pytest

from app import objectives as O
from app.prop import thirty_day as T

ROOT = Path(__file__).resolve().parents[1]


def test_horizons_match_the_thirty_day_module():
    assert O.A_TARGET_DAYS == T.DEFAULT_HORIZON_DAYS == 30
    assert O.A_MAX_DAYS == T.DEFAULT_LONG_HORIZON_DAYS == 60
    assert O.DIRECTIVES["A"].horizon_days == 30 and O.DIRECTIVES["A"].horizon_max_days == 60
    # B has no deadline in the owner's wording; 365 days is the measurement window the scorecard reads its probabilities at (a first payout inside a year)
    assert O.DIRECTIVES["B"].horizon_days is None and O.B_PAYOUT_HORIZON_DAYS == 365


@pytest.mark.parametrize("spelling,key", [("A", "A"), ("Objective A", "A"), ("pass", "A"), ("B", "B"), ("Objective B", "B"), ("payout", "B"), ("C", "NET"),
                                          ("Objective C", "NET"), ("compounder", "NET"), ("net_profit_compounder", "NET"), ("NET", "NET")])
def test_every_spelling_maps_to_its_objective(spelling, key):
    assert O.normalize_objective(spelling) == key


def test_the_owners_wording_is_verbatim():
    assert "The goal is to pass" in O.DIRECTIVES["A"].goal and "not to preserve the account long-term" in O.DIRECTIVES["A"].goal
    assert "The goal is to get paid and keep the account alive" in O.DIRECTIVES["B"].goal
    assert "The goal is to grow capital and maximize net wealth" in O.DIRECTIVES["C" if "C" in O.DIRECTIVES else "NET"].goal
    for must in ("independent strategy discovery", "Never optimize a strategy for one objective using another objective's priorities",
                 "judged exclusively by how effectively they accomplish their assigned mission"):
        assert must in O.ENGINE_DIRECTIVE


def test_each_objective_has_its_own_primary_and_secondary_metrics():
    prim = {k: d.primary_metric for k, d in O.DIRECTIVES.items()}
    assert len(set(prim.values())) == 3
    assert "median days to pass" in " ".join(O.DIRECTIVES["A"].secondary_metrics).lower()
    assert "calmar" in " ".join(O.DIRECTIVES["NET"].secondary_metrics).lower()
    assert O.DIRECTIVES["NET"].overnight_allowed and not O.DIRECTIVES["A"].overnight_allowed and not O.DIRECTIVES["B"].overnight_allowed


CHAMP = {"name": "x", "thirty_day": {"p_pass_30": 62.0, "lower_bound": 41.0, "p_bust_30": 20.0, "median_days": 9}, "p_pass_30": 62.0, "lower_bound": 41.0,
         "p_paid": 55.0, "mean_payout_usd": 2100.0, "net_objective": 3.2, "funded_survival": 71.0, "cagr": 18.0, "calmar": 2.1, "p_bust_30": 20.0}


@pytest.mark.parametrize("obj", ["A", "B", "NET"])
def test_isolation_never_changes_the_ranking_it_protects(obj):
    """Ranking a champion stripped of ANOTHER objective's numbers gives the same key: nothing foreign was moving the order."""
    iso = O.isolated_champion(obj, CHAMP)
    assert O.champion_rank_key(obj, iso) == O.champion_rank_key(obj, CHAMP)
    for foreign in O.DIRECTIVES[O.normalize_objective(obj)].forbidden_inputs:
        assert foreign not in iso


def test_forbidden_inputs_are_disjoint_from_each_objectives_own_metrics():
    own = {"A": {"p_pass_30", "lower_bound", "p_bust_30"}, "B": {"p_paid", "mean_payout_usd", "funded_survival"}, "NET": {"net_objective", "cagr", "calmar"}}
    for k, mine in own.items():
        assert not (set(O.DIRECTIVES[k].forbidden_inputs) & mine), k


def test_generated_markdown_names_all_three_and_the_engine_directive():
    md = O.directive_markdown()
    for s in ("OBJECTIVE A: EVALUATION PASSER", "OBJECTIVE B: PAYOUT HUNTER", "OBJECTIVE C: NET PROFIT COMPOUNDER", "ENGINE DIRECTIVE"):
        assert s in md
    on_disk = ROOT / "docs" / "OBJECTIVES.md"
    if on_disk.exists():
        assert on_disk.read_text(encoding="utf-8").strip() == md.strip(), "docs/OBJECTIVES.md is stale: regenerate with python -c 'from app.objectives import directive_markdown; ...'"


def test_directive_endpoint_serves_the_same_text():
    from app.web.server import app
    r = app.test_client().get("/trading-bots/api/directive").get_json()
    assert r["ok"] and r["engine_directive"] == O.ENGINE_DIRECTIVE and set(r["objectives"]) == {"A", "B", "NET"}


def test_shipped_bots_follow_their_objective():
    from app.bots.presets import preset_configs
    by = {c.id: c for c in preset_configs()}
    assert by["bot-pass"].objective == "A" and by["bot-payout"].objective == "B" and by["bot-profit"].objective == "NET"
    assert by["bot-profit"].account.venue == "paper" and any(lg.kind == "gate27" for lg in by["bot-profit"].legs)
    for bid in ("bot-pass", "bot-payout"):
        assert by[bid].account.preset_key and not any(lg.kind == "gate27" for lg in by[bid].legs)      # a prop account must be flat overnight
    assert len(by["bot-pass"].legs) >= 3 and len(by["bot-payout"].legs) >= 2 and len([lg for lg in by["bot-profit"].legs if lg.kind != "gate27"]) >= 5
