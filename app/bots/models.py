"""Data shapes for T58 Trading Bots (config, runtime state, trade rows). Plain dataclasses, JSON round-trippable."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.bots.risk_governor import OBJECTIVES, GovernorConfig

STATUSES = ("stopped", "running", "paused", "halted", "complete")
OBJECTIVE_NAMES = {"A": "Pass the evaluation", "B": "Get paid", "NET": "Net profit"}
DEMO_ACCOUNT_ID = "t58-demo"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class BotLeg:
    """One strategy inside a bot. ``strategy`` is a path relative to the repo's ``strategies/`` folder."""
    strategy: str
    label: str
    symbol: str = "NQ"                 # research instrument (data + specs)
    weight: float = 1.0                # size multiplier on top of the governor's risk
    priority: int = 0                  # lower wins when two legs signal on the same instrument at once
    lookback_days: int = 30            # history the strategy needs to warm up (calendar days of 1-minute bars)
    note: str = ""
    kind: str = "intraday"             # "intraday" (a strategy file read bar by bar) | "gate27" (monthly swing leg held through the flatten window)
    params: dict = field(default_factory=dict)   # kind == "gate27": sma_window / vol_window / daily_vol_target_pct / leverage_cap / phase_in_days overrides

    @classmethod
    def from_dict(cls, d: dict) -> "BotLeg":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class AccountLink:
    """Where the bot trades. Default = the T58 demo account (simulated prop evaluation, no money)."""
    venue: str = "demo"                # demo | paper | broker
    account_id: str = "t58-demo"       # live_settings account id when venue == "broker"
    size: float = 50_000.0
    broker_symbol: str = "MNQ"         # symbol the broker knows the micro contract by
    preset_key: str = "lucid_50k"      # prop-firm rule set the governor protects (limits, floor, targets)

    @classmethod
    def from_dict(cls, d: dict) -> "AccountLink":
        return cls(**{k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__})


@dataclass
class BotConfig:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    name: str = "My bot"
    objective: str = "A"
    tagline: str = ""
    description: str = ""
    preset_key: str = ""               # which shipped preset this started from ("" = custom)
    legs: list = field(default_factory=list)       # list[BotLeg]
    governor: dict = field(default_factory=dict)   # GovernorConfig.to_dict()
    account: AccountLink = field(default_factory=AccountLink)
    daily_loss_cap_pct_of_soft: float = 40.0       # combined day stop across legs, % of the soft daily limit
    flatten_hhmm_et: str = "16:45"                 # flat by this time (Lucid-style 4:45 pm ET / 15:45 CT) ...
    reopen_hhmm_et: str = "18:00"                  # ... and no new entries until the Globex session reopens
    max_trades_per_day: int = 6
    max_open_positions: int = 2                    # intraday positions open at once across instruments (one per instrument)
    created_at: str = field(default_factory=now_iso)
    preset_rev: int = 0                            # shipped presets only: which revision of the preset this copy was seeded from (store._seed)

    def governor_cfg(self) -> GovernorConfig:
        g = GovernorConfig.from_dict(self.governor)
        return g.with_(objective=self.objective) if g.objective != self.objective else g

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "BotConfig":
        d = dict(d or {})
        legs = [BotLeg.from_dict(x) if isinstance(x, dict) else x for x in d.pop("legs", [])]
        acct = AccountLink.from_dict(d.pop("account", {}))
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        # any spelling of the goal ("pass", "payout", "net_profit", ...) maps to the governor's A / B / NET; unknown or blended means A
        from app.objectives import OBJECTIVES as _GOALS, normalize_objective
        _o = normalize_objective(known.get("objective"), default="")
        known["objective"] = _o if _o in _GOALS else "A"
        return cls(legs=legs, account=acct, **known)


@dataclass
class OpenPos:
    leg: str
    symbol: str
    direction: int
    kind: str                           # mini | micro
    qty: int
    entry_time: str
    entry_price: float
    stop_price: float
    tp_price: Optional[float]
    risk_dollars: float
    stop_points: float
    mult: float
    ticket: str = ""
    broker: bool = False
    # trade management state (profit-lock ladder / loser cut); all inert unless the governor turns them on
    peak_usd: float = 0.0               # best open profit (dollars) reached so far
    lock_next: Optional[float] = None   # rung earned on the previous bar: takes effect on the next bar
    locked: Optional[float] = None      # dollars the stop currently locks (None = the stop is still the original one)
    minutes: int = 0                    # minutes the position has been open

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "OpenPos":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class BotRuntime:
    status: str = "stopped"
    mode: str = "simulation"            # simulation (T58 data replay) | feed (broker/real-time bars)
    started_at: str = ""
    stopped_at: str = ""
    last_bar_time: str = ""
    last_price: float = 0.0
    position: Optional[dict] = None
    pending: Optional[dict] = None      # entry/exit decided at the last bar close, filled at the next open
    state: dict = field(default_factory=dict)       # AccountState.to_dict() of the bot's own paper account
    replay_cursor: str = ""             # simulation: timestamp of the last bar processed
    message: str = "Ready."
    halted_reason: str = ""
    next_decision: str = ""             # plain-words "why am I (not) trading right now"
    payouts: float = 0.0                # funded payouts withdrawn (simulation / paper)
    passes: int = 0
    breaches: int = 0
    day_trades: int = 0
    day_key: str = ""
    day_realised: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "BotRuntime":
        return cls(**{k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)
