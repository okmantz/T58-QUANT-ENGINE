"""Independent-event count: the READY trade floor counts trades, a basket or pooled run must ALSO count independent events.

300 trades is a fair floor for one strategy on one market. It is not a fair floor for a basket: the same signal firing on ES, NQ and YM on
the same FOMC morning is one macro event traded three times, not three observations, and a pooled run over 8 correlated markets can
reach 300 trades from 40 market-days. ``pooled_edge`` already blocks its bootstrap by trading day for the same reason; this module gives
the verdict the matching count.

An EVENT is a cluster of trades that cannot be treated as independent draws:

    * trades that share a trading day (the 17:00 CT roll, ``app.data.trading_day``), on any market, are one event, and
    * a trade that is still open when the next day starts joins that day's event (a multi-day hold links the days it touches).

``count_independent_events`` returns the number of such clusters. For a single-market intraday strategy with about one trade a day it is
close to the trade count and the extra floor changes nothing; for a basket it is the number that actually measures the evidence.

``effective_events`` adds the correlation haircut a day-cluster cannot see: markets that are correlated on DIFFERENT days (momentum
bursts that start on Tuesday in ES and Wednesday in NQ). It scales the day count by the equicorrelation design effect.
"""
from __future__ import annotations

import pandas as pd

import math
from dataclasses import dataclass, field

DEFAULT_MIN_EVENTS = 150


@dataclass
class EventCount:
    n_trades: int
    n_events: int
    n_markets: int
    trades_per_event: float
    is_basket: bool
    effective_events: float | None = None
    avg_cross_corr: float | None = None
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _market_of(t) -> str | None:
    for attr in ("symbol", "instrument", "market"):
        v = getattr(t, attr, None) if not isinstance(t, dict) else t.get(attr)
        if v:
            return str(v).upper()
    return None


def _stamp(t, attr: str):
    return getattr(t, attr, None) if not isinstance(t, dict) else t.get(attr)


def _trading_day_codes(stamps) -> list:
    """Trading-day label per timestamp via the app's own roll rule; falls back to the UTC date if the helper is unavailable."""
    import pandas as pd
    ser = pd.to_datetime(pd.Series(list(stamps)), utc=True, errors="coerce")
    try:
        from app.data.trading_day import trading_days
        ok = ser.notna().to_numpy()
        out = [None] * len(ser)
        if ok.any():
            td = trading_days(pd.DatetimeIndex(ser[ok].dt.tz_localize(None)))
            for i, d in zip([i for i, k in enumerate(ok) if k], pd.to_datetime(td)):
                out[i] = d.toordinal()
        return out
    except Exception:  # noqa: BLE001
        return [None if pd.isna(x) else x.date().toordinal() for x in ser]


def count_independent_events(trades, *, min_markets_for_basket: int = 2) -> EventCount:
    """Cluster ``trades`` (objects or dicts with entry_time / exit_time and optionally symbol) into independent events."""
    trades = list(trades or [])
    n = len(trades)
    if n == 0:
        return EventCount(0, 0, 0, 0.0, False, notes=["no trades"])
    entries = [_stamp(t, "entry_time") for t in trades]
    exits = [_stamp(t, "exit_time") or _stamp(t, "entry_time") for t in trades]
    e_days = _trading_day_codes(entries)
    x_days = _trading_day_codes(exits)
    markets = {m for m in (_market_of(t) for t in trades) if m}
    parent: dict = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    unparsed = 0
    for i, (d0, d1) in enumerate(zip(e_days, x_days)):
        if d0 is None:
            unparsed += 1
            find(("u", i))                       # an unparseable stamp is its own event, never silently merged
            continue
        find(d0)
        if d1 is not None and d1 > d0:
            for d in range(d0, d1 + 1):          # a multi-day hold links every trading day it touches
                union(d0, d)
    roots = {find(k) for k in list(parent)}
    n_events = len(roots)
    notes = []
    if unparsed:
        notes.append(f"{unparsed} trade(s) had no readable timestamp and were counted as separate events")
    is_basket = len(markets) >= min_markets_for_basket
    return EventCount(n, n_events, len(markets), n / n_events if n_events else 0.0, is_basket, notes=notes)


def effective_events(trades, ec: EventCount | None = None) -> EventCount:
    """Add the equicorrelation design effect for baskets: n_eff = events / (1 + (m - 1) * rho), rho = mean pairwise correlation of the
    markets' daily R. Single-market runs are returned unchanged. Needs per-market R, so trades must carry ``symbol`` and ``pnl`` and
    ``initial_risk`` (or a ready ``r``); anything else falls back to the plain event count."""
    ec = ec or count_independent_events(trades)
    if not ec.is_basket:
        ec.effective_events = float(ec.n_events)
        return ec
    try:
        import numpy as np
        import pandas as pd
        rows = []
        for t in trades:
            m = _market_of(t)
            r = _stamp(t, "r")
            if r is None:
                pnl, risk, size = _stamp(t, "pnl"), _stamp(t, "initial_risk"), _stamp(t, "size")
                if pnl is None or not risk or not size:
                    continue
                r = float(pnl) / (float(risk) * float(size))
            rows.append((m, _stamp(t, "entry_time"), float(r)))
        df = pd.DataFrame(rows, columns=["m", "t", "r"])
        df["d"] = _trading_day_codes(df["t"])
        piv = df.pivot_table(index="d", columns="m", values="r", aggfunc="sum").fillna(0.0)
        piv = piv.loc[:, piv.std() > 0]
        if piv.shape[1] < 2 or piv.shape[0] < 20:
            ec.notes.append("not enough market-days to estimate cross-market correlation; effective count = event count")
            ec.effective_events = float(ec.n_events)
            return ec
        c = np.corrcoef(piv.to_numpy().T)
        m = c.shape[0]
        rho = float((c.sum() - m) / (m * (m - 1)))
        rho = min(max(rho, 0.0), 0.95)
        ec.avg_cross_corr = rho
        ec.effective_events = ec.n_events / (1.0 + (m - 1) * rho)
        return ec
    except Exception as exc:  # noqa: BLE001
        ec.notes.append(f"correlation haircut skipped: {exc}")
        ec.effective_events = float(ec.n_events)
        return ec


def independent_event_gate(trades, *, min_events: int = DEFAULT_MIN_EVENTS, require_for_single_market: bool = False,
                           basket_hint: bool = False) -> dict:
    """The verdict gate: ``applies`` is True for basket / pooled runs (several markets in the trade list, or ``basket_hint`` from the
    caller, e.g. a pooled-edge run). It PASSES when the independent-event count reaches ``min_events``. A single-market run is not
    held to the extra floor unless ``require_for_single_market``."""
    ec = effective_events(trades)
    applies = bool(ec.is_basket or basket_hint or require_for_single_market)
    count_for_gate = ec.effective_events if (ec.is_basket and ec.effective_events is not None) else float(ec.n_events)
    ok = (not applies) or count_for_gate >= float(min_events)
    reason = ""
    if applies and not ok:
        reason = (f"INDEPENDENT EVENTS: {ec.n_trades} trades across {max(ec.n_markets, 1)} market(s) collapse to {ec.n_events} independent events"
                  + (f" (~{ec.effective_events:.0f} after cross-market correlation {ec.avg_cross_corr:.2f})" if ec.avg_cross_corr is not None else "")
                  + f"; a basket or pooled run needs at least {int(min_events)} before it can be READY, because trades fired together on the same day are one observation")
    return {"applies": applies, "passed": bool(ok), "min_events": int(min_events), "count": float(count_for_gate), "reason": reason, **ec.to_dict()}


def pooled_event_count(per_market: dict) -> int:
    """Independent events for a pooled run given ``{symbol: (r_list, day_list)}``: the number of distinct trading days with at least one
    trade on ANY market (same-day trades on different markets share a day-block, exactly as ``pooled_edge_test`` bootstraps them).
    Days may be dates, timestamps or integer day indexes."""
    seen = set()
    for _sym, (rs, ds) in (per_market or {}).items():
        for d in list(ds)[: len(rs)]:
            try:
                seen.add(pd.Timestamp(d).date() if not isinstance(d, (int, float)) else int(d))
            except (TypeError, ValueError):
                seen.add(str(d))
    return len(seen)
