"""The T58 demo prop account.

Every user starts in Demo mode. A demo account is a 25k / 50k / 100k T58 Prop Firm simulation with the SAME rule shape the
Rulebook v2 pipeline validates against (``app.prop.lifecycle_v2.V2Rules.tier``): trailing end-of-day loss limit that locks at
start + offset, a daily soft limit, a profit target and a best-day consistency cap.  A strategy "deployed" to it receives the same
TradingView / Pine alerts as a real account (through the webhook relay); every closed trade is booked here as a visible win or
loss, and the account passes or breaches exactly as a real evaluation would.  Live mode never touches this file.

Funded stage: when the evaluation is PASSED the person picks one of two ways forward (``advance_to_funded`` or ``reset``): move on to the
simulated funded account, where the Payout Hunter and any strategy trade for payouts, or start the evaluation again. A funded demo account has no
profit target; it pays out (``request_payout``) once enough winning days have been banked in the cycle and the cycle is net positive.

State: one small JSON file under data/config/. Pure stdlib; all money values are dollars.
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.data.storage import get_app_base_dir

TIERS = (25_000, 50_000, 100_000)
MODES = ("demo", "live")
MAX_TRADES = 5000
_LOCK = threading.RLock()
_FILE = "demo_account.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path() -> Path:
    d = get_app_base_dir() / "data" / "config"
    d.mkdir(parents=True, exist_ok=True)
    return d / _FILE


def _rules(size: float):
    from app.prop.lifecycle_v2 import V2Rules
    return V2Rules().tier(float(size))


@dataclass
class DemoAccount:
    size: float = 50_000.0
    balance: float = 50_000.0
    start_balance: float = 50_000.0
    floor: float = 48_000.0                 # trailing end-of-day loss floor (breach when balance <= floor)
    eod_high: float = 50_000.0              # best end-of-day balance so far
    day: str = ""                           # trading date of ``day_start``
    day_start: float = 50_000.0
    best_day: float = 0.0                   # best single-day profit (consistency)
    status: str = "active"                  # active | passed | breached
    status_reason: str = ""
    soft_limit_hits: int = 0
    day_stopped: bool = False               # today's soft daily limit was hit: the strategy should stand down until tomorrow
    attempt: int = 1
    created_at: str = ""
    relay_ids: list = field(default_factory=list)   # webhook relays that feed this account
    strategy: str = ""                      # name of the deployed strategy (display only)
    trades: list = field(default_factory=list)
    phase: str = "evaluation"               # evaluation | funded (the funded stage is entered by choice after a passed evaluation)
    payouts: list = field(default_factory=list)      # simulated payouts taken on the funded stage: {n, at, amount, trader_share}
    cycle_from: int = 0                     # index into ``trades`` where the current payout cycle starts
    last_payout_balance: float = 0.0        # balance right after the last payout (the funded start balance before the first one)
    funded_since: str = ""

    # ---- derived
    @property
    def rules(self):
        return _rules(self.size)

    @property
    def net_pnl(self) -> float:
        return round(self.balance - self.start_balance, 2)

    def to_dict(self) -> dict:
        r = self.rules
        wins = [t["pnl"] for t in self.trades if t["pnl"] > 0]
        losses = [t["pnl"] for t in self.trades if t["pnl"] < 0]
        n = len(self.trades)
        return {
            **{k: v for k, v in asdict(self).items() if k != "trades"},
            "net_pnl": self.net_pnl, "cushion": round(self.balance - self.floor, 2),
            "profit_target": r.profit_target, "loss_limit": r.loss_limit, "soft_daily_limit": r.soft_daily_limit,
            "target_pct": (round(100.0 * min(payout_status(self)["winning_days"] / max(payout_status(self)["days_needed"], 1), 1.0), 1)
                           if self.phase == "funded" else (round(100.0 * max(self.net_pnl, 0.0) / r.profit_target, 1) if r.profit_target else 0.0)),
            "day_pnl": round(self.balance - self.day_start, 2),
            "n_trades": n, "n_wins": len(wins), "n_losses": len(losses),
            "win_rate": round(100.0 * len(wins) / n, 1) if n else None,
            "avg_win": round(sum(wins) / len(wins), 2) if wins else None,
            "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
            "recent_trades": list(reversed(self.trades[-25:])),
            "rules_sheet": rules_sheet(self), "trading_days": trading_days(self), "equity": equity_points(self),
            "daily_room": round(r.soft_daily_limit + (self.balance - self.day_start), 2), "projection": projection(self),
            "stage": stage_label(self),
            "payout": payout_status(self), "payout_total": round(sum(p.get("amount", 0.0) for p in self.payouts), 2),
            "next_step": next_step(self),
        }


def stage_label(acct: DemoAccount) -> str:
    if acct.phase == "funded":
        return "Funded" if acct.status == "active" else "Funded account breached"
    return "Evaluation" if acct.status == "active" else ("Evaluation passed" if acct.status == "passed" else "Evaluation failed")


def next_step(acct: DemoAccount) -> dict | None:
    """What the person should do now, when the account is waiting on a decision (passed or breached). None while it is simply trading."""
    if acct.phase == "evaluation" and acct.status == "passed":
        return {"kind": "choose", "title": "Evaluation passed. What next?",
                "options": [{"key": "funded", "label": "Move to the funded demo account",
                             "detail": "Fresh balance and loss floor, no profit target: trade for payouts with the Payout Hunter bot or your strategy."},
                            {"key": "reset", "label": "Start the evaluation again",
                             "detail": "A clean evaluation attempt (same size), e.g. to test another bot or strategy."}]}
    if acct.status == "breached":
        return {"kind": "restart", "title": "Account breached" if acct.phase == "evaluation" else "Funded account breached",
                "options": [{"key": "reset", "label": "Start a new evaluation attempt", "detail": "Back to a fresh evaluation at the same size."}]}
    return None


def _cycle_days(acct: DemoAccount) -> dict:
    days: dict = {}
    for t in acct.trades[acct.cycle_from:]:
        d = t.get("day") or str(t.get("closed_at", ""))[:10]
        days[d] = days.get(d, 0.0) + float(t.get("pnl") or 0.0)
    return days


def payout_status(acct: DemoAccount) -> dict | None:
    """Funded stage only: where the account stands against its payout rule (enough winning days AND a net-positive cycle)."""
    if acct.phase != "funded":
        return None
    r = acct.rules
    p = r.payout
    days = _cycle_days(acct)
    winning = sum(1 for v in days.values() if v >= p.qualifying_day_min)
    gain = round(acct.balance - (acct.last_payout_balance or acct.start_balance), 2)
    buffer_room = round(acct.balance - acct.floor - p.buffer_above_floor, 2)
    amount = max(min(gain, buffer_room, p.cap if p.cap else float("inf")), 0.0)
    reasons = []
    if acct.status != "active":
        reasons.append("The account is no longer active.")
    if len(acct.payouts) >= p.max_payouts:
        reasons.append(f"The simulated account allows {p.max_payouts} payouts.")
    if winning < p.qualifying_days:
        reasons.append(f"{winning} of {p.qualifying_days} winning days (${p.qualifying_day_min:,.0f} or more) banked this cycle.")
    if gain <= 0:
        reasons.append("The cycle is not net positive yet.")
    elif amount <= 0:
        reasons.append(f"Keep ${p.buffer_above_floor:,.0f} above the loss floor before taking a payout.")
    eligible = not reasons
    return {"eligible": eligible, "amount": round(amount, 2) if eligible else 0.0, "trader_share": round(amount * p.split, 2) if eligible else 0.0,
            "winning_days": winning, "days_needed": p.qualifying_days, "day_min": p.qualifying_day_min, "cycle_gain": gain, "split_pct": round(p.split * 100),
            "reasons": reasons, "count": len(acct.payouts), "max_payouts": p.max_payouts}


def trading_days(acct: DemoAccount) -> int:
    return len({(t.get("day") or t["closed_at"][:10]) for t in acct.trades if t.get("day") or t.get("closed_at")})


def rules_sheet(acct: DemoAccount) -> list[dict]:
    """Every rule of this account in plain words, with where the account stands against it right now."""
    r = acct.rules
    cap = r.consistency_best_day_pct
    cap = None if cap is None else (cap / 100.0 if cap > 1 else cap)
    profit = max(acct.balance - acct.start_balance, 0.0)
    best = max(acct.best_day, acct.balance - acct.day_start)
    share = (best / profit) if profit > 0 else 0.0
    trail = ("The floor trails your best end-of-day balance and locks once it reaches the starting balance + "
             f"${r.lock_floor_offset:,.0f}." if r.trailing else "The floor is fixed at the starting balance minus the limit.")
    if acct.phase == "funded":
        ps = payout_status(acct) or {}
        p = r.payout
        return [
            {"key": "payout", "name": "Payout rule", "value": f"{p.qualifying_days} winning days of ${p.qualifying_day_min:,.0f}+",
             "plain": "A payout is available once enough winning days are banked since the last payout (they need not be in a row) and the cycle is net positive.",
             "now": f"{ps.get('winning_days', 0)} of {p.qualifying_days} winning days; cycle {ps.get('cycle_gain', 0):+,.0f}"},
            {"key": "max_drawdown", "name": "Maximum loss (drawdown)", "value": f"${r.loss_limit:,.0f}",
             "plain": "If your balance touches the loss floor the funded account is breached. Taking a payout never lowers the floor.",
             "now": f"Floor ${acct.floor:,.0f}; cushion ${acct.balance - acct.floor:,.0f}"},
            {"key": "daily_limit", "name": "Daily loss limit (soft)", "value": f"${r.soft_daily_limit:,.0f}",
             "plain": "Lose this much in one day and trading locks until tomorrow. It does NOT fail the account.",
             "now": f"${max(r.soft_daily_limit + (acct.balance - acct.day_start), 0):,.0f} of room left today" + (" - locked for today" if acct.day_stopped else "")},
            {"key": "split", "name": "Profit split (simulated)", "value": f"{p.split * 100:.0f}% yours",
             "plain": "Simulated: shows what a payout would be worth to you. No money moves.", "now": f"{len(acct.payouts)} payout(s) taken"},
        ]
    return [
        {"key": "profit_target", "name": "Profit target", "value": f"${r.profit_target:,.0f}",
         "plain": "Make this much net profit to pass the evaluation.",
         "now": f"${max(acct.balance - acct.start_balance, 0):,.0f} so far ({min(100.0 * profit / r.profit_target, 100):.0f}%)" if r.profit_target else ""},
        {"key": "max_drawdown", "name": "Maximum loss (drawdown)", "value": f"${r.loss_limit:,.0f}",
         "plain": "If your balance touches the loss floor, the account is breached and the evaluation is over. " + trail,
         "now": f"Floor ${acct.floor:,.0f}; cushion ${acct.balance - acct.floor:,.0f}"},
        {"key": "daily_limit", "name": "Daily loss limit (soft)", "value": f"${r.soft_daily_limit:,.0f}",
         "plain": "Lose this much in one day and trading locks until tomorrow. It does NOT fail the account.",
         "now": f"${max(r.soft_daily_limit + (acct.balance - acct.day_start), 0):,.0f} of room left today" + (" - locked for today" if acct.day_stopped else "")},
        {"key": "consistency", "name": "Consistency (best-day rule)",
         "value": "None" if cap is None else f"Best day <= {cap:.0%} of profit",
         "plain": "No single day may be too large a share of your total profit." if cap is not None
                  else "The T58 demo has no best-day cap, so one big day can pass the evaluation.",
         "now": "" if cap is None else f"Best day is {share:.0%} of profit"},
        {"key": "min_days", "name": "Minimum trading days", "value": "None",
         "plain": "You may pass as soon as the target is reached; there is no minimum number of days.",
         "now": f"{trading_days(acct)} trading day(s) so far"},
        {"key": "max_days", "name": "Time limit", "value": f"{r.max_eval_days} days",
         "plain": "Reach the target inside this window or start a new attempt.", "now": ""},
        {"key": "fee", "name": "Evaluation fee (simulated)", "value": f"${r.fee:,.0f}",
         "plain": "Simulated: shown so the cost of each attempt is visible. No money moves.", "now": f"Attempt #{acct.attempt}"},
    ]


def projection(acct: DemoAccount, n_sims: int = 800, max_trades: int = 1500) -> dict | None:
    """Bootstrap the account's OWN closed trades to estimate pass chance and time. Needs 15+ trades; otherwise None.

    Honest limits: it assumes future trades look like past ones, treats the loss floor as the current cushion (no further trailing),
    and ignores the daily lock. It is a guide for how a run is going, not a promise."""
    import numpy as np
    pnl = np.array([t["pnl"] for t in acct.trades], dtype=float)
    if len(pnl) < 15:
        return None
    r = acct.rules
    need = r.profit_target - (acct.balance - acct.start_balance)
    room = acct.balance - acct.floor
    if need <= 0:
        return {"pass_pct": 100.0, "days_to_pass": 0.0, "basis_trades": int(len(pnl))}
    rng = np.random.default_rng(58)
    draws = rng.choice(pnl, size=(int(n_sims), int(max_trades)))
    path = np.cumsum(draws, axis=1)
    hit = path >= need
    bust = path <= -room
    first_hit = np.where(hit.any(1), hit.argmax(1), max_trades + 1)
    first_bust = np.where(bust.any(1), bust.argmax(1), max_trades + 1)
    passed = first_hit < first_bust
    days = trading_days(acct)
    per_day = len(pnl) / max(days, 1)
    med = float(np.median(first_hit[passed])) + 1 if passed.any() else None
    return {"pass_pct": round(100.0 * float(passed.mean()), 1), "days_to_pass": None if med is None else round(med / per_day, 1),
            "basis_trades": int(len(pnl))}


def equity_points(acct: DemoAccount, limit: int = 300) -> list[float]:
    pts = [acct.start_balance] + [t["balance"] for t in acct.trades]
    return pts[-limit:]


def _fresh(size: float, *, attempt: int = 1, relay_ids=None, strategy: str = "") -> DemoAccount:
    size = float(size) if float(size) in TIERS else 50_000.0
    r = _rules(size)
    return DemoAccount(size=size, balance=size, start_balance=size, floor=size - r.loss_limit, eod_high=size, day_start=size,
                       attempt=attempt, created_at=_now(), relay_ids=list(relay_ids or []), strategy=strategy)


def load() -> DemoAccount:
    with _LOCK:
        try:
            d = json.loads(_path().read_text(encoding="utf-8"))
            known = DemoAccount.__dataclass_fields__
            return DemoAccount(**{k: v for k, v in d.items() if k in known})
        except Exception:  # noqa: BLE001 - missing / corrupt file: a fresh 50k demo, never a crash
            return _fresh(50_000.0)


def _save(acct: DemoAccount) -> None:
    acct.trades = acct.trades[-MAX_TRADES:]
    tmp = _path().with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(acct)), encoding="utf-8")
    tmp.replace(_path())


def reset(size: float | None = None, *, keep_deployment: bool = True) -> DemoAccount:
    """New evaluation attempt (after a pass or a breach, or on request). Keeps the tier, relays and strategy unless told otherwise."""
    with _LOCK:
        old = load()
        acct = _fresh(size or old.size, attempt=old.attempt + 1, relay_ids=old.relay_ids if keep_deployment else [],
                      strategy=old.strategy if keep_deployment else "")
        _save(acct)
        return acct


def advance_to_funded() -> DemoAccount:
    """The evaluation was passed: move on to the simulated FUNDED account (fresh balance and loss floor, no profit target, payouts instead).
    Allowed only from a passed evaluation. The trade history stays; the payout cycle starts after it."""
    with _LOCK:
        acct = load()
        if acct.phase != "evaluation" or acct.status != "passed":
            raise ValueError("The funded account is available once the evaluation is passed.")
        r = acct.rules
        size = float(acct.size)
        acct.phase, acct.status, acct.status_reason = "funded", "active", "Funded stage: trade for payouts."
        acct.balance = acct.start_balance = acct.eod_high = acct.day_start = acct.last_payout_balance = size
        acct.floor = size - r.loss_limit
        acct.best_day, acct.soft_limit_hits, acct.day_stopped = 0.0, 0, False
        acct.cycle_from, acct.funded_since, acct.payouts = len(acct.trades), _now(), []
        _save(acct)
        return acct


def request_payout() -> dict:
    """Take a simulated payout on the funded stage when the rule is met. Returns {ok, payout?, error?}; the floor does not move."""
    with _LOCK:
        acct = load()
        ps = payout_status(acct)
        if ps is None:
            return {"ok": False, "error": "Payouts start on the funded account."}
        if not ps["eligible"]:
            return {"ok": False, "error": " ".join(ps["reasons"]) or "Not eligible yet."}
        row = {"n": len(acct.payouts) + 1, "at": _now(), "amount": ps["amount"], "trader_share": ps["trader_share"], "balance_before": acct.balance}
        acct.payouts.append(row)
        acct.balance = round(acct.balance - ps["amount"], 2)
        acct.last_payout_balance = acct.balance
        acct.day_start = acct.balance          # the withdrawal is not a trading loss: today's P&L starts again from here
        acct.cycle_from = len(acct.trades)
        _save(acct)
        return {"ok": True, "payout": row}


def set_tier(size: float) -> DemoAccount:
    if float(size) not in TIERS:
        raise ValueError(f"Demo tiers are {', '.join(f'${t:,}' for t in TIERS)}.")
    with _LOCK:
        old = load()
        acct = _fresh(size, attempt=1, relay_ids=old.relay_ids, strategy=old.strategy)
        _save(acct)
        return acct


# ---- mode (Demo / Live) -----------------------------------------------------------------------------------------------------
def get_mode() -> str:
    try:
        from app.accounts.settings import load_account_settings
        m = (load_account_settings().account_mode or "demo").lower()
        return m if m in MODES else "demo"
    except Exception:  # noqa: BLE001
        return "demo"


def set_mode(mode: str) -> str:
    mode = (mode or "").strip().lower()
    if mode not in MODES:
        raise ValueError("Mode must be 'demo' or 'live'.")
    from app.accounts.settings import load_account_settings, save_account_settings
    s = load_account_settings()
    s.account_mode = mode
    save_account_settings(s)
    return mode


# ---- booking trades -----------------------------------------------------------------------------------------------------------
def _roll_day(acct: DemoAccount, today: str) -> None:
    """New trading day: bank yesterday's close into the end-of-day high, trail (or lock) the floor, reset the day counters."""
    if acct.day and acct.day != today:
        r = acct.rules
        day_profit = acct.balance - acct.day_start
        acct.best_day = max(acct.best_day, day_profit)
        acct.eod_high = max(acct.eod_high, acct.balance)
        if r.trailing:
            trailed = acct.eod_high - r.loss_limit
            acct.floor = max(acct.floor, min(trailed, acct.start_balance + r.lock_floor_offset))
        acct.day_start = acct.balance
        acct.day_stopped = False
    if not acct.day or acct.day != today:
        acct.day = today
        if not acct.trades:
            acct.day_start = acct.balance


def roll_day(today: str) -> DemoAccount:
    """Move the account to trading day ``today`` (YYYY-MM-DD) even when no trade closed: yesterday's close is banked, the end-of-day floor trails and the
    day counters (day start, soft-limit stop) reset.

    A bot reads the account's day start to size its next trade. The day used to advance only when a trade was BOOKED, so after one losing day the bot saw
    "down $526 today" forever (the day never rolled because the day stop it triggered stopped it booking anything): it skipped every later signal, for months
    of a replay, and a longer run on the same account took no trade at all. The bots call this at the first bar of every trading day."""
    with _LOCK:
        acct = load()
        if acct.status != "active" or acct.day == today:
            return acct
        _roll_day(acct, str(today)[:10])
        _save(acct)
        return acct


def record_trade(pnl: float, *, root: str = "", side: str = "", qty: float = 1.0, entry=None, exit=None, why: str = "",
                 source: str = "alert", closed_at: str | None = None, day: str | None = None, opened_at: str | None = None,
                 extra: dict | None = None) -> dict | None:
    """Book one closed trade. Returns the trade row (with running balance) or None when the account is no longer active
    (a passed or breached evaluation stops booking until it is reset, exactly like a real one).

    ``day`` (YYYY-MM-DD) is the trading day the trade belongs to; by default the date of ``closed_at``. A bot passes its own session day (the
    New York day that rolls at the 18:00 ET Globex open) so the account and the bot always agree on what "today" is."""
    with _LOCK:
        acct = load()
        if acct.status != "active":
            return None
        when = closed_at or _now()
        today = str(day or when[:10])[:10]
        _roll_day(acct, today)
        r = acct.rules
        acct.balance = round(acct.balance + float(pnl), 2)
        day_pnl = acct.balance - acct.day_start
        row = {"n": len(acct.trades) + 1, "closed_at": when, "day": today, "root": root, "side": side, "qty": qty, "entry": entry, "exit": exit,
               "pnl": round(float(pnl), 2), "result": "win" if pnl > 0 else "loss" if pnl < 0 else "flat", "why": why, "source": source,
               "balance": acct.balance, "day_pnl": round(day_pnl, 2), "attempt": acct.attempt, "opened_at": opened_at or "",
               "strategy": acct.strategy}
        if extra:                                    # a bot adds its name, strategy leg, risk and R so the trade log can show them
            row.update({k: v for k, v in extra.items() if v is not None})
        acct.trades.append(row)
        if day_pnl <= -r.soft_daily_limit and not acct.day_stopped:
            acct.day_stopped = True
            acct.soft_limit_hits += 1
        profit = acct.balance - acct.start_balance
        best = max(acct.best_day, day_pnl)
        if acct.balance <= acct.floor:
            acct.status, acct.status_reason = "breached", f"Balance ${acct.balance:,.2f} hit the loss floor ${acct.floor:,.2f}."
        elif acct.phase == "evaluation" and profit >= r.profit_target:
            share = best / profit if profit > 0 else 1.0
            cap = r.consistency_best_day_pct
            cap = None if cap is None else (cap / 100.0 if cap > 1 else cap)
            if cap is None or share <= cap:
                acct.status, acct.status_reason = "passed", f"Profit target ${r.profit_target:,.0f} reached with the best day at {share:.0%} of profit."
            else:
                acct.status_reason = f"Target reached but best day is {share:.0%} of profit (cap {cap:.0%}): keep trading."
        row["status"] = acct.status
        _save(acct)
        return row


def record_relay_actions(relay_id: str, actions: list) -> int:
    """Called by the webhook relay after each accepted alert: books every CLOSED leg for a relay linked to the demo account."""
    if not actions:
        return 0
    acct = load()
    if relay_id not in acct.relay_ids or get_mode() != "demo":
        return 0
    n = 0
    for a in actions:
        if a.get("action") in ("close", "reduce") and a.get("pnl") is not None:
            if record_trade(a["pnl"], root=a.get("root", ""), side=a.get("side", ""), qty=a.get("qty", 1.0), entry=a.get("entry"),
                            exit=a.get("exit"), why=a.get("why", ""), source="tradingview", closed_at=a.get("closed_at")):
                n += 1
    return n


# ---- deploy a validated strategy to the demo account --------------------------------------------------------------------------
def deploy_strategy(name: str, *, size: float | None = None, tickers: list | None = None, public_url: str = "") -> dict:
    """Create (or reuse) the webhook relay that feeds the demo account and return everything the user pastes into TradingView:
    the webhook URL and the alert message. Identical to what the real-account path uses, so Demo behaves the same as Live."""
    from app.webhook_relay import config as relay_config
    from app.webhook_relay.signals import pine_alert_message
    with _LOCK:
        acct = load()
        if size and float(size) != acct.size:
            acct = set_tier(float(size))
        relay = next((r for r in (relay_config.get_relay(i) for i in acct.relay_ids) if r is not None), None)
        if relay is None:
            relay = relay_config.create_relay({"name": f"T58 Demo {int(acct.size / 1000)}k"})
            acct.relay_ids = [relay.id]
        if tickers is not None:
            relay_config.update_relay(relay.id, {"allowed_tickers": [t.upper() for t in tickers]})
        acct.strategy = (name or acct.strategy or "").strip()[:80]
        _save(acct)
    base = (public_url or relay_config.get_public_url() or "").rstrip("/")
    return {"relay_id": relay.id, "strategy": acct.strategy, "size": acct.size, "alert_message": pine_alert_message(relay.passphrase),
            "webhook_url": f"{base}/webhook/tradingview/{relay.token}" if base else "", "path": f"/webhook/tradingview/{relay.token}",
            "url_ready": bool(base)}


# ---- header pill --------------------------------------------------------------------------------------------------------------------
def header_payload(live_rows: list | None = None) -> dict:
    """What the top-right P&L tracker shows. Demo: the T58 demo account. Live: the running real sessions (passed in)."""
    mode = get_mode()
    if mode == "demo":
        d = load().to_dict()
        return {"mode": "demo", "label": f"T58 Demo {int(d['size'] / 1000)}k", "pnl": d["net_pnl"], "day_pnl": d["day_pnl"],
                "balance": d["balance"], "status": d["status"], "target_pct": d["target_pct"], "n_trades": d["n_trades"],
                "cushion": d["cushion"], "running": bool(d["relay_ids"])}
    rows = live_rows or []
    pnl = sum((r.get("net_pnl") or 0) + (r.get("floating") or 0) for r in rows)
    bal = next((r.get("balance") for r in rows if r.get("balance") is not None), None)
    return {"mode": "live", "label": rows[0].get("label", "Live") if rows else "Live · no account running", "pnl": round(pnl, 2),
            "day_pnl": None, "balance": bal, "status": "active" if rows else "idle", "n_trades": sum(r.get("n_trades_closed") or 0 for r in rows),
            "running": bool(rows)}
