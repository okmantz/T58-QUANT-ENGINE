"""Stage-aware view of a firm's rules: evaluation phase(s) -> funded stage -> payout terms -> fees (2026-11-14, audit item O1/O2).

``PropAccount`` still executes one rule set per account; this module gives every engine ONE read-only description of the whole lifecycle,
derived from the same preset, so the evaluation (Objective A) and the funded stage (Objective B) are never described by two different
hand-copied tables. Nothing here is a second source of truth: ``firm_rules(preset_key)`` builds the view from ``presets`` and ``fee_schedule``.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.prop.presets import get_fee_info, get_preset


@dataclass(frozen=True)
class StageRules:
    name: str                          # "evaluation" | "funded"
    drawdown_type: str
    dd_basis: str
    trailing_lock: bool
    lock_offset_pct: float
    daily_loss_pct: float | None
    daily_loss_action: str
    max_contracts: int | None
    profit_target_pct: float | None
    consistency_pct: float | None
    min_trading_days: int


@dataclass(frozen=True)
class PayoutRules:
    winning_days: int
    min_winning_day_profit: float
    consistency_pct: float | None
    profit_goal_pct: float             # profit above the buffer a cycle must earn
    buffer_pct: float                  # buffer the account must hold above the start before a payout
    cap_pct: float | None
    cap_dollars: float | None
    max_payouts: int | None
    cycle_days: int
    split_pct: float
    pins_floor_to_lock: bool           # post-payout: the floor stops trailing and sits at the lock level


@dataclass(frozen=True)
class FeeSchedule:
    purchase: float | None
    reset: float | None
    activation: float
    monthly: bool
    source_tier: str
    date_checked: str


@dataclass(frozen=True)
class FirmRules:
    preset_key: str
    firm: str
    account_size: float
    evaluation: StageRules
    funded: StageRules
    payout: PayoutRules
    fees: FeeSchedule
    funded_starts_fresh: bool
    rules_checked_on: str


def firm_rules(preset_key: str) -> FirmRules:
    p = get_preset(preset_key)
    fee = get_fee_info(preset_key)
    ev = StageRules("evaluation", p.drawdown_type, p.dd_basis, p.trailing_lock, p.trailing_lock_offset_pct, p.daily_loss_limit_pct,
                    p.daily_loss_action, p.max_contracts, p.evaluation_profit_target_pct, p.consistency_rule_pct, p.min_trading_days)
    fu = StageRules("funded", p.drawdown_type, p.dd_basis, p.trailing_lock, p.trailing_lock_offset_pct, p.daily_loss_limit_pct,
                    p.daily_loss_action, p.max_contracts, None, p.funded_consistency_rule_pct, 0)
    pay = PayoutRules(p.winning_days_for_payout, p.min_winning_day_profit, p.funded_consistency_rule_pct, p.payout_threshold_pct, p.required_buffer_pct,
                      p.payout_cap_pct, p.payout_cap_dollars, p.max_payouts, p.payout_frequency_days,
                      float(fee.profit_split_pct) if fee else 80.0, p.payout_pins_floor_to_lock)
    fees = FeeSchedule(fee.challenge_price if fee else None, fee.reset_price if fee else None, fee.activation_fee if fee else 0.0,
                       bool(fee.monthly_subscription) if fee else False, fee.source_tier if fee else "unverified", fee.date_checked if fee else "")
    return FirmRules(p.key, p.firm, p.account_size, ev, fu, pay, fees, p.funded_starts_fresh, p.rules_checked_on)


# ----------------------------------------------------------------------------------------------------------------------------------
# Multi-phase execution (audit E-F8/E-F9): the read-only view above is now backed by a real run. Each phase is its own PropAccount on the
# same preset rules with that phase's profit target; passing a phase starts the next one FRESH on the following trading day (the
# firms reset the balance and drawdown between phases), and the last phase hands over to a funded PropAccount.
# ----------------------------------------------------------------------------------------------------------------------------------
# Second-phase ("Verification" / "Phase 2") profit target in % of the account, for the firms whose presets are two-step challenges.
# One-step firms (Topstep, Lucid, MFFU, Apex, Tradeify) have no entry here and run a single evaluation phase.
SECOND_PHASE_TARGET_PCT = {"ftmo": 5.0, "fundednext": 5.0, "the5ers": 5.0}


@dataclass
class PhaseOutcome:
    name: str
    passed: bool
    failed: bool
    failure_reason: str | None
    trading_days: int
    end_balance: float
    payouts: int = 0
    payout_total: float = 0.0


@dataclass
class StagedResult:
    preset_key: str
    phases: list
    funded_reached: bool
    funded_failed: bool
    n_payouts: int
    total_payout: float
    trades_used: int

    @property
    def passed_all_evaluation(self) -> bool:
        return bool(self.phases) and all(p.passed for p in self.phases if p.name != "funded")

    def to_dict(self) -> dict:
        from dataclasses import asdict
        d = asdict(self)
        d["passed_all_evaluation"] = self.passed_all_evaluation
        return d


def phase_plan(preset_key: str) -> list:
    """[(name, profit_target_pct)] for the evaluation phases of ``preset_key``, then ("funded", None)."""
    p = get_preset(preset_key)
    plan = [("phase_1", p.evaluation_profit_target_pct)]
    second = SECOND_PHASE_TARGET_PCT.get(str(p.firm).lower().replace("%", "").replace(" ", "").replace("the5ers", "the5ers"))
    if second is None and str(p.key).split("_")[0] in SECOND_PHASE_TARGET_PCT:
        second = SECOND_PHASE_TARGET_PCT[str(p.key).split("_")[0]]
    if second is not None:
        plan.append(("phase_2", second))
    plan.append(("funded", None))
    return plan


def run_staged(trades, preset_key: str, *, phase_targets: dict | None = None) -> StagedResult:
    """Run one trade stream through every phase of ``preset_key`` in order using real ``PropAccount`` objects.

    ``trades``: anything with ``pnl`` and ``entry_time`` (chronological order is enforced). ``phase_targets``: optional
    {"phase_1": pct, "phase_2": pct} override. A failed phase ends the run (a real trader buys a new attempt; use the Monte Carlo
    engines for repeated attempts). Trades that arrive while a phase is "passed" but waiting for its next day roll to the next phase."""
    import dataclasses
    import pandas as pd
    from app.prop.account import DAY_LOCKED, FAILED, PropAccount

    base = get_preset(preset_key).to_prop_rules()
    ordered = sorted(trades, key=lambda t: pd.Timestamp(t.entry_time))
    dates = [pd.Timestamp(t.entry_time).normalize() for t in ordered]
    day_dates = sorted(set(dates))
    day_idx = {d: i for i, d in enumerate(day_dates)}
    plan = phase_plan(preset_key)
    if phase_targets:
        plan = [(n, (phase_targets.get(n, tgt))) for n, tgt in plan]

    outcomes: list = []
    k = 0                                            # next trade index
    n = len(ordered)
    funded_reached = funded_failed = False
    n_pay, tot_pay = 0, 0.0
    for name, target in plan:
        rules = base if target is None else dataclasses.replace(base, evaluation_profit_target_pct=float(target))
        if k >= n:
            break
        acct = PropAccount(rules, start_day_index=day_idx[dates[k]], day_dates=day_dates)
        locked_day = None
        done = False
        k0 = k
        while k < n and not done:
            d = day_idx[dates[k]]
            if locked_day == d:
                k += 1
                continue
            last = (k + 1 >= n) or day_idx[dates[k + 1]] != d
            res = acct.on_trade_close(float(ordered[k].pnl), d, is_last_of_day=last)
            k += 1
            if res == FAILED:
                done = True
            elif res == DAY_LOCKED:
                locked_day = d
            elif name != "funded" and acct.passed_evaluation:
                done = True
        days = len({dates[i] for i in range(k0, k)})
        passed = bool(acct.passed_evaluation) and not acct.failed
        outcomes.append(PhaseOutcome(name, passed if name != "funded" else not acct.failed, bool(acct.failed), acct.failure_reason,
                                     int(days), float(acct.balance), len(acct.payouts), float(acct.total_payout_amount)))
        if name == "funded":
            funded_reached, funded_failed = True, bool(acct.failed)
            n_pay, tot_pay = len(acct.payouts), float(acct.total_payout_amount)
        if acct.failed:
            break
        if name != "funded" and not passed:
            break                                    # ran out of trades before the target
    return StagedResult(preset_key, outcomes, funded_reached, funded_failed, n_pay, tot_pay, k)
