"""Deterministic default agents. They need no language model: each is a thin, auditable wrapper over modules that already exist.
A language model can be plugged in as ``narrate`` to add commentary; it never changes a verdict.

Each ``act_*`` function takes the desk, the candidate context and returns the filed artifact. Heavy work (the full pipeline, a
backtest) is injected through ``ctx`` so the desk stays testable and never starts a job on its own.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from app.ai.agent_desk.desk import Artifact, Desk


@dataclass
class Context:
    candidate: str                               # e.g. "tsmom_vol_targeted@ES/5m"
    family: str = ""
    instrument: str = ""
    timeframe: str = ""
    build_fn: Callable[[dict], dict] | None = None            # spec -> {"config":..., "code_ref":...}
    bars: object = None                                        # DataFrame for conformance checks
    trades: list = field(default_factory=list)
    pipeline_result: dict | None = None                        # verdict dict from the full pipeline (verdict, reasons, gate_vector, mc, ...)
    book_corr: float | None = None                             # correlation of this strategy's daily R to the running book
    narrate: Callable[[str, dict], str] | None = None


def _note(ctx: Context, role: str, body: dict) -> dict:
    if ctx.narrate:
        try:
            body = {**body, "commentary": ctx.narrate(role, body)}
        except Exception:  # noqa: BLE001
            pass
    return body


def act_scout(desk: Desk, agent_id: str, ctx: Context, *, limit: int = 5) -> list[Artifact]:
    """Leads = open families with real evidence that the coverage ledger says are under-tested. Closed families are never proposed."""
    from app.research_ledger import closed_families, coverage_summary, grade_table
    closed = set(closed_families()) if callable(closed_families) else set()
    cov = coverage_summary(sync=False)
    thin = set(cov.get("thin_high_evidence", [])) | set(cov.get("never_tested", []))
    rank = {"A": 0, "B": 1, "C": 2, "D": 3}
    rows = [r for r in grade_table() if r["family"] not in closed and r["status"] != "blocked" and r["family"] in thin]
    rows.sort(key=lambda r: (rank.get(r["grade"], 4), r["number"]))
    out = []
    for r in rows[:limit]:
        out.append(desk.file(agent_id, "lead", _note(ctx, "scout", {"family": r["family"], "grade": r["grade"], "basis": r["basis"], "why": "under-tested and not closed"}),
                             candidate=f"{r['family']}@{ctx.instrument or '*'}/{ctx.timeframe or '*'}"))
    return out


def act_designer(desk: Desk, agent_id: str, ctx: Context, lead: Artifact, *, stated_trades_per_day: float | None = None, session: str | None = None) -> Artifact:
    from app.research_ledger import family_grade
    g = family_grade(ctx.family or lead.body.get("family")) or {}
    spec = {"family": ctx.family or lead.body.get("family"), "mechanism": g.get("hypothesis") or lead.body.get("basis"), "instruments": ctx.instrument,
            "timeframe": ctx.timeframe, "trades_per_day": stated_trades_per_day, "session": session, "evidence_grade": g.get("grade")}
    return desk.file(agent_id, "spec", _note(ctx, "designer", spec), parents=[lead.id], candidate=lead.candidate)


def act_analyst(desk: Desk, agent_id: str, ctx: Context, lead: Artifact, spec: Artifact) -> Artifact:
    from app.research_ledger import is_closed
    fam = spec.body.get("family")
    try:
        closed = bool(is_closed(fam))
    except Exception:  # noqa: BLE001
        closed = False
    body = {"family": fam, "closed": closed, "grade": spec.body.get("evidence_grade"), "feasible": not closed,
            "flags": (["family is CLOSED by the hard close rule; reopen with a written reason first"] if closed else [])}
    return desk.file(agent_id, "analysis", _note(ctx, "analyst", body), parents=[lead.id, spec.id], candidate=spec.candidate)


def act_builder(desk: Desk, agent_id: str, ctx: Context, spec: Artifact, analysis: Artifact) -> Artifact:
    if analysis.body.get("closed"):
        raise ValueError("builder will not build a closed family")
    built = ctx.build_fn(dict(spec.body)) if ctx.build_fn else {"config": {"family": spec.body.get("family")}, "code_ref": None}
    return desk.file(agent_id, "build", _note(ctx, "builder", {"spec": spec.id, **built}), parents=[spec.id, analysis.id], candidate=spec.candidate)


def act_verifier(desk: Desk, agent_id: str, ctx: Context, spec: Artifact, build: Artifact, *, full: bool = False) -> Artifact:
    """Spec conformance on the BUILD's trades. Not measured when no trades/bars were supplied -- never a pass by default."""
    if ctx.bars is None or not ctx.trades:
        return desk.file(agent_id, "verification", {"measured": False, "note": "no bars/trades supplied"}, subject=build.id, parents=[spec.id],
                         verdict="NOT_MEASURED", candidate=spec.candidate)
    from app.validation import spec_conformance as sc
    s = sc.SpecConformanceSpec.from_spec_card(spec.body, instrument=ctx.instrument)
    res = (sc.run_pass2 if full else sc.run_pass1)(ctx.bars, ctx.trades, s)
    verdict = {"PASS": "PASS", "WARN": "PASS", "FAIL": "FAIL", "UNMEASURED": "NOT_MEASURED"}[res.status]
    if res.worst == sc.MAJOR:
        verdict = "MARGINAL"
    return desk.file(agent_id, "verification", {"result": res.to_dict(), "pass": res.pass_name}, subject=build.id, parents=[spec.id], verdict=verdict, candidate=spec.candidate)


def act_quant(desk: Desk, agent_id: str, ctx: Context, spec: Artifact, build: Artifact) -> Artifact:
    """Reads the pipeline's own verdict; the quant adds no opinion that could lift it."""
    pr = ctx.pipeline_result
    if not pr:
        return desk.file(agent_id, "quant_review", {"measured": False, "note": "no pipeline result supplied"}, subject=build.id, parents=[spec.id],
                         verdict="NOT_MEASURED", candidate=spec.candidate)
    v = str(pr.get("verdict", "")).upper().replace(" ", "_")
    verdict = {"READY": "PASS", "MARGINAL": "MARGINAL", "NOT_READY": "FAIL"}.get(v, "NOT_MEASURED")
    gv = pr.get("gate_vector") or {}
    return desk.file(agent_id, "quant_review", {"pipeline_verdict": pr.get("verdict"), "capping": gv.get("capping"), "failing": gv.get("failing"),
                                                 "reasons": list(pr.get("reasons") or [])[:6]}, subject=build.id, parents=[spec.id], verdict=verdict, candidate=spec.candidate)


def act_portfolio(desk: Desk, agent_id: str, ctx: Context, spec: Artifact, build: Artifact, ver: Artifact, qr: Artifact) -> Artifact:
    c = ctx.book_corr
    share = 1.0 if c is None else max(0.0, 1.0 - abs(float(c)))
    return desk.file(agent_id, "allocation", {"book_corr": c, "risk_share": round(share, 2),
                                              "note": "no book supplied: full share" if c is None else "share scales down with correlation to the running book"},
                     parents=[spec.id, build.id, ver.id, qr.id], candidate=spec.candidate)


def act_prop(desk: Desk, agent_id: str, ctx: Context, spec: Artifact, build: Artifact, ver: Artifact, qr: Artifact) -> Artifact:
    pr = ctx.pipeline_result or {}
    mc = pr.get("mc") or {}
    return desk.file(agent_id, "prop_plan", {"per_attempt_pass_pct": mc.get("per_attempt_pass_probability"), "payout": pr.get("payout"),
                                              "note": "figures come from the pipeline's own Monte Carlo; none are estimated here"},
                     parents=[spec.id, build.id, ver.id, qr.id], candidate=spec.candidate)


def act_head(desk: Desk, agent_id: str, ctx: Context, evidence: list[Artifact]) -> Artifact:
    """Strictest decision the evidence supports. PROMOTE needs a PASS from both reviewers; FORWARD_TEST allows a MARGINAL quant verdict."""
    by = {a.kind: a for a in evidence}
    ver, qr = by.get("verification"), by.get("quant_review")
    if not ver or not qr or "NOT_MEASURED" in (ver.verdict, qr.verdict):
        d, why = "REWORK", "a review is missing or was not measured"
    elif "FAIL" in (ver.verdict, qr.verdict):
        d, why = "REJECT", "a reviewer failed the build"
    elif ver.verdict == "PASS" and qr.verdict == "PASS":
        d, why = "PROMOTE", "both reviewers passed"
    elif ver.verdict == "PASS" and qr.verdict == "MARGINAL":
        d, why = "FORWARD_TEST", "verified; the edge is not proven enough to fund"
    else:
        d, why = "REWORK", "the verifier raised major findings"
    return desk.file(agent_id, "decision", {"why": why}, parents=[a.id for a in evidence], verdict=d, candidate=evidence[0].candidate)


def run_candidate(desk: Desk, ctx: Context, lead: Artifact, *, full_verify: bool = False) -> Artifact:
    """Run one candidate through all nine roles. Returns the head of desk's decision."""
    r = desk.by_role
    spec = act_designer(desk, r["designer"].id, ctx, lead)
    ana = act_analyst(desk, r["analyst"].id, ctx, lead, spec)
    if ana.body.get("closed"):
        return desk.file(r["head_of_desk"].id, "decision", {"why": "family closed"}, parents=[lead.id, spec.id, ana.id], verdict="REJECT", candidate=lead.candidate)
    build = act_builder(desk, r["builder"].id, ctx, spec, ana)
    ver = act_verifier(desk, r["verifier"].id, ctx, spec, build, full=full_verify)
    qr = act_quant(desk, r["quant"].id, ctx, spec, build)
    alloc = act_portfolio(desk, r["portfolio_manager"].id, ctx, spec, build, ver, qr)
    prop = act_prop(desk, r["prop_strategist"].id, ctx, spec, build, ver, qr)
    return act_head(desk, r["head_of_desk"].id, ctx, [lead, spec, ana, build, ver, qr, alloc, prop])
