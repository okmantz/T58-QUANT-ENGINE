"""The nine desk roles and the separation rules between them.

Pipeline of artifacts (each role makes exactly one kind of artifact, from only the kinds it is allowed to read):

    scout -> lead -> designer -> spec -> analyst -> analysis -> builder -> build -> verifier -> verification
                                                                                -> quant -> quant_review
                       portfolio_manager -> allocation    prop_strategist -> prop_plan    head_of_desk -> decision

Separation, enforced by ``Desk`` (not by convention):
  * one agent holds one role; builder, verifier and quant are three DIFFERENT agents with different ids and different sessions
  * a review (verification, quant_review) names the artifact it grades; its author must not appear anywhere in that artifact's lineage
  * the builder never reads verification or quant_review output (it cannot tune to the graders), the verifier and quant never read each
    other's verdicts before filing their own, and the head of desk decides only from filed artifacts (never grades, never builds)
  * nobody can approve their own work: a decision is void if its author appears anywhere in the lineage it rests on
"""
from __future__ import annotations

from dataclasses import dataclass

ARTIFACT_KINDS = ("lead", "spec", "analysis", "build", "verification", "quant_review", "allocation", "prop_plan", "decision")
REVIEW_KINDS = ("verification", "quant_review")


@dataclass(frozen=True)
class Role:
    id: str
    title: str
    purpose: str
    makes: str                 # the one artifact kind this role files
    reads: tuple               # artifact kinds it may read
    grades: tuple = ()         # artifact kinds it may grade (reviews only)
    sees_sealed_checks: bool = False   # may see the thresholds / sealed holdout design (verifier, quant only)


ROLES: dict[str, Role] = {r.id: r for r in (
    Role("scout", "Scout", "Finds candidate ideas: open, well-evidenced, under-tested families and sources. Logs sources and queries to the research ledger.",
         "lead", ()),
    Role("designer", "Designer", "Turns a lead into a pre-registered spec card: mechanism, sign, session, entry/exit, stated trade rate, instruments.",
         "spec", ("lead",)),
    Role("analyst", "Analyst", "Checks the spec against the data and the record: closed-family state, evidence grade, coverage, cost drag, trade count feasibility.",
         "analysis", ("lead", "spec")),
    Role("builder", "Builder", "Implements the spec as a strategy. Never sees how it will be graded.",
         "build", ("spec", "analysis")),
    Role("verifier", "Verifier", "Checks the build does what the spec says: spec-conformance passes, lookahead, calendar and roll handling.",
         "verification", ("spec", "build"), grades=("build",), sees_sealed_checks=True),
    Role("quant", "Quant", "Decides whether the edge is real: validation gates, cliff gate, independent events, cost stress, null, DSR.",
         "quant_review", ("spec", "build"), grades=("build",), sees_sealed_checks=True),
    Role("portfolio_manager", "Portfolio manager", "Sizes a surviving strategy inside the book: correlation to what is already running, risk share.",
         "allocation", ("spec", "build", "verification", "quant_review")),
    Role("prop_strategist", "Prop strategist", "Fits the strategy to the prop firm's rules: pass odds, daily-loss and drawdown rules, payout lifecycle.",
         "prop_plan", ("spec", "build", "verification", "quant_review")),
    Role("head_of_desk", "Head of desk", "Decides: reject, rework, forward-test or promote. Decides only from filed artifacts; never builds or grades.",
         "decision", ("lead", "spec", "analysis", "build", "verification", "quant_review", "allocation", "prop_plan")),
)}

ROLE_ORDER = tuple(ROLES)
MUST_DIFFER = ("builder", "verifier", "quant")          # three different agents, always
