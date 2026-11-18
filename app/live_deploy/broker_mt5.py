"""
Wraps the existing, already-working app.forward_test.mt5_connector.MT5Connector
so it satisfies the new BrokerAdapter interface, without changing
MT5Connector itself.

Why wrap instead of refactor MT5Connector to subclass BrokerAdapter
directly: MT5Connector is used today by the Forward Test tab against a
*demo* account, is already tested in that role, and its OrderResult/
OpenPosition/ConnectionResult field types (int tickets, etc.) are baked
into app.forward_test.engine and app.forward_test.journal. Changing its
field types to match BrokerAdapter's (stringified tickets, so every
platform can share one type) would risk breaking Forward Test for a
purely cosmetic gain. This thin wrapper is the entire cost of
interoperability instead.
"""
from __future__ import annotations

import math
from typing import Optional

import pandas as pd

from app.forward_test.mt5_connector import MT5Connector
from app.live_deploy.broker_base import (
    BrokerAdapter, ConnectionResult, OpenPosition, OrderResult, PendingOrder,
)


class MT5BrokerAdapter(BrokerAdapter):
    platform_name = "MT4/MT5"

    def __init__(self, login: str, password: str, server: str, terminal_path: str = ""):
        self._conn = MT5Connector(login=login, password=password, server=server, terminal_path=terminal_path)

    def connect(self) -> ConnectionResult:
        r = self._conn.connect()
        return ConnectionResult(
            ok=r.ok, message=r.message,
            account_login=str(r.account_login) if r.account_login is not None else None,
            account_server=r.account_server, balance=r.balance, equity=r.equity,
            currency=r.currency, resolved_terminal_path=r.resolved_terminal_path,
        )

    def disconnect(self) -> None:
        self._conn.disconnect()

    def is_alive(self) -> bool:
        return self._conn.is_alive()

    def account_summary(self) -> Optional[dict]:
        return self._conn.account_summary()

    def fetch_completed_bars(self, symbol: str, timeframe_minutes: int, count: int) -> pd.DataFrame:
        return self._conn.fetch_completed_bars(symbol, timeframe_minutes, count)

    def get_open_positions(self, symbol: Optional[str] = None) -> list[OpenPosition]:
        return [
            OpenPosition(
                ticket=str(p.ticket), symbol=p.symbol, direction=p.direction, volume=p.volume,
                open_price=p.open_price, sl=p.sl, tp=p.tp, open_time=p.open_time, profit=p.profit,
            )
            for p in self._conn.get_open_positions(symbol)
        ]

    def to_broker_qty(
        self, units: float, contract_size: Optional[float], units_per_lot: Optional[float],
    ) -> float:
        # MT5 order volume is LOTS. For FX, 1 lot = 100,000 base-currency
        # units and sizing "units" are exactly base-currency units
        # (PnL = units x price_move), so units_per_lot=100,000 converts
        # correctly. For futures on MT5, 1 lot is normally 1 contract, so
        # callers pass units_per_lot = contract_size. Floored to 0.01
        # (MT5's finest common volume step) -- never rounded up. Refuses
        # (0.0) when units_per_lot is missing: passing raw units as lots
        # would otherwise send e.g. 100,000-lot orders (v7 P0-1).
        if not units_per_lot or units_per_lot <= 0:
            return 0.0
        return math.floor(units / units_per_lot * 100 + 1e-9) / 100.0

    def place_market_order(
        self, symbol: str, direction: int, volume: float,
        sl_price: float | None = None, tp_price: float | None = None,
        comment: str = "T58 Live", deviation: int = 20,
    ) -> OrderResult:
        # `volume` here is broker-native LOTS, converted via to_broker_qty
        # by the caller -- never raw sizing units (v7 P0-1).
        r = self._conn.place_market_order(
            symbol, direction, volume, sl_price=sl_price, tp_price=tp_price,
            comment=comment[:31], deviation=deviation,  # MT5 comment field is capped at 31 chars
        )
        return OrderResult(ok=r.ok, message=r.message, ticket=str(r.ticket) if r.ticket is not None else None,
                            price=r.price, volume=r.volume)

    def close_position(self, ticket: str, comment: str = "T58 Live close") -> OrderResult:
        r = self._conn.close_position(int(ticket), comment=comment[:31])
        return OrderResult(ok=r.ok, message=r.message, ticket=str(r.ticket) if r.ticket is not None else None,
                            price=r.price, volume=r.volume)

    # ------------------------------------------------------------ stop / limit orders (mocked-tested, NOT live-tested)
    supports_limit_orders = True
    supports_stop_orders = True
    supports_order_modify = True
    supports_position_stops = True

    def _pending(self, symbol, direction, volume, kind, price, sl=None, tp=None, comment="T58 Live", limit_price=None) -> OrderResult:
        from app.forward_test.mt5_connector import mt5
        tmap = {("limit", 1): "ORDER_TYPE_BUY_LIMIT", ("limit", -1): "ORDER_TYPE_SELL_LIMIT", ("stop", 1): "ORDER_TYPE_BUY_STOP",
                ("stop", -1): "ORDER_TYPE_SELL_STOP", ("stop_limit", 1): "ORDER_TYPE_BUY_STOP_LIMIT", ("stop_limit", -1): "ORDER_TYPE_SELL_STOP_LIMIT"}
        try:
            req = {"action": mt5.TRADE_ACTION_PENDING, "symbol": symbol, "volume": float(volume), "type": getattr(mt5, tmap[(kind, direction)]),
                   "price": float(price), "comment": comment[:31], "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_RETURN}
            if kind == "stop_limit" and limit_price:
                req["stoplimit"] = float(limit_price)
            if sl:
                req["sl"] = float(sl)
            if tp:
                req["tp"] = float(tp)
            res = self._conn._send_with_fill_fallback(req)
            if res is None:
                code, desc = mt5.last_error()
                return OrderResult(ok=False, message=f"order_send returned None ({code}): {desc}")
            if res.retcode != mt5.TRADE_RETCODE_DONE:
                return OrderResult(ok=False, message=self._conn._reject_message("Pending order rejected", res))
            return OrderResult(ok=True, message="Order working.", ticket=str(res.order), price=price, volume=volume)
        except Exception as exc:  # noqa: BLE001
            return OrderResult(ok=False, message=str(exc))

    def place_limit_order(self, symbol, direction, volume, limit_price, sl_price=None, tp_price=None, comment="T58 Live", reduce_only=False) -> OrderResult:
        return self._pending(symbol, direction, volume, "limit", limit_price, sl_price, tp_price, comment)

    def place_stop_order(self, symbol, direction, volume, stop_price, sl_price=None, tp_price=None, comment="T58 Live", reduce_only=False,
                         limit_price=None) -> OrderResult:
        return self._pending(symbol, direction, volume, "stop_limit" if limit_price else "stop", stop_price, sl_price, tp_price, comment, limit_price)

    def cancel_order(self, order_id: str) -> OrderResult:
        from app.forward_test.mt5_connector import mt5
        try:
            res = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": int(order_id)})
            if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
                return OrderResult(ok=False, message=f"Cancel rejected: {getattr(res, 'comment', 'no reply')}")
            return OrderResult(ok=True, message="Cancelled.", ticket=str(order_id))
        except Exception as exc:  # noqa: BLE001
            return OrderResult(ok=False, message=str(exc))

    def modify_order(self, order_id, *, price=None, stop_price=None, volume=None, sl_price=None, tp_price=None) -> OrderResult:
        from app.forward_test.mt5_connector import mt5
        try:
            cur = mt5.orders_get(ticket=int(order_id))
            if not cur:
                return OrderResult(ok=False, message=f"Order {order_id} is not working on MT5.")
            o = cur[0]
            req = {"action": mt5.TRADE_ACTION_MODIFY, "order": int(order_id), "price": float(stop_price if stop_price is not None else price if price is not None else o.price_open),
                   "sl": float(sl_price if sl_price is not None else o.sl), "tp": float(tp_price if tp_price is not None else o.tp),
                   "type_time": mt5.ORDER_TIME_GTC}
            res = mt5.order_send(req)
            if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
                return OrderResult(ok=False, message=f"Modify rejected: {getattr(res, 'comment', 'no reply')}")
            return OrderResult(ok=True, message="Modified.", ticket=str(order_id))
        except Exception as exc:  # noqa: BLE001
            return OrderResult(ok=False, message=str(exc))

    def modify_position_stops(self, ticket, sl_price=None, tp_price=None) -> OrderResult:
        from app.forward_test.mt5_connector import mt5
        try:
            pos = mt5.positions_get(ticket=int(ticket))
            if not pos:
                return OrderResult(ok=False, message=f"No open position with ticket {ticket}.")
            p = pos[0]
            res = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": int(ticket), "symbol": p.symbol,
                                  "sl": float(sl_price if sl_price is not None else p.sl), "tp": float(tp_price if tp_price is not None else p.tp)})
            if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
                return OrderResult(ok=False, message=f"Stop change rejected: {getattr(res, 'comment', 'no reply')}")
            return OrderResult(ok=True, message="Stops updated.", ticket=str(ticket))
        except Exception as exc:  # noqa: BLE001
            return OrderResult(ok=False, message=str(exc))

    def get_pending_orders(self, symbol=None) -> list[PendingOrder]:
        from app.forward_test.mt5_connector import mt5
        try:
            rows = mt5.orders_get(symbol=symbol) if symbol else mt5.orders_get()
        except Exception:  # noqa: BLE001
            return []
        out = []
        for o in rows or []:
            n = {getattr(mt5, "ORDER_TYPE_BUY_LIMIT", -1): ("limit", 1), getattr(mt5, "ORDER_TYPE_SELL_LIMIT", -2): ("limit", -1),
                 getattr(mt5, "ORDER_TYPE_BUY_STOP", -3): ("stop", 1), getattr(mt5, "ORDER_TYPE_SELL_STOP", -4): ("stop", -1),
                 getattr(mt5, "ORDER_TYPE_BUY_STOP_LIMIT", -5): ("stop_limit", 1), getattr(mt5, "ORDER_TYPE_SELL_STOP_LIMIT", -6): ("stop_limit", -1)}.get(o.type)
            if n is None:
                continue
            out.append(PendingOrder(order_id=str(o.ticket), symbol=o.symbol, direction=n[1], volume=float(o.volume_current), order_type=n[0],
                                    price=float(o.price_open), stop_price=float(getattr(o, "price_stoplimit", 0.0) or 0.0), sl=float(o.sl), tp=float(o.tp)))
        return out
