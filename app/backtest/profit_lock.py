"""Cut losers short, let winners run: the profit-lock ladder and the adaptive loser cut.

Both pieces are PURE functions of one open trade's state, so the backtest engine (app.backtest.execution), the live / simulated bot engine
(app.bots.engine) and the tests all share one implementation and cannot drift apart.

PROFIT-LOCK LADDER. The stop of a winning trade only ever moves toward price, in dollar steps tied to the best open profit the trade has
reached (its peak, intrabar):

    open profit reaches $100   ->  stop moves to  +$0   (break-even)
    open profit reaches $200   ->  stop moves to  +$75  (locks $50-$100)
    open profit reaches $300   ->  stop moves to  +$150
    open profit reaches $400   ->  stop moves to  +$250 (the winning day is locked in even if the trade reverses)
    open profit reaches $600   ->  stop moves to  +$420
    beyond the last rung       ->  the stop trails at ``trail_frac`` of the peak open profit, so a runner keeps ratcheting

The ladder is expressed in dollars for a 50K account and scaled by ``scale`` for other account sizes. Locks are NET of the round-trip
commission, so "locked $250" means $250 after costs. The stop never moves away from price, so the ladder can only reduce a loss or bank
a gain relative to the plain stop; it never widens risk.

ADAPTIVE LOSER CUT. A trade that is not working is closed before its full stop is reached: once it has been open at least ``min_bars`` bars,
has never shown real follow-through (best open profit under ``max_mfe_frac`` of its initial risk), and is down ``cut_frac`` of its initial risk,
it is closed at the bar close. A trade that first went well and is now pulling back is NOT cut here (the ladder protects it instead).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

# (open profit reached in $, dollars to lock in $) for a 50K account, ascending.
DEFAULT_TIERS: tuple = ((100.0, 0.0), (200.0, 75.0), (300.0, 150.0), (400.0, 250.0), (600.0, 420.0))
DEFAULT_TRAIL_FRAC = 0.72
DEFAULT_SCALE_BASE = 50_000.0


@dataclass(frozen=True)
class ProfitLockConfig:
    tiers: tuple = DEFAULT_TIERS
    trail_frac: float = DEFAULT_TRAIL_FRAC
    scale: float = 1.0                      # 1.0 = the 50K ladder above; 2.0 doubles every rung (a 100K account)
    cost_dollars: float = 0.0               # round-trip commission to add to the lock so the lock is NET of costs

    def scaled_tiers(self) -> tuple:
        return tuple((float(t) * self.scale, float(l) * self.scale) for t, l in self.tiers)


def normalise_tiers(tiers: Optional[Sequence]) -> tuple:
    """Sorted, validated tiers; a lock can never exceed the trigger that produced it (that would lock more than the trade has made)."""
    out = []
    for pair in (tiers or ()):
        trig, lock = float(pair[0]), float(pair[1])
        if trig <= 0:
            continue
        out.append((trig, max(0.0, min(lock, trig))))
    out.sort()
    # locks must be non-decreasing as the trigger rises (a higher rung never locks less)
    fixed, hi = [], 0.0
    for trig, lock in out:
        hi = max(hi, lock)
        fixed.append((trig, hi))
    return tuple(fixed)


def ladder_lock_dollars(peak_open_profit: float, cfg: ProfitLockConfig) -> Optional[float]:
    """Dollars the stop should lock given the best open profit reached, or None when below the first rung.

    Beyond the last rung the lock follows ``trail_frac`` of the peak (never less than the last rung's lock)."""
    tiers = normalise_tiers(cfg.scaled_tiers())
    if not tiers or peak_open_profit < tiers[0][0]:
        return None
    lock = 0.0
    for trig, lk in tiers:
        if peak_open_profit >= trig:
            lock = lk
        else:
            break
    last_trig = tiers[-1][0]
    if cfg.trail_frac > 0 and peak_open_profit > last_trig:
        lock = max(lock, min(peak_open_profit * cfg.trail_frac, peak_open_profit))
    return lock


def lock_stop_price(entry: float, direction: int, size: float, lock_dollars: float, cost_dollars: float = 0.0) -> float:
    """The stop price that books ``lock_dollars`` NET of ``cost_dollars`` when hit. ``size`` is dollars per price unit (engine convention)."""
    if size <= 0:
        return entry
    return entry + direction * (float(lock_dollars) + float(cost_dollars)) / float(size)


def tightened(stop: Optional[float], candidate: float, direction: int) -> Optional[float]:
    """Return the tighter (closer to price) of the two stops; a stop only ever moves toward price."""
    if stop is None:
        return candidate
    if direction == 1:
        return candidate if candidate > stop else stop
    return candidate if candidate < stop else stop


@dataclass(frozen=True)
class LoserCutConfig:
    cut_frac: float = 0.6          # close once the open loss is this fraction of the trade's initial risk
    min_bars: int = 3              # ... and it has been open at least this many bars
    max_mfe_frac: float = 0.25     # ... and it never made more than this fraction of its initial risk


def should_cut_loser(bars_held: int, open_pnl_dollars: float, peak_open_profit: float, initial_risk_dollars: float,
                     cfg: LoserCutConfig) -> bool:
    """True when a trade that is not working should be closed now, before its full stop."""
    if initial_risk_dollars <= 0 or bars_held < cfg.min_bars:
        return False
    if open_pnl_dollars >= 0:
        return False
    if peak_open_profit > cfg.max_mfe_frac * initial_risk_dollars:
        return False
    return -open_pnl_dollars >= cfg.cut_frac * initial_risk_dollars
