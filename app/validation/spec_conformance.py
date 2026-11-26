"""Spec-conformance verifier: does the backtest do what the strategy's spec SAYS it does?

A strategy can score well because the engine did something the spec never described: entries outside the stated session, fills at prices
that never traded, trades held across a contract roll (the spread is booked as profit), a trigger firing 3x as often as claimed, or a
rule that never fires where it should. None of the statistical gates see that, because they all start from the trade list.

Two passes, so the cheap evidence is gathered before the expensive validation and the full audit runs only on survivors:

    pass 1  ("cheap")  sampled entries and exits, trigger rate vs the stated rate, trades straddling a roll gap.        Seconds.
    pass 2  ("full")   every trade; a missed-signal scan against an independent reference signal (when one exists);
                       the full ``contract_calendar`` audit and ``roll_handling`` detection over the whole file.         Run only after
                       the strategy has survived validation (verdict still READY / MARGINAL).

Findings carry a severity:
    critical   the backtest is not measuring what it claims (price outside the bar, entry outside the session, overlapping trades,
               a trade before its own exit) -> NOT READY
    major      the strategy does not behave as specified (trigger rate off, signals missed, spread booked across a roll) -> MARGINAL
    minor      worth knowing, never changes a verdict

Everything is demote-only. A check that cannot be run (no stated rate, no reference signal, an instrument with no calendar) is reported as
NOT MEASURED and never counts as a pass or a failure.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

import numpy as np
import pandas as pd

CRITICAL, MAJOR, MINOR = "critical", "major", "minor"


@dataclass
class SpecConformanceSpec:
    instrument: str = ""
    session_start: str | None = None          # "HH:MM" local to ``session_tz``; None = no session check
    session_end: str | None = None
    session_tz: str = "America/New_York"
    direction: str = "both"                    # "long" | "short" | "both"
    stated_trades_per_day: float | None = None
    rate_tolerance: float = 1.5                # observed/stated outside [1/x, x] AND outside the 99% Poisson interval -> major
    max_hold_minutes: float | None = None
    single_position: bool = True
    price_tol_frac: float = 0.0005             # fill may sit this fraction of price outside the bar range (slippage/rounding)
    reference_signal: Optional[Callable[[pd.DataFrame], Sequence[int]]] = None   # independent implementation: +1 / -1 / 0 per bar
    signal_lag_bars: int = 1                   # a reference signal on bar i may fill on bar i .. i+lag
    missed_signal_tol: float = 0.05            # fraction of reference signals (while flat) with no trade before it is major
    sample_size: int = 200

    @classmethod
    def from_spec_card(cls, card: dict | None, instrument: str = "", **kw) -> "SpecConformanceSpec":
        card = card or {}
        s = cls(instrument=instrument or str(card.get("instruments") or ""), **kw)
        try:
            if card.get("trades_per_day") is not None and s.stated_trades_per_day is None:
                s.stated_trades_per_day = float(card["trades_per_day"])
        except (TypeError, ValueError):
            pass
        sess = str(card.get("session") or "")
        if "-" in sess and ":" in sess:
            a, _, b = sess.partition("-")
            s.session_start, s.session_end = a.strip()[:5], b.strip()[:5]
        return s


@dataclass
class Finding:
    check: str
    severity: str
    message: str
    n: int = 0
    examples: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class SpecConformanceResult:
    pass_name: str
    status: str = "PASS"                       # PASS | WARN | FAIL | UNMEASURED
    findings: list = field(default_factory=list)
    measured: list = field(default_factory=list)
    not_measured: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def worst(self) -> str | None:
        sev = {f.severity for f in self.findings}
        return CRITICAL if CRITICAL in sev else (MAJOR if MAJOR in sev else (MINOR if MINOR in sev else None))

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["findings"] = [f.to_dict() for f in self.findings]
        d["worst"] = self.worst
        return d

    def render(self) -> str:
        head = f"Spec conformance ({self.pass_name}): {self.status}; checked {', '.join(self.measured) or 'nothing'}"
        if self.not_measured:
            head += f"; not measured: {', '.join(self.not_measured)}"
        return "\n".join([head] + [f"  [{f.severity}] {f.check}: {f.message}" for f in self.findings])


# ------------------------------------------------------------------------------------------------------------------- helpers
def _bars(df: pd.DataFrame) -> pd.DataFrame:
    b = df.copy()
    b["timestamp"] = pd.to_datetime(b["timestamp"])
    return b.sort_values("timestamp").reset_index(drop=True)


def _sample(items: list, k: int, seed: int) -> list:
    if len(items) <= k:
        return list(items)
    rng = np.random.default_rng(seed)
    return [items[i] for i in sorted(rng.choice(len(items), size=k, replace=False))]


def _hhmm(s: str) -> int:
    h, m = s.split(":")[:2]
    return int(h) * 60 + int(m)


def _in_session(ts: pd.Timestamp, spec: SpecConformanceSpec) -> bool:
    t = pd.Timestamp(ts)
    t = t.tz_localize("UTC") if t.tzinfo is None else t
    loc = t.tz_convert(spec.session_tz)
    m = loc.hour * 60 + loc.minute
    a, b = _hhmm(spec.session_start), _hhmm(spec.session_end)
    return (a <= m < b) if a <= b else (m >= a or m < b)          # overnight windows wrap


def _bar_at(ts_index: pd.DatetimeIndex, ts) -> int:
    i = int(ts_index.searchsorted(pd.Timestamp(ts), side="right")) - 1
    return max(i, 0)


def _poisson_interval(count: int, conf: float = 0.99) -> tuple[float, float]:
    a = (1.0 - conf) / 2.0
    try:
        from scipy.stats import chi2
        lo = 0.0 if count == 0 else 0.5 * float(chi2.ppf(a, 2 * count))
        hi = 0.5 * float(chi2.ppf(1 - a, 2 * count + 2))
        return lo, hi
    except Exception:  # noqa: BLE001
        z = 2.576
        return max(0.0, count - z * math.sqrt(max(count, 1))), count + z * math.sqrt(max(count, 1)) + 1.0


def _t(x):
    return pd.Timestamp(x)


# --------------------------------------------------------------------------------------------------------------------- checks
def check_entries_exits(bars: pd.DataFrame, trades: list, spec: SpecConformanceSpec, *, seed: int = 0, sample: int | None = None) -> list[Finding]:
    """Sampled (pass 1) or full (pass 2) entry/exit integrity: fills must have happened inside a real bar, in the stated session and direction."""
    out: list[Finding] = []
    idx = pd.DatetimeIndex(bars["timestamp"])
    hi, lo = bars["high"].to_numpy(float), bars["low"].to_numpy(float)
    chosen = _sample(list(trades), sample, seed) if sample else list(trades)
    bad_price, bad_sess, bad_dir, bad_time, bad_stop, bad_hold = [], [], [], [], [], []
    for t in chosen:
        et, xt = _t(t.entry_time), _t(t.exit_time)
        if xt < et:
            bad_time.append(f"{et} -> {xt}")
        for label, ts, px in (("entry", et, float(t.entry_price)), ("exit", xt, float(t.exit_price))):
            if ts < idx[0] or ts > idx[-1]:
                bad_price.append(f"{label} {ts} is outside the data range")
                continue
            i = _bar_at(idx, ts)
            tol = abs(px) * spec.price_tol_frac
            # a fill at the OPEN of the next bar is legitimate: accept the range of the bar at ts and its successor
            j = min(i + 1, len(idx) - 1)
            lo_ok, hi_ok = min(lo[i], lo[j]) - tol, max(hi[i], hi[j]) + tol
            if not (lo_ok <= px <= hi_ok) and not (label == "exit" and str(getattr(t, "exit_reason", "")) == "end_of_data"):
                bad_price.append(f"{label} {ts} price {px:g} not in bar range [{lo_ok:g}, {hi_ok:g}]")
        if spec.session_start and spec.session_end and not _in_session(et, spec):
            bad_sess.append(str(et))
        d = int(t.direction)
        if (spec.direction == "long" and d != 1) or (spec.direction == "short" and d != -1):
            bad_dir.append(f"{et} direction {d}")
        reason = str(getattr(t, "exit_reason", ""))
        if reason in ("stop_loss", "take_profit"):
            moved = (float(t.exit_price) - float(t.entry_price)) * d
            if (reason == "stop_loss" and moved > abs(float(t.entry_price)) * spec.price_tol_frac) or \
               (reason == "take_profit" and moved < -abs(float(t.entry_price)) * spec.price_tol_frac):
                bad_stop.append(f"{et} {reason} but price moved {moved:+g} in the trade's direction")
        if spec.max_hold_minutes and (xt - et).total_seconds() / 60.0 > spec.max_hold_minutes * 1.001:
            bad_hold.append(f"{et} held {(xt - et).total_seconds() / 60.0:.0f} min")
    n = len(chosen)
    for chk, items, sev, msg in (
        ("fill_price", bad_price, CRITICAL, "fills at prices outside the bar they claim to occupy -- the engine is booking trades that never traded"),
        ("time_order", bad_time, CRITICAL, "trades that exit before they enter"),
        ("session", bad_sess, MAJOR, "entries outside the stated session"),
        ("direction", bad_dir, MAJOR, "trades in a direction the spec does not allow"),
        ("exit_reason", bad_stop, MAJOR, "stop/target exits that moved the wrong way for their label"),
        ("max_hold", bad_hold, MAJOR, "holds longer than the stated maximum"),
    ):
        if items:
            out.append(Finding(chk, sev, f"{len(items)} of {n} sampled trade(s): {msg}", len(items), items[:5]))
    if spec.single_position and len(trades) > 1:
        ordered = sorted(trades, key=lambda t: _t(t.entry_time))
        over = [f"{_t(b.entry_time)} opens before the {_t(a.exit_time)} exit" for a, b in zip(ordered, ordered[1:]) if _t(b.entry_time) < _t(a.exit_time)]
        if over:
            out.append(Finding("overlap", CRITICAL, f"{len(over)} overlapping trade(s) in a single-position strategy", len(over), over[:5]))
    return out


def check_trigger_rate(bars: pd.DataFrame, trades: list, spec: SpecConformanceSpec) -> tuple[list[Finding], dict]:
    stats: dict = {}
    if not spec.stated_trades_per_day or spec.stated_trades_per_day <= 0:
        return [], stats
    from app.data.trading_day import trading_days
    days = trading_days(pd.DatetimeIndex(bars["timestamp"]))
    n_days = int(len(set(np.asarray(days).tolist()))) if len(days) else 0
    if n_days < 20:
        return [], {"note": f"only {n_days} trading day(s); too few to test a rate"}
    n = len(trades)
    exp = spec.stated_trades_per_day * n_days
    lo, hi = _poisson_interval(n)
    ratio = (n / exp) if exp > 0 else float("inf")
    stats = {"trades": n, "trading_days": n_days, "observed_per_day": n / n_days, "stated_per_day": spec.stated_trades_per_day, "ratio": ratio,
             "expected_trades": exp, "poisson_99": (lo, hi)}
    outside_ci = not (lo <= exp <= hi)
    outside_tol = ratio > spec.rate_tolerance or ratio < 1.0 / spec.rate_tolerance
    if outside_ci and outside_tol:
        return [Finding("trigger_rate", MAJOR, f"observed {n / n_days:.3f} trades/day vs stated {spec.stated_trades_per_day:.3f} "
                        f"({ratio:.2f}x; stated rate implies {exp:.0f} trades, observed {n}, 99% interval for the observed count {lo:.0f}-{hi:.0f})", n)], stats
    if outside_ci or outside_tol:
        return [Finding("trigger_rate", MINOR, f"observed {n / n_days:.3f} trades/day vs stated {spec.stated_trades_per_day:.3f} ({ratio:.2f}x) -- off, "
                        f"but inside the tolerance on one of the two tests", n)], stats
    return [], stats


def check_missed_signals(bars: pd.DataFrame, trades: list, spec: SpecConformanceSpec) -> tuple[list[Finding], dict]:
    """Compare the trade list with an independent reference signal. Needs ``spec.reference_signal``."""
    if spec.reference_signal is None:
        return [], {}
    sig = np.asarray(list(spec.reference_signal(bars)), dtype=int)
    if len(sig) != len(bars):
        return [Finding("missed_signals", MINOR, f"reference signal has {len(sig)} values for {len(bars)} bars; check skipped")], {}
    idx = pd.DatetimeIndex(bars["timestamp"])
    entries = sorted((_bar_at(idx, t.entry_time), int(t.direction), _bar_at(idx, t.exit_time)) for t in trades)
    entry_bars = np.array([e[0] for e in entries], dtype=int)
    exit_bars = np.array([e[2] for e in entries], dtype=int)
    in_trade = np.zeros(len(bars) + 1, dtype=bool)
    for a, _d, b in entries:
        in_trade[a:b + 1] = True
    lag = max(int(spec.signal_lag_bars), 0)
    expected = missed = 0
    miss_ex = []
    for i in np.flatnonzero(sig != 0):
        if in_trade[i] and not (entry_bars == i).any():
            continue                                          # a signal while already in a trade is correctly ignored
        if spec.session_start and spec.session_end and not _in_session(idx[i], spec):
            continue
        expected += 1
        hit = bool(((entry_bars >= i) & (entry_bars <= i + lag)).any())
        if not hit:
            missed += 1
            if len(miss_ex) < 5:
                miss_ex.append(str(idx[i]))
    unexpected = 0
    sig_bars = np.flatnonzero(sig != 0)
    for a in entry_bars:
        if not ((sig_bars <= a) & (sig_bars >= a - lag)).any():
            unexpected += 1
    stats = {"reference_signals_while_flat": expected, "missed": missed, "unexpected_entries": unexpected, "trades": len(entries)}
    out = []
    if expected and missed / expected > spec.missed_signal_tol:
        out.append(Finding("missed_signals", MAJOR, f"{missed} of {expected} reference signals (while flat, in session) produced no trade "
                           f"({missed / expected:.1%} > {spec.missed_signal_tol:.0%})", missed, miss_ex))
    if entries and unexpected / len(entries) > spec.missed_signal_tol:
        out.append(Finding("unexpected_entries", MAJOR, f"{unexpected} of {len(entries)} entries have no matching reference signal "
                           f"({unexpected / len(entries):.1%})", unexpected))
    return out, stats


def check_roll_straddle(bars: pd.DataFrame, trades: list, spec: SpecConformanceSpec) -> tuple[list[Finding], dict]:
    """Cheap calendar check: trades held ACROSS a detected roll gap book the contract spread as P&L."""
    from app.data.roll_handling import detect_roll_bars
    inst = (spec.instrument or "").upper().split("-")[0]
    try:
        rb = detect_roll_bars(bars, inst)
    except Exception as exc:  # noqa: BLE001
        return [], {"note": f"roll detection unavailable: {exc}"}
    if len(rb) == 0:
        return [], {"roll_bars": 0, "trades_spanning_roll": 0}
    roll_ts = [pd.Timestamp(bars["timestamp"].iloc[int(j)]) for j in rb]
    hits = []
    for t in trades:
        et, xt = _t(t.entry_time), _t(t.exit_time)
        for r in roll_ts:
            if et < r <= xt:
                hits.append(f"{et} -> {xt} spans the roll at {r}")
                break
    stats = {"roll_bars": int(len(rb)), "trades_spanning_roll": len(hits)}
    if hits:
        return [Finding("roll_straddle", MAJOR, f"{len(hits)} trade(s) held across a contract roll gap; the spread between contracts is booked as profit or loss",
                        len(hits), hits[:5])], stats
    return [], stats


def check_calendar_audit(bars: pd.DataFrame, spec: SpecConformanceSpec) -> tuple[list[Finding], dict]:
    """Full calendar audit: close-to-open jumps vs the expected roll windows (``contract_calendar.audit_rolls``)."""
    from app.data.contract_calendar import audit_rolls
    sym = (spec.instrument or "").upper().split("-")[0]
    try:
        a = audit_rolls(bars, sym)
    except ValueError as exc:
        return [], {"note": str(exc)}
    stats = {"expected_rolls": a.n_expected, "big_jumps": a.n_detected_jumps, "unexplained": len(a.unexplained_jumps), "mid_session_splices": len(a.mid_session_splices),
             "missing": len(a.missing_rolls)}
    out = []
    if a.mid_session_splices:
        out.append(Finding("calendar_splice", MAJOR, f"{len(a.mid_session_splices)} contract switch(es) happened mid-session; the spread is booked as P&L",
                           len(a.mid_session_splices), a.mid_session_splices[:5]))
    if a.unexplained_jumps:
        out.append(Finding("calendar_jump", MINOR, f"{len(a.unexplained_jumps)} large gap(s) not near any expected roll window (bad ticks, a data seam, or a missing-bar span)",
                           len(a.unexplained_jumps), a.unexplained_jumps[:5]))
    return out, stats


# --------------------------------------------------------------------------------------------------------------------- passes
def _finish(res: SpecConformanceResult) -> SpecConformanceResult:
    w = res.worst
    res.status = "FAIL" if w in (CRITICAL, MAJOR) else ("WARN" if w == MINOR else ("PASS" if res.measured else "UNMEASURED"))
    return res


def run_pass1(df: pd.DataFrame, trades: list, spec: SpecConformanceSpec, *, seed: int = 0) -> SpecConformanceResult:
    """Cheap first pass: sampled entries/exits, trigger rate, roll straddle."""
    res = SpecConformanceResult("pass 1 (cheap)")
    if not trades:
        res.not_measured.append("everything (no trades)")
        return _finish(res)
    bars = _bars(df)
    res.findings += check_entries_exits(bars, trades, spec, seed=seed, sample=spec.sample_size)
    res.measured.append(f"{min(len(trades), spec.sample_size)} sampled entries/exits")
    f, st = check_trigger_rate(bars, trades, spec)
    if st.get("trades") is not None:
        res.measured.append("trigger rate"); res.stats["trigger_rate"] = st; res.findings += f
    else:
        res.not_measured.append("trigger rate (no stated rate)" if not spec.stated_trades_per_day else "trigger rate (too few days)")
    f, st = check_roll_straddle(bars, trades, spec)
    if "trades_spanning_roll" in st:
        res.measured.append("roll straddle"); res.stats["roll"] = st; res.findings += f
    else:
        res.not_measured.append("roll straddle")
    return _finish(res)


def run_pass2(df: pd.DataFrame, trades: list, spec: SpecConformanceSpec) -> SpecConformanceResult:
    """Full second pass: every trade, missed signals vs the reference, whole-file calendar audit. Run only on survivors."""
    res = SpecConformanceResult("pass 2 (full)")
    if not trades:
        res.not_measured.append("everything (no trades)")
        return _finish(res)
    bars = _bars(df)
    res.findings += check_entries_exits(bars, trades, spec)
    res.measured.append(f"all {len(trades)} entries/exits")
    f, st = check_trigger_rate(bars, trades, spec)
    if st.get("trades") is not None:
        res.measured.append("trigger rate"); res.stats["trigger_rate"] = st; res.findings += f
    else:
        res.not_measured.append("trigger rate")
    f, st = check_missed_signals(bars, trades, spec)
    if st:
        res.measured.append("missed signals"); res.stats["missed_signals"] = st; res.findings += f
    else:
        res.not_measured.append("missed signals (no independent reference signal)")
    f, st = check_roll_straddle(bars, trades, spec)
    if "trades_spanning_roll" in st:
        res.measured.append("roll straddle"); res.stats["roll"] = st; res.findings += f
    f, st = check_calendar_audit(bars, spec)
    if "expected_rolls" in st:
        res.measured.append("calendar audit"); res.stats["calendar"] = st; res.findings += f
    else:
        res.not_measured.append("calendar audit (" + str(st.get("note", "unavailable")) + ")")
    return _finish(res)


def apply_spec_cap(verdict: str, reasons: list, result: SpecConformanceResult | None) -> tuple[str, list]:
    """Demote-only. critical -> NOT READY; major -> cap READY at MARGINAL; minor/unmeasured -> a note, nothing else."""
    reasons = list(reasons)
    if result is None or result.status in ("PASS", "UNMEASURED"):
        return verdict, reasons
    w = result.worst
    top = [f for f in result.findings if f.severity == w][:3]
    why = "; ".join(f"{f.check}: {f.message}" for f in top)
    if w == CRITICAL and verdict != "NOT READY":
        reasons.insert(0, f"SPEC CONFORMANCE ({result.pass_name}) FAILED: {why}. The backtest is not measuring what the spec says. NOT READY.")
        return "NOT READY", reasons
    if w == MAJOR and verdict == "READY":
        reasons.insert(0, f"CAPPED AT MARGINAL: spec conformance ({result.pass_name}): {why}.")
        return "MARGINAL", reasons
    if w == MINOR:
        reasons.append(f"Spec conformance note ({result.pass_name}): {why}.")
    return verdict, reasons
