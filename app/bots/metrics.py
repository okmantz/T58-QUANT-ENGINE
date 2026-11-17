"""Plain-number performance metrics for a bot, computed from its closed-trade rows (dollars). Pure, no I/O."""
from __future__ import annotations

import math
from collections import defaultdict


def _f(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def compute_metrics(trades: list[dict], start_balance: float = 50_000.0) -> dict:
    n = len(trades)
    pnl = [_f(t.get("pnl")) for t in trades]
    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p < 0]
    gw, gl = sum(wins), -sum(losses)
    eq, peak, maxdd, cur = start_balance, start_balance, 0.0, []
    for p in pnl:
        eq += p
        peak = max(peak, eq)
        maxdd = max(maxdd, peak - eq)
        cur.append(round(eq, 2))
    # streaks
    best_w = best_l = run_w = run_l = 0
    for p in pnl:
        run_w = run_w + 1 if p > 0 else 0
        run_l = run_l + 1 if p < 0 else 0
        best_w, best_l = max(best_w, run_w), max(best_l, run_l)
    by_day: dict = defaultdict(float)
    for t in trades:
        by_day[str(t.get("exit_time") or t.get("closed_at") or "")[:10]] += _f(t.get("pnl"))
    days = {k: v for k, v in by_day.items() if k}
    day_vals = list(days.values())
    mean_d = sum(day_vals) / len(day_vals) if day_vals else 0.0
    sd = math.sqrt(sum((v - mean_d) ** 2 for v in day_vals) / (len(day_vals) - 1)) if len(day_vals) > 1 else 0.0
    by_leg: dict = defaultdict(lambda: {"n": 0, "pnl": 0.0, "wins": 0})
    for t in trades:
        b = by_leg[t.get("leg", "")]
        b["n"] += 1
        b["pnl"] += _f(t.get("pnl"))
        b["wins"] += 1 if _f(t.get("pnl")) > 0 else 0
    legs = [{"leg": k, "trades": v["n"], "pnl": round(v["pnl"], 2), "win_rate": round(100.0 * v["wins"] / v["n"], 1) if v["n"] else None}
            for k, v in by_leg.items()]
    rs = [_f(t.get("r_multiple")) for t in trades if t.get("r_multiple") is not None]
    return {
        "trades": n, "net_pnl": round(sum(pnl), 2), "win_rate": round(100.0 * len(wins) / n, 1) if n else None,
        "profit_factor": round(gw / gl, 2) if gl > 0 else (None if gw == 0 else 999.0),
        "avg_win": round(gw / len(wins), 2) if wins else None, "avg_loss": round(-gl / len(losses), 2) if losses else None,
        "expectancy": round(sum(pnl) / n, 2) if n else None, "avg_r": round(sum(rs) / len(rs), 2) if rs else None,
        "best_trade": round(max(pnl), 2) if pnl else None, "worst_trade": round(min(pnl), 2) if pnl else None,
        "max_drawdown": round(maxdd, 2), "best_day": round(max(day_vals), 2) if day_vals else None,
        "worst_day": round(min(day_vals), 2) if day_vals else None, "trading_days": len(days),
        "green_days": sum(1 for v in day_vals if v > 0), "red_days": sum(1 for v in day_vals if v < 0),
        "daily_sharpe": round(mean_d / sd * math.sqrt(252), 2) if sd > 0 else None,
        "max_win_streak": best_w, "max_loss_streak": best_l, "equity": cur[-400:], "by_leg": legs,
        "daily": [{"day": k, "pnl": round(v, 2)} for k, v in sorted(days.items())][-60:],
    }
