"""Stop / limit order support in the broker adapters. Mocked transports only: NONE of this is live-tested."""
from __future__ import annotations

from app.live_deploy.broker_base import BrokerAdapter, OrderResult, PendingOrder
from tests.backtest.test_broker_rest_adapters import _Session, _tl, _tv


class _Bare(BrokerAdapter):
    platform_name = "Bare"
    def connect(self): ...
    def disconnect(self): ...
    def is_alive(self): return True
    def account_summary(self): return None
    def fetch_completed_bars(self, *a, **k): ...
    def get_open_positions(self, symbol=None): return []
    def place_market_order(self, symbol, direction, volume, sl_price=None, tp_price=None, comment="", deviation=20):
        return OrderResult(ok=True, message="m", ticket="1", volume=volume)
    def close_position(self, ticket, comment=""): return OrderResult(ok=True, message="c")
    def to_broker_qty(self, units, cs, upl): return units


def test_defaults_say_not_supported_instead_of_raising():
    b = _Bare()
    assert not b.supports_limit_orders and not b.supports_stop_orders
    r = b.place_limit_order("X", 1, 1, 100.0)
    assert not r.ok and "does not support" in r.message
    assert not b.place_stop_order("X", 1, 1, 100.0).ok
    assert not b.cancel_order("1").ok and b.get_pending_orders() == []


def test_place_order_dispatch_and_validation():
    b = _Bare()
    assert b.place_order("market", "X", 1, 2).ok
    assert not b.place_order("limit", "X", 1, 2).ok            # no price
    assert not b.place_order("stop", "X", 1, 2).ok             # no trigger
    assert not b.place_order("weird", "X", 1, 2).ok


def test_tradovate_limit_stop_cancel_modify_list():
    a = _tv()
    a._session.routes[("POST", "/order/cancelorder")] = {"orderId": 900}
    a._session.routes[("POST", "/order/modifyorder")] = {"orderId": 900}
    a._session.routes[("GET", "/order/list")] = [
        {"id": 900, "accountId": 5, "contractName": "NQZ6", "action": "Sell", "orderQty": 2, "orderType": "Stop", "stopPrice": 99.0, "ordStatus": "Working"},
        {"id": 901, "accountId": 5, "contractName": "NQZ6", "action": "Buy", "orderQty": 1, "orderType": "Limit", "price": 90.0, "ordStatus": "Filled"}]
    assert a.place_limit_order("NQZ6", 1, 2, 100.25).ok
    assert a.place_stop_order("NQZ6", -1, 2, 99.0).ok
    assert a.place_stop_order("NQZ6", -1, 2, 99.0, limit_price=98.5).ok
    bodies = [c[2] for c in a._session.calls if c[1] == "/order/placeorder"]
    assert (bodies[0]["orderType"], bodies[0]["price"]) == ("Limit", 100.25)
    assert (bodies[1]["orderType"], bodies[1]["stopPrice"]) == ("Stop", 99.0)
    assert (bodies[2]["orderType"], bodies[2]["price"], bodies[2]["stopPrice"]) == ("StopLimit", 98.5, 99.0)
    assert a.cancel_order("900").ok
    assert a.modify_order("900", stop_price=98.0).ok
    pend = a.get_pending_orders("NQZ6")
    assert len(pend) == 1 and isinstance(pend[0], PendingOrder) and pend[0].order_type == "stop" and pend[0].direction == -1


def test_tradovate_protective_orders_are_reduce_side_exits():
    a = _tv()
    out = a.place_protective_orders("NQZ6", 1, 2, 99.0, 103.0)
    assert out["stop"].ok and out["target"].ok
    bodies = [c[2] for c in a._session.calls if c[1] == "/order/placeorder"]
    assert bodies[0]["action"] == "Sell" and bodies[0]["orderType"] == "Stop"
    assert bodies[1]["action"] == "Sell" and bodies[1]["orderType"] == "Limit"


def test_tradolocker_pending_flow():
    a = _tl()
    a.connect()
    acct = "/trade/accounts/9"
    a._session.routes[("GET", acct + "/orders")] = {"d": {"orders": [{"id": 7, "tradableInstrumentId": 77, "qty": 1, "side": "sell", "type": "stop",
                                                                     "status": "Working", "price": 0, "stopPrice": 1.08}]}}
    a._session.routes[("DELETE", "/trade/orders/7")] = {"s": "ok"}
    a._session.routes[("PATCH", "/trade/orders/7")] = {"s": "ok"}
    a._session.routes[("PATCH", "/trade/positions/501")] = {"s": "ok"}
    r = a.place_stop_order("EURUSD", -1, 0.5, 1.08, tp_price=1.05)
    assert r.ok and r.ticket == "42"
    body = [c for c in a._session.calls if c[0] == "POST" and c[1].endswith("/orders")][-1][2]
    assert body["type"] == "stop" and body["stopPrice"] == 1.08 and body["validity"] == "GTC"
    assert a.place_limit_order("EURUSD", 1, 0.5, 1.09).ok
    assert a.cancel_order("7").ok and a.modify_order("7", stop_price=1.07).ok
    assert a.modify_position_stops("501", sl_price=1.09).ok and not a.modify_position_stops("501").ok
    pend = a.get_pending_orders("EURUSD")
    assert len(pend) == 1 and pend[0].direction == -1 and pend[0].stop_price == 1.08
