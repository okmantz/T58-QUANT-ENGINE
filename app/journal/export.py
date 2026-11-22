"""CSV exports for every trade log (Trading Journal, a Trading Bot, the T58 demo account).

Pure functions: rows in, CSV text out, no Flask and no I/O, so the routes and the tests share one source. Every export carries the
per-trade numbers (entry and exit times, duration, prices, size, risk, P&L, R, running P&L and balance, why it closed) and has a
matching summary-statistics export (win rate, profit factor, expectancy, drawdown, streaks, best and worst day ...).
"""
from __future__ import annotations

import csv
import io
import math
from datetime import datetime, timezone
from typing import Iterable

JOURNAL_FIELDS = [
    "date", "entry_time", "exit_time", "duration_min", "instrument", "direction", "strategy", "bot", "source", "account", "venue", "mode",
    "volume", "entry_price", "exit_price", "stop", "take_profit", "risk_usd", "pnl_usd", "r_multiple", "cumulative_pnl_usd",
    "exit_reason", "setup", "session", "regime", "violations", "playbook", "tags", "checklist_pct", "backtest_avg_r", "notes", "id",
]

BOT_FIELDS = [
    "n", "day", "entry_time", "exit_time", "duration_min", "bot", "strategy_leg", "symbol", "side", "contracts", "contract_type",
    "entry_price", "exit_price", "risk_usd", "pnl_usd", "r_multiple", "cumulative_pnl_usd", "account_balance_usd", "size_multiplier", "exit_reason",
]

DEMO_FIELDS = [
    "n", "day", "entry_time", "exit_time", "duration_min", "instrument", "side", "contracts", "entry_price", "exit_price", "pnl_usd",
    "result", "r_multiple", "cumulative_pnl_usd", "balance_usd", "day_pnl_usd", "source", "bot", "strategy", "why", "attempt",
]


def _f(x, default=None):
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _dt(s):
    try:
        if not s:
            return None
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _minutes(a, b):
    da, db = _dt(a), _dt(b)
    return round((db - da).total_seconds() / 60.0, 1) if da and db else ""


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.6g}" if abs(v) < 1e-3 and v != 0 else f"{v:.4f}".rstrip("0").rstrip(".")
    return v


def to_csv(fields: list[str], rows: Iterable[dict]) -> str:
    """CSV text (UTF-8, CRLF line ends, header first). Cells that start with = + - @ are prefixed so a spreadsheet never runs them as formulas."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(fields)
    for r in rows:
        out = []
        for k in fields:
            v = _fmt(r.get(k))
            if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") and not _is_number(v):
                v = "'" + v
            out.append(v)
        w.writerow(out)
    return buf.getvalue()


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


# ------------------------------------------------------------------------------------------------ summary statistics
def summary_stats(pnls: list[float], *, days: dict | None = None, start_balance: float | None = None, r_values: list[float] | None = None) -> list[tuple[str, object]]:
    """[(metric, value)] for a list of closed-trade P&Ls in time order. ``days`` is {day: pnl}."""
    n = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gw, gl = sum(wins), -sum(losses)
    eq = peak = float(start_balance or 0.0)
    maxdd = 0.0
    run_w = run_l = best_w = best_l = 0
    for p in pnls:
        eq += p
        peak = max(peak, eq)
        maxdd = max(maxdd, peak - eq)
        run_w = run_w + 1 if p > 0 else 0
        run_l = run_l + 1 if p < 0 else 0
        best_w, best_l = max(best_w, run_w), max(best_l, run_l)
    dv = list((days or {}).values())
    rs = [r for r in (r_values or []) if r is not None]
    pf = (gw / gl) if gl > 0 else None
    rows: list[tuple[str, object]] = [
        ("trades", n), ("wins", len(wins)), ("losses", len(losses)), ("breakeven", n - len(wins) - len(losses)),
        ("win_rate_pct", round(100.0 * len(wins) / n, 2) if n else ""),
        ("net_pnl_usd", round(sum(pnls), 2)), ("gross_profit_usd", round(gw, 2)), ("gross_loss_usd", round(-gl, 2)),
        ("profit_factor", round(pf, 3) if pf is not None else ("infinite" if gw > 0 else "")),
        ("expectancy_usd", round(sum(pnls) / n, 2) if n else ""),
        ("avg_win_usd", round(gw / len(wins), 2) if wins else ""), ("avg_loss_usd", round(-gl / len(losses), 2) if losses else ""),
        ("payoff_ratio", round((gw / len(wins)) / (gl / len(losses)), 3) if wins and losses and gl > 0 else ""),
        ("best_trade_usd", round(max(pnls), 2) if pnls else ""), ("worst_trade_usd", round(min(pnls), 2) if pnls else ""),
        ("avg_r", round(sum(rs) / len(rs), 3) if rs else ""), ("r_trades", len(rs)),
        ("max_drawdown_usd", round(maxdd, 2)), ("max_win_streak", best_w), ("max_loss_streak", best_l),
    ]
    if dv:
        mean = sum(dv) / len(dv)
        sd = math.sqrt(sum((v - mean) ** 2 for v in dv) / (len(dv) - 1)) if len(dv) > 1 else 0.0
        rows += [("trading_days", len(dv)), ("green_days", sum(1 for v in dv if v > 0)), ("red_days", sum(1 for v in dv if v < 0)),
                 ("best_day_usd", round(max(dv), 2)), ("worst_day_usd", round(min(dv), 2)), ("avg_day_usd", round(mean, 2)),
                 ("daily_sharpe_annualised", round(mean / sd * math.sqrt(252), 2) if sd > 0 else "")]
    if start_balance:
        rows += [("starting_balance_usd", round(float(start_balance), 2)), ("ending_balance_usd", round(float(start_balance) + sum(pnls), 2)),
                 ("return_pct", round(100.0 * sum(pnls) / float(start_balance), 3))]
    return rows


def stats_csv(stats: list[tuple[str, object]]) -> str:
    return to_csv(["metric", "value"], ({"metric": k, "value": v} for k, v in stats))


# ------------------------------------------------------------------------------------------------ Trading Journal
def journal_rows(trades: list[dict], playbooks: dict | None = None, tag_names: dict | None = None) -> list[dict]:
    """Journal trades (oldest first) -> export rows with a running P&L column."""
    playbooks, tag_names = playbooks or {}, tag_names or {}
    ordered = sorted(trades, key=lambda t: (t.get("entryTime") or t.get("date") or "", t.get("exitTime") or "", t.get("id") or ""))
    out, cum = [], 0.0
    for t in ordered:
        pnl = _f(t.get("pnl"), 0.0)
        cum += pnl
        risk = _f(t.get("riskAmount"), 0.0)
        r = _f(t.get("rMultiple"))
        if r is None and risk and risk > 0:
            r = round(pnl / risk, 3)
        cl = t.get("checklist") or {}
        out.append({
            "date": t.get("date", ""), "entry_time": t.get("entryTime", ""), "exit_time": t.get("exitTime", ""),
            "duration_min": t.get("durationMin") if t.get("durationMin") not in (None, "") else _minutes(t.get("entryTime"), t.get("exitTime")),
            "instrument": t.get("instrument", ""), "direction": t.get("direction", ""), "strategy": t.get("strategy", ""), "bot": t.get("bot", ""),
            "source": t.get("source") or "Manual", "account": t.get("account", ""), "venue": t.get("venue", ""), "mode": t.get("mode", ""),
            "volume": _f(t.get("volume")), "entry_price": _f(t.get("entry")), "exit_price": _f(t.get("exitPrice")),
            "stop": _f(t.get("stop")) or None, "take_profit": _f(t.get("tp")) or None, "risk_usd": risk or None, "pnl_usd": round(pnl, 2), "r_multiple": r,
            "cumulative_pnl_usd": round(cum, 2), "exit_reason": t.get("exitReason", ""), "setup": t.get("setup", ""), "session": t.get("session", ""),
            "regime": t.get("regime", ""), "violations": " | ".join(t.get("violations") or []),
            "playbook": (playbooks.get(t.get("playbookId")) or "") if t.get("playbookId") else "",
            "tags": " | ".join(tag_names.get(x, x) for x in (t.get("tags") or [])),
            "checklist_pct": t.get("compliancePct") if cl else None, "backtest_avg_r": _f(t.get("backtestAvgR")),
            "notes": (t.get("notes") or "").replace("\r", " ").replace("\n", " "), "id": t.get("id", ""),
        })
    return out


def journal_csv(trades: list[dict], settings: dict | None = None) -> str:
    settings = settings or {}
    pbs = {p.get("id"): p.get("title", "") for p in settings.get("playbooks", [])}
    tags = {i.get("id"): i.get("name", "") for g in settings.get("tagGroups", []) for i in g.get("items", [])}
    return to_csv(JOURNAL_FIELDS, journal_rows(trades, pbs, tags))


def journal_stats_csv(trades: list[dict], settings: dict | None = None) -> str:
    rows = journal_rows(trades)
    days: dict = {}
    for r in rows:
        d = str(r.get("date") or "")[:10]
        if d:
            days[d] = days.get(d, 0.0) + (r.get("pnl_usd") or 0.0)
    bal = _f((settings or {}).get("accountBalance"))
    return stats_csv(summary_stats([r["pnl_usd"] for r in rows], days=days, start_balance=bal or None, r_values=[r["r_multiple"] for r in rows]))


# ------------------------------------------------------------------------------------------------ Trading Bot
def bot_rows(trades: list[dict]) -> list[dict]:
    out, cum = [], 0.0
    for i, t in enumerate(trades, 1):
        pnl = _f(t.get("pnl"), 0.0)
        cum += pnl
        out.append({
            "n": t.get("n", i), "day": t.get("day", ""), "entry_time": t.get("entry_time", ""), "exit_time": t.get("exit_time", ""),
            "duration_min": _minutes(t.get("entry_time"), t.get("exit_time")), "bot": t.get("bot", ""), "strategy_leg": t.get("leg", ""),
            "symbol": t.get("symbol", ""), "side": t.get("side", ""), "contracts": t.get("qty"), "contract_type": t.get("kind", ""),
            "entry_price": _f(t.get("entry")), "exit_price": _f(t.get("exit")), "risk_usd": _f(t.get("risk")), "pnl_usd": round(pnl, 2),
            "r_multiple": _f(t.get("r_multiple")), "cumulative_pnl_usd": round(cum, 2), "account_balance_usd": _f(t.get("balance")),
            "size_multiplier": _f(t.get("mult")), "exit_reason": t.get("reason") or t.get("exit_reason") or "",
        })
    return out


def bot_csv(trades: list[dict]) -> str:
    return to_csv(BOT_FIELDS, bot_rows(trades))


def bot_stats_csv(trades: list[dict], start_balance: float | None = None) -> str:
    rows = bot_rows(trades)
    days: dict = {}
    for r in rows:
        d = str(r.get("day") or r.get("exit_time") or "")[:10]
        if d:
            days[d] = days.get(d, 0.0) + (r.get("pnl_usd") or 0.0)
    stats = summary_stats([r["pnl_usd"] for r in rows], days=days, start_balance=start_balance, r_values=[r["r_multiple"] for r in rows])
    by_leg: dict = {}
    for r in rows:
        b = by_leg.setdefault(r.get("strategy_leg") or "", [0, 0.0, 0])
        b[0] += 1
        b[1] += r["pnl_usd"] or 0.0
        b[2] += 1 if (r["pnl_usd"] or 0) > 0 else 0
    for leg, (n, pnl, w) in sorted(by_leg.items()):
        stats += [(f"strategy[{leg}].trades", n), (f"strategy[{leg}].net_pnl_usd", round(pnl, 2)), (f"strategy[{leg}].win_rate_pct", round(100.0 * w / n, 1) if n else "")]
    return stats_csv(stats)


# ------------------------------------------------------------------------------------------------ T58 demo account
def demo_rows(trades: list[dict]) -> list[dict]:
    out, cum = [], 0.0
    for i, t in enumerate(trades, 1):
        pnl = _f(t.get("pnl"), 0.0)
        cum += pnl
        out.append({
            "n": t.get("n", i), "day": t.get("day", ""), "entry_time": t.get("opened_at", ""), "exit_time": t.get("closed_at", ""),
            "duration_min": _minutes(t.get("opened_at"), t.get("closed_at")), "instrument": t.get("root", ""), "side": t.get("side", ""),
            "contracts": t.get("qty"), "entry_price": _f(t.get("entry")), "exit_price": _f(t.get("exit")), "pnl_usd": round(pnl, 2),
            "result": t.get("result", ""), "r_multiple": _f(t.get("r_multiple")), "cumulative_pnl_usd": round(cum, 2), "balance_usd": _f(t.get("balance")),
            "day_pnl_usd": _f(t.get("day_pnl")), "source": t.get("source", ""), "bot": t.get("bot", ""), "strategy": t.get("strategy", ""),
            "why": t.get("why", ""), "attempt": t.get("attempt", ""),
        })
    return out


def demo_csv(trades: list[dict]) -> str:
    return to_csv(DEMO_FIELDS, demo_rows(trades))
