"""Sources, queries and coverage ledgers.

    sources    every paper, book, dataset or feed that informed a family or a rule (what was READ, and how strong it is)
    queries    every search or question asked of a tool (what was ASKED, and whether it produced anything usable)
    coverage   which (family, instrument, timeframe) cells have been tried, how many trials were spent there and what came of it

The three answer different audit questions: "where did this idea come from", "did we already look for this", and "what have we NOT
looked at". Coverage is rebuilt idempotently from the graveyard (``sync_coverage_from_graveyard``), so the existing history counts
without any migration. Everything is append-only JSON Lines; nothing here changes a verdict.
"""
from __future__ import annotations

import re
from collections import defaultdict

from app.research_ledger._store import append_row, ledger_dir, read_rows

SOURCE_KINDS = ("paper", "book", "dataset", "feed", "code", "note")
QUERY_CHANNELS = ("web", "ai", "library", "graveyard", "engine", "other")
QUERY_OUTCOMES = ("hit", "miss", "duplicate", "error")
COVERAGE_STATUS = ("tested", "survived", "dead")


def norm_instrument(raw) -> str:
    """'ES1!' / 'ES' / 'EURUSD/EURUSD240.csv' -> 'ES' / 'ES' / 'EURUSD' (graveyard file names and UI labels differ)."""
    s = str(raw or "").strip().replace("\\", "/").split("/")[0]
    s = re.sub(r"\.(csv|parquet|tsv|txt|zip)$", "", s, flags=re.I)
    s = s.upper().strip("!-_ ")
    s = re.split(r"[-_ ]", s)[0] if re.search(r"[-_ ]", s) else s     # graveyard file names are sanitised: 'USDJPY-USDJPY60-CSV'
    s = s.rstrip("!")
    s = re.sub(r"(?<=[A-Z])1$", "", s) if re.fullmatch(r"[A-Z]{1,4}1", s) else s
    return s or "UNKNOWN"


def norm_timeframe(raw) -> str:
    s = str(raw or "unknown").strip().lower().replace(" ", "")
    return s or "unknown"


class ResearchLedger:
    """Thin object wrapper so a caller (or a test) can point all three ledgers at one folder."""

    def __init__(self, base=None):
        self.base = base

    def source(self, **kw) -> dict:
        return log_source(_base=self.base, **kw)

    def query(self, **kw) -> dict:
        return log_query(_base=self.base, **kw)

    def coverage(self, **kw) -> dict:
        return record_coverage(_base=self.base, **kw)

    def summary(self, **kw) -> dict:
        return coverage_summary(_base=self.base, **kw)


def log_source(*, title: str, kind: str = "paper", url: str = "", authors: str = "", year: int | None = None, grade: str | None = None,
               families=(), takeaway: str = "", _base=None) -> dict:
    """Record something that was read. ``grade`` (A-D) is the strength of THIS source as evidence, same scale as app.research_ledger.evidence."""
    if not str(title).strip():
        raise ValueError("a source needs a title")
    if kind not in SOURCE_KINDS:
        raise ValueError(f"kind must be one of {SOURCE_KINDS}")
    if grade is not None and grade not in ("A", "B", "C", "D"):
        raise ValueError("grade must be A, B, C or D")
    return append_row("sources", {"title": str(title).strip(), "kind": kind, "url": url, "authors": authors, "year": year, "grade": grade,
                                  "families": sorted({str(f) for f in families}), "takeaway": takeaway}, _base)


def log_query(*, text: str, channel: str = "other", n_results: int = 0, n_used: int = 0, outcome: str | None = None, families=(),
              notes: str = "", _base=None) -> dict:
    """Record something that was asked. ``outcome`` defaults from the counts: used>0 -> hit, results>0 -> duplicate-or-unused is 'miss'."""
    if not str(text).strip():
        raise ValueError("a query needs text")
    if channel not in QUERY_CHANNELS:
        raise ValueError(f"channel must be one of {QUERY_CHANNELS}")
    if outcome is None:
        outcome = "hit" if n_used > 0 else "miss"
    if outcome not in QUERY_OUTCOMES:
        raise ValueError(f"outcome must be one of {QUERY_OUTCOMES}")
    return append_row("queries", {"text": str(text).strip(), "channel": channel, "n_results": int(n_results), "n_used": int(n_used),
                                  "outcome": outcome, "families": sorted({str(f) for f in families}), "notes": notes}, _base)


def record_coverage(*, family: str, instrument: str, timeframe: str = "unknown", trials: int = 1, status: str = "tested",
                    best_edge_lb_r: float | None = None, source: str = "engine", _base=None) -> dict:
    """One observation of a cell. For the same (cell, source) the LATEST row replaces the earlier one when read back, so a source that
    reports a running total (the graveyard sync does) is idempotent; use distinct ``source`` labels for distinct engines."""
    if status not in COVERAGE_STATUS:
        raise ValueError(f"status must be one of {COVERAGE_STATUS}")
    return append_row("coverage", {"family": str(family), "instrument": norm_instrument(instrument), "timeframe": norm_timeframe(timeframe),
                                   "trials": int(trials), "status": status, "best_edge_lb_r": best_edge_lb_r, "source": str(source)}, _base)


def _fold_coverage(rows: list[dict]) -> dict:
    """{(family, instrument, timeframe): {trials, status, best_edge_lb_r, sources}} -- latest row per (cell, source), summed across sources."""
    latest: dict = {}
    for r in rows:
        key = (r.get("family"), r.get("instrument"), r.get("timeframe"), r.get("source", "engine"))
        latest[key] = r
    cells: dict = {}
    rank = {"survived": 2, "tested": 1, "dead": 1}
    for (fam, inst, tf, src), r in latest.items():
        c = cells.setdefault((fam, inst, tf), {"trials": 0, "status": "tested", "best_edge_lb_r": None, "sources": []})
        c["trials"] += int(r.get("trials") or 0)
        c["sources"].append(src)
        if rank.get(r.get("status"), 0) >= rank.get(c["status"], 0) and r.get("status") == "survived":
            c["status"] = "survived"
        elif r.get("status") == "dead" and c["status"] != "survived":
            c["status"] = "dead"
        b = r.get("best_edge_lb_r")
        if isinstance(b, (int, float)) and (c["best_edge_lb_r"] is None or b > c["best_edge_lb_r"]):
            c["best_edge_lb_r"] = float(b)
    return cells


def sync_coverage_from_graveyard(_base=None) -> int:
    """Fold every instrument-scoped graveyard file into the coverage ledger as a running-total snapshot per (family, cell).
    Safe to call repeatedly: a snapshot replaces the previous one. Returns the number of snapshot rows written."""
    from app.research_ledger.closure import graveyard_cell_stats
    n = 0
    existing = _fold_coverage([r for r in read_rows("coverage", _base) if r.get("source") == "graveyard"])
    for (fam, inst, tf), st in graveyard_cell_stats().items():
        prev = existing.get((fam, inst, tf))
        if prev and prev["trials"] == st["deaths"]:
            continue
        record_coverage(family=fam, instrument=inst, timeframe=tf, trials=st["deaths"], status="survived" if st["near_misses"] else "dead",
                        best_edge_lb_r=st.get("best_r"), source="graveyard", _base=_base)
        n += 1
    return n


def coverage_summary(families=None, instruments=None, timeframes=None, *, sync: bool = True, _base=None) -> dict:
    """Per-family coverage over the observed instruments x timeframes (or the ones given), plus the gaps worth looking at.

    ``families`` defaults to the 100 numbered v13 families. A family's ``pct`` is cells tested / cells in the grid; ``gaps`` lists
    families never tested anywhere, and grade A / B families that cover under half of the grid (the ones with a reason to look)."""
    if sync:
        try:
            sync_coverage_from_graveyard(_base)
        except Exception:  # noqa: BLE001 -- coverage is a report; a missing graveyard must not break it
            pass
    cells = _fold_coverage(read_rows("coverage", _base))
    if families is None:
        from app.research_ledger.evidence import grade_table
        fam_rows = {r["family"]: r for r in grade_table()}
        families = list(fam_rows)
    else:
        from app.research_ledger.evidence import family_grade
        fam_rows = {f: (family_grade(f) or {"family": f, "grade": None}) for f in families}
    insts = sorted({k[1] for k in cells} if instruments is None else {norm_instrument(i) for i in instruments})
    tfs = sorted({k[2] for k in cells} if timeframes is None else {norm_timeframe(t) for t in timeframes})
    grid = max(len(insts) * len(tfs), 1)
    per = []
    for f in families:
        mine = {(i, t): v for (fam, i, t), v in cells.items() if fam == f and i in insts and t in tfs}
        trials = sum(v["trials"] for v in mine.values())
        per.append({"family": f, "grade": fam_rows[f].get("grade"), "cells_tested": len(mine), "cells_total": grid if insts and tfs else 0,
                    "pct": round(100.0 * len(mine) / grid, 1) if insts and tfs else 0.0, "trials": trials,
                    "survived_cells": sum(1 for v in mine.values() if v["status"] == "survived")})
    never = [p["family"] for p in per if p["cells_tested"] == 0]
    thin = [p["family"] for p in per if p["grade"] in ("A", "B") and p["cells_tested"] and p["pct"] < 50.0]
    return {"instruments": insts, "timeframes": tfs, "families": per, "n_families": len(per), "never_tested": never,
            "thin_high_evidence": thin, "n_cells_observed": len(cells), "dir": str(_base or ledger_dir())}
