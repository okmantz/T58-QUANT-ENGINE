"""Round 4 comparison: baselines (repo PRESET_REV 5) vs the round-3 and round-4 picks on research 2020-2023, validation
2024-01-01 .. 2026-11-20 (Mar-Nov 2026 included, read once in round 3) and the sealed 2016-11-24 .. 2019-12-31 holdout (read once),
all from the same scoring code. BOT-A is judged on the round-4 bar (r4.a_bar: primary tests + limits); BOT-B on every metric.
Inputs: research/final_dev_r4.csv, final_hold_r4.csv.  Usage: T58_R4=1 python3 compare_r4.py
-> research/comparison_r4.md, comparison_long_r4.csv, shortfalls_r4.csv, a_bar_r4.csv"""
import os, sys
os.environ["T58_R4"] = "1"; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
import compare as C, r4
R = C.R
d = pd.concat([pd.read_csv(f"{R}/final_dev_r4.csv"), pd.read_csv(f"{R}/final_hold_r4.csv")], ignore_index=True)
d.to_csv(f"{R}/comparison_long_r4.csv", index=False)
lock = d[d.firm == "lock_on_payout"].copy(); d = d[d.firm == "current"].copy(); C.d = d
SETS = [("BOT-A-R4", "baseline_A", "pro50", C.MA), ("BOT-A-R4-port", "baseline_A", "pro50", C.MA), ("BOT-A-R3", "baseline_A", "pro50", C.MA),
        ("BOT-B-R4", "baseline_B", "flex50", C.MB), ("BOT-B-R4-port", "baseline_B", "flex50", C.MB), ("BOT-B-R3", "baseline_B", "flex50", C.MB)]
SPLITS = ("research", "validation", "holdout")
def abar_rows():
    out = []
    for bot in ("BOT-A-R4", "BOT-A-R4-port", "BOT-A-R3"):
        for cost in ("stress", "base"):
            for sp in SPLITS:
                g = lambda w: d[(d.bot == w) & (d.split == sp) & (d.cost == cost) & (d.plan == "pro50")]
                if g(bot).empty: continue
                pf, lf = r4.a_bar(g(bot).iloc[0], g("baseline_A").iloc[0])
                out.append(dict(bot=bot, cost=cost, split=sp, primary_fails=";".join(pf), limit_fails=";".join(lf),
                                meets_bar=not pf and not lf))
    return pd.DataFrame(out)
if __name__ == "__main__":
    md, sf = [], []
    for bot, base, plan, ms in SETS:
        for cost in ("stress", "base"):
            t, f = C.table(base, bot, plan, cost, ms)
            md.append(f"### {bot} vs {base} ({plan}, {cost} cost)\n\n{t}\n\nCells worse than the baseline ({len(f)}): " +
                      ("; ".join(f"{s} {C.NAMES[m]} {b} -> {a}" for s, m, b, a in f) or "none"))
            sf += [dict(bot=bot, baseline=base, plan=plan, cost=cost, split=s, metric=m, baseline_value=b, bot_value=a) for s, m, b, a in f]
    lk = ["| Bot | Split | P(first payout in 30d) | $ paid in 90 funded days | P(2+ payouts in 90d) | 90d funded bust |", "|---|---|---|---|---|---|"]
    for _, r in lock.sort_values(["split", "bot"]).iterrows():
        lk.append(f"| {r.bot} | {r.split} | {100*r.p_payout:.1f}% | {r.f90_paid:,.0f} | {100*r.f90_p2:.1f}% | {100*r.f90_bust:.1f}% |")
    md.append("### Flex lock-on-payout sensitivity (stress cost, the floor locks at the start balance after the first payout)\n\n" + "\n".join(lk))
    open(f"{R}/comparison_r4.md", "w").write("\n\n".join(md) + "\n")
    s = pd.DataFrame(sf); s.to_csv(f"{R}/shortfalls_r4.csv", index=False)
    a = abar_rows(); a.to_csv(f"{R}/a_bar_r4.csv", index=False)
    print(s.groupby(["bot", "cost", "split"]).size().unstack(fill_value=0).to_string()); print(a.to_string())
