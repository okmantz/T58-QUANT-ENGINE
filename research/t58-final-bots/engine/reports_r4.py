"""Round 4 reports: final/T58_FINAL_BOTS_PERFORMANCE_2026-11-24.md and final/T58_FINAL_BOTS_COMPARISON_2026-11-24.md (= COMPARISON.md)
from research/comparison_long_r4.csv, comparison_r4.md, shortfalls_r4.csv, a_bar_r4.csv, mc_r4.csv. Numbers only; no rescoring.
Round-3 versions kept as *_r3.md. Usage: python3 reports_r4.py"""
import pandas as pd, compare as C
R, F = C.R, "research/t58_final_bots/final"
d = pd.read_csv(f"{R}/comparison_long_r4.csv"); lock = d[d.firm == "lock_on_payout"]; d = d[d.firm == "current"]
mc = pd.read_csv(f"{R}/mc_r4.csv"); sf = pd.read_csv(f"{R}/shortfalls_r4.csv"); ab = pd.read_csv(f"{R}/a_bar_r4.csv")
fmt = C.fmt; SPL = ("research", "validation", "holdout")
def v(bot, sp, m, cost="stress"):
    x = d[(d.bot == bot) & (d.split == sp) & (d.cost == cost)]; return fmt(m, x[m].iloc[0])
def tri(bot, m): return " / ".join(v(bot, sp, m) for sp in SPL)
def perf(bot, ms):
    out = ["| Metric | " + " | ".join(f"{sp.capitalize()} {c}" for sp in SPL for c in ("base", "stress")) + " |", "|---|" + "---|" * 6]
    for m in ms:
        out.append("| " + " | ".join([C.NAMES[m]] + [v(bot, sp, m, c) for sp in SPL for c in ("base", "stress")]) + " |")
    return "\n".join(out)
def mct(bots):
    out = ["| Bot | Pool | Resampler | P(pass in 30d) | Median days to pass | Eval bust | P(first payout in 30d) | Median days to payout | 90-day EV (5th to 95th pct) |",
           "|---|---|---|---|---|---|---|---|---|"]
    for _, r in mc[mc.bot.isin(bots)].iterrows():
        out.append(f"| {r.bot} | {r.pool} | {r.method} | {100*r.p_pass:.1f}% | {r.med_days_pass:.0f} | {100*r.bust:.1f}% | {100*r.p_payout:.1f}% | "
                   f"{r.med_days_payout:.0f} | {r.ev90:,.0f} ({r.ev90_p5:,.0f} to {r.ev90_p95:,.0f}) |")
    return "\n".join(out)
def abt():
    out = ["| Bot | Cost | Split | Primary tests missed | Limits broken | Meets the bar |", "|---|---|---|---|---|---|"]
    for _, r in ab.iterrows():
        out.append(f"| {r.bot} | {r.cost} | {r.split} | {r.primary_fails if isinstance(r.primary_fails, str) else 'none'} | "
                   f"{r.limit_fails if isinstance(r.limit_fails, str) else 'none'} | {'yes' if r.meets_bar else 'no'} |")
    return "\n".join(out)
def ns(bot, cost="stress"): return sf[(sf.bot == bot) & (sf.cost == cost)]
HEAD = """Research code only. Nothing in this work placed, changed or cancelled an order, signed in to a prop firm, broker or exchange, or created
an alert. Every number comes from one engine (research/t58_final_bots/engine): the repo's own strategy files for the existing legs,
next-bar-open fills, stops filled at the stop price plus slippage, Lucid 50K rules simulated by firm.py. Costs: base = $3.50 a side on
ES/NQ ($4.60 GC; micros $1.00 / $1.60) plus 1 tick a side; stress = 1.5x both (the cost every pick was chosen on).

**What was and was not touched (round 4).**
- Research 2020-01-01 .. 2023-12-31: used to fit every filter, weight and sizing setting.
- Validation 2024-01-01 .. 2026-11-20: used to confirm. It is NOT untouched: Sep 2025 .. Feb 2026 was the round-1/2 holdout and
  Mar 2 .. Nov 20 2026 was the round-3 holdout, each read before; in round 4 they are ordinary validation data.
- Holdout 2016-11-24 .. 2019-12-31 (Owen's new pack): untouched. Sealed by hash before any price was read; only row counts, session
  counts, roll checks and the splice offset were computed on it before the picks were frozen (research/FROZEN_PICKS_R4.sha256), then
  read exactly once per finalist. The pack's 2020 part overlaps research and was not used; MES and MNQ start in 2019-05 and were not used.
- Pre-2020 bars get the same session, cost and roll handling: the repo engine runs on the combined file and prices are shifted onto
  the repo's back-adjusted basis (offset spread 0). No roll splice was detected before 2020; the detector is partial, so a small
  unadjusted roll gap cannot be ruled out.
Pass and payout metrics average rolling account starts in each split; trade metrics cover the whole split."""
if __name__ == "__main__":
    bA, bB = ns("BOT-B-R4"), ns("BOT-B-R3")
    p = [f"# T58 final bots: performance report, round 4 (2026-11-24)\n\n{HEAD}\n", "## Bottom line\n",
         "- **BOT-A (pass LucidPro 50K) meets your new bar on 2020-2026 at stress cost, and nearly meets it on the untouched 2016-2019 data.** "
         f"P(pass in 30 days) {tri('BOT-A-R4','p_pass')} vs {tri('baseline_A','p_pass')} for your current BOT-A (research / validation / "
         f"2016-2019); median days to pass {tri('BOT-A-R4','med_days_pass')} vs {tri('baseline_A','med_days_pass')}; eval bust "
         f"{tri('BOT-A-R4','bust')} vs {tri('baseline_A','bust')}; 90-day EV {tri('BOT-A-R4','ev')} vs {tri('baseline_A','ev')}. "
         "On 2016-2019 it misses P(pass) by 0.1 point and breaks one limit (funded first payout).",
         "- **Monte Carlo agrees on 2020-2026 and not on 2016-2019.** On 70-session resamples BOT-A round 4 passes 30-33% vs 19-23% for "
         "your current BOT-A (FULL and OOS pools), but on 2016-2019 resamples it passes 15.5-19.4% vs 17.2-21.4%, with fewer busts. "
         "Round-3 A is a little ahead of round-4 A in every Monte Carlo pool; round 4 is the pick because it keeps the limits.",
         "- **The sizing you suggested did not raise the pass rate.** It kept the round-3 pass rate within about 2 points and brought "
         "every limit back inside tolerance; round-3 A broke two limits on 2020-2026 and five on 2016-2019.",
         f"- **BOT-B (Flex payouts) beats or ties your current BOT-B on {54 - len(bA)} of 54 cells at stress cost** (round-3 B: "
         f"{54 - len(bB)}). Misses: trades a month in research and validation; 90-day EV, payouts in 90 days and P(2+ payouts) on 2016-2019.",
         "- **The regime filter found little.** Of the causal filters tested, only the 10-signal equity filter on the ES ORB15 leg cleared "
         "the pre-registered research rule. None fixed the NQ legs that lost in Mar-Nov 2026, so the Mar-Nov problem is not solved; it is disclosed.",
         "- 2016-2019 was a weak stretch for every bot, current bots included (current A PF 1.06, current B PF 0.85 at stress).\n",
         "## BOT-A round 4 on LucidPro 50K\n", perf("BOT-A-R4", C.MA),
         "\nRepo-format legs (strategies/python/*_t58.py, causal bar-count filter; what the zip ships):\n", perf("BOT-A-R4-port", C.MA),
         "\n## BOT-B round 4 on LucidFlex 50K\n", perf("BOT-B-R4", C.MB), "\nRepo-format legs:\n", perf("BOT-B-R4-port", C.MB),
         "\n## Monte Carlo (10,000 paths per row, stress cost)\n",
         "Each path is 70 sessions resampled from the bot's own booked trade days (whole days kept together). FULL = 2020-01-01 .. "
         "2026-11-20, OOS = 2024-01-01 .. 2026-11-20, H3 = 2016-11-24 .. 2019-12-31 (run after its single read; it chooses nothing). "
         "'block' keeps 10-session runs; 'reshuffle' draws days independently. BOT-B's 90-day EV pays for an evaluation it rarely passes, "
         "so it is negative by design.\n",
         mct(["baseline_A", "BOT-A-R3", "BOT-A-R4", "BOT-A-R4-port", "baseline_B", "BOT-B-R3", "BOT-B-R4", "BOT-B-R4-port"]),
         "\n## Disclosures\n",
         "- No single leg passed the Deflated Sharpe gate (research/gate_ladder_log.md). Acceptance rests on research-to-validation "
         "replication at stress cost and the 2016-2019 holdout.",
         "- Validation includes two windows read before as holdouts (see above).",
         "- In 2016-2019 index prices were much lower, so stops in points cost fewer dollars and many more signals fit a fixed dollar "
         "budget (BOT-B traded 43 a month there vs 11 in 2020-2023). The holdout tests a different sizing regime as well as a different market.",
         "- The research leg factory's whole-day bar-count filter is a mild lookahead; the repo-format legs are causal and score lower "
         "(rows above).",
         "- The round-4 Pine edits were not compiled on TradingView: the daily tool quota was used up. Compile final/pine/T58_BOT.pine once before use.",
         "- The Pine port leaves out IR_NQ and the cross-instrument cap; the Flex lock-on-payout rule is reported as a sensitivity only.",
         ]
    open(f"{F}/T58_FINAL_BOTS_PERFORMANCE_2026-11-24.md", "w").write("\n".join(p) + "\n")
    rows = ["| Bot | Plan | Research | Validation | 2016-2019 holdout | Total (stress) | Total (base) |", "|---|---|---|---|---|---|---|"]
    for bot, base, plan, ms in __import__("compare_r4").SETS:
        s, b = ns(bot), ns(bot, "base")
        rows.append(f"| {bot} | {plan} | " + " | ".join(str((s.split == sp).sum()) for sp in SPL) + f" | {len(s)} of {3*len(ms)} | {len(b)} of {3*len(ms)} |")
    c = [f"# T58 final bots: comparison report, round 4 (2026-11-24)\n\n{HEAD}\n",
         "Baselines are your current bots in the repo (PRESET_REV 5): baseline_A on LucidPro 50K, baseline_B on LucidFlex 50K.\n",
         "## BOT-A against the round-4 bar\n",
         "Primary (beat or tie the current BOT-A): P(pass), median days to pass (and under 30), eval bust, 90-day EV after fees and resets. "
         "Limits: no other metric more than 10% worse (25% for max drawdown and worst day), worst day never below -$1,200. "
         "Stress cost decides (research/PREREG_R4.md).\n", abt(),
         "\n## Every-metric count (cells worse than the baseline; BOT-B's bar, shown for A too)\n", "\n".join(rows),
         "\nR3 = round-3 pick rescored on the round-4 splits. -port = R4 pick on the repo-format leg files.\n",
         "## Why these picks\n",
         "- BOT-A-R4: one of three of 1,476 A variants that meet the whole bar on both dev splits at stress cost; they differ only in the "
         "funded day cap and the pick is the middle one. Round-3 A passes a little more often in research but breaks two limits.",
         "- BOT-B-R4: no B variant of 144 clears the every-metric bar. The pick fails only trades a month (as round 3) with higher payouts "
         "in both dev splits. Five variants fail one cell fewer but pay about half as much; rejected, reason logged before the holdout read.",
         "- Both picks were frozen and hashed before the 2016-2019 read (research/FROZEN_PICKS_R4.md); nothing was changed after it.\n",
         "## Full tables\n", open(f"{R}/comparison_r4.md").read(),
         "\n## Monte Carlo (10,000 paths per row, stress cost)\n", mct(sorted(mc.bot.unique())),
         "\n## What would invalidate this\n",
         "- 60 live sessions with PF below 1.0 at real fills (2016-2019 and Mar-Nov 2026 both showed such stretches for every bot).",
         "- Real slippage above 1.5 ticks a side.",
         "- A change to Lucid's rules: Pro $3,000 target with a $2,000 EOD trailing floor locking at $50,100; Flex five $150 days, 50% split, "
         "$2,000 cap. Flex's lock-on-payout floor is shown above as a sensitivity.",
         "- NQ volatility or price level far outside the tested range (stops in points change how many signals fit the dollar budget).",
         "- Both untouched windows are now spent; any further tuning needs new data to test on.",
         ]
    txt = "\n".join(c) + "\n"
    open(f"{F}/T58_FINAL_BOTS_COMPARISON_2026-11-24.md", "w").write(txt); open(f"{F}/COMPARISON.md", "w").write(txt)
    print("ok")
