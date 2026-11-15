"""Cost headroom: how many times today's friction can the strategy absorb before net profit reaches zero?

The Strategy Graveyard's central comparison is gross edge per trade vs round-trip friction. The engine already stress-tests at fixed
multiples (1.5x / 2x); this module finds the BREAK-EVEN multiple, which is the single number that says how thin the edge is:

    breakeven_multiple <  1.5   thin     -- one realistic cost surprise erases it
    1.5 <= multiple    <  3.0   modest
    multiple           >= 3.0   comfortable

``find_breakeven_multiple`` is pure (takes a ``net_at(multiple) -> float`` callable) so it is cheap to test; ``cost_headroom_for_strategy``
wires it to the engine using app.optimize.two_stage.stress_risk, the same cost scaler every other stress test uses.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CostHeadroom:
    baseline_net: float
    breakeven_multiple: float | None      # None = still profitable at max_multiple (effectively unbounded)
    band: str                             # "unprofitable" | "thin" | "modest" | "comfortable"
    probes: list = field(default_factory=list)   # (multiple, net) pairs evaluated, in order

    def summary(self) -> str:
        if self.band == "unprofitable":
            return f"Already unprofitable at 1x costs (net {self.baseline_net:,.0f}); no cost headroom."
        be = "more than the largest multiple probed" if self.breakeven_multiple is None else f"{self.breakeven_multiple:.2f}x current costs"
        return f"Net profit {self.baseline_net:,.0f} at 1x costs; reaches zero at {be} -> cost headroom is {self.band}."


def _band(m: float | None) -> str:
    if m is None or m >= 3.0:
        return "comfortable"
    return "thin" if m < 1.5 else "modest"


def find_breakeven_multiple(net_at, *, max_multiple: float = 16.0, tol: float = 0.05, max_iters: int = 24) -> CostHeadroom:
    """Bisect for the cost multiple where ``net_at`` crosses zero. Assumes net profit is non-increasing in cost."""
    probes: list = []

    def f(m: float) -> float:
        v = float(net_at(m))
        probes.append((m, v))
        return v

    base = f(1.0)
    if base <= 0.0:
        return CostHeadroom(base, 0.0, "unprofitable", probes)
    hi = 2.0
    while hi < max_multiple and f(hi) > 0.0:
        hi *= 2.0
    if hi >= max_multiple and f(max_multiple) > 0.0:
        return CostHeadroom(base, None, "comfortable", probes)
    hi = min(hi, max_multiple)
    lo = hi / 2.0 if hi > 2.0 else 1.0
    for _ in range(max_iters):
        if hi - lo <= tol:
            break
        mid = (lo + hi) / 2.0
        if f(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    be = (lo + hi) / 2.0
    return CostHeadroom(base, be, _band(be), probes)


def cost_headroom_for_strategy(df, strategy, risk, **kw) -> CostHeadroom:
    from app.backtest.engine import run_backtest
    from app.optimize.two_stage import stress_risk

    def net_at(m: float) -> float:
        bt = run_backtest(df, strategy, risk if m == 1.0 else stress_risk(risk, m), lookahead_check="skip")
        return float(sum(float(t.pnl) for t in bt.trades))

    return find_breakeven_multiple(net_at, **kw)
