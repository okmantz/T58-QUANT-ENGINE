"""The two prop-firm objectives, as separate, testable numbers (2026-11-14, audit item O1/O2).

OBJECTIVE A -- pass the evaluation efficiently.
    Primary metric  P(reach the target within ``horizon`` calendar days without breaching any rule), in percent of purchased attempts.
    Also reported   time to target, maximum adverse excursion (drawdown of the passing paths), daily-loss survival, the share of attempts
                    blocked by consistency / minimum-day rules after touching the target.

OBJECTIVE B -- keep a funded account paying.
    Primary metric  expected SUSTAINABLE withdrawals per funded account: the trader's share of the payouts, counted only when the account's
                    survival probability at the chosen horizon (default 90 days) clears the stated floor. Below the floor the score is 0, so a
                    strategy cannot buy a big expected payout with a high chance of blowing the account.
    Also reported   survival at 30 / 60 / 90 days (Kaplan-Meier), P(1st / 2nd / 3rd payout), drawdown cause split, withdrawals net of costs.

Both read a ``LifecycleResult`` (``app.prop.lifecycle.run_lifecycle``), which already replays every path through the exact-rule
``simulate_account`` -- the same engine the pass/payout gates use -- so no number here comes from an approximation. All functions are pure.
"""
from __future__ import annotations

DEFAULT_PASS_HORIZON_DAYS = 30
DEFAULT_SURVIVAL_HORIZON_DAYS = 90
DEFAULT_MIN_SURVIVAL_PCT = 70.0
SURVIVAL_REPORT_DAYS = (30, 60, 90)


def _get(d: dict | None, k, default=None):
    if not d:
        return default
    for key in (k, str(k)):
        if key in d:
            return d[key]
    return default


# ---------------------------------------------------------------------------------------------------------------- Objective A
def objective_pass(lc, horizon_days: int | None = None) -> float:
    """O1: P(pass within ``horizon_days`` calendar days, no breach), % of all purchased attempts. ``None`` = no time limit.

    A pass is by construction a path that reached the target without breaching; censored paths (history ran out) are NOT counted."""
    e = lc.evaluation
    if horizon_days is None:
        return float(e.p_pass)
    v = _get(e.p_pass_within_days, int(horizon_days))
    if v is None:
        raise ValueError(f"horizon {horizon_days}d was not simulated; LifecycleConfig.pass_windows_days has {sorted(e.p_pass_within_days)}")
    if not _get(e.windows_covered, int(horizon_days), True):
        raise ValueError(f"the source history is shorter than {horizon_days} calendar days, so P(pass within {horizon_days}d) is not measurable")
    return float(v)


def objective_a_report(lc, horizon_days: int = DEFAULT_PASS_HORIZON_DAYS) -> dict:
    e = lc.evaluation
    try:
        primary = objective_pass(lc, horizon_days)
        covered = True
    except ValueError:
        primary, covered = None, False
    return {
        "objective": "A", "name": "Pass the evaluation efficiently",
        "primary_metric": f"P(pass within {horizon_days} days, no breach)", "primary_pct": primary, "horizon_covered": covered,
        "p_pass_any_time_pct": float(e.p_pass), "p_pass_ci": list(e.p_pass_ci),
        "time_to_target_calendar_days": e.time_to_target.get("calendar", {}),
        "time_to_target_trading_days": e.time_to_target.get("trading", {}),
        "max_adverse_excursion": {"p_fail_max_drawdown_pct": float(e.p_fail_max_drawdown)},
        "daily_loss": {"p_violation_pct": float(e.p_daily_loss_violation), "p_fail_on_rule_pct": float(e.p_fail_daily_loss),
                       "survival_pct": 100.0 - float(e.p_daily_loss_violation)},
        "rule_blocks": {"p_blocked_after_target_pct": float(e.p_blocked_by_rules_after_target),
                        "p_consistency_ok_given_target_pct": e.p_consistency_ok_given_target},
        "p_fail_time_limit_pct": float(e.p_fail_time_limit), "p_unresolved_pct": float(e.p_unresolved),
    }


# ---------------------------------------------------------------------------------------------------------------- Objective B
def _funded_fraction(lc) -> float:
    return float(lc.funded.p_funded) / 100.0


def objective_payout(lc, n_payouts: int = 1, min_survive_days: int | None = None) -> float:
    """O2: P(pass AND reach >= ``n_payouts`` payouts [AND still alive after ``min_survive_days``]), % of all purchased attempts.

    ``n_payouts`` 1..3 are measured directly. The survival factor multiplies by the funded Kaplan-Meier S(min_survive_days); it assumes
    survival is independent of the payout count, which is conservative for the first payout and optimistic for the third -- so the number is
    a ranking value, and the report states the assumption."""
    f = lc.funded
    cond = {1: f.p_first_payout_given_funded, 2: f.p_second_payout_given_funded, 3: f.p_third_payout_given_funded}.get(int(n_payouts))
    if int(n_payouts) not in (1, 2, 3):
        raise ValueError("n_payouts must be 1, 2 or 3 (those are the payout counts the lifecycle measures)")
    if cond is None:
        return 0.0
    out = _funded_fraction(lc) * float(cond)          # % of attempts
    if min_survive_days is not None:
        s = _get(f.p_survive_given_funded, int(min_survive_days))
        if s is None:
            raise ValueError(f"funded survival at {min_survive_days}d was not simulated or not observed")
        out *= float(s) / 100.0
    return out


def sustainable_withdrawals(lc, split_pct: float = 80.0, *, survival_days: int = DEFAULT_SURVIVAL_HORIZON_DAYS,
                            min_survival_pct: float = DEFAULT_MIN_SURVIVAL_PCT) -> dict:
    """Primary metric of Objective B: expected trader withdrawals per FUNDED account, valid only while survival clears the floor."""
    f = lc.funded
    s = _get(f.p_survive_given_funded, int(survival_days))
    gross = float(f.expected_gross_payout_per_funded or 0.0)
    net = gross * float(split_pct) / 100.0
    feasible = s is not None and float(s) >= float(min_survival_pct)
    return {"gross_per_funded": gross, "net_per_funded": net, "split_pct": float(split_pct), "survival_days": int(survival_days),
            "survival_pct": None if s is None else float(s), "min_survival_pct": float(min_survival_pct), "feasible": bool(feasible),
            "score": net if feasible else 0.0,
            "why": ("survival floor met" if feasible else
                    ("survival not observed at this horizon" if s is None else f"survival {float(s):.0f}% is under the {min_survival_pct:.0f}% floor"))}


def objective_net(lc) -> float:
    """Expected trader net per purchased attempt: the split of the payouts minus the evaluation fee (already computed by the lifecycle)."""
    return float(lc.expected_net_per_attempt)


def objective_b_report(lc, split_pct: float = 80.0, *, survival_days: int = DEFAULT_SURVIVAL_HORIZON_DAYS,
                       min_survival_pct: float = DEFAULT_MIN_SURVIVAL_PCT) -> dict:
    f = lc.funded
    sw = sustainable_withdrawals(lc, split_pct, survival_days=survival_days, min_survival_pct=min_survival_pct)
    return {
        "objective": "B", "name": "Sustainable funded payouts",
        "primary_metric": f"expected withdrawals per funded account, valid only if P(survive {survival_days}d) >= {min_survival_pct:.0f}%",
        "sustainable": sw, "primary_score": sw["score"],
        "survival_pct": {int(d): _get(f.p_survive_given_funded, d) for d in SURVIVAL_REPORT_DAYS},
        "survival_observed_accounts": {int(d): _get(f.survival_at_risk, d) for d in SURVIVAL_REPORT_DAYS},
        "p_payout_given_funded_pct": {1: f.p_first_payout_given_funded, 2: f.p_second_payout_given_funded, 3: f.p_third_payout_given_funded},
        "funded_failure_causes_pct": {"daily_loss": f.p_fail_funded_daily_loss, "drawdown": f.p_fail_funded_drawdown},
        "median_payout": f.median_payout_amount, "time_to_first_payout_days": f.time_to_first_payout,
        "net_per_purchased_attempt": objective_net(lc), "p_funded_pct": float(f.p_funded),
        "assumption": "survival is treated as independent of payout count when combining them; see objective_payout()",
    }


# ---------------------------------------------------------------------------------------------------------------- dispatch
def objective_value(lc, mode: str, *, horizon_days: int = DEFAULT_PASS_HORIZON_DAYS, split_pct: float = 80.0) -> float:
    """The number an optimiser maximises for ``mode`` in {"pass", "payout", "prop_net"}. Raises for any other mode (those live in lifecycle.py)."""
    m = str(mode)
    if m == "pass":
        try:
            return objective_pass(lc, horizon_days)
        except ValueError:
            return objective_pass(lc, None)
    if m == "payout":
        has_s90 = _get(lc.funded.p_survive_given_funded, DEFAULT_SURVIVAL_HORIZON_DAYS) is not None
        return objective_payout(lc, 1, DEFAULT_SURVIVAL_HORIZON_DAYS if has_s90 else None)
    if m == "prop_net":
        return objective_net(lc)
    raise ValueError(f"unknown objective mode {mode!r}")
