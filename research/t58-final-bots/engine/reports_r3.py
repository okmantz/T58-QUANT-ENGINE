"""Write final/T58_FINAL_BOTS_PERFORMANCE_2026-11-24.md and final/T58_FINAL_BOTS_COMPARISON_2026-11-24.md (also final/COMPARISON.md)
from research/comparison_long_r3.csv, comparison_r3.md, shortfalls_r3.csv, mc_r3.csv, mc.csv/mc_r2.csv. Numbers only; no rescoring."""
import pandas as pd, compare as C
R, F = C.R, "research/t58_final_bots/final"
d = pd.read_csv(f"{R}/comparison_long_r3.csv"); mc = pd.read_csv(f"{R}/mc_r3.csv"); sf = pd.read_csv(f"{R}/shortfalls_r3.csv")
fmt = C.fmt
def perf(bot, plan, ms):
    out = ["| Metric | " + " | ".join(f"{sp.capitalize()} {c}" for sp in ("research", "validation", "holdout") for c in ("base", "stress")) + " |",
           "|---|" + "---|" * 6]
    for m in ms:
        row = [C.NAMES[m]]
        for sp in ("research", "validation", "holdout"):
            for c in ("base", "stress"):
                x = d[(d.bot == bot) & (d.plan == plan) & (d.split == sp) & (d.cost == c)]
                row.append(fmt(m, x[m].iloc[0]) if len(x) else "")
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)
def mct(bots):
    out = ["| Bot | Pool | Resampler | P(pass in 30d) | Median days to pass | Eval bust | P(first payout in 30d) | Median days to payout | 90-day EV (5th to 95th pct) |",
           "|---|---|---|---|---|---|---|---|---|"]
    for _, r in mc[mc.bot.isin(bots)].iterrows():
        out.append(f"| {r.bot} | {r.pool} | {r.method} | {100*r.p_pass:.1f}% | {r.med_days_pass:.0f} | {100*r.bust:.1f}% | {100*r.p_payout:.1f}% | "
                   f"{r.med_days_payout:.0f} | {r.ev90:,.0f} ({r.ev90_p5:,.0f} to {r.ev90_p95:,.0f}) |")
    return "\n".join(out)
def nshort(bot, cost):
    return sf[(sf.bot == bot) & (sf.cost == cost)]
def cells(ms): return 3 * len(ms)
HEAD = """Research code only. Nothing in this work placed, changed or cancelled an order, signed in to a prop firm, broker or exchange, or created
an alert. Every number comes from one engine (research/t58_final_bots/engine): the repo's own strategy files for the existing legs,
next-bar-open fills, stops filled at the stop price plus slippage, Lucid 50K rules simulated by firm.py. Costs: base = $3.50 a side on
ES/NQ ($4.60 GC; micros $1.00 / $1.60) plus 1 tick a side; stress = 1.5x both (the cost every pick was chosen on).
Splits: research 2020-01-01 .. 2023-12-31, validation 2024-01-01 .. 2026-03-01, holdout 2026-03-02 .. 2026-11-20 (Owen's Mar-Nov 2026
files, sealed until the picks were frozen and read exactly once). Pass and payout metrics are averaged over rolling account starts
in the split; trade metrics (PF, expectancy, Sharpe, drawdown, worst day, trades a month) cover the whole split."""
if __name__ == "__main__":
    a_s, b_s = nshort("BOT-A-R3", "stress"), nshort("BOT-B-R3", "stress")
    p = [f"# T58 final bots: performance report (2026-11-24)\n\n{HEAD}\n",
         "## Bottom line\n",
         f"- **BOT-B (payouts on LucidFlex 50K) is the better bot and the closer miss.** At stress cost it beats or ties the current BOT-B on "
         f"{cells(C.MB) - len(b_s)} of {cells(C.MB)} cells. On the fresh holdout it reached a first payout 24.0% of the time vs 9.7%, paid "
         "$742 vs $161 over 90 funded days, and made 2+ payouts 41.5% of the time vs 0%. It falls short on max drawdown and worst day on the "
         "holdout and on trade count in research.",
         f"- **BOT-A (passing LucidPro 50K) passes more often and faster, and busts less, in every split**, holdout included (17.9% vs 12.6% "
         f"pass, 7.7% vs 12.6% bust). It beats or ties the current BOT-A on {cells(C.MA) - len(a_s)} of {cells(C.MA)} cells at stress cost; "
         "the misses are trade-quality metrics (PF, expectancy, Sharpe, Sortino) and drawdown, mostly on the holdout.",
         "- **Neither meets the brief of beating the current bots on every metric.** The search is exhausted under the rules: with the fresh "
         "holdout read, any more tuning would have no untouched test left.",
         "- Mar-Nov 2026 was a losing stretch for every bot, baseline included (baseline A PF 0.97, baseline B PF 0.76 at stress).\n",
         "## BOT-A (round 3) on LucidPro 50K\n", perf("BOT-A-R3", "pro50", C.MA),
         "\nRepo-format legs (strategies/python/*_t58.py, causal bar-count filter):\n", perf("BOT-A-R3-port", "pro50", C.MA),
         "\n## BOT-B (round 3) on LucidFlex 50K\n", perf("BOT-B-R3", "flex50", C.MB),
         "\nRepo-format legs:\n", perf("BOT-B-R3-port", "flex50", C.MB),
         "\n## Monte Carlo (10,000 paths per row, stress cost)\n",
         "Each path is 70 sessions resampled from the bot's own booked trade days (whole days kept together). FULL pool = 2020-01-01 .. "
         "2026-03-01, OOS pool = 2024-01-01 .. 2026-03-01. The pools stop before the holdout so it is not reused. 'block' keeps 10-session runs "
         "(volatility clustering); 'reshuffle' draws days independently. The 90-day EV pays for an evaluation and runs the bot through it, "
         "so it is negative for BOT-B by design (B is a funded-account bot).\n",
         mct(["baseline_A", "BOT-A-R3", "BOT-A-R3-port", "baseline_B", "BOT-B-R3", "BOT-B-R3-port"]),
         "\n## Disclosures\n",
         "- No single leg passed the Deflated Sharpe gate (research/gate_ladder_log.md). Acceptance rests on research-to-validation "
         "replication at stress cost, and the holdout.",
         "- The research leg factory skipped days with fewer than 80% of RTH bars over the whole day, which a live bot cannot know at "
         "entry (a mild lookahead). The repo-format legs check only the bars up to the signal; their rows are shown above, and they are "
         "what the zip ships.",
         "- The Sep 2025 .. Feb 2026 window was read as a holdout in rounds 1 and 2 before joining validation in round 3.",
         "- The Python ports of IR_NQ, CDL and Open Drive are the repo's own files. The Pine port leaves out IR_NQ and the cross-instrument cap.",
         ]
    open(f"{F}/T58_FINAL_BOTS_PERFORMANCE_2026-11-24.md", "w").write("\n".join(p) + "\n")
    rows = ["| Bot | Plan | Research | Validation | Holdout | Total short (stress) | Total short (base) |", "|---|---|---|---|---|---|---|"]
    for bot, base, plan, ms in __import__("compare_r3").SETS:
        s = nshort(bot, "stress"); b = nshort(bot, "base")
        rows.append(f"| {bot} | {plan} | " + " | ".join(str((s.split == sp).sum()) for sp in ("research", "validation", "holdout")) +
                    f" | {len(s)} of {cells(ms)} | {len(b)} of {cells(ms)} |")
    c = [f"# T58 final bots: comparison report (2026-11-24)\n\n{HEAD}\n",
         "Baselines are the current bots in the repo (PRESET_REV 5): baseline_A on LucidPro 50K, baseline_B on LucidFlex 50K. "
         "A pick passes only if it beats or ties its baseline on every metric in every split. ✗ marks a shortfall.\n",
         "## Shortfall count per pick (cells where the pick is worse than its baseline)\n", "\n".join(rows),
         "\nR1 = round 1, R2 = round 2, R3 = round 3 (the final picks). -port = R3 pick on the repo-format leg files.\n",
         "## Why these picks\n",
         "- BOT-A-R3 has the fewest stress-cost shortfalls of 784 A variants (research/bot_trials_r3.csv) and keeps A's own objective, "
         "P(pass), well above baseline. Round-1 A had 18 stress shortfalls over the three splits; R3 has 11.",
         "- BOT-B-R3 was the B variant clean on both validation cells at full detail, with the fewest shortfalls overall (3 of 54 at stress).",
         "- Honest caveat: on the Mar-Nov 2026 holdout, round-2 B did better than round-3 B on its own objective too (first payout 26.3% vs "
         "24.0%, $858 vs $742 paid in 90 funded days, PF 1.28 vs 0.99, max drawdown $1,531 vs $2,954). It has more shortfalls overall "
         "(5 of 54: validation trade count and holdout days to payout, drawdown and worst day). Switching to it now would be choosing on the "
         "holdout, so R3 stays the pick; R2 (BOT-B/params_r2.json) is the lower-drawdown alternative if drawdown matters more to you.",
         "- Top 5 per objective: research/top5_per_objective_r3.csv.\n",
         "## Full tables\n", open(f"{R}/comparison_r3.md").read(),
         "\n## Monte Carlo (10,000 paths per row, stress cost, pools stop at 2026-03-01)\n", mct(sorted(mc.bot.unique())),
         "\n## What would invalidate this\n",
         "- 60 live sessions with PF below 1.0 at real fills (the holdout already showed one such stretch for every bot).",
         "- Real slippage above 1.5 ticks a side.",
         "- A change to Lucid's rules: Pro $3,000 target with a $2,000 EOD trailing floor locking at $50,100; Flex five $150 days, 50% split, $2,000 cap.",
         "- NQ volatility far outside 2020-2026 (stops in points get wider, fewer trades can be sized at one micro).",
         ]
    txt = "\n".join(c) + "\n"
    open(f"{F}/T58_FINAL_BOTS_COMPARISON_2026-11-24.md", "w").write(txt); open(f"{F}/COMPARISON.md", "w").write(txt)
    print("ok")
