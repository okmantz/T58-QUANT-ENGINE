"""Closed families: a HARD close rule on top of the graveyard's soft penalty.

The graveyard already steers search two ways, and both are deliberately gentle (``app.discovery_engine.graveyard_guidance``): a
neighbourhood that keeps dying is charged at most ``max_penalty_r`` (0.04R) in fitness, and a coarse parameter signature is skipped
after N deaths. A *family* is never banned. That is the right default for one noisy neighbourhood and the wrong one for a hypothesis
that has been tried everywhere and has never come close: it keeps winning candidate budget, and every extra look on it is another trial
the multiple-testing correction has to pay for.

A family is CLOSED when ALL of these hold, counted over the graveyard rows of every instrument / timeframe cell:

    deaths            >= required deaths, which scales with the family's evidence grade (A needs 2x, B 1.5x, C 1x, D 0.5x the base)
    cells             deaths are spread over at least ``min_cells`` cells with at least ``min_cell_deaths`` rows each
                      (a dead family on ONE market is a dead neighbourhood, not a dead idea)
    near misses       none: no row that was net positive at doubled costs with enough trades
    median net R      not above ``max_median_r`` (the typical row loses money after costs)

Closed means: ``filter_open`` removes it from every "all families" and explicit-list search, with the reason, until a person
reopens it with ``reopen_family`` and a written reason naming what is DIFFERENT (a new mechanism, new data, a fixed bug). A reopen
grants a budget of further rows (``reopen_budget``); if they too are all losers the family closes again. A person can also close a
family by hand. Nothing here ever lifts a candidate over a gate.

Switch: ``T58_HARD_CLOSE=0`` disables the filter (tests, or a deliberate full re-search).
"""
from __future__ import annotations

import math
import os
import statistics
from dataclasses import dataclass, field

from app.research_ledger._store import append_row, read_rows

GRADE_MULTIPLIER = {"A": 2.0, "B": 1.5, "C": 1.0, "D": 0.5, None: 1.0}


@dataclass(frozen=True)
class ClosureRules:
    base_deaths: int = 40              # rows needed for a grade-C family
    min_cells: int = 3
    min_cell_deaths: int = 5
    max_near_misses: int = 0
    max_median_r: float = 0.0
    min_near_miss_trades: int = 100
    watch_fraction: float = 0.5        # at this share of the required deaths the family is flagged WATCH
    reopen_budget: int = 20            # further rows a reopened family may burn before it closes again

    def required_deaths(self, grade: str | None) -> int:
        return int(math.ceil(self.base_deaths * GRADE_MULTIPLIER.get(grade, 1.0)))


@dataclass
class ClosureDecision:
    family: str
    state: str                          # OPEN | WATCH | CLOSED | REOPENED
    grade: str | None
    deaths: int
    required_deaths: int
    cells: int
    near_misses: int
    median_r: float | None
    reason: str
    manual: bool = False
    checks: list = field(default_factory=list)

    @property
    def closed(self) -> bool:
        return self.state == "CLOSED"

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def enabled() -> bool:
    """Off with ``T58_HARD_CLOSE=0``, and off whenever graveyard read-back is off (the test suite sets T58_DISABLE_GRAVEYARD_READBACK=1)."""
    if os.environ.get("T58_DISABLE_GRAVEYARD_READBACK", "") in ("1", "true", "True"):
        return False
    return os.environ.get("T58_HARD_CLOSE", "1").strip().lower() not in ("0", "false", "no", "off")


# ------------------------------------------------------------------------------------------------------------ graveyard stats
_CACHE: dict = {}


def _row_r(row: dict):
    v = row.get("doubled_cost_avg_r")
    v = row.get("avg_r_net") if v is None else v
    return float(v) if isinstance(v, (int, float)) and math.isfinite(v) else None


def stats_from_rows(rows: list, *, min_near_miss_trades: int = 100) -> dict:
    """{family: {deaths, near_misses, rs}} from raw graveyard rows."""
    out: dict = {}
    for r in rows or []:
        fam = r.get("family") or "unknown"
        s = out.setdefault(fam, {"deaths": 0, "near_misses": 0, "rs": [], "unmeasured": 0, "unmeasured_losers": 0})
        s["deaths"] += 1
        ar = _row_r(r)
        if ar is not None:
            s["rs"].append(ar)
            if ar > 0 and int(r.get("n_trades") or 0) >= min_near_miss_trades:
                s["near_misses"] += 1
        else:                                   # starter-seed rows carry a verdict but no R: count them as losers only when they say so
            s["unmeasured"] += 1
            if str(r.get("oos_result") or "").lower() == "negative":
                s["unmeasured_losers"] += 1
    return out


def graveyard_cell_stats(min_near_miss_trades: int = 100) -> dict:
    """{(family, instrument, timeframe): {deaths, near_misses, median_r, best_r}} over every instrument-scoped graveyard file.
    Cached per file by (mtime, size) so repeated calls during one run cost a ``stat`` per file, not a re-read."""
    from app.research_ledger.ledger import norm_instrument, norm_timeframe
    try:
        from app.search.graveyard import list_graveyard_files, load_graveyard
        files = list_graveyard_files()
    except Exception:  # noqa: BLE001
        return {}
    out: dict = {}
    for f in files:
        path = f["path"]
        try:
            import pathlib
            st = pathlib.Path(path).stat()
            key = (path, st.st_mtime_ns, st.st_size, min_near_miss_trades)
        except OSError:
            continue
        cached = _CACHE.get(path)
        if cached and cached[0] == key:
            per_family = cached[1]
        else:
            per_family = stats_from_rows(load_graveyard(path, _install=False), min_near_miss_trades=min_near_miss_trades)
            _CACHE[path] = (key, per_family)
        inst, tf = norm_instrument(f["instrument"]), norm_timeframe(f["timeframe"])
        for fam, s in per_family.items():
            cell = out.setdefault((fam, inst, tf), {"deaths": 0, "near_misses": 0, "rs": [], "unmeasured": 0, "unmeasured_losers": 0})
            for k in ("deaths", "near_misses", "unmeasured", "unmeasured_losers"):
                cell[k] += s[k]
            cell["rs"].extend(s["rs"])
    for cell in out.values():
        rs = cell.pop("rs")
        cell["median_r"] = statistics.median(rs) if rs else None
        cell["best_r"] = max(rs) if rs else None
    return out


# ------------------------------------------------------------------------------------------------------------------ decisions
def _events() -> list[dict]:
    return read_rows("closures")


def _latest_event(family: str) -> dict | None:
    last = None
    for e in _events():
        if e.get("family") == family:
            last = e
    return last


def evaluate_family(family: str, cells: dict | None = None, *, rules: ClosureRules = ClosureRules(), grade: str | None = None) -> ClosureDecision:
    """Decide one family. ``cells`` is {(instrument, timeframe): {deaths, near_misses, median_r}} for THIS family (defaults to the
    graveyard on disk); pass it explicitly to test the rule without touching disk."""
    if grade is None:
        try:
            from app.research_ledger.evidence import family_grade
            g = family_grade(family)
            grade = g["grade"] if g else None
        except Exception:  # noqa: BLE001
            grade = None
    if cells is None:
        cells = {(i, t): v for (f, i, t), v in graveyard_cell_stats(rules.min_near_miss_trades).items() if f == family}
    deaths = sum(int(c["deaths"]) for c in cells.values())
    near = sum(int(c.get("near_misses", 0)) for c in cells.values())
    deep_cells = sum(1 for c in cells.values() if int(c["deaths"]) >= rules.min_cell_deaths)
    med_pool = [c["median_r"] for c in cells.values() if c.get("median_r") is not None for _ in range(max(int(c["deaths"]), 1))]
    median_r = statistics.median(med_pool) if med_pool else None
    unmeasured = sum(int(c.get("unmeasured", 0)) for c in cells.values())
    unmeasured_losers = sum(int(c.get("unmeasured_losers", 0)) for c in cells.values())
    # no R recorded anywhere (starter-seed rows): accept "at least 90% of the rows lost out of sample" as the median test
    median_ok = (median_r is not None and median_r <= rules.max_median_r) or (
        median_r is None and unmeasured > 0 and unmeasured_losers >= 0.9 * unmeasured)
    need = rules.required_deaths(grade)

    ev = _latest_event(family)
    manual_close = bool(ev and ev.get("action") == "close")
    reopened = bool(ev and ev.get("action") == "reopen")
    if reopened:
        need = int(ev.get("deaths_at_reopen", 0)) + rules.reopen_budget       # a reopened family gets a fresh, smaller budget
    checks = [
        {"name": f"deaths >= {need}", "ok": deaths >= need, "detail": f"{deaths} graveyard row(s)"},
        {"name": f"spread over >= {rules.min_cells} cells (>= {rules.min_cell_deaths} rows each)", "ok": deep_cells >= rules.min_cells,
         "detail": f"{deep_cells} qualifying cell(s) of {len(cells)}"},
        {"name": f"near misses <= {rules.max_near_misses}", "ok": near <= rules.max_near_misses, "detail": f"{near} row(s) positive at doubled costs"},
        {"name": f"median net R <= {rules.max_median_r:+.2f}", "ok": bool(median_ok),
         "detail": (f"{median_r:+.3f}R" if median_r is not None else (f"no R recorded; {unmeasured_losers}/{unmeasured} rows lost out of sample" if unmeasured else "n/a"))},
    ]
    base = dict(family=family, grade=grade, deaths=deaths, required_deaths=need, cells=deep_cells, near_misses=near, median_r=median_r, checks=checks)
    if manual_close:
        return ClosureDecision(state="CLOSED", reason=f"closed by hand: {ev.get('reason', '')}", manual=True, **base)
    if all(c["ok"] for c in checks):
        why = (f"{deaths} graveyard rows over {deep_cells} cells, none positive at doubled costs, "
               + (f"median {median_r:+.3f}R" if median_r is not None else "all measured rows lost out of sample")
               + (f" (reopened once; the extra {rules.reopen_budget} rows also lost)" if reopened else ""))
        return ClosureDecision(state="CLOSED", reason=why, **base)
    if reopened:
        return ClosureDecision(state="REOPENED", reason=f"reopened: {ev.get('reason', '')}", **base)
    if deaths >= rules.watch_fraction * need and near <= rules.max_near_misses:
        return ClosureDecision(state="WATCH", reason=f"{deaths}/{need} rows toward a close, no near miss yet", **base)
    return ClosureDecision(state="OPEN", reason="not enough evidence of failure to close", **base)


def _families_in_graveyard() -> dict:
    by: dict = {}
    for (fam, inst, tf), v in graveyard_cell_stats().items():
        by.setdefault(fam, {})[(inst, tf)] = v
    return by


def closed_families(rules: ClosureRules = ClosureRules()) -> dict:
    """{family: ClosureDecision} for every family that is CLOSED right now (graveyard rule or by hand)."""
    out: dict = {}
    seen = set()
    for fam, cells in _families_in_graveyard().items():
        seen.add(fam)
        d = evaluate_family(fam, cells, rules=rules)
        if d.closed:
            out[fam] = d
    for e in _events():                                  # manual closes of a family the graveyard has never seen
        fam = e.get("family")
        if fam and fam not in seen and e.get("action") == "close":
            d = evaluate_family(fam, {}, rules=rules)
            if d.closed:
                out[fam] = d
    return out


def is_closed(family: str, rules: ClosureRules = ClosureRules()) -> bool:
    return enabled() and family in closed_families(rules)


def filter_open(names, rules: ClosureRules = ClosureRules()) -> tuple[list, dict]:
    """(names still open, {closed name: reason}). With the switch off, everything is open."""
    names = list(names)
    if not enabled():
        return names, {}
    closed = closed_families(rules)
    kept = [n for n in names if n not in closed]
    return kept, {n: "CLOSED: " + closed[n].reason + ". Reopen it with a written reason (app.research_ledger.reopen_family) to search it again."
                  for n in names if n in closed}


def reopen_family(family: str, reason: str, *, what_changed: str = "", by: str = "") -> dict:
    """Reopen a closed family. ``reason`` and ``what_changed`` are required: a close is only worth having if reopening takes a sentence."""
    if len(str(reason).strip()) < 10 or not str(what_changed).strip():
        raise ValueError("reopening needs a reason (10+ characters) and a statement of what is different this time")
    cells = {(i, t): v for (f, i, t), v in graveyard_cell_stats().items() if f == family}
    deaths = sum(int(c["deaths"]) for c in cells.values())
    return append_row("closures", {"action": "reopen", "family": family, "reason": reason.strip(), "what_changed": what_changed.strip(),
                                   "by": by, "deaths_at_reopen": deaths})


def close_family(family: str, reason: str, *, by: str = "") -> dict:
    if len(str(reason).strip()) < 10:
        raise ValueError("closing by hand needs a reason (10+ characters)")
    return append_row("closures", {"action": "close", "family": family, "reason": reason.strip(), "by": by})


def close_report(rules: ClosureRules = ClosureRules()) -> dict:
    """Every graded family with its state, for the Research page and the audit trail."""
    from app.research_ledger.evidence import grade_table
    by_graveyard = _families_in_graveyard()
    rows = []
    for g in grade_table():
        d = evaluate_family(g["family"], by_graveyard.get(g["family"], {}), rules=rules, grade=g["grade"])
        rows.append({"number": g["number"], "family": g["family"], "grade": g["grade"], "state": d.state, "deaths": d.deaths,
                     "required": d.required_deaths, "near_misses": d.near_misses, "reason": d.reason})
    counts: dict = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    return {"rows": rows, "counts": counts, "enabled": enabled(), "rules": rules.__dict__}
