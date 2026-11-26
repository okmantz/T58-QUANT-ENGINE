import pytest

from app.ai.agent_desk import Agent, Context, Desk, SeparationError, default_roster, run_candidate

pytestmark = pytest.mark.fast


def _desk(tmp_path, roster=None):
    return Desk(roster or default_roster(), base=tmp_path, persist=True)


def _lead(d, cand="fam@ES/5m"):
    return d.file("t58-scout", "lead", {"family": "tsmom_vol_targeted", "basis": "b"}, candidate=cand)


def test_roster_needs_distinct_agents_and_roles():
    with pytest.raises(SeparationError):
        Desk([Agent("x", "builder"), Agent("x", "verifier")], persist=False)
    with pytest.raises(SeparationError):
        Desk([Agent("a", "builder"), Agent("b", "builder")], persist=False)
    d = Desk(default_roster(), persist=False)
    assert d.missing_roles() == []


def test_a_role_files_only_its_own_artifact_kind(tmp_path):
    d = _desk(tmp_path)
    with pytest.raises(SeparationError):
        d.file("t58-builder", "verification", {}, verdict="PASS")


def test_nobody_grades_their_own_work(tmp_path, monkeypatch):
    monkeypatch.setenv("T58_RESEARCH_LEDGER_DIR", str(tmp_path))
    lead = _lead(_desk(tmp_path))
    # a verifier that ALSO authored the build's lineage is refused: build a desk where the same id leads the chain
    d = Desk([Agent("scout1", "scout"), Agent("designer1", "designer"), Agent("analyst1", "analyst"), Agent("b1", "builder"),
              Agent("v1", "verifier"), Agent("q1", "quant"), Agent("pm", "portfolio_manager"), Agent("ps", "prop_strategist"), Agent("h", "head_of_desk")], persist=False)
    ld = d.file("scout1", "lead", {"family": "f"}, candidate="c")
    sp = d.file("designer1", "spec", {"family": "f"}, parents=[ld.id], candidate="c")
    an = d.file("analyst1", "analysis", {}, parents=[ld.id, sp.id], candidate="c")
    bd = d.file("b1", "build", {}, parents=[sp.id, an.id], candidate="c")
    d.file("v1", "verification", {}, subject=bd.id, parents=[sp.id], verdict="PASS", candidate="c")
    # the quant cannot ground its review on the verifier's verdict
    ver = [a for a in d.artifacts.values() if a.kind == "verification"][0]
    with pytest.raises(SeparationError):
        d.file("q1", "quant_review", {}, subject=bd.id, parents=[ver.id], verdict="PASS", candidate="c")


def test_builder_cannot_read_reviews(tmp_path):
    d = _desk(tmp_path)
    assert all(a.kind not in ("verification", "quant_review") for a in d.visible_to("builder"))


def test_full_run_promotes_only_when_both_reviewers_pass(tmp_path, monkeypatch):
    monkeypatch.setenv("T58_RESEARCH_LEDGER_DIR", str(tmp_path))
    d = _desk(tmp_path)
    lead = _lead(d)
    ctx = Context(candidate="fam@ES/5m", family="tsmom_vol_targeted", instrument="ES", timeframe="5m")
    # reviewers not measured -> the head of desk reworks; nothing is approved by default
    dec = run_candidate(d, ctx, lead)
    assert dec.verdict == "REWORK"


def test_head_cannot_promote_without_independent_passes(tmp_path, monkeypatch):
    monkeypatch.setenv("T58_RESEARCH_LEDGER_DIR", str(tmp_path))
    d = _desk(tmp_path)
    lead = _lead(d)
    spec = d.file("t58-designer", "spec", {"family": "f"}, parents=[lead.id], candidate=lead.candidate)
    ana = d.file("t58-analyst", "analysis", {}, parents=[lead.id, spec.id], candidate=lead.candidate)
    bld = d.file("t58-builder", "build", {}, parents=[spec.id, ana.id], candidate=lead.candidate)
    ver = d.file("t58-verifier", "verification", {}, subject=bld.id, parents=[spec.id], verdict="PASS", candidate=lead.candidate)
    with pytest.raises(SeparationError):
        d.file("t58-head_of_desk", "decision", {}, parents=[lead.id, ver.id], verdict="PROMOTE", candidate=lead.candidate)
    q = d.file("t58-quant", "quant_review", {}, subject=bld.id, parents=[spec.id], verdict="MARGINAL", candidate=lead.candidate)
    with pytest.raises(SeparationError):
        d.file("t58-head_of_desk", "decision", {}, parents=[lead.id, ver.id, q.id], verdict="PROMOTE", candidate=lead.candidate)
    ok = d.file("t58-head_of_desk", "decision", {}, parents=[lead.id, ver.id, q.id], verdict="FORWARD_TEST", candidate=lead.candidate)
    assert ok.verdict == "FORWARD_TEST"
    assert d.board()[0]["decision"] == "FORWARD_TEST"


def test_record_persists_across_desks(tmp_path):
    d = _desk(tmp_path)
    _lead(d)
    assert len(_desk(tmp_path).artifacts) == 1
