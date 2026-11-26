"""The agent desk: nine roles, artifacts with lineage, and role separation enforced at filing time.

``Desk.file`` is the only way an artifact enters the record, and it refuses anything that breaks a separation rule:
a wrong role for the kind, a read of something the role may not read, a review of the author's own lineage, a verdict on work the
reviewer built, or a decision resting on evidence its author produced. The desk never makes a verdict itself and never lifts one:
the head of desk may approve only what the verifier AND the quant (two different agents) have both passed.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from app.ai.agent_desk.roles import MUST_DIFFER, REVIEW_KINDS, ROLE_ORDER, ROLES
from app.research_ledger._store import append_row, read_rows

DECISIONS = ("REJECT", "REWORK", "FORWARD_TEST", "PROMOTE")


class SeparationError(ValueError):
    """A filing that would break role separation. Always refused, never downgraded to a warning."""


@dataclass
class Agent:
    id: str
    role: str
    backend: str = "deterministic"      # "deterministic" | "ollama" | "anthropic" | ... -- informational; separation is by id and session
    session: str = ""                   # each agent has its own context; the desk refuses two agents sharing one

    def __post_init__(self):
        if self.role not in ROLES:
            raise ValueError(f"unknown role {self.role!r}; roles: {', '.join(ROLE_ORDER)}")
        if not self.session:
            self.session = hashlib.sha1(f"{self.id}:{self.role}".encode()).hexdigest()[:10]


@dataclass
class Artifact:
    id: str
    kind: str
    author: str
    role: str
    subject: str | None                 # the artifact a review grades
    parents: list                       # artifact ids it was produced from
    verdict: str | None                 # reviews: PASS | MARGINAL | FAIL | NOT_MEASURED ; decisions: one of DECISIONS
    body: dict
    candidate: str = ""
    ts: float = 0.0

    def to_row(self) -> dict:
        return {"artifact_id": self.id, "kind": self.kind, "author": self.author, "role": self.role, "subject": self.subject, "parents": self.parents,
                "verdict": self.verdict, "body": self.body, "candidate": self.candidate}


def _aid(kind: str, author: str, body: dict, parents: list) -> str:
    return hashlib.sha1(json.dumps([kind, author, body, parents], sort_keys=True, default=str).encode()).hexdigest()[:12]


class Desk:
    def __init__(self, agents: list[Agent], *, base: Path | None = None, persist: bool = True):
        self.base, self.persist = base, persist
        self.agents: dict[str, Agent] = {}
        self.by_role: dict[str, Agent] = {}
        self.artifacts: dict[str, Artifact] = {}
        for a in agents:
            self.hire(a)
        self.check_roster()
        if persist:
            self._load()

    # ------------------------------------------------------------------------------------------------------------ roster
    def hire(self, a: Agent) -> None:
        if a.id in self.agents:
            raise SeparationError(f"agent id {a.id!r} is already on the desk: one agent, one role")
        if any(o.session == a.session for o in self.agents.values()):
            raise SeparationError(f"agent {a.id!r} shares a session with another agent; each agent needs its own context")
        if a.role in self.by_role:
            raise SeparationError(f"role {a.role!r} is already held by {self.by_role[a.role].id!r}")
        self.agents[a.id] = a
        self.by_role[a.role] = a

    def check_roster(self) -> None:
        held = [self.by_role[r].id for r in MUST_DIFFER if r in self.by_role]
        if len(set(held)) != len(held):
            raise SeparationError("builder, verifier and quant must be three different agents")

    def missing_roles(self) -> list[str]:
        return [r for r in ROLE_ORDER if r not in self.by_role]

    # ------------------------------------------------------------------------------------------------------------ lineage
    def lineage(self, artifact_id: str) -> list[Artifact]:
        """The artifact and everything it rests on (parents and, for a review, its subject)."""
        seen, out, stack = set(), [], [artifact_id]
        while stack:
            i = stack.pop()
            if i in seen or i not in self.artifacts:
                continue
            seen.add(i)
            a = self.artifacts[i]
            out.append(a)
            stack += list(a.parents) + ([a.subject] if a.subject else [])
        return out

    def authors_of(self, artifact_id: str) -> set[str]:
        return {a.author for a in self.lineage(artifact_id)}

    def visible_to(self, role: str, candidate: str | None = None) -> list[Artifact]:
        """What a role may read: only the kinds its role allows; the builder never sees reviews; reviewers never see each other's verdicts."""
        r = ROLES[role]
        return [a for a in self.artifacts.values() if a.kind in r.reads and (candidate is None or a.candidate == candidate)]

    # ------------------------------------------------------------------------------------------------------------ filing
    def file(self, agent_id: str, kind: str, body: dict, *, parents: list | None = None, subject: str | None = None, verdict: str | None = None,
             candidate: str = "") -> Artifact:
        if agent_id not in self.agents:
            raise SeparationError(f"{agent_id!r} is not on the desk")
        ag = self.agents[agent_id]
        role = ROLES[ag.role]
        parents = list(parents or [])
        if kind != role.makes:
            raise SeparationError(f"a {role.title} files {role.makes!r}, not {kind!r}")
        for pid in parents + ([subject] if subject else []):
            if pid not in self.artifacts:
                raise SeparationError(f"artifact {pid!r} is not on the record")
            pk = self.artifacts[pid].kind
            if pk not in role.reads and not (subject == pid and pk in role.grades):
                raise SeparationError(f"a {role.title} may not read {pk!r} artifacts")
        if kind in REVIEW_KINDS:
            if not subject:
                raise SeparationError(f"a {kind} must name the build it grades (subject)")
            if self.artifacts[subject].kind not in role.grades:
                raise SeparationError(f"a {role.title} grades {role.grades}, not {self.artifacts[subject].kind!r}")
            if ag.id in self.authors_of(subject):
                raise SeparationError(f"{ag.id!r} appears in the lineage of {subject!r}: nobody grades their own work")
            if verdict not in ("PASS", "MARGINAL", "FAIL", "NOT_MEASURED"):
                raise SeparationError("a review needs a verdict: PASS, MARGINAL, FAIL or NOT_MEASURED")
            for p in parents:
                if self.artifacts[p].kind in REVIEW_KINDS:
                    raise SeparationError("a review may not be built on the other reviewer's verdict")
        if kind == "decision":
            if verdict not in DECISIONS:
                raise SeparationError(f"a decision is one of {DECISIONS}")
            lin_authors = set()
            for p in parents:
                lin_authors |= self.authors_of(p)
            if ag.id in lin_authors:
                raise SeparationError("the head of desk appears in the lineage of the evidence it is deciding on")
            if verdict in ("FORWARD_TEST", "PROMOTE"):
                self._require_independent_passes(parents, promote=(verdict == "PROMOTE"))
        a = Artifact(_aid(kind, agent_id, body, parents + ([subject] if subject else [])), kind, agent_id, ag.role, subject, parents, verdict, dict(body), candidate)
        import time
        a.ts = round(time.time(), 3)
        self.artifacts[a.id] = a
        if self.persist:
            append_row("desk_artifacts", a.to_row(), self.base)
        return a

    def _require_independent_passes(self, parents: list, *, promote: bool) -> None:
        reviews = [self.artifacts[p] for p in parents if p in self.artifacts and self.artifacts[p].kind in REVIEW_KINDS]
        ver = [r for r in reviews if r.kind == "verification"]
        quant = [r for r in reviews if r.kind == "quant_review"]
        if not ver or not quant:
            raise SeparationError("forward-test or promote needs both a verification and a quant review in the evidence")
        if ver[0].author == quant[0].author or ver[0].subject != quant[0].subject:
            raise SeparationError("verification and quant review must come from different agents on the same build")
        if ver[0].verdict != "PASS":
            raise SeparationError(f"the verifier's verdict is {ver[0].verdict}: not approvable")
        ok = ("PASS",) if promote else ("PASS", "MARGINAL")
        if quant[0].verdict not in ok:
            raise SeparationError(f"the quant's verdict is {quant[0].verdict}: {'PROMOTE needs PASS' if promote else 'forward test needs PASS or MARGINAL'}")

    # ------------------------------------------------------------------------------------------------------------ record
    def _load(self) -> None:
        for r in read_rows("desk_artifacts", self.base):
            try:
                a = Artifact(r["artifact_id"], r["kind"], r["author"], r["role"], r.get("subject"), list(r.get("parents") or []), r.get("verdict"),
                             dict(r.get("body") or {}), r.get("candidate", ""), float(r.get("ts", 0)))
                self.artifacts[a.id] = a
            except (KeyError, TypeError, ValueError):
                continue

    def candidates(self) -> list[str]:
        return sorted({a.candidate for a in self.artifacts.values() if a.candidate})

    def board(self) -> list[dict]:
        """One row per candidate: where it stands on the desk."""
        out = []
        for c in self.candidates():
            arts = [a for a in self.artifacts.values() if a.candidate == c]
            by_kind = {k: max((a for a in arts if a.kind == k), key=lambda x: x.ts, default=None) for k in ("lead", "spec", "analysis", "build", "verification", "quant_review", "decision")}
            out.append({"candidate": c, **{k: (v.verdict or "filed") if v else None for k, v in by_kind.items()},
                        "decision": by_kind["decision"].verdict if by_kind["decision"] else None})
        return out


def default_roster(prefix: str = "t58") -> list[Agent]:
    return [Agent(f"{prefix}-{r}", r) for r in ROLE_ORDER]
