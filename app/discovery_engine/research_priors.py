"""Distilled Strategy Graveyard research priors for the discovery engine.

``app/search/seed_data/graveyard_research_priors.jsonl`` holds one record per frozen experiment in the Graveyard research archive
(verdict, headline numbers, the lesson, and which T58 strategy families it bears on). It is a PRIOR for where to spend search
budget and which costs/gates to be suspicious about -- never evidence that a candidate works. Only distilled verdicts live here;
the archive's code and data are not reproduced (the archive is personal-use / no-redistribution).

    from app.discovery_engine.research_priors import load_priors, priors_for_family, family_prior_note

``priors_for_family`` returns the experiments whose ``related_engine_families`` name the family; ``family_prior_note`` is a one-line
human-readable summary for run logs (empty string when the archive says nothing about the family).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PRIORS_PATH = Path(__file__).resolve().parents[1] / "search" / "seed_data" / "graveyard_research_priors.jsonl"
FAIL_VERDICTS = {"FAIL"}


@lru_cache(maxsize=1)
def load_priors(path: str | None = None) -> tuple:
    p = Path(path) if path else PRIORS_PATH
    if not p.exists():
        return ()
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return tuple(rows)


def priors_for_family(family: str) -> list:
    return [r for r in load_priors() if family in (r.get("related_engine_families") or [])]


def priors_with_tag(tag: str) -> list:
    return [r for r in load_priors() if tag in (r.get("tags") or [])]


def family_prior_note(family: str) -> str:
    hits = priors_for_family(family)
    if not hits:
        return ""
    parts = [f"{r['experiment']}: {r['verdict']} ({r['headline']})" for r in hits]
    return f"Graveyard research on '{family}': " + "; ".join(parts)


def family_is_research_survivor(family: str) -> bool:
    """True when at least one related experiment PASSED and none FAILED -- a reason to keep a slow family in the search, not a pass."""
    hits = priors_for_family(family)
    return bool(hits) and any(r["verdict"] == "PASS" for r in hits) and not any(r["verdict"] in FAIL_VERDICTS for r in hits)
