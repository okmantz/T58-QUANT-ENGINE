"""Hard cliff gate: every one-step parameter neighbour must stay profitable after costs, or the verdict is capped at MARGINAL.

Parameter stability is only 5 of the 100 score points, so a strategy sitting on a lone spike can still score 75+ on everything else and
be called READY. The score cannot express "this one parameter value is the whole edge". A gate can.

For every tunable parameter p with value v, the two ONE-STEP neighbours are v - step and v + step (step = ``step_frac`` x |v|, never less
than one unit for an integer parameter and never less than 2% of the allowed range for a float; clipped to the allowed range, rounded
for integers). Every other parameter stays at its chosen value. Each neighbour is run through the real engine WITH costs; the gate
passes only when every neighbour's net profit is above ``min_net``. One unprofitable neighbour is a cliff.

    PASS        every neighbour measured is profitable after costs
    FAIL        at least one neighbour loses money after costs        -> caps READY at MARGINAL (never lifts, never rejects by itself)
    UNMEASURED  fewer than ``min_neighbours`` could be measured (no tunable parameters, a backtest error, too few trades)
                -> reported, does NOT cap: a gate that cannot measure cannot convict

The optimizer's own plateau probe (``chosen_neighbor_fitnesses``) is a free pre-screen when its fitness is an edge in R after costs; the
direct measurement here is authoritative because it uses the full engine, the full costs and the full dataset the verdict used.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

DEFAULT_STEP_FRAC = 0.10
DEFAULT_MIN_NEIGHBOURS = 2
EDGE_FITNESS_METRICS = ("edge_lb_r", "mean_r", "plan_edge_r")      # fitness values that are R per trade after costs: > 0 means profitable


@dataclass
class NeighbourPoint:
    param: str
    direction: int                  # -1 / +1
    value: float
    base_value: float
    net: float | None               # net profit after costs ($) or net R, depending on ``unit``
    unit: str = "$"
    profitable: bool | None = None  # None = could not be measured

    def to_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class CliffGateResult:
    status: str                                       # PASS | FAIL | UNMEASURED
    neighbours: list = field(default_factory=list)
    n_measured: int = 0
    n_unprofitable: int = 0
    worst: dict | None = None
    source: str = "direct"                            # "direct" | "plateau_probe"
    notes: list = field(default_factory=list)

    @property
    def caps(self) -> bool:
        return self.status == "FAIL"

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["neighbours"] = [n.to_dict() if hasattr(n, "to_dict") else n for n in self.neighbours]
        d["caps"] = self.caps
        return d

    def render(self) -> str:
        if self.status == "UNMEASURED":
            return "Cliff gate: not measured (" + "; ".join(self.notes or ["too few neighbours"]) + "). No cap applied."
        head = f"Cliff gate: {self.n_measured - self.n_unprofitable}/{self.n_measured} one-step neighbours profitable after costs"
        if self.status == "PASS":
            return head + " -> PASS."
        w = self.worst or {}
        return (head + f" -> FAIL: {w.get('param', '?')} {'-' if w.get('direction', 0) < 0 else '+'}1 step (to {w.get('value')}) nets "
                f"{w.get('net')}{w.get('unit', '')}. A strategy that only works at one exact value is not READY.")


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def evaluate_neighbours(points, *, min_net: float = 0.0, min_neighbours: int = DEFAULT_MIN_NEIGHBOURS, source: str = "direct") -> CliffGateResult:
    """Pure decision rule over already-measured neighbours (a ``NeighbourPoint`` list). Unit tested without an engine."""
    pts = list(points or [])
    measured = [p for p in pts if p.net is not None and _is_num(p.net)]
    for p in pts:
        if p.net is None or not _is_num(p.net):
            p.profitable = None
        else:
            p.profitable = bool(p.net > min_net)
    res = CliffGateResult("UNMEASURED", neighbours=pts, n_measured=len(measured), source=source)
    # a neighbour whose backtest produced NO trades at all (net = -inf from the engine wrapper) is a real failure: the strategy stops trading
    dead = [p for p in pts if p.net is not None and not _is_num(p.net) and p.net < 0]
    for p in dead:
        p.profitable = False
    counted = measured + dead
    res.n_measured = len(counted)
    if len(counted) < int(min_neighbours):
        res.notes.append(f"only {len(counted)} of {len(pts)} neighbour(s) could be measured (need {int(min_neighbours)})")
        return res
    bad = [p for p in counted if p.profitable is False]
    res.n_unprofitable = len(bad)
    if bad:
        worst = min(bad, key=lambda p: (p.net if _is_num(p.net) else -1e18))
        res.worst = worst.to_dict()
        res.status = "FAIL"
    else:
        res.status = "PASS"
    return res


def neighbour_values(base: float, lo: float, hi: float, is_int: bool, step_frac: float = DEFAULT_STEP_FRAC) -> list[tuple[int, float]]:
    """The one-step neighbours of one parameter value as [(direction, value)], clipped to [lo, hi] and de-duplicated against the base."""
    span_range = (hi - lo) if hi > lo else 0.0
    step = max(abs(base) * float(step_frac), 1.0 if is_int else span_range * 0.02)
    out = []
    for d in (-1, 1):
        v = min(max(base + d * step, lo), hi)
        if is_int:
            v = float(int(round(v)))
        if abs(v - base) < 1e-12:
            continue
        out.append((d, float(v)))
    return out


def from_plateau_report(plateau: dict | None, fitness_metric: str) -> CliffGateResult | None:
    """Free pre-screen from the optimizer's own probe. Only meaningful when the fitness is an edge in R after costs; otherwise None."""
    if not plateau or fitness_metric not in EDGE_FITNESS_METRICS:
        return None
    nb = [float(x) for x in (plateau.get("chosen_neighbor_fitnesses") or []) if _is_num(x)]
    if not nb:
        return None
    pts = [NeighbourPoint(param="(optimizer probe)", direction=0, value=float("nan"), base_value=float("nan"), net=x, unit="R") for x in nb]
    return evaluate_neighbours(pts, min_net=0.0, source="plateau_probe")


def measure_neighbours(df, strategy, risk, prop_rules, mc_config, *, step_frac: float = DEFAULT_STEP_FRAC, max_params: int = 8,
                       min_neighbours: int = DEFAULT_MIN_NEIGHBOURS, tmp_dir=None, progress_cb=None) -> CliffGateResult:
    """Run every one-step neighbour through the real engine (net profit after the configured costs) and apply ``evaluate_neighbours``."""
    from app.backtest.risk import build_run_context
    from app.optimize.refinement import _build_adapter
    from app.validation.process_sweep import GenomeEvaluator
    from app.validation.sensitivity import _metric_for

    risk = build_run_context(risk, prop_rules)
    genes, build = _build_adapter(strategy, tmp_dir)
    if not genes:
        return CliffGateResult("UNMEASURED", notes=["the strategy has no tunable numeric parameters"])
    genomes, owners = [], []
    for gi, g in enumerate(genes[:max_params]):
        for d, v in neighbour_values(g.base_value, g.lo, g.hi, g.is_int, step_frac):
            genome = [x.base_value for x in genes]
            genome[gi] = v
            genomes.append(genome)
            owners.append((g.label, d, v, g.base_value))
    if not genomes:
        return CliffGateResult("UNMEASURED", notes=["every parameter sits on its allowed bound, so there is no neighbour to test"])
    with GenomeEvaluator(df=df, strategy=strategy, genes=genes, risk=risk, prop_rules=prop_rules, mc_config=mc_config,
                         local_fn=lambda g: _metric_for(df, build(g), risk, prop_rules, mc_config, "net_profit"),
                         task="metric", task_args=("net_profit",), n_items=len(genomes), tmp_dir=tmp_dir) as ev:
        vals = ev.map(genomes)
    pts = []
    for (label, d, v, base), net in zip(owners, vals):
        net_f = float(net) if net is not None else None
        pts.append(NeighbourPoint(param=label, direction=d, value=v, base_value=base, net=net_f, unit="$"))
    if progress_cb:
        try:
            progress_cb(f"Cliff gate: measured {len(pts)} one-step neighbours.")
        except Exception:  # noqa: BLE001
            pass
    return evaluate_neighbours(pts, min_net=0.0, min_neighbours=min_neighbours, source="direct")


def apply_cliff_cap(verdict: str, reasons: list, *, cfg, strategy, df, risk, prop_rules, mc_config=None, plateau: dict | None = None,
                    log=lambda m: None) -> tuple[str, list, dict]:
    """Demote-only: a READY verdict becomes MARGINAL when a one-step neighbour is unprofitable after costs. Returns (verdict, reasons, evidence).
    Never raises; a measurement that fails is UNMEASURED and caps nothing."""
    reasons = list(reasons)
    ev: dict = {"enabled": bool(getattr(cfg, "cliff_gate_enabled", True))}
    if not ev["enabled"] or verdict != "READY":
        ev["skipped"] = "not READY" if verdict != "READY" else "disabled"
        return verdict, reasons, ev
    res: CliffGateResult | None = None
    try:
        pre = from_plateau_report(plateau, str(getattr(cfg, "fitness_metric", "")))
        if pre is not None and pre.status == "FAIL":
            res = pre
            log("  " + pre.render() + " (from the optimizer's own neighbourhood probe)")
        elif getattr(cfg, "cliff_gate_direct", True) and strategy is not None and df is not None:
            from app.monte_carlo.engine import MonteCarloConfig
            res = measure_neighbours(df, strategy, risk, prop_rules, mc_config or MonteCarloConfig(n_simulations=200, random_seed=1),
                                     step_frac=float(getattr(cfg, "cliff_gate_step_frac", DEFAULT_STEP_FRAC)),
                                     max_params=int(getattr(cfg, "cliff_gate_max_params", 8)),
                                     min_neighbours=int(getattr(cfg, "cliff_gate_min_neighbours", DEFAULT_MIN_NEIGHBOURS)))
            log("  " + res.render())
        else:
            res = pre
    except Exception as exc:  # noqa: BLE001 -- a gate that cannot measure cannot convict
        res = CliffGateResult("UNMEASURED", notes=[f"measurement failed: {exc}"])
        log(f"  Cliff gate skipped: {exc}")
    if res is None:
        res = CliffGateResult("UNMEASURED", notes=["no neighbour evidence available"])
    ev["result"] = res.to_dict()
    ev["status"] = res.status
    if res.caps:
        verdict = "MARGINAL"
        reasons.insert(0, "CLIFF GATE: " + res.render() + " Capped at MARGINAL (parameter stability is only 5 of the 100 score points, so this is a gate, not a score term).")
    return verdict, reasons, ev
