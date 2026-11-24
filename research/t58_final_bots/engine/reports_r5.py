"""Write final/T58_FINAL_BOTS_ROUND5_2026-11-24.md from research/final_dev_r5.csv, plateau_r5_B.csv, mc_r5.csv, bot_trials_r5.csv.
Usage: T58_R5=1 python3 reports_r5.py"""
import sys, json
sys.path.insert(0, "research/t58_final_bots/engine")
import r5, search as S
import pandas as pd, numpy as np
R = r5.OUT; FIN = "research/t58_final_bots/final"
def md(df, fmt="{:.3f}"):
    cols = list(df.columns); idx = df.index.names if isinstance(df.index, pd.MultiIndex) else [df.index.name or ""]
    h = "| " + " | ".join(list(idx) + cols) + " |\n|" + "---|" * (len(idx) + len(cols)) + "\n"
    for i, r in df.iterrows():
        ii = list(i) if isinstance(i, tuple) else [i]
        h += "| " + " | ".join([str(v) for v in ii] + ["" if pd.isna(v) else (fmt.format(v) if isinstance(v, (float, np.floating)) else str(v)) for v in r]) + " |\n"
    return h
d = pd.read_csv(f"{R}/final_dev_r5.csv"); pl = pd.read_csv(f"{R}/plateau_r5_B.csv"); mc = pd.read_csv(f"{R}/mc_r5.csv")
tr = pd.read_csv(f"{R}/bot_trials_r5.csv")
COLS = ["p_pass", "med_days_pass", "bust", "ev", "p_payout", "med_days_payout", "f90_paid", "f90_payouts", "pf", "sharpe", "max_dd", "worst_day", "trades_pm"]
NAME = {"h3": "2016-11-24..2019-12-31", "research": "2020-2023", "validation": "2024-01-01..2026-11-20"}
cells = []
for c in ("stress", "base"):
    for sp in r5.DEV:
        g = d[(d.cost == c) & (d.split == sp)].set_index("bot")
        pa, la = r5.a_bar(g.loc["BOT-A-R4"].to_dict(), g.loc["baseline_A"].to_dict())
        b4 = S.beats(g.loc["BOT-B-R4"].to_dict(), g.loc["baseline_B"].to_dict(), sustained=True)
        b5 = S.beats(g.loc["BOT-B-R5"].to_dict(), g.loc["baseline_B"].to_dict(), sustained=True)
        cells.append(dict(cost=c, period=NAME[sp], A_primary_fails=", ".join(pa) or "none", A_limit_fails=", ".join(la) or "none",
                          B_round4_shortfalls=", ".join(b4) or "none", B_alt_shortfalls=", ".join(b5) or "none"))
cells = pd.DataFrame(cells).set_index(["cost", "period"])
nplat = int((pl.nbad <= 3).sum())
out = f"""# T58 final bots, round 5 (2026-11-24)

**Bottom line.** Round 5 found nothing that should replace the round-4 bots. Ship round-4 BOT-A and round-4 BOT-B unchanged.

**Every window here was already read.** Round 5 searched and scored on 2016-11-24 .. 2026-11-20. No unread data is left:
- 2016-11-24 .. 2019-12-31 (H3) was round 4's holdout, read once on 2026-11-24 at 18:56 UTC. In round 5 it is dev data.
- 2020-2023 (research) has been the tuning window since round 1.
- 2024-01-01 .. 2026-11-20 (validation) includes the round-2 and round-3 holdout windows, read in those rounds.

So every number below is in-sample. Owen confirmed no pre-2016 data is available, so there is no holdout. The rotation, plateau and
Monte Carlo checks stand in for one, and none of them is a holdout.

Cost model, lookahead protection, firm rules and the bars are unchanged from round 4 (research/PREREG_R4.md). Each bar had to hold in
all three periods (research/PREREG_R5.md, written before any round-5 score).

## What was searched
{len(tr):,} configs, stride 2, at stress cost (research/bot_trials_r5.csv):
- A1: 1,500 bot A leg mixes (each leg 0/0.5/1, plus one optional new leg, regime rule on or off).
- A2: 480 funded-side settings on the A1 top 10.
- B1: 1,500 bot B leg mixes.
- B2: 240 funded-side settings on the B1 top 10.

Trials across all rounds (bot-level configs scored):
- R1: 3,912
- R2: 416
- R3: 1,776
- R4: 1,620
- R5: 3,720, plus 29 plateau neighbours

That is 11,473 in total, plus 1,825 single-strategy screens in round 1. With that many tries on the same ten years, a small edge over
round 4 is expected by chance alone.

## BOT-A
- No config clears every BOT-A bar in all three periods.
- The best one ties round-4 A exactly.
- Raising the 2016-2019 payout rate (round-4 A's one standing miss) broke 12 to 14 other limits.

Round-4 A stays. Stride 1 confirms the round-4 picture:
- 2020-2026: round-4 A clears the bar at stress cost.
- 2016-2019: P(pass) is .149 vs .150 (within noise, but a fail by the letter), and the first-30-day payout rate is .017 vs .045.

## BOT-B
The best B is search tag B2-26, a slimmer round-4 B. It drops Context Drive Long ES, ORB15 compression ES (and with it the regime
rule), ORB30 with trend NQ and Gap with trend GC. It halves Ind Rule NQ, VWAP pullback NQ and Prior-day break GC, adds the 10:00
time-of-day NQ leg at 0.5, and removes the $200 funded day cap. Every other setting is the same.

At stress cost it has 2 shortfall cells against the current B across the three periods, vs 5 for round-4 B (8 vs 13 at base cost).
By the pre-registered count it wins.

I am not shipping it. It is kept as BOT_B_ALT in code/picks_r5.py and final/BOT-B/params_r5_alt.json. Reasons:
- **Rotation check fails.** A B picked on any two periods misses 1 to 3 cells on the third, so the gains don't carry across periods.
- **Plateau check fails.** Only {nplat} of its 29 one-step neighbours stay within one cell of it (research/plateau_r5_B.csv). It sits on
  a narrow peak.
- **It pays out less often in recent years.** Its first-30-day payout rate is .485 vs .565 on 2020-2023 and .373 vs .449 on
  2024-2026. That is the number a payout bot exists for. Most of its gain is on 2016-2019, the one window round 5 tuned on that
  round 4 had not.
- **Monte Carlo puts it about level.** On the full 2016-2026 pool, round-5 alt and round-4 B pay out about equally often (.40-.43),
  and the alt's 90-day EV is $8 to $20 less negative.

This decision goes beyond the pre-registered rule. It was made and frozen (research/FROZEN_PICKS_R5.md) after the confirm and plateau
checks and before the Monte Carlo was read. If you'd rather follow the count, swap in BOT_B_ALT. Every number for it is below.

## Shortfall cells by period (stride 1)
{md(cells)}
## Metrics (stride 1)
"""
for c in ("stress", "base"):
    out += f"\n### {c} cost\n" + md(d[d.cost == c].assign(period=d.split.map(NAME)).set_index(["period", "bot"])[COLS])
out += "\n## Plateau, BOT_B_ALT one-step neighbours (stride 2, stress)\n" + md(pl.set_index("step")[["nbad"]], "{}")
out += "\n## Monte Carlo (10,000 70-session paths per row, stress cost; FULL = 2016-11-24..2026-11-20, OOS = 2024-01-01..2026-11-20, both already read)\n"
out += md(mc.set_index(["bot", "pool", "method"])[["p_pass", "med_days_pass", "bust", "p_payout", "med_days_payout", "ev90"]])
out += """
## Files
- code/r5.py, r5_search.py, r5_pick.py, r5_confirm.py, reports_r5.py, picks_r5.py; mc.py gains an r5 mode; data.py gains T58_R5
  (pre-edit copies in research/round1_code/).
- research/PREREG_R5.md, FROZEN_PICKS_R5.md (+ .sha256), bot_trials_r5.csv, final_dev_r5.csv, plateau_r5_B.csv, mc_r5.csv.
"""
open(f"{FIN}/T58_FINAL_BOTS_ROUND5_2026-11-24.md", "w").write(out); print(len(out))
