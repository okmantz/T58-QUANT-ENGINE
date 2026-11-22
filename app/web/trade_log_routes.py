"""Trade-log exports: the Trading Journal's trade log and the T58 demo account's trade log as CSV, plus the demo account's full trade list.

(The Trading Bot page's own export lives with the bot routes: /trading-bots/api/bot/<id>/trades.csv.)
One blueprint, registered once in server.py. Read-only; nothing here changes a trade.
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, request

from app.journal import export as ex
from app.web import journal_store

trade_log_bp = Blueprint("trade_log", __name__)


def _csv_response(text: str, stem: str) -> Response:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    resp = Response("﻿" + text, mimetype="text/csv")          # BOM so Excel opens the UTF-8 file correctly
    resp.headers["Content-Disposition"] = f'attachment; filename="{stem}-{stamp}.csv"'
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _journal_selection() -> tuple[list[dict], dict]:
    data = journal_store.load()
    trades = data["trades"]
    for key, field in (("source", "source"), ("strategy", "strategy"), ("account", "account")):
        want = (request.args.get(key) or "").strip()
        if want:
            trades = [t for t in trades if (t.get(field) or ("Manual" if field == "source" else "")) == want]
    lo, hi = (request.args.get("from") or "").strip(), (request.args.get("to") or "").strip()
    if lo:
        trades = [t for t in trades if (t.get("date") or "") >= lo]
    if hi:
        trades = [t for t in trades if (t.get("date") or "") <= hi]
    return trades, data["settings"]


@trade_log_bp.route("/api/journal/export.csv")
def journal_export_csv():
    """Every trade in the journal's trade log (hand-entered and auto-captured) with all its numbers. Filters: source, strategy, account, from, to."""
    trades, settings = _journal_selection()
    return _csv_response(ex.journal_csv(trades, settings), "t58-trade-journal")


@trade_log_bp.route("/api/journal/export-stats.csv")
def journal_export_stats_csv():
    """The summary statistics of the same selection (win rate, profit factor, expectancy, drawdown, streaks, best and worst day ...)."""
    trades, settings = _journal_selection()
    return _csv_response(ex.journal_stats_csv(trades, settings), "t58-trade-journal-stats")


@trade_log_bp.route("/api/demo-account/trades")
def demo_account_trades():
    """The demo account's whole trade log for its current attempt, newest first."""
    from app.demo_account import load
    a = load()
    rows = list(reversed(a.trades))
    return jsonify({"ok": True, "attempt": a.attempt, "n": len(rows), "trades": rows, "bots": _running_bot_ids("demo")})


@trade_log_bp.route("/api/demo-account/trades.csv")
def demo_account_trades_csv():
    from app.demo_account import load
    a = load()
    return _csv_response(ex.demo_csv(a.trades), f"t58-demo-trades-attempt{a.attempt}")


def _running_bot_ids(venue: str | None = None) -> list[str]:
    try:
        from app.bots import runner, store
        out = []
        for rec in store.list_bots():
            cfg = rec["config"]
            if venue and (cfg.get("account") or {}).get("venue") != venue:
                continue
            if runner.is_running(cfg["id"]):
                out.append(cfg["id"])
        return out
    except Exception:  # noqa: BLE001
        return []
