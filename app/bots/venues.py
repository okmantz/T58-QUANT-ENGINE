"""Where a bot's orders go. Three venues, one interface:

  PaperVenue   the bot's own sandbox account (default for a custom bot); nothing outside the bot is touched.
  DemoVenue    the T58 demo account (the default for the three shipped bots): every closed trade is booked into it, the account's trailing
               floor / daily limit / target decide pass and breach, and the bot sizes from the account's real state.
  BrokerVenue  a connected live or prop-firm account through the existing ``BrokerAdapter`` (Tradovate, MT5, cTrader, TradeLocker,
               DXtrade). Orders are market orders with the stop and target attached at the broker; ``poll`` notices a broker-side exit.

Simulated venues fill inside the engine (``simulated_fills = True``); the broker venue returns the real fill.
"""
from __future__ import annotations

from typing import Optional

from app.bots.models import OpenPos
from app.bots.risk_governor import AccountRulesLite, AccountState


class Venue:
    kind = "paper"
    label = "Bot sandbox"
    simulated_fills = True
    supports_sync = False

    def sync_state(self, state: AccountState) -> None:  # noqa: D401
        """Overwrite ``state`` from the venue's own source of truth (no-op for the sandbox)."""

    def roll_day(self, day: str) -> None:
        """The bot's first bar of a new trading day (``YYYY-MM-DD``): venues that keep their own day counters move them forward (no-op elsewhere)."""

    def open(self, pos: OpenPos, *, symbol_hint: str = "") -> tuple[bool, Optional[float], str, str]:
        return True, None, "", ""

    def close(self, pos: OpenPos, price: float, reason: str) -> tuple[bool, Optional[float], str]:
        return True, None, ""

    def poll(self, pos: OpenPos) -> Optional[dict]:
        return None

    def book(self, trade: dict) -> None:
        return None

    def flatten_all(self) -> None:
        return None

    def describe(self) -> dict:
        return {"kind": self.kind, "label": self.label}


class PaperVenue(Venue):
    kind = "paper"
    label = "Bot sandbox (own paper account)"


class DemoVenue(Venue):
    """Books into app.demo_account (the shared T58 demo prop account). Sizing reads the account's true balance / floor / day state."""
    kind = "demo"
    label = "T58 Demo account"
    supports_sync = True

    def _acct(self):
        from app.demo_account import account as demo
        return demo.load()

    def roll_day(self, day: str) -> None:
        from app.demo_account import account as demo
        demo.roll_day(day)

    def sync_state(self, state: AccountState) -> None:
        a = self._acct()
        rules = a.rules
        state.rules = AccountRulesLite.from_v2(rules)
        state.balance, state.start_balance, state.floor = float(a.balance), float(a.start_balance), float(a.floor)
        state.eod_high, state.day_start = float(a.eod_high), float(a.day_start)
        if state.day and a.day and a.day != state.day:
            # the demo account has not seen today yet (no trade booked, no roll): today starts from the current balance and nothing is stopped
            state.day_start = float(a.balance)
            state.eod_high = max(float(a.eod_high), float(a.balance))
        state.peak_equity = max(state.peak_equity, state.balance)
        if a.status == "active" and getattr(a, "phase", "evaluation") == "funded":
            state.phase = "funded"                       # the demo account was moved on to its funded stage by its owner
            state.last_payout_balance = float(a.last_payout_balance or a.start_balance)
        elif a.status == "active" and state.phase not in ("funded",):
            state.phase = "evaluation"
        elif a.status == "breached":
            state.phase = "breached"
        elif a.status == "passed" and state.phase == "evaluation":
            state.phase = "passed"
        state.stopped_today = bool(a.day_stopped) and not (state.day and a.day and a.day != state.day)

    def book(self, trade: dict) -> None:
        from app.demo_account import account as demo
        demo.record_trade(float(trade["pnl"]), root=trade.get("symbol", ""), side=trade.get("side", ""), qty=float(trade.get("qty", 1)),
                          entry=trade.get("entry"), exit=trade.get("exit"), why=f"{trade.get('bot', 'bot')}: {trade.get('leg', '')} ({trade.get('reason', '')})",
                          source="bot", closed_at=str(trade.get("exit_time") or ""), day=trade.get("day") or None,
                          opened_at=str(trade.get("entry_time") or ""),
                          extra={"bot": trade.get("bot", ""), "leg": trade.get("leg", ""), "strategy": trade.get("leg", ""), "risk": trade.get("risk"),
                                 "r_multiple": trade.get("r_multiple"), "kind": trade.get("kind", ""), "reason": trade.get("reason", "")})

    owns_payouts = True

    def request_payout(self) -> dict:
        from app.demo_account import account as demo
        return demo.request_payout()

    def describe(self) -> dict:
        a = self._acct()
        return {"kind": self.kind, "label": f"T58 Demo ${a.size / 1000:,.0f}K", "status": a.status, "balance": a.balance}


class BrokerVenue(Venue):
    """A connected live / prop-firm account. ``adapter`` is a connected ``BrokerAdapter``; ``symbol`` the broker's own contract symbol."""
    kind = "broker"
    simulated_fills = False
    supports_sync = True

    def __init__(self, adapter, symbol: str, label: str = "Broker account", *, contract_size: float = 2.0, units_per_lot: float | None = None):
        self.adapter, self.symbol, self.label = adapter, symbol, label
        self.contract_size, self.units_per_lot = float(contract_size), units_per_lot
        self._start_balance: Optional[float] = None
        self.symbol_map: dict = {}               # research instrument (NQ / ES / GC) -> the broker's contract symbol; empty = everything on ``symbol``

    def _sym(self, pos: OpenPos) -> str:
        return self.symbol_map.get(pos.symbol, self.symbol)

    def sync_state(self, state: AccountState) -> None:
        try:
            s = self.adapter.account_summary() or {}
        except Exception:  # noqa: BLE001
            return
        bal = s.get("balance") if isinstance(s, dict) else None
        if bal is None:
            return
        if self._start_balance is None:
            self._start_balance = float(bal)
        state.balance = float(bal)
        state.peak_equity = max(state.peak_equity, state.balance)

    def open(self, pos: OpenPos, *, symbol_hint: str = "") -> tuple[bool, Optional[float], str, str]:
        qty = self.adapter.to_broker_qty(float(pos.qty) * self.contract_size, self.contract_size, self.units_per_lot)
        if qty <= 0:
            return False, None, "", "broker quantity rounds to zero: order skipped"
        res = self.adapter.place_market_order(self._sym(pos), int(pos.direction), qty, sl_price=pos.stop_price, tp_price=pos.tp_price,
                                              comment=f"T58 bot {pos.leg}")
        return bool(res.ok), res.price, str(res.ticket or ""), str(res.message or "")

    def close(self, pos: OpenPos, price: float, reason: str) -> tuple[bool, Optional[float], str]:
        if not pos.ticket:
            return False, None, "no broker ticket"
        res = self.adapter.close_position(pos.ticket, comment=f"T58 bot exit: {reason}")
        return bool(res.ok), res.price, str(res.message or "")

    def poll(self, pos: OpenPos) -> Optional[dict]:
        """None while the broker still holds the position; a dict {'closed': True} once it is gone (stop / target hit at the broker)."""
        try:
            open_ = self.adapter.get_open_positions(self._sym(pos))
        except Exception:  # noqa: BLE001
            return None
        if any(str(p.ticket) == str(pos.ticket) for p in open_):
            return None
        return {"closed": True}

    def flatten_all(self) -> None:
        try:
            self.adapter.close_all(self.symbol)
        except Exception:  # noqa: BLE001
            return None

    def describe(self) -> dict:
        return {"kind": self.kind, "label": self.label, "symbol": self.symbol}


def venue_for(cfg_account, *, adapter=None) -> Venue:
    """Venue for a bot's AccountLink. ``adapter`` is only needed for the broker venue (the caller builds + connects it)."""
    if cfg_account.venue == "demo":
        return DemoVenue()
    if cfg_account.venue == "broker":
        if adapter is None:
            raise ValueError("a broker venue needs a connected account")
        return BrokerVenue(adapter, cfg_account.broker_symbol, label=f"Broker · {cfg_account.broker_symbol}")
    return PaperVenue()
