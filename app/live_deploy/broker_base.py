"""
BrokerAdapter -- the common interface every platform connector (MT5,
cTrader, Tradovate, TradeLocker, DXtrade) implements, so the rest of the
app (execution_engine.LiveExecutionSession, the Deploy Live routes) can
run a strategy against ANY connected funded account without knowing or
caring which platform it lives on.

This is new: previously app.forward_test.mt5_connector.MT5Connector was
the only connector in the codebase, and it was wired directly into
ForwardTestSession with no interface boundary -- there was nothing another
platform's connector could implement to slot into the same code path.

The dataclasses here (ConnectionResult, OrderResult, OpenPosition) are
intentionally IDENTICAL in shape to the ones already defined inline in
app.forward_test.mt5_connector, so MT5Connector can be wrapped by
broker_mt5.MT5BrokerAdapter with zero changes to MT5Connector itself --
see that file's docstring for why MT5Connector stays untouched rather than
being refactored to subclass this.

Every new adapter in this package (broker_ctrader.py, broker_tradovate.py,
broker_tradelocker.py, broker_dxtrade.py) is written against each
platform's real, documented, publicly-available API. None of them have
been exercised against a live account by anyone on this project -- there
was no account to test against. Treat first use with any of them as an
integration test: run it against a demo/practice account before pointing
it at a funded one, and expect to file a bug against whichever adapter you
hit first. This is explicitly flagged rather than hidden because the
alternative (a confident-looking connector that silently mis-executes on a
funded account) is worse than an honest "not yet battle-tested" label.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import pandas as pd

@dataclass
class ConnectionResult:
    ok: bool
    message: str
    account_login: str | None = None
    account_server: str | None = None
    balance: float | None = None
    equity: float | None = None
    currency: str | None = None
    resolved_terminal_path: str | None = None  # MT5-only; always None for REST-based platforms


@dataclass
class OrderResult:
    ok: bool
    message: str
    ticket: str | None = None   # order/deal/position id, stringified -- platforms use ints, uuids, or opaque strings
    price: float | None = None
    volume: float | None = None


@dataclass
class OpenPosition:
    ticket: str
    symbol: str
    direction: int  # 1 long, -1 short
    volume: float
    open_price: float
    sl: float
    tp: float
    open_time: pd.Timestamp
    profit: float


@dataclass
class PendingOrder:
    """A working (not yet filled) order at the broker: a limit, a stop or a stop-limit, entry or protective exit."""
    order_id: str
    symbol: str
    direction: int            # 1 buy, -1 sell
    volume: float             # broker-native units, like OrderResult.volume
    order_type: str           # "limit" | "stop" | "stop_limit"
    price: float = 0.0        # the limit price (limit / stop_limit) or the trigger (stop)
    stop_price: float = 0.0   # the trigger of a stop_limit
    sl: float = 0.0
    tp: float = 0.0
    reduce_only: bool = False
    comment: str = ""


ORDER_TYPES = ("market", "limit", "stop", "stop_limit")


def not_supported(platform: str, what: str) -> "OrderResult":
    """The honest answer of an adapter that has no implementation of ``what`` yet. Never raises, never pretends."""
    return OrderResult(ok=False, message=f"{platform} adapter does not support {what} yet. Use a market order, or a platform that does.")


class BrokerAdapter(ABC):
    """Every method here mirrors a method MT5Connector already had, so
    execution_engine.LiveExecutionSession (the generalized successor to
    app.forward_test.engine.ForwardTestSession) can treat any adapter
    identically. Implementations should never raise out of these methods
    for ordinary failure conditions (bad credentials, rejected order,
    network hiccup) -- return ok=False / None with a human-readable
    message instead, matching MT5Connector's existing convention, since
    LiveExecutionSession logs `.message` directly into the session journal
    a real user will read while real capital is on the line.
    """

    platform_name: str = "unknown"

    # Capability flags (class-level so the trade-copier preflight can read them
    # without opening a connection). supports_bars: fetch_completed_bars really
    # returns price history. supports_broker_stops: place_market_order attaches
    # the sl_price / tp_price it is given to the order at the broker. An adapter
    # that cannot do one of these overrides the flag to False.
    supports_bars: bool = True
    supports_broker_stops: bool = True
    # Order-type capabilities. An adapter that implements place_limit_order / place_stop_order / cancel_order / modify_order /
    # get_pending_orders / modify_position_stops sets the matching flag True. Everything defaults to "not supported" and the
    # default methods below say so in plain words instead of raising, so a bot can ask first and fall back to market orders.
    supports_limit_orders: bool = False
    supports_stop_orders: bool = False
    supports_order_modify: bool = False
    supports_position_stops: bool = False      # modify_position_stops: move / attach a position's stop and target after the fill

    @abstractmethod
    def connect(self) -> ConnectionResult: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def is_alive(self) -> bool: ...

    def ensure_connected(self, max_attempts: int = 3, retry_delay_seconds: float = 2.0) -> ConnectionResult:
        """Default retry wrapper, identical in behavior to
        MT5Connector.ensure_connected. Adapters can override this if a
        platform needs different reconnect semantics (e.g. refreshing an
        OAuth token instead of a full re-login)."""
        import time as _time
        if self.is_alive():
            return ConnectionResult(ok=True, message="Connected.")
        last_result = ConnectionResult(ok=False, message="Not connected.")
        for attempt in range(1, max_attempts + 1):
            last_result = self.connect()
            if last_result.ok:
                return last_result
            if attempt < max_attempts:
                _time.sleep(retry_delay_seconds)
        return last_result

    @abstractmethod
    def account_summary(self) -> Optional[dict]: ...

    @abstractmethod
    def fetch_completed_bars(self, symbol: str, timeframe_minutes: int, count: int) -> pd.DataFrame: ...

    def latest_completed_bar_time(self, symbol: str, timeframe_minutes: int) -> Optional[pd.Timestamp]:
        df = self.fetch_completed_bars(symbol, timeframe_minutes, 1)
        if df.empty:
            return None
        return df["timestamp"].iloc[-1]

    @abstractmethod
    def get_open_positions(self, symbol: Optional[str] = None) -> list[OpenPosition]: ...

    @abstractmethod
    def place_market_order(
        self, symbol: str, direction: int, volume: float,
        sl_price: float | None = None, tp_price: float | None = None,
        comment: str = "T58 Live", deviation: int = 20,
    ) -> OrderResult:
        """Place a market order. ``volume`` is the BROKER-NATIVE quantity
        (whole contracts on Tradovate, lots on MT5/cTrader/TradeLocker/
        DXtrade) -- callers MUST convert via ``to_broker_qty`` first;
        never pass raw sizing units here (v7 P0-1)."""

    @abstractmethod
    def close_position(self, ticket: str, comment: str = "T58 Live close") -> OrderResult: ...

    def close_all(self, symbol: Optional[str] = None) -> list[OrderResult]:
        return [self.close_position(p.ticket) for p in self.get_open_positions(symbol)]

    @abstractmethod
    def to_broker_qty(
        self, units: float, contract_size: Optional[float], units_per_lot: Optional[float],
    ) -> float:
        """Convert generic sizing units into this platform's native order quantity.

        ``units`` come from ``RiskConfig.position_size`` and mean
        ``PnL = units x price_move`` -- they are NOT contracts, lots, or
        base-currency amounts, and passing them verbatim as an order
        quantity is the 50x-oversize bug this method exists to kill
        (v7 P0-1: $50k/1%/10-pt-stop ES sizes to 50.0 units, which is ONE
        contract, not fifty).

        ``contract_size`` is sizing units per ONE whole contract (e.g.
        ES=50, MES=5 -- see app.data.instrument_specs); ``units_per_lot``
        is sizing units per ONE broker lot (FX standard 100,000; futures
        usually = contract_size). Each adapter uses whichever factor its
        platform's quantity semantics need, documented on the override.

        HARD RULES, no exceptions:
        * FLOOR to the platform's minimum quantity increment -- never
          round up. Rounding up risks more than the configured risk
          amount at the stop.
        * Return 0.0 when the size is below one whole minimum unit (the
          engine skips the entry; a sub-1-contract size must NEVER
          become a fractional contract or a rounded-up 1 lot).
        * Return 0.0 when the conversion factor this platform needs is
          missing or <= 0. Refusing is always safer than guessing on
          real capital -- there are NO silent defaults here.
        """
        ...

    # ------------------------------------------------------------------------------------------------------ stop / limit orders
    # ``volume`` is broker-native (see to_broker_qty). ``direction`` is the side of the ORDER (a protective stop on a long is a SELL stop).
    # ``reduce_only`` asks the broker to refuse an order that would open or flip a position (where the platform has the flag).
    def place_limit_order(
        self, symbol: str, direction: int, volume: float, limit_price: float,
        sl_price: float | None = None, tp_price: float | None = None,
        comment: str = "T58 Live", reduce_only: bool = False,
    ) -> OrderResult:
        """A resting limit order: buy at ``limit_price`` or lower, sell at ``limit_price`` or higher. Returns the ORDER id in ``ticket``."""
        return not_supported(self.platform_name, "limit orders")

    def place_stop_order(
        self, symbol: str, direction: int, volume: float, stop_price: float,
        sl_price: float | None = None, tp_price: float | None = None,
        comment: str = "T58 Live", reduce_only: bool = False, limit_price: float | None = None,
    ) -> OrderResult:
        """A stop order: becomes a market order when ``stop_price`` trades (buy above the market, sell below it). With ``limit_price`` it is a
        stop-limit. A protective stop is a stop order on the closing side. Returns the ORDER id in ``ticket``."""
        return not_supported(self.platform_name, "stop orders")

    def cancel_order(self, order_id: str) -> OrderResult:
        return not_supported(self.platform_name, "cancelling orders")

    def modify_order(self, order_id: str, *, price: float | None = None, stop_price: float | None = None,
                     volume: float | None = None, sl_price: float | None = None, tp_price: float | None = None) -> OrderResult:
        return not_supported(self.platform_name, "modifying orders")

    def modify_position_stops(self, ticket: str, sl_price: float | None = None, tp_price: float | None = None) -> OrderResult:
        """Move or attach an open position's stop-loss / take-profit (trail to break-even, add a target after the fill)."""
        return not_supported(self.platform_name, "changing a position's stop and target")

    def get_pending_orders(self, symbol: Optional[str] = None) -> list[PendingOrder]:
        """Working orders on the account (never filled yet). Used by a bot's restart reconciliation. [] when the platform cannot list them."""
        return []

    def place_order(self, order_type: str, symbol: str, direction: int, volume: float, *, price: float | None = None,
                    stop_price: float | None = None, sl_price: float | None = None, tp_price: float | None = None,
                    comment: str = "T58 Live", reduce_only: bool = False) -> OrderResult:
        """One entry point for the four order types, so a bot maps a level to an order without branching on the platform.

            market      price ignored
            limit       ``price`` is the limit
            stop        ``stop_price`` (or ``price``) is the trigger
            stop_limit  ``stop_price`` is the trigger, ``price`` the limit
        """
        t = str(order_type or "market").lower().replace("-", "_")
        if t not in ORDER_TYPES:
            return OrderResult(ok=False, message=f"Unknown order type {order_type!r}; use one of {', '.join(ORDER_TYPES)}.")
        if t == "market":
            return self.place_market_order(symbol, direction, volume, sl_price=sl_price, tp_price=tp_price, comment=comment)
        if t == "limit":
            if not price:
                return OrderResult(ok=False, message="A limit order needs a price.")
            return self.place_limit_order(symbol, direction, volume, float(price), sl_price=sl_price, tp_price=tp_price, comment=comment, reduce_only=reduce_only)
        trig = stop_price or price
        if not trig:
            return OrderResult(ok=False, message="A stop order needs a trigger price.")
        return self.place_stop_order(symbol, direction, volume, float(trig), sl_price=sl_price, tp_price=tp_price, comment=comment, reduce_only=reduce_only,
                                     limit_price=float(price) if (t == "stop_limit" and price) else None)

    def place_protective_orders(self, symbol: str, position_direction: int, volume: float, stop_price: float | None,
                                target_price: float | None, comment: str = "T58 protect") -> dict:
        """Attach a stop-loss and a take-profit to a position that already exists, as resting EXIT orders (opposite side, reduce-only).

        For platforms whose market order cannot carry stops (``supports_broker_stops`` False) and that have no per-position SL/TP edit. Returns
        {'stop': OrderResult | None, 'target': OrderResult | None}. If the stop is refused the caller must flatten: a position without a stop is not allowed."""
        exit_side = -int(position_direction)
        out: dict = {"stop": None, "target": None}
        if stop_price:
            out["stop"] = self.place_stop_order(symbol, exit_side, volume, float(stop_price), comment=comment, reduce_only=True)
        if target_price:
            out["target"] = self.place_limit_order(symbol, exit_side, volume, float(target_price), comment=comment, reduce_only=True)
        return out
