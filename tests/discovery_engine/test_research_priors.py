import json
from pathlib import Path
from app.discovery_engine import research_priors as rp
from app.search.graveyard import param_signature  # noqa: F401  (import sanity: sibling module still loads)


def test_priors_load_and_are_well_formed():
    rows = rp.load_priors()
    assert len(rows) >= 25
    for r in rows:
        for k in ("experiment", "verdict", "headline", "lesson", "tags", "related_engine_families"):
            assert k in r


def test_related_families_exist_in_engine_seed():
    seed = Path(rp.PRIORS_PATH).parent / "graveyard_seed.jsonl"
    fams = {json.loads(l)["family"] for l in seed.read_text().splitlines() if l.strip()}
    named = {f for r in rp.load_priors() for f in r["related_engine_families"]}
    assert named <= fams, sorted(named - fams)


def test_family_notes_and_survivor_flag():
    assert "smc_experiment" in rp.family_prior_note("order_block_reaction")
    assert rp.family_prior_note("no_such_family") == ""
    assert rp.family_is_research_survivor("ichimoku_cloud_trend")
    assert not rp.family_is_research_survivor("order_block_reaction")
