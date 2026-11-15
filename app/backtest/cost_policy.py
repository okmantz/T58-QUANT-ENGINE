"""Explicit cost policy for every backtest path (audit items A-R1 and B-4, 2026-11-14).

Before this module the friction a run was charged depended on which entry point built the risk config: Search Lab filled registry costs
when the config was untouched, Quick Optimize and Full Pipeline did not, and the registry convention itself (a FULL spread charged on each side
PLUS slippage) cost an ES round trip about $54.20 -- roughly $12.50 more than the repo's own "1 tick inside spread" assumption implies.

The policy is now one decision, in one place, applied by every path that resolves a registry cost (``apply_instrument_spec``,
``apply_any_instrument_spec``, ``resolve_leg_risk``, ``resolve_run_costs``, Quick Optimize, Full Pipeline, Search Lab, Evolution):

    realistic   Project_Specifications section 2.3 BASE case.
                CME/COMEX/CBOT/NYMEX futures: spread 0 (the 1-tick slippage per side already pays the 1-tick inside spread -- charging both
                double-counts it), slippage = the registry's ticks per side, commission = the Lucid base schedule (ES/NQ $3.50, GC $4.60,
                MES/MNQ $1.00, MGC $1.60 round turn), registry commission for contracts the schedule does not price.
                Retail FX/CFD: HALF the quoted spread per side (a round trip crosses it once), registry slippage and commission.
    stress      Methodology section 6.9: stress commissions (Alpha all-in schedule: ES/NQ $4.78, GC $5.22, MES/MNQ $1.32, MGC $1.82) and 2x
                slippage. A strategy must stay positive on BOTH profiles. Retail FX/CFD: full spread, 2x slippage.
    legacy      The pre-2026-11-14 behaviour (full spread each side + slippage, registry commission). Kept only so old runs can be reproduced.

The active profile is ``realistic`` unless ``T58_COST_PROFILE`` says otherwise or ``set_active_profile`` is called. Whatever the profile, a
value the user typed into the risk config is never overwritten -- only untouched defaults are filled.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

PROFILES = ("realistic", "stress", "legacy")
DEFAULT_PROFILE = "realistic"
_FUTURES_EXCHANGES = ("CME", "CBOT", "COMEX", "NYMEX")
_active: str | None = None


def active_profile() -> str:
    p = (_active or os.environ.get("T58_COST_PROFILE", "") or DEFAULT_PROFILE).strip().lower()
    return p if p in PROFILES else DEFAULT_PROFILE


def set_active_profile(name: str | None) -> None:
    """Pin the profile for this process (None = back to the environment / default)."""
    global _active
    if name is not None and name.strip().lower() not in PROFILES:
        raise ValueError(f"unknown cost profile {name!r}; choose one of {', '.join(PROFILES)}")
    _active = None if name is None else name.strip().lower()


@dataclass(frozen=True)
class Costs:
    spread_ticks: float            # charged per side
    slippage_ticks: float          # charged per side
    commission_round_turn: float   # $ per contract, round turn
    profile: str
    commission_source: str         # "fee_schedule:lucid-base" | "fee_schedule:stress" | "registry"

    def round_trip_dollars(self, tick_value: float, contracts: float = 1.0) -> float:
        return (2.0 * (self.spread_ticks + self.slippage_ticks) * tick_value + self.commission_round_turn) * contracts


def _is_listed_future(spec) -> bool:
    return str(getattr(spec, "exchange", "")).upper() in _FUTURES_EXCHANGES


def costs_for(spec, profile: str | None = None) -> Costs:
    """Friction for one instrument spec under a profile (default: the active one)."""
    prof = (profile or active_profile()).lower()
    reg_spread = float(spec.default_spread_ticks)
    reg_slip = float(spec.default_slippage_ticks)
    reg_comm = float(spec.default_commission_round_turn)
    if prof == "legacy":
        return Costs(reg_spread, reg_slip, reg_comm, "legacy", "registry")
    from app.prop import fee_schedule as fs
    if _is_listed_future(spec):
        comm_profile = "stress" if prof == "stress" else "base"
        priced = fs.commission_rt(spec.symbol, profile=comm_profile)
        slip = reg_slip * (2.0 if prof == "stress" else 1.0)
        if priced is not None:
            return Costs(0.0, slip, float(priced), prof, "fee_schedule:stress" if prof == "stress" else "fee_schedule:lucid-base")
        return Costs(0.0, slip, reg_comm, prof, "registry")
    # retail FX / CFD / spot: the spread is a real cost, but a round trip crosses it once (half per side) unless stressed
    spread = reg_spread if prof == "stress" else reg_spread / 2.0
    slip = reg_slip * (2.0 if prof == "stress" else 1.0)
    return Costs(spread, slip, reg_comm, prof, "registry")


def describe(spec, profile: str | None = None) -> str:
    c = costs_for(spec, profile)
    return (f"{c.profile} costs for {spec.symbol}: {c.spread_ticks:g} tick spread + {c.slippage_ticks:g} tick slippage per side, "
            f"${c.commission_round_turn:g}/contract round turn ({c.commission_source}).")
