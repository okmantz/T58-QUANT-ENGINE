"""Risk governor: how much a T58 bot risks on the NEXT trade, given where the account stands.

Pure and deterministic (no I/O, no clock): the same function sizes the live bot and the research replay that picked its parameters,
so a number in the research report and a number on the Trading Bots page come from one piece of code.

Three objectives, three personalities (parameters live in ``GovernorConfig``; the shipped presets in ``app.bots.presets``):

  A   PASS      Spend risk while the trailing floor is far away, bank the target, then stop gambling: size follows progress to the
                profit target and how much cushion is left above the floor. Ends at the pass.
  B   PAYOUT    Survive first. Risk is a small share of the cushion and of the loss limit; a day-stop and a profit-lock keep one bad day
                (or one great day, for the consistency rule) from deciding the cycle.
  NET NET PROFIT Compounding on a non-prop account: risk a fixed share of equity, throttled by drawdown from the equity peak.

Everything is in DOLLARS of risk per trade at the stop; ``contracts_for_risk`` converts to whole contracts (floor, micro fallback,
never above the cap, never a rounded-up contract) -- the same rule as ``BrokerAdapter.to_broker_qty``.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, replace
from typing import Optional

OBJECTIVES = ("A", "B", "NET")


# ------------------------------------------------------------------------------------------------------------------ account state
@dataclass
class AccountRulesLite:
    """The rule shape the governor needs. Built from ``app.prop.lifecycle_v2.V2Rules`` (the T58 demo / Lucid-style shape)."""
    account_size: float = 50_000.0
    profit_target: float = 3_000.0
    loss_limit: float = 2_000.0
    soft_daily_limit: float = 1_200.0
    lock_floor_offset: float = 100.0
    trailing: bool = True
    funded_buffer: float = 2_100.0          # cushion a funded account keeps above its floor before it requests a payout
    payout_goal: float = 500.0              # profit above the buffer a funded cycle needs
    # Objective B payout rule: "standard" = payout_goal + funded_buffer (above). "winning_days_net_positive" = ``winning_days`` days that each made at
    # least ``winning_day_profit`` since the last payout (not necessarily consecutive) AND the cycle's wins outweigh its losses (net P&L > 0).
    payout_mode: str = "standard"
    winning_days: int = 5
    winning_day_profit: float = 250.0

    def with_winning_days_payout(self, days: int = 5, day_profit: float = 250.0) -> "AccountRulesLite":
        """The same account under the "5 days of $250, wins bigger than losses" payout rule (Objective B)."""
        return replace(self, payout_mode="winning_days_net_positive", winning_days=int(days), winning_day_profit=float(day_profit))

    @classmethod
    def from_v2(cls, v2) -> "AccountRulesLite":
        pt = getattr(v2, "payout", None)
        return cls(account_size=float(v2.account_size), profit_target=float(v2.profit_target), loss_limit=float(v2.loss_limit),
                   soft_daily_limit=float(v2.soft_daily_limit), lock_floor_offset=float(v2.lock_floor_offset), trailing=bool(v2.trailing),
                   funded_buffer=float(getattr(pt, "buffer_above_floor", 2_100.0) or 2_100.0),
                   payout_goal=float(getattr(pt, "cumulative_min", 500.0) or 500.0) - float(getattr(pt, "buffer_above_floor", 0.0) or 0.0))

    @classmethod
    def lucid_50k(cls) -> "AccountRulesLite":
        return cls()

    @classmethod
    def live_account(cls, size: float) -> "AccountRulesLite":
        """A rule-free account for Objective NET: no profit target to pass, no payout goal, no daily limit and a floor at zero (only ruin ends
        the run). The trailing prop floor, the evaluation and the funded stage simply do not exist here."""
        big = 1e12
        return cls(account_size=float(size), profit_target=big, loss_limit=float(size), soft_daily_limit=big, lock_floor_offset=0.0,
                   trailing=False, funded_buffer=0.0, payout_goal=big)

    @classmethod
    def tier(cls, size: float) -> "AccountRulesLite":
        k = float(size) / 50_000.0
        b = cls()
        return cls(account_size=float(size), profit_target=b.profit_target * k, loss_limit=b.loss_limit * k, soft_daily_limit=b.soft_daily_limit * k,
                   lock_floor_offset=b.lock_floor_offset * k, trailing=True, funded_buffer=b.funded_buffer * k, payout_goal=b.payout_goal * k)


@dataclass
class AccountState:
    """Where the account stands. ``update`` is called on every closed trade; ``roll_day`` on the first event of a new trading day."""
    rules: AccountRulesLite = field(default_factory=AccountRulesLite)
    phase: str = "evaluation"               # evaluation | funded | passed | breached
    balance: float = 50_000.0
    start_balance: float = 50_000.0
    floor: float = 48_000.0
    eod_high: float = 50_000.0
    day_start: float = 50_000.0
    day: str = ""
    peak_equity: float = 50_000.0
    trades_today: int = 0
    stopped_today: bool = False
    last_payout_balance: float = 50_000.0
    cycle_days: dict = field(default_factory=dict)      # winning_days_net_positive mode: day -> realised P&L since the last payout / funded start

    @classmethod
    def fresh(cls, rules: Optional[AccountRulesLite] = None, *, phase: str = "evaluation") -> "AccountState":
        r = rules or AccountRulesLite()
        return cls(rules=r, phase=phase, balance=r.account_size, start_balance=r.account_size, floor=r.account_size - r.loss_limit,
                   eod_high=r.account_size, day_start=r.account_size, peak_equity=r.account_size, last_payout_balance=r.account_size)

    # derived ---------------------------------------------------------------------------------------------------------------
    @property
    def cushion(self) -> float:
        return self.balance - self.floor

    @property
    def profit(self) -> float:
        return self.balance - self.start_balance

    @property
    def progress(self) -> float:
        """Share of the profit target already made (0..1+). In a funded phase: progress to the next payout goal."""
        if self.phase == "funded":
            need = max(self.rules.payout_goal, 1.0)
            return max(self.balance - self.last_payout_balance, 0.0) / need
        return max(self.profit, 0.0) / max(self.rules.profit_target, 1.0)

    @property
    def day_pnl(self) -> float:
        return self.balance - self.day_start

    @property
    def drawdown_from_peak(self) -> float:
        return max(self.peak_equity - self.balance, 0.0)

    # transitions -----------------------------------------------------------------------------------------------------------
    def roll_day(self, day: str) -> None:
        if self.day and self.day != day:
            self.eod_high = max(self.eod_high, self.balance)
            if self.rules.trailing:
                trailed = self.eod_high - self.rules.loss_limit
                self.floor = max(self.floor, min(trailed, self.start_balance + self.rules.lock_floor_offset))
            self.day_start = self.balance
            self.trades_today = 0
            self.stopped_today = False
        if self.day != day:
            self.day = day

    def update(self, pnl: float, day: str) -> None:
        """Book one closed trade (dollars)."""
        if self.phase in ("passed", "breached"):
            return
        self.roll_day(day)
        self.balance += float(pnl)
        if self.phase == "funded" and self.rules.payout_mode == "winning_days_net_positive":
            self.cycle_days[day] = self.cycle_days.get(day, 0.0) + float(pnl)
        self.trades_today += 1
        self.peak_equity = max(self.peak_equity, self.balance)
        if self.balance <= self.floor:
            self.phase = "breached"
        elif self.phase == "evaluation" and self.profit >= self.rules.profit_target:
            self.phase = "passed"

    def to_funded(self) -> None:
        """Evaluation passed -> funded account (firms with ``funded_starts_fresh`` hand over a fresh balance and floor)."""
        r = self.rules
        self.phase, self.balance, self.start_balance = "funded", r.account_size, r.account_size
        self.floor, self.eod_high, self.day_start = r.account_size - r.loss_limit, r.account_size, r.account_size
        self.peak_equity, self.last_payout_balance, self.trades_today, self.stopped_today = r.account_size, r.account_size, 0, False
        self.cycle_days = {}

    def winning_days_count(self) -> int:
        """Days since the last payout (or funded start) whose P&L reached ``winning_day_profit``; they need not be consecutive."""
        return sum(1 for v in self.cycle_days.values() if v >= self.rules.winning_day_profit)

    def payout_due(self) -> float:
        """Dollars a funded account may withdraw now (0 when not eligible): profit since the last payout beats the goal AND the cushion
        stays above the required buffer. Withdrawing does not lower the floor, so the cushion (and the next trade's size) shrinks."""
        if self.phase != "funded":
            return 0.0
        r = self.rules
        gain = self.balance - self.last_payout_balance
        if r.payout_mode == "winning_days_net_positive":
            # wins bigger than losses over the cycle, enough qualifying days; never withdraw below the starting balance
            if self.winning_days_count() >= r.winning_days and gain > 0 and sum(self.cycle_days.values()) > 0:
                return float(max(min(gain, self.balance - r.account_size, 2_000.0 * r.account_size / 50_000.0), 0.0))
            return 0.0
        spare = self.cushion - r.funded_buffer
        if gain >= r.payout_goal and spare >= r.payout_goal:
            return float(min(gain, spare, 2_000.0 * r.account_size / 50_000.0))
        return 0.0

    def take_payout(self) -> float:
        amt = self.payout_due()
        if amt > 0:
            self.balance -= amt
            self.last_payout_balance = self.balance
            self.cycle_days = {}                                # a payout starts a new winning-day cycle
        return amt

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(cushion=self.cushion, profit=self.profit, progress=self.progress, day_pnl=self.day_pnl)
        return d


# ----------------------------------------------------------------------------------------------------------------------- config
@dataclass(frozen=True)
class GovernorConfig:
    objective: str = "A"
    base_risk_pct: float = 1.0              # % of account size risked per trade at multiplier 1 (1% of 50K = $500)
    # --- A / B: progress ladder (progress = profit / target, or / payout goal when funded)
    early_mult: float = 1.0                 # progress < p1
    mid_mult: float = 1.0                   # p1 <= progress < p2
    late_mult: float = 1.0                  # progress >= p2
    p1: float = 0.35
    p2: float = 0.70
    # --- cushion ladder (cushion / loss_limit)
    low_cushion_frac: float = 0.50          # below this share of the loss limit ...
    low_cushion_mult: float = 0.50          # ... multiply risk by this
    crit_cushion_frac: float = 0.25
    crit_cushion_mult: float = 0.25
    cushion_risk_frac: Optional[float] = None   # cap risk at this share of the cushion (None = no cap)
    # --- the day
    day_stop_frac: float = 0.40             # stop for the day after realised loss of this share of the soft daily limit
    day_profit_lock_frac: Optional[float] = None  # stop for the day after profit of this share of the target / payout goal
    # --- need-based tapering (A): when only `need` dollars remain to the target, risk at most need * need_risk_mult
    need_risk_mult: Optional[float] = None
    # --- funded switch
    funded_mult: float = 1.0                # extra multiplier once the account is funded
    # --- NET objective
    compounding: bool = False               # base risk follows equity instead of the account size
    dd_throttle_tol_pct: float = 10.0       # NET: size falls linearly to min_mult as drawdown from peak reaches this % of equity
    min_mult: float = 0.25
    max_mult: float = 3.0
    # --- hard floors/caps in dollars
    min_risk_dollars: float = 30.0          # about one micro contract at a typical stop; below this the trade is skipped
    max_risk_dollars: Optional[float] = None
    # --- cut losers short, let winners run (app.backtest.profit_lock): the same ladder the backtester uses, applied to every bot trade
    profit_lock: bool = False               # once a trade is positive, ratchet its stop up in dollar steps so a reversal cannot give the day back
    lock_tiers: Optional[tuple] = None      # ((open profit $, locked $), ...) for a 50K account; None = the default ladder ($200 -> $75, $400 -> $250, ...)
    lock_trail_frac: float = 0.72           # beyond the last rung the stop trails at this share of the peak open profit (0 = no trail)
    lock_scale: float = 1.0                 # multiplies every rung
    lock_scale_by_risk: bool = True         # also scale the rungs by (the trade's risk / $500), so a small-risk trade ratchets sooner in dollars
    loss_cut_frac: Optional[float] = None   # close a trade that never worked once it is down this share of its risk (None = off)
    loss_cut_min_minutes: int = 10          # ... and it has been open at least this many minutes
    loss_cut_max_mfe_frac: float = 0.25     # ... and its best open profit stayed under this share of its risk

    def with_(self, **kw) -> "GovernorConfig":
        return replace(self, **kw)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "GovernorConfig":
        known = cls.__dataclass_fields__
        return cls(**{k: v for k, v in (d or {}).items() if k in known})


@dataclass(frozen=True)
class RiskDecision:
    allow: bool
    risk_dollars: float
    multiplier: float
    reason: str


def _ladder(progress: float, cfg: GovernorConfig) -> float:
    if progress < cfg.p1:
        return cfg.early_mult
    if progress < cfg.p2:
        return cfg.mid_mult
    return cfg.late_mult


def decide_risk(state: AccountState, cfg: GovernorConfig, open_risk: float = 0.0) -> RiskDecision:
    """Dollars to risk on the next trade (at its stop), or a skip with the reason spelled out.

    ``open_risk`` is the dollars already at risk in other open positions (another instrument): it comes off the room the new trade may use."""
    r = state.rules
    if state.phase in ("passed", "breached"):
        return RiskDecision(False, 0.0, 0.0, "evaluation finished" if state.phase == "passed" else "account breached")
    if cfg.objective == "NET":
        eq = max(state.balance, 0.0)
        base = (eq if cfg.compounding else r.account_size) * cfg.base_risk_pct / 100.0
        dd_pct = 100.0 * state.drawdown_from_peak / max(state.peak_equity, 1.0)
        thr = max(cfg.min_mult, 1.0 - dd_pct / max(cfg.dd_throttle_tol_pct, 0.1) * (1.0 - cfg.min_mult))
        mult = min(max(thr, cfg.min_mult), cfg.max_mult)
        risk = base * mult
        if cfg.cushion_risk_frac is not None and state.rules.loss_limit > 0:      # on a prop account: never risk more than this share of the cushion
            risk = min(risk, max(state.cushion - open_risk, 0.0) * cfg.cushion_risk_frac)
        if cfg.max_risk_dollars:
            risk = min(risk, cfg.max_risk_dollars)
        if risk < cfg.min_risk_dollars:
            return RiskDecision(False, 0.0, mult, "risk below one micro contract")
        why = "full size" if mult >= 0.999 else f"drawdown throttle x{mult:.2f}"
        return RiskDecision(True, risk, mult, why)

    # ---- prop objectives (A, B)
    soft = r.soft_daily_limit
    if state.stopped_today or state.day_pnl <= -cfg.day_stop_frac * soft:
        return RiskDecision(False, 0.0, 0.0, f"day stop: down ${-state.day_pnl:,.0f} (limit {cfg.day_stop_frac:.0%} of the soft daily limit)")
    if cfg.day_profit_lock_frac is not None:
        goal = r.payout_goal if state.phase == "funded" else r.profit_target
        if state.day_pnl >= cfg.day_profit_lock_frac * goal:
            return RiskDecision(False, 0.0, 0.0, "day profit lock: today's gain is banked")
    base = r.account_size * cfg.base_risk_pct / 100.0
    mult = _ladder(state.progress, cfg)
    cushion_frac = state.cushion / max(r.loss_limit, 1.0)
    why = ["progress ladder"]
    if cushion_frac < cfg.crit_cushion_frac:
        mult *= cfg.crit_cushion_mult
        why.append("critical cushion")
    elif cushion_frac < cfg.low_cushion_frac:
        mult *= cfg.low_cushion_mult
        why.append("low cushion")
    if state.phase == "funded":
        mult *= cfg.funded_mult
    mult = min(max(mult, 0.0), cfg.max_mult)
    risk = base * mult
    if cfg.cushion_risk_frac is not None:
        risk = min(risk, max(state.cushion - open_risk, 0.0) * cfg.cushion_risk_frac)
    if cfg.need_risk_mult is not None and state.phase == "evaluation":
        need = max(r.profit_target - state.profit, 0.0)
        risk = min(risk, max(need * cfg.need_risk_mult, cfg.min_risk_dollars))
        why.append("need taper")
    # never risk more than the cushion left above the floor, or the room left in today's soft limit
    risk = min(risk, max(state.cushion - open_risk, 0.0) * 0.9, max(soft + state.day_pnl - open_risk, 0.0) * 0.9)
    if cfg.max_risk_dollars:
        risk = min(risk, cfg.max_risk_dollars)
    if risk < cfg.min_risk_dollars:
        return RiskDecision(False, 0.0, mult, "room below one micro contract")
    return RiskDecision(True, risk, (risk / base) if base else 0.0, ", ".join(why))


# ------------------------------------------------------------------------------------------------------------------ contract sizing
def contracts_for_risk(risk_dollars: float, stop_points: float, point_value_mini: float, point_value_micro: float,
                       max_minis: int, max_micros: int, *, cost_per_contract: float = 0.0) -> tuple[str, int]:
    """Whole contracts so that (stop x point value + cost) x n <= risk. Prefers minis, falls back to micros; returns (kind, n) with n == 0 to skip.

    Floors (never rounds up), never exceeds the account's contract caps, and never shrinks the strategy's stop to fit."""
    if not (risk_dollars > 0 and stop_points > 0):
        return "micro", 0
    per_mini = stop_points * point_value_mini + cost_per_contract
    n = int(math.floor(risk_dollars / per_mini)) if per_mini > 0 else 0
    if n >= 1:
        return "mini", min(n, max_minis)
    per_micro = stop_points * point_value_micro + cost_per_contract / 10.0
    n = int(math.floor(risk_dollars / per_micro)) if per_micro > 0 else 0
    return "micro", min(max(n, 0), max_micros)
