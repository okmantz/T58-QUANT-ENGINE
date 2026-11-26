"""Same-days replay: re-run the frozen strategy over the exact days it traded live, then diff the two trade lists.

The frozen-code guard proves the CODE did not change. SPRT and the win-rate / drawdown drift flags prove the RESULTS look consistent.
Neither proves the live system took the trades the backtest engine would have taken on the same bars. If it did not, the backtest
that justified going live is not the thing running live (a different fill rule, a data gap, a bar-close race, a broker-side exit the
model never had), and every forward-test statistic is measuring something else.

    replay    run_backtest over the bars covering the live window (history before it is warm-up)
    diff      one-to-one match by direction and entry time (default: within two bars)
    kill      ANY trade that appears in one list and not the other -> the forward test is killed (entries blocked, sticky)

Scope rules that keep the kill honest rather than noisy:
  * the window ends where entries were blocked (a halted live session SHOULD stop trading; the replay must not be blamed for the rest);
  * a trade still open at the window end is excluded from both lists;
  * a replay trade that began before the live session started is excluded (the live account did not exist yet);
  * price differences between matched trades are REPORTED (slippage, spread) but are not a kill: they are not "a trade in one and not the other".
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class TradeLite:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp | None
    direction: int
    entry_price: float
    exit_price: float | None = None
    source: str = ""

    def label(self) -> str:
        return f"{'LONG' if self.direction > 0 else 'SHORT'} @ {self.entry_price:g} on {self.entry_time:%Y-%m-%d %H:%M}"


@dataclass
class ReplayDiff:
    status: str                                   # OK | KILL | UNMEASURED
    window: tuple | None = None
    n_live: int = 0
    n_replay: int = 0
    matched: list = field(default_factory=list)   # [(live, replay)]
    only_live: list = field(default_factory=list)
    only_replay: list = field(default_factory=list)
    entry_slip_mean: float | None = None          # mean signed live-minus-replay entry price in the trade direction (cost of live execution)
    notes: list = field(default_factory=list)

    @property
    def kill(self) -> bool:
        return self.status == "KILL"

    def kill_reason(self) -> str:
        parts = []
        if self.only_live:
            parts.append(f"{len(self.only_live)} live trade(s) the replay never takes (e.g. {self.only_live[0].label()})")
        if self.only_replay:
            parts.append(f"{len(self.only_replay)} replay trade(s) never taken live (e.g. {self.only_replay[0].label()})")
        return ("SAME-DAYS REPLAY KILL: " + "; ".join(parts) + ". The live system is not trading the strategy that was backtested.") if parts else ""

    def to_dict(self) -> dict:
        def row(t): return {"entry_time": str(t.entry_time), "direction": t.direction, "entry_price": t.entry_price, "source": t.source}
        return {"status": self.status, "window": [str(x) for x in self.window] if self.window else None, "n_live": self.n_live, "n_replay": self.n_replay,
                "n_matched": len(self.matched), "only_live": [row(t) for t in self.only_live], "only_replay": [row(t) for t in self.only_replay],
                "entry_slip_mean": self.entry_slip_mean, "notes": list(self.notes), "kill_reason": self.kill_reason()}


def _utc(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def live_trades_from_journal(journal, session_id: int) -> list[TradeLite]:
    """CLOSED journal trades of one session (open ones are excluded: they have no exit to compare and may still be running)."""
    out = []
    for r in journal.all_trades(session_id):
        if r.status != "closed" or r.exit_time is None:
            continue
        out.append(TradeLite(_utc(pd.Timestamp(r.entry_time, unit="s")), _utc(pd.Timestamp(r.exit_time, unit="s")), int(r.direction), float(r.entry_price),
                             None if r.exit_price is None else float(r.exit_price), "live"))
    return sorted(out, key=lambda t: t.entry_time)


def replay_trades(bars: pd.DataFrame, strategy, risk, window_start, window_end, *, adaptive_risk=None) -> list[TradeLite]:
    """Backtest ``strategy`` over ``bars`` (which must include warm-up history before ``window_start``) and keep trades entered inside the window
    that also finished inside it."""
    from app.backtest.engine import run_backtest
    bt = run_backtest(bars, strategy, risk, adaptive_risk=adaptive_risk) if adaptive_risk is not None else run_backtest(bars, strategy, risk)
    a, b = _utc(window_start), _utc(window_end)
    out = []
    for t in bt.trades:
        et, xt = _utc(t.entry_time), _utc(t.exit_time)
        if et < a or xt > b or str(getattr(t, "exit_reason", "")) == "end_of_data":
            continue
        out.append(TradeLite(et, xt, int(t.direction), float(t.entry_price), float(t.exit_price), "replay"))
    return sorted(out, key=lambda t: t.entry_time)


def diff_trade_lists(live: list[TradeLite], replay: list[TradeLite], *, tol: pd.Timedelta, window: tuple | None = None) -> ReplayDiff:
    """One-to-one nearest match on (direction, entry time within ``tol``). Pure: unit tested without an engine or a broker."""
    d = ReplayDiff("OK", window=window, n_live=len(live), n_replay=len(replay))
    free = list(range(len(replay)))
    slips = []
    for lt in live:
        best, best_gap = None, None
        for k in free:
            rt = replay[k]
            if rt.direction != lt.direction:
                continue
            gap = abs(rt.entry_time - lt.entry_time)
            if gap <= tol and (best_gap is None or gap < best_gap):
                best, best_gap = k, gap
        if best is None:
            d.only_live.append(lt)
        else:
            free.remove(best)
            d.matched.append((lt, replay[best]))
            slips.append((lt.entry_price - replay[best].entry_price) * lt.direction)
    d.only_replay = [replay[k] for k in free]
    if slips:
        d.entry_slip_mean = float(sum(slips) / len(slips))
    if d.only_live or d.only_replay:
        d.status = "KILL"
    return d


def run_same_days_replay(*, journal, session_id: int, bars: pd.DataFrame, strategy, risk, live_start, live_end, timeframe_minutes: int,
                         tol_bars: float = 2.0, min_live_trades: int = 1, adaptive_risk=None) -> ReplayDiff:
    """The full check. ``bars`` = completed bars from before ``live_start`` through now. ``live_end`` = now, or the moment entries were blocked."""
    live = [t for t in live_trades_from_journal(journal, session_id) if _utc(live_start) <= t.entry_time and t.exit_time is not None and t.exit_time <= _utc(live_end)]
    win = (_utc(live_start), _utc(live_end))
    if len(bars) < 50:
        return ReplayDiff("UNMEASURED", window=win, notes=["too few bars for a replay"])
    first_bar = _utc(bars["timestamp"].iloc[0])
    if first_bar > _utc(live_start):
        return ReplayDiff("UNMEASURED", window=win, notes=[f"bars start {first_bar:%Y-%m-%d %H:%M}, after the live start: no data to replay the first live days"])
    tol = pd.Timedelta(minutes=float(timeframe_minutes) * float(tol_bars))
    rep = replay_trades(bars, strategy, risk, live_start, live_end, adaptive_risk=adaptive_risk)
    if not live and not rep:
        return ReplayDiff("OK", window=win, notes=["no trades in the window on either side"])
    if len(live) < int(min_live_trades) and not rep:
        return ReplayDiff("OK", window=win, n_live=len(live), notes=["nothing to compare yet"])
    # a replay trade whose entry is within tol of the window end may simply not have been polled yet: drop it
    rep = [t for t in rep if t.entry_time <= _utc(live_end) - tol]
    live = [t for t in live if t.entry_time <= _utc(live_end) - tol]
    return diff_trade_lists(live, rep, tol=tol, window=win)
