"""Monte Carlo frontier for the three objectives under Lucid-50K-style rules (docs/T58_OBJECTIVES_RESEARCH_2026-11-18.md).

Question: what edge (expectancy per trade in R), trade frequency and risk size make a bot (A) pass an evaluation inside 30 trading days,
(B) bank a payout inside 30 trading days after funding, (NET) compound fastest at a survivable drawdown?  A trade here is an i.i.d. draw from a
two-point distribution (win +b R with probability p, else -1 R) -- the simplest honest model; it is a *requirement* calculator, not a backtest.

    python scripts/run_objectives_research.py            # prints every table used in the paper
"""
from __future__ import annotations

import sys

import numpy as np

SIMS = 20_000
TARGET, LOSS, SOFT, LOCK = 3_000.0, 2_000.0, 1_200.0, 100.0
START = 50_000.0


def _trades(rng, shape, p, b):
    return np.where(rng.random(shape) < p, b, -1.0)


def run_eval(exp_r: float, per_day: float, risk: float, days: int = 30, wr: float = 0.45, sims: int = SIMS, seed: int = 1,
             need_taper: bool = True, day_stop: float = 0.4) -> tuple[float, float, float]:
    """(P(pass within days), P(breach), median days to pass) for a fixed-risk bot with a taper near the target."""
    rng = np.random.default_rng(seed)
    b = (exp_r + 1.0 - wr) / wr if wr > 0 else 1.0                    # payoff that gives the stated expectancy at this win rate
    eq = np.full(sims, START); hi = eq.copy(); floor = np.full(sims, START - LOSS)
    state = np.zeros(sims, int); done_day = np.full(sims, -1)           # 0 live, 1 passed, 2 breached
    maxn = int(max(2, np.ceil(per_day * 3)))
    for d in range(days):
        n = np.minimum(rng.poisson(per_day, sims), maxn)
        day_pnl = np.zeros(sims); start_eq = eq.copy()
        for k in range(maxn):
            live = (state == 0) & (n > k) & (day_pnl > -day_stop * SOFT)
            if not live.any(): break
            cushion = np.maximum(eq - floor, 1.0)
            need = np.maximum(TARGET - (eq - START), 1.0)
            r = np.minimum(risk, 0.5 * cushion)
            if need_taper: r = np.minimum(r, np.maximum(need * 0.6, 40.0))
            pnl = np.where(live, _trades(rng, sims, wr, b) * r, 0.0)
            eq = eq + pnl; day_pnl += pnl
            breach = live & (eq <= floor) ; state[breach] = 2; done_day[breach] = d
            ok = live & (eq - START >= TARGET) & (state == 0); state[ok] = 1; done_day[ok] = d
        hi = np.where(state == 0, np.maximum(hi, eq), hi)
        floor = np.where(state == 0, np.minimum(np.maximum(floor, hi - LOSS), START + LOCK), floor)
    passed = state == 1
    return float(passed.mean()), float((state == 2).mean()), float(np.median(done_day[passed]) + 1) if passed.any() else float("nan")


def run_payout(exp_r: float, per_day: float, risk: float, days: int = 30, wr: float = 0.45, sims: int = SIMS, seed: int = 2,
               win_days: int = 5, win_day_profit: float = 250.0, day_stop: float = 0.3) -> tuple[float, float]:
    """Funded account: P(5 days of >= $250 profit, net-positive cycle, inside `days`) and P(breach)."""
    rng = np.random.default_rng(seed)
    b = (exp_r + 1.0 - wr) / wr
    eq = np.full(sims, START + LOCK + 2_100.0); hi = eq.copy(); floor = np.full(sims, START + LOCK)
    wd = np.zeros(sims, int); cyc = np.zeros(sims); state = np.zeros(sims, int)
    maxn = int(max(2, np.ceil(per_day * 3)))
    for d in range(days):
        n = np.minimum(rng.poisson(per_day, sims), maxn); day_pnl = np.zeros(sims)
        for k in range(maxn):
            live = (state == 0) & (n > k) & (day_pnl > -day_stop * SOFT) & (day_pnl < 1.6 * win_day_profit)
            if not live.any(): break
            r = np.minimum(risk, 0.25 * np.maximum(eq - floor, 1.0))
            pnl = np.where(live, _trades(rng, sims, wr, b) * r, 0.0)
            eq += pnl; day_pnl += pnl; cyc += pnl
            state[live & (eq <= floor)] = 2
        wd += ((day_pnl >= win_day_profit) & (state == 0)).astype(int)
        hi = np.where(state == 0, np.maximum(hi, eq), hi)
        floor = np.where(state == 0, np.minimum(np.maximum(floor, hi - LOSS), START + LOCK), floor)
        state[(state == 0) & (wd >= win_days) & (cyc > 0)] = 1
    return float((state == 1).mean()), float((state == 2).mean())


def run_net(exp_r: float, per_day: float, frac: float, days: int = 250, wr: float = 0.45, sims: int = 4_000, seed: int = 3, streams: int = 1):
    """Compounding at `frac` of equity risked per trade: (median multiple, 5th-percentile multiple, P(-50% drawdown))."""
    rng = np.random.default_rng(seed)
    b = (exp_r + 1.0 - wr) / wr
    eq = np.ones(sims); peak = eq.copy(); dd = np.zeros(sims)
    f = frac / np.sqrt(streams)                                         # streams share the same total risk budget; independent streams diversify
    for _ in range(days):
        n = rng.poisson(per_day * streams, sims); mx = int(n.max())
        for k in range(mx):
            live = n > k
            eq = np.where(live, eq * (1.0 + _trades(rng, sims, wr, b) * f), eq)
            peak = np.maximum(peak, eq); dd = np.maximum(dd, 1 - eq / peak)
    return float(np.median(eq)), float(np.percentile(eq, 5)), float((dd >= 0.5).mean())


def main() -> int:
    print("== A: P(pass inside 30 trading days), Lucid 50K ($3,000 target, $2,000 EOD trailing, 40% day stop). rows: expectancy R; cols: trades/day; risk $500, WR 45%")
    ex = [0.0, 0.05, 0.10, 0.15, 0.20, 0.30]; fr = [0.5, 1, 2, 3, 5]
    print("exp_R  " + "  ".join(f"{f:>5}/d" for f in fr))
    for e in ex:
        print(f"{e:5.2f}  " + "  ".join(f"{run_eval(e, f, 500)[0] * 100:6.1f}" for f in fr))
    print("\n== A: same, risk per trade swept at 1.6 trades/day (shipped Evaluation Passer frequency)   cols: P(pass) / P(breach)")
    for e in (0.05, 0.10, 0.20):
        print(f"exp {e:.2f}R: " + "  ".join(f"${rk}: {run_eval(e, 1.6, rk)[0] * 100:4.1f}/{run_eval(e, 1.6, rk)[1] * 100:4.1f}" for rk in (200, 300, 500, 750, 1000)))
    print("\n== A: days allowed vs P(pass), exp 0.10R, 2 trades/day, $500")
    print("  ".join(f"{d}d: {run_eval(0.10, 2, 500, days=d)[0] * 100:4.1f}" for d in (10, 15, 20, 30, 45, 60)))
    print("\n== B: P(5 winning days >= $250 and a net-positive cycle inside 30 days after funding)  rows exp R; cols trades/day; risk $300")
    for e in ex:
        print(f"{e:5.2f}  " + "  ".join(f"{run_payout(e, f, 300)[0] * 100:6.1f}" for f in fr))
    print("\n== NET: median multiple of the account after 250 sessions / 5th percentile / P(-50% DD); 2 trades/day per stream, WR 45%")
    for e in (0.05, 0.10, 0.20):
        for fq in (0.005, 0.01, 0.02):
            for st in (1, 4):
                m, lo, p = run_net(e, 2, fq, streams=st)
                print(f"exp {e:.2f}R risk {fq * 100:.1f}% streams {st}: median x{m:7.2f}  p5 x{lo:6.2f}  P(DD>=50%) {p * 100:4.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
