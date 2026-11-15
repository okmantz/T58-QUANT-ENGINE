

def test_every_hypothesis_sits_in_a_family_and_ranking_is_stable():
    from app.research_knowledge import FAMILIES, HYPOTHESES, rank_engine_families
    in_fam = {i for _n, ids, _t in FAMILIES.values() for i in ids}
    assert {h.id for h in HYPOTHESES} <= in_fam
    for hid, sf in (("B04", "SF3"), ("G02", "SF3"), ("B07", "SF6"), ("H01", "SF8"), ("J03", "SF9")):
        assert hid in FAMILIES[sf][1]
    names = ["trend_breakout", "rsi_extreme_reversion", "order_flow_absorption"]
    assert sorted(rank_engine_families(names)) == sorted(names)
    assert rank_engine_families(names)[-1] == "order_flow_absorption"      # SF6 has no runnable hypothesis on bars
