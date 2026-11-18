"""Central risk arbiter: several strategies (and several bots) share ONE account, so they share ONE position slot and ONE daily limit.

Without it each leg / bot would judge its own risk in isolation: three bots on the same prop account could each open a full-size position on NQ,
or each spend its own daily-loss budget, and together breach the firm's single daily limit. Every entry goes through ``Arbiter.request_entry``; every
fill and every close is reported back (``on_open`` / ``on_close``), so the arbiter always knows the account's combined state.

What it enforces, per account and per trading day (all combined across every leg and every bot on the account):

  * at most ``max_open_positions`` positions open at once (default 1: "one position") and never two positions on the same instrument,
  * at most ``max_trades_per_day`` entries,
  * no new entry once the day's realised loss reached ``daily_loss_cap_usd`` (the combined day stop),
  * the sum of open risk (dollars at the stop) plus the new entry never above ``max_open_risk_usd``.

Backends: ``Arbiter.memory()`` keeps everything in the process (simulation / replay: every replay starts clean, nothing leaks between runs) and
``Arbiter.persistent(account_key)`` keeps the day ledger and the open slots in the bots SQLite database, so a restart (or a second process) sees the
same combined state. ``request_entry`` + ``on_open`` is not a single atomic step across processes; the persistent backend therefore RESERVES the slot inside
``request_entry`` (a row in ``arbiter_positions``) and ``on_open`` / ``release`` only finish or undo that reservation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Limits:
    max_open_positions: int = 1
    max_trades_per_day: int = 6
    daily_loss_cap_usd: float = 0.0          # 0 = no cap
    max_open_risk_usd: float = 0.0           # 0 = no cap


@dataclass(frozen=True)
class Verdict:
    allow: bool
    reason: str = ""


class _MemoryBackend:
    def __init__(self) -> None:
        self.days: dict = {}                 # (account, day) -> [trades, realised]
        self.pos: dict = {}                  # (account, bot, leg) -> dict

    def day(self, account: str, day: str) -> tuple[int, float]:
        t, r = self.days.get((account, day), [0, 0.0])
        return int(t), float(r)

    def add_trade(self, account: str, day: str, realised: float, count: int) -> None:
        d = self.days.setdefault((account, day), [0, 0.0])
        d[0] += count
        d[1] += realised

    def positions(self, account: str) -> list[dict]:
        return [v for (a, _b, _l), v in self.pos.items() if a == account]

    def put(self, account: str, bot: str, leg: str, row: dict) -> None:
        self.pos[(account, bot, leg)] = {**row, "bot_id": bot, "leg": leg}

    def drop(self, account: str, bot: str, leg: str) -> None:
        self.pos.pop((account, bot, leg), None)

    def drop_bot(self, account: str, bot: str) -> None:
        for k in [k for k in self.pos if k[0] == account and k[1] == bot]:
            del self.pos[k]


class _SqliteBackend:
    """The same operations on the bots database (see app.bots.store). One short transaction per call."""

    def _cx(self):
        from app.bots import store
        return store.connect()

    def day(self, account: str, day: str) -> tuple[int, float]:
        cx = self._cx()
        try:
            r = cx.execute("SELECT trades, realised FROM day_ledger WHERE account_key=? AND day=?", (account, day)).fetchone()
            return (int(r["trades"]), float(r["realised"])) if r else (0, 0.0)
        finally:
            cx.close()

    def add_trade(self, account: str, day: str, realised: float, count: int) -> None:
        cx = self._cx()
        try:
            cx.execute("BEGIN IMMEDIATE")
            cx.execute("INSERT INTO day_ledger(account_key, day, trades, realised) VALUES(?,?,?,?) "
                       "ON CONFLICT(account_key, day) DO UPDATE SET trades=trades+excluded.trades, realised=realised+excluded.realised",
                       (account, day, count, realised))
            cx.execute("COMMIT")
        finally:
            cx.close()

    def positions(self, account: str) -> list[dict]:
        cx = self._cx()
        try:
            return [dict(r) for r in cx.execute("SELECT * FROM arbiter_positions WHERE account_key=?", (account,))]
        finally:
            cx.close()

    def put(self, account: str, bot: str, leg: str, row: dict) -> None:
        cx = self._cx()
        try:
            cx.execute("INSERT OR REPLACE INTO arbiter_positions(account_key, bot_id, leg, symbol, direction, qty, risk_dollars, opened) VALUES(?,?,?,?,?,?,?,?)",
                       (account, bot, leg, row["symbol"], int(row["direction"]), float(row["qty"]), float(row["risk_dollars"]), row.get("opened", "")))
        finally:
            cx.close()

    def drop(self, account: str, bot: str, leg: str) -> None:
        cx = self._cx()
        try:
            cx.execute("DELETE FROM arbiter_positions WHERE account_key=? AND bot_id=? AND leg=?", (account, bot, leg))
        finally:
            cx.close()

    def drop_bot(self, account: str, bot: str) -> None:
        cx = self._cx()
        try:
            cx.execute("DELETE FROM arbiter_positions WHERE account_key=? AND bot_id=?", (account, bot))
        finally:
            cx.close()


class Arbiter:
    def __init__(self, account_key: str, backend=None) -> None:
        self.account = str(account_key)
        self._b = backend or _MemoryBackend()

    @classmethod
    def memory(cls, account_key: str = "sim") -> "Arbiter":
        return cls(account_key, _MemoryBackend())

    @classmethod
    def persistent(cls, account_key: str) -> "Arbiter":
        return cls(account_key, _SqliteBackend())

    # ------------------------------------------------------------------------------------------------------------------ queries
    def day_state(self, day: str) -> dict:
        t, r = self._b.day(self.account, day)
        return {"trades": t, "realised": r}

    def open_positions(self) -> list[dict]:
        return self._b.positions(self.account)

    # ------------------------------------------------------------------------------------------------------------------ decisions
    def request_entry(self, bot_id: str, leg: str, symbol: str, direction: int, risk_dollars: float, day: str, limits: Limits) -> Verdict:
        """Ask for an entry slot. On ``allow`` the slot is RESERVED (counted as open risk) until ``on_open`` confirms it or ``release`` gives it back."""
        trades, realised = self._b.day(self.account, day)
        if limits.max_trades_per_day and trades >= limits.max_trades_per_day:
            return Verdict(False, f"combined daily trade cap reached ({trades}/{limits.max_trades_per_day} across every strategy on this account)")
        if limits.daily_loss_cap_usd and realised <= -abs(limits.daily_loss_cap_usd):
            return Verdict(False, f"combined day stop: ${-realised:,.0f} lost today across all strategies (cap ${limits.daily_loss_cap_usd:,.0f})")
        others = [p for p in self._b.positions(self.account) if not (p["bot_id"] == bot_id and p["leg"] == leg)]
        for p in others:
            if p["symbol"] == symbol:
                return Verdict(False, f"{symbol} is already held on this account by {p['bot_id']} / {p['leg']}: one position per instrument")
        if len(others) >= max(1, int(limits.max_open_positions)):
            return Verdict(False, f"{len(others)} position(s) already open on this account (limit {limits.max_open_positions}): one position at a time")
        open_risk = sum(float(p["risk_dollars"]) for p in others)
        if limits.max_open_risk_usd and open_risk + float(risk_dollars) > limits.max_open_risk_usd + 1e-9:
            return Verdict(False, f"open risk ${open_risk + risk_dollars:,.0f} would exceed the account budget ${limits.max_open_risk_usd:,.0f}")
        self._b.put(self.account, bot_id, leg, {"symbol": symbol, "direction": int(direction), "qty": 0.0, "risk_dollars": float(risk_dollars), "opened": ""})
        return Verdict(True, "")

    def on_open(self, bot_id: str, leg: str, symbol: str, direction: int, qty: float, risk_dollars: float, day: str, opened: str = "") -> None:
        self._b.put(self.account, bot_id, leg, {"symbol": symbol, "direction": int(direction), "qty": float(qty), "risk_dollars": float(risk_dollars), "opened": opened})
        self._b.add_trade(self.account, day, 0.0, 1)

    def release(self, bot_id: str, leg: str) -> None:
        """Give back a reserved slot that never filled (order rejected, entry cancelled)."""
        self._b.drop(self.account, bot_id, leg)

    def on_close(self, bot_id: str, leg: str, realised: float, day: str) -> None:
        self._b.drop(self.account, bot_id, leg)
        self._b.add_trade(self.account, day, float(realised), 0)

    def ensure_day(self, day: str, trades: int, realised: float) -> None:
        """Restart: make sure today's ledger is at least what this bot's own persisted runtime says it did (never lowers a larger shared figure)."""
        t, r = self._b.day(self.account, day)
        if trades > t or realised < r:
            self._b.add_trade(self.account, day, min(0.0, realised - r) if realised < r else 0.0, max(0, trades - t))

    def forget_bot(self, bot_id: str) -> None:
        self._b.drop_bot(self.account, bot_id)

    def sync_open(self, bot_id: str, rows: list[dict]) -> None:
        """Restart reconciliation: replace this bot's slots with the positions it really holds (symbol, direction, qty, risk_dollars, leg)."""
        self._b.drop_bot(self.account, bot_id)
        for r in rows:
            self._b.put(self.account, bot_id, r["leg"], {"symbol": r["symbol"], "direction": int(r["direction"]), "qty": float(r.get("qty", 0)),
                                                         "risk_dollars": float(r.get("risk_dollars", 0)), "opened": r.get("opened", "")})


def account_key(account) -> str:
    """The identity of an account across bots: venue + account id (two bots linked to the same account share it)."""
    return f"{getattr(account, 'venue', 'paper')}:{getattr(account, 'account_id', '') or 'default'}"
