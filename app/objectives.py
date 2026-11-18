"""The three optimisation goals, defined ONCE and read by every engine in the app.

    A    PASS     Pass the prop-firm evaluation, fast, without breaching a rule.
    B    PAYOUT   Reach (and keep reaching) funded-account payouts without blowing the account.
    NET  NET      Make the most money after costs on an account with no evaluation to pass (no prop rules).

Before this module each engine invented its own spelling ("pass", "objective_a", "prop", "prop_lifecycle", "net", "live", ...) and
several silently ignored two of the three (Forge, Speed Run, the bot engine on a rule-free account, the portfolio composer). Everything
now goes through ``normalize_objective`` and the small adapters below, so a run started for Objective B is an Objective B run in the
discovery engine, Forge, the full pipeline, the Evolution Lab, Speed Run, the portfolio composer and the trading bots.

``BLEND`` is the legacy "prop lifecycle" mode (pass AND payout together, with speed and survival bonuses). It stays the default for
callers that name no objective so no existing run changes; it is deliberately NOT one of the three goals.

The mission, rules, primary / secondary metrics and the ENGINE DIRECTIVE for each goal are written down once, verbatim, in ``DIRECTIVES`` and
``ENGINE_DIRECTIVE`` below (docs/OBJECTIVES.md is generated from them). They are the standing instructions for every engine: discovery, test,
optimise, validate and the trading bots. A strategy is judged only by how well it does the job of the objective it is being built for.

Pure functions, no I/O. The heavy simulators live in ``app.prop`` and are imported lazily.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

OBJ_A = "A"
OBJ_B = "B"
OBJ_NET = "NET"
OBJ_BLEND = "BLEND"
OBJECTIVES = (OBJ_A, OBJ_B, OBJ_NET)


@dataclass(frozen=True)
class ObjectiveSpec:
    key: str
    name: str                 # button / column label
    question: str             # the one question this objective answers
    lifecycle_mode: str       # app.prop.lifecycle objective mode
    engine_mode: str          # app.discovery_engine objective_mode ("pass" | "payout" | "net_profit" | "prop")
    governor: str             # app.bots.risk_governor objective code ("A" | "B" | "NET")
    uses_prop_rules: bool     # False -> every prop-firm rule, gate and account simulation is skipped
    primary_metric: str
    speed_matters: bool       # True: time to the goal is part of the score
    what_it_rewards: str
    what_it_punishes: str


SPECS: dict[str, ObjectiveSpec] = {
    OBJ_A: ObjectiveSpec(
        OBJ_A, "Objective A: Evaluation Passer", "How often does a fresh evaluation reach its target inside the horizon without a breach?",
        "pass", "pass", "A", True, "P(pass within the horizon, no breach)", True,
        "A high hit rate on a short clock: front-loaded edge, frequent small wins, a bounded worst day.",
        "Slow strategies, one-big-winner equity curves, any path that touches the trailing floor or the daily limit."),
    OBJ_B: ObjectiveSpec(
        OBJ_B, "Objective B: Payout Hunter", "How often does a funded account reach a payout and stay alive while doing it?",
        "payout", "payout", "B", True, "P(pass AND paid), valid only above the funded-survival floor", False,
        "Smooth, consistent days: low variance, small drawdowns, no single day carrying the profit.",
        "Big days (consistency rules), deep intraday excursions, anything that trades survival for a larger payout."),
    OBJ_NET: ObjectiveSpec(
        OBJ_NET, "Objective C: Net Profit Compounder", "How much does the account earn after costs per unit of drawdown, with no evaluation to pass?",
        "net_profit", "net_profit", "NET", False, "net profit after costs, shrunk by drawdown and a thin sample", False,
        "Edge times frequency, compounding, positive skew; prop-firm rules do not apply.",
        "Cost drag, deep drawdowns, a thin trade sample."),
}

_ALIASES = {
    "a": OBJ_A, "obj_a": OBJ_A, "objective_a": OBJ_A, "objective a": OBJ_A, "pass": OBJ_A, "evaluation": OBJ_A, "eval": OBJ_A,
    "eval_pass": OBJ_A, "pass_eval": OBJ_A,
    "b": OBJ_B, "obj_b": OBJ_B, "objective_b": OBJ_B, "objective b": OBJ_B, "payout": OBJ_B, "get_paid": OBJ_B, "funded": OBJ_B,
    "first_payout": OBJ_B, "prop_net": OBJ_B,
    "c": OBJ_NET, "obj_c": OBJ_NET, "objective_c": OBJ_NET, "objective c": OBJ_NET, "compounder": OBJ_NET, "net_profit_compounder": OBJ_NET,
    "net": OBJ_NET, "net_profit": OBJ_NET, "netprofit": OBJ_NET, "obj_net": OBJ_NET, "objective_net": OBJ_NET, "profit": OBJ_NET, "live": OBJ_NET,
    "prop": OBJ_BLEND, "prop_firm": OBJ_BLEND, "prop_lifecycle": OBJ_BLEND, "lifecycle": OBJ_BLEND, "blend": OBJ_BLEND, "blended": OBJ_BLEND,
    "balanced": OBJ_BLEND, "": OBJ_BLEND,
}


def normalize_objective(value: Any, default: str = OBJ_BLEND) -> str:
    """Any spelling -> "A" | "B" | "NET" | "BLEND". Unknown or empty input returns ``default`` (BLEND: the legacy behaviour)."""
    if isinstance(value, ObjectiveSpec):
        return value.key
    key = str(getattr(value, "value", value) or "").strip().lower().replace("-", "_")
    key = key.replace("  ", " ")
    hit = _ALIASES.get(key) or _ALIASES.get(key.replace(" ", "_"))
    return hit if hit else default


def is_objective(value: Any) -> bool:
    """True when ``value`` names one of the three real goals (A, B or NET)."""
    return normalize_objective(value, default="") in OBJECTIVES


def spec_for(value: Any) -> Optional[ObjectiveSpec]:
    """The spec for A / B / NET, or None for the legacy blend."""
    return SPECS.get(normalize_objective(value))


# --------------------------------------------------------------------------------------------------------------------- adapters
def lifecycle_mode(value: Any) -> str:
    """app.prop.lifecycle mode string for this objective (BLEND -> 'prop_lifecycle')."""
    s = spec_for(value)
    return s.lifecycle_mode if s else "prop_lifecycle"


def engine_mode(value: Any) -> str:
    """Discovery-engine objective_mode string: 'pass' | 'payout' | 'net_profit' | 'prop' (BLEND)."""
    s = spec_for(value)
    return s.engine_mode if s else "prop"


def governor_objective(value: Any) -> str:
    """Bot risk-governor code. The blend has no governor of its own and sizes like A (the evaluation is the first thing to survive)."""
    s = spec_for(value)
    return s.governor if s else OBJ_A


def fitness_metric(value: Any, explicit: str | None = None) -> str:
    """The optimiser fitness metric to use for this objective (an explicit prop metric is kept for A / B / BLEND, replaced for NET)."""
    from app.optimize.refinement import fitness_for_objective_mode
    return fitness_for_objective_mode(lifecycle_mode(value), explicit)


def evolution_goal_preset(value: Any) -> str:
    """Evolution Lab ``fitness_goal`` preset name for this objective (see app.evolution.prop_fitness.FITNESS_GOAL_PRESETS)."""
    return {OBJ_A: "eval_pass_rate", OBJ_B: "first_payout", OBJ_NET: "net_profit"}.get(normalize_objective(value), "balanced")


def portfolio_score_metric(value: Any, *, have_prop_rules: bool = True) -> str:
    """Portfolio-composer scoring metric: pass odds for A, payout odds for B, net profit for NET (profit factor when no rules exist)."""
    o = normalize_objective(value)
    if o == OBJ_NET or not have_prop_rules:
        return "net_profit" if o == OBJ_NET else "profit_factor"
    return "first_payout_probability" if o == OBJ_B else "eval_pass_probability"


def uses_prop_rules(value: Any) -> bool:
    s = spec_for(value)
    return True if s is None else s.uses_prop_rules


# ------------------------------------------------------------------------------------------------------------------ champion ranking
def _f(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def champion_rank_key(value: Any, champion: dict) -> tuple:
    """Sort key (bigger is better) for a discovery-engine champion under ``value``. Reads only fields the engine already measured.

    A      lower bound of P(pass within 30 days), then the point estimate, then the edge lower bound (the engine's long-standing ranking).
    B      P(pass AND paid), then mean payouts, then LOWER bust odds, then edge. A champion that busts more often than it passes is not a
           payout candidate however large its payout, so bust odds above 50% sort below every champion at or under it.
    NET    net profit objective of the champion's own trades (after costs, shrunk by drawdown), then the edge lower bound. No prop numbers.
    BLEND  same as A (legacy).
    """
    o = normalize_objective(value)
    edge = -1e9 if champion.get("edge_lb_r") is None else _f(champion.get("edge_lb_r"), -1e9)
    td = champion.get("thirty_day")
    td_ok = bool(td) and not td.get("error")
    if o == OBJ_NET:
        net = champion.get("net_objective")
        return (_f(net, -1e18) if net is not None else -1e18, edge)
    if not td_ok:
        return (-1.0, -1.0, -1.0, edge) if o == OBJ_B else (-1.0, -1.0, edge)
    if o == OBJ_B:
        bust = _f(td.get("p_bust_30"))
        return (0 if bust > 0.5 else 1, _f(td.get("p_paid")), _f(td.get("mean_payout_usd")), -bust, edge)
    return (_f(td.get("lower_bound")), _f(td.get("p_pass_30")), edge)


def annotate_champion(value: Any, champion: dict, trades: Iterable | None = None, account_size: float | None = None) -> dict:
    """Stamp ``objective`` / ``objective_score`` (and ``net_objective`` for NET) onto a champion record, in place; returns it."""
    o = normalize_objective(value)
    champion["objective"] = o
    if o == OBJ_NET and trades is not None:
        from app.prop.lifecycle import net_profit_objective
        r = net_profit_objective(list(trades), account_size)
        champion["net_objective"] = r["objective"]
        champion["net_components"] = {k: r[k] for k in ("net_profit", "n_trades", "net_per_trade", "profit_factor", "max_drawdown_pct")}
    td = champion.get("thirty_day")
    if o == OBJ_A and td and not td.get("error"):
        champion["objective_score"] = {"metric": "P(pass <= 30d), 95% lower bound", "value": _f(td.get("lower_bound")), "point": _f(td.get("p_pass_30"))}
    elif o == OBJ_B and td and not td.get("error"):
        champion["objective_score"] = {"metric": "P(pass and paid)", "value": _f(td.get("p_paid")), "bust_30": _f(td.get("p_bust_30"))}
    elif o == OBJ_NET and champion.get("net_objective") is not None:
        champion["objective_score"] = {"metric": "net-profit objective", "value": _f(champion["net_objective"])}
    return champion


# -------------------------------------------------------------------------------------------------------------------- trade scoring
@dataclass
class ObjectiveScore:
    objective: str
    value: float                       # what an optimiser maximises
    headline: str
    feasible: bool = True              # B: survival floor met; A / NET: enough evidence to read the number at all
    reason: str = ""
    components: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"objective": self.objective, "value": self.value, "headline": self.headline, "feasible": self.feasible,
                "reason": self.reason, "components": self.components}


def score_trades(trades, rules, value: Any, *, cfg=None, account_size: float | None = None, horizon_days: int = 30,
                 split_pct: float = 80.0) -> ObjectiveScore:
    """Score one trade list under one objective with the app's own simulators.

    A and B need ``rules`` (a ``PropRules``). Without rules they fall back to the net-profit score and say so in ``reason`` rather than
    inventing a pass or payout number. NET never uses rules."""
    from app.prop import objectives as po
    from app.prop.lifecycle import net_profit_objective, run_lifecycle
    o = normalize_objective(value, default=OBJ_A)
    if o == OBJ_BLEND:
        o = OBJ_A
    trades = list(trades or [])
    if o == OBJ_NET or rules is None:
        r = net_profit_objective(trades, account_size or (getattr(rules, "account_size", None) if rules else None))
        feasible = r["n_trades"] >= 30 and r["net_profit"] > 0
        why = "" if o == OBJ_NET else "no prop rules supplied: scored on net profit instead"
        if o == OBJ_NET and not feasible:
            why = "fewer than 30 trades or no net profit"
        return ObjectiveScore(OBJ_NET if o == OBJ_NET else o, float(r["objective"]),
                              f"net ${r['net_profit']:,.0f} over {r['n_trades']} trades, max drawdown {r['max_drawdown_pct']:.1f}%",
                              feasible, why, {k: v for k, v in r.items() if k != "mode"})
    if len(trades) < 20:
        return ObjectiveScore(o, float("-inf"), f"only {len(trades)} trades: too few to simulate an account", False, "fewer than 20 trades", {})
    lc = run_lifecycle(trades, rules, cfg, objective_mode=lifecycle_mode(o))
    if o == OBJ_A:
        rep = po.objective_a_report(lc, horizon_days)
        val = rep["primary_pct"] if rep.get("primary_pct") is not None else float(lc.evaluation.p_pass)
        return ObjectiveScore(OBJ_A, float(val), lc.headline(), True, "" if rep.get("horizon_covered") else
                              f"history shorter than {horizon_days} days: scored on pass odds with no time limit", rep)
    rep = po.objective_b_report(lc, split_pct)
    sw = rep["sustainable"]
    return ObjectiveScore(OBJ_B, float(lc.objective_value), lc.headline(), bool(sw["feasible"]), "" if sw["feasible"] else sw["why"], rep)


# -------------------------------------------------------------------------------------------------------------------- wiring audit
# Every engine and the function that reads the objective in it. ``tests/test_objectives_wiring.py`` imports each entry, so a refactor
# that drops the wiring fails a test instead of silently reverting an engine to the blend.
ENGINE_WIRING: dict[str, str] = {
    "Discovery engine (Search Lab / Evolution Lab / Forge / Speed Run presets)": "app.discovery_engine.engine:DiscoveryEngine",
    "Forge": "app.orchestration.forge:_forge_fitness_metric",
    "Full pipeline": "app.orchestration.full_pipeline:_objective_key",
    "Evolution Lab": "app.evolution.engine:EvolutionConfig.objective_mode",
    "Speed Run": "app.orchestration.speed_run:SpeedRunConfig.objective_mode",
    "Portfolio composer": "app.portfolio.portfolio:PortfolioConfig.objective_mode",
    "Trading bots": "app.bots.engine:BotEngine._objective",
    "Web forms": "app.web.objective_mode:apply_objective_mode_to_form",
}


# ================================================================================================================ THE DIRECTIVES
# Standing instructions for every engine. Written once, here; docs/OBJECTIVES.md and the trading-bot pages read them from this file.
# The wording of ``mission``, ``rules`` and ``goal`` is the owner's own and is kept verbatim.
A_TARGET_DAYS = 30            # Objective A: the horizon it is optimised for ...
A_MAX_DAYS = 60               # ... and the longest horizon still acceptable
B_PAYOUT_HORIZON_DAYS = 365   # Objective B: first payout inside a year, funded account alive
C_MIN_TRADES = 100            # Objective C: fewer trades than this is an anecdote, not an out-of-sample edge


@dataclass(frozen=True)
class Directive:
    key: str                         # "A" | "B" | "NET" (Objective C)
    letter: str                      # "A" | "B" | "C" as the owner writes it
    codename: str                    # EVALUATION PASSER / PAYOUT HUNTER / NET PROFIT COMPOUNDER
    mission: str
    rules: tuple
    primary_metric: str
    secondary_metrics: tuple
    goal: str
    horizon_days: Optional[int]      # the horizon the primary metric is read at (None: no evaluation clock)
    horizon_max_days: Optional[int]
    risk_posture: str                # how much variance the objective accepts, in one line
    sizing_posture: str
    market_scope: str
    overnight_allowed: bool
    forbidden_inputs: tuple = ()     # numbers that belong to ANOTHER objective and must never move this one's ranking


ENGINE_DIRECTIVE = (
    "Each objective must have its own independent strategy discovery, optimization, portfolio construction, position-sizing logic, risk governor, "
    "scoring system, and selection criteria. Never optimize a strategy for one objective using another objective's priorities. A strategy that "
    "is excellent at passing an evaluation may be unsuitable for payouts or live compounding. Strategies must be judged exclusively by how "
    "effectively they accomplish their assigned mission.")

DIRECTIVES: dict[str, Directive] = {
    OBJ_A: Directive(
        OBJ_A, "A", "EVALUATION PASSER",
        "Pass a prop-firm evaluation as quickly and efficiently as possible. Optimize strategy portfolios for the highest probability of reaching the "
        "profit target within 30 days, with 60 days as the maximum acceptable horizon, while minimizing the probability of breaching drawdown rules "
        "before passing.",
        ("Prioritize probability of passing, speed to target, and capital efficiency.",
         "Accept higher variance and more aggressive risk than Objective B, provided drawdown survival remains statistically viable.",
         "Optimize position sizing, trade frequency, strategy combinations, and risk dynamically as the account approaches its profit target or "
         "drawdown limit.",
         "Maximize the probability of reaching the profit target before violating any account rules."),
        "Probability of passing within 30/60 days.",
        ("Median days to pass", "breach probability", "profit-target efficiency", "risk of ruin"),
        "The goal is to pass—not to preserve the account long-term.",
        A_TARGET_DAYS, A_MAX_DAYS,
        "aggressive: more variance than B, as long as survival to the target stays statistically viable",
        "dynamic: full size while the floor is far, trimmed as the target or the floor comes near; ends at the pass",
        "intraday futures inside the firm's rules (flat at the close, news and consistency rules respected)", False,
        ("p_paid", "mean_payout_usd", "net_objective", "funded_survival", "cagr", "calmar")),
    OBJ_B: Directive(
        OBJ_B, "B", "PAYOUT HUNTER",
        "Secure a funded account, preserve it, and extract payouts as quickly and consistently as possible. Optimize for the highest probability of "
        "generating a payout while minimizing the risk of losing the funded account.",
        ("Prioritize survivability, capital preservation, consistency, and sustainable payout generation.",
         "Use conservative risk sizing and reduce exposure as drawdown increases or the account's safety buffer shrinks.",
         "Favor robust strategies, low drawdown, shorter losing streaks, consistency-rule compliance, and uncorrelated portfolio exposure.",
         "Optimize for reaching payout thresholds efficiently without jeopardizing the account.",
         "Avoid unnecessary risk after achieving payout eligibility or daily profit objectives."),
        "Probability of reaching a payout without breaching account rules.",
        ("Time to first payout", "payout expectancy", "account survival", "drawdown", "consistency compliance", "repeat payout probability"),
        "The goal is to get paid and keep the account alive—not to pass aggressively or maximize raw trading profits.",
        None, B_PAYOUT_HORIZON_DAYS,
        "conservative: low variance, small drawdowns, short losing streaks, no single day carrying the profit",
        "shrinks with drawdown and with the safety buffer; eased back once payout-eligible or after a good day",
        "intraday futures inside the firm's rules, diversified across uncorrelated sleeves", False,
        ("p_pass_30", "lower_bound", "cagr", "calmar", "net_objective")),
    OBJ_NET: Directive(
        OBJ_NET, "C", "NET PROFIT COMPOUNDER",
        "Maximize long-term risk-adjusted net profit on unrestricted live accounts. Optimize for sustainable wealth generation and account growth "
        "after all trading costs, with no prop-firm restrictions.",
        ("Maximize long-term net profit and compound growth.",
         "Optimize risk-adjusted returns, expectancy, drawdown efficiency, and capital utilization.",
         "Trade any suitable market: forex, stocks, indices, futures, commodities, etc.",
         "Permit overnight, swing, position, and longer-term trades where statistically advantageous.",
         "Allow flexible leverage, sizing, holding periods, portfolio allocation, and compounding based on validated risk controls.",
         "Prioritize durable out-of-sample edges over short-term performance or artificial trading-frequency constraints."),
        "Long-term net profit and compounded growth.",
        ("Risk-adjusted return", "Calmar ratio", "expectancy", "maximum drawdown", "return on capital", "robustness across market regimes"),
        "The goal is to grow capital and maximize net wealth—not pass evaluations or satisfy payout rules.",
        None, None,
        "growth: as much volatility as the validated drawdown budget allows, throttled as drawdown deepens",
        "compounds with equity; falls to a floor multiple as drawdown from the equity peak deepens",
        "any liquid market: futures, indices, commodities, FX, equities; overnight, swing and position holds allowed", True,
        ("p_pass_30", "lower_bound", "p_paid", "mean_payout_usd", "p_bust_30")),
}


def directive_for(value: Any) -> Optional[Directive]:
    """The standing directive for A / B / C (any spelling), or None for the legacy blend."""
    return DIRECTIVES.get(normalize_objective(value))


def metrics_for(value: Any) -> dict:
    """{'primary': str, 'secondary': tuple} an objective is judged on."""
    d = directive_for(value)
    return {"primary": d.primary_metric, "secondary": d.secondary_metrics} if d else {"primary": "", "secondary": ()}


def isolated_champion(value: Any, champion: dict) -> dict:
    """A copy of ``champion`` with every number that belongs to ANOTHER objective removed. Ranking this copy must give the same order as ranking
    the original, which ``tests/test_objective_directive.py`` checks: it is how the engine directive ("never optimize a strategy for one objective
    using another objective's priorities") is enforced rather than just stated."""
    d = directive_for(value)
    if d is None:
        return dict(champion)
    out = {k: v for k, v in champion.items() if k not in d.forbidden_inputs}
    td = out.get("thirty_day")
    if isinstance(td, dict):
        out["thirty_day"] = {k: v for k, v in td.items() if k not in d.forbidden_inputs}
    return out


def directive_markdown() -> str:
    """docs/OBJECTIVES.md body, generated from ``DIRECTIVES`` so the page can never drift from the code."""
    out = ["# The three objectives", "",
           "Generated from `app/objectives.py` (`DIRECTIVES`, `ENGINE_DIRECTIVE`). Edit the code, not this file.", ""]
    for key in OBJECTIVES:
        d = DIRECTIVES[key]
        out += [f"## OBJECTIVE {d.letter}: {d.codename}", "", f"**Mission:** {d.mission}", ""]
        out += [f"- {r}" for r in d.rules]
        out += ["", f"**Primary metric:** {d.primary_metric}", f"**Secondary metrics:** {', '.join(d.secondary_metrics)}.", "", f"**{d.goal}**", "",
                f"- Risk posture: {d.risk_posture}", f"- Sizing: {d.sizing_posture}", f"- Markets: {d.market_scope}",
                f"- Overnight holds: {'allowed' if d.overnight_allowed else 'not allowed'}", ""]
    out += ["## ENGINE DIRECTIVE", "", ENGINE_DIRECTIVE, ""]
    return "\n".join(out)
