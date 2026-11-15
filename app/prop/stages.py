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
