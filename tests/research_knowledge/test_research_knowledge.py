from app.research_knowledge import FAMILIES, GATES, HYPOTHESES, assistant_brief, status_counts, zero_edge_pass_probability
from app.research_knowledge.methodology import LUCIDPRO


def test_registry_matches_the_study_counts():
    assert len(HYPOTHESES) == 60
    c = status_counts()
    assert c["Active"] == 47 and c["Low confidence"] == 5 and c["Rejected for account type"] == 4
    assert c["Conditional, rule-blocked"] == 2 and c["Rejected as standalone"] == 1 and c["Rejected"] == 1
    assert len({h.id for h in HYPOTHESES}) == 60


def test_only_c05_has_grade_a():
    assert [h.id for h in HYPOTHESES if h.evidence == "A"] == ["C05"]


def test_family_members_exist():
    ids = {h.id for h in HYPOTHESES}
    assert len(FAMILIES) == 11
    assert all(i in ids for f in FAMILIES.values() for i in f[1])


def test_zero_edge_null_matches_the_methodology():
    assert abs(zero_edge_pass_probability(3000, 2000) - 0.241) < 0.001
    assert abs(zero_edge_pass_probability(6000, 3000) - 0.181) < 0.001


def test_lucid_derived_figures_are_consistent():
    for k in ("50K", "100K"):
        r = LUCIDPRO[k]
        assert r["lock_level"] == r["start"] + 100 and r["buffer"] == r["start"] + r["mll"] + 100


def test_gates_and_brief():
    assert list(GATES) == [f"G{i}" for i in range(8)]
    b = assistant_brief()
    assert "24%" in b and "G3" in b


def test_assistant_prompts_carry_the_baseline():
    from app.ai import trading_assistant as ta
    assert "RESEARCH BASELINE" in ta.T58_GROUP_SYSTEM_PROMPT and "RESEARCH BASELINE" in ta.PERSONAL_MODE_SYSTEM_PROMPT
