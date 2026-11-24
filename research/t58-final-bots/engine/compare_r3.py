"""Round 3 comparison: baseline (repo PRESET_REV 5) vs every pick, on research, extended validation (2024-01 .. 2026-03-01) and the
fresh Mar-Nov 2026 holdout, all from the same scoring code (score.full + score.sustained_block).
Inputs: research/baseline_dev_r3.csv, baseline_dev_flex_r3.csv, final_dev_r3.csv, final_devres_r3.csv, port_bots_check.csv,
final_hold_r3.csv.  Usage: python3 compare_r3.py -> research/comparison_r3.md, comparison_long_r3.csv, shortfalls_r3.csv"""
import pandas as pd
import compare as C
R = C.R
pt = pd.read_csv(f"{R}/port_bots_check.csv")
pt = pt[pt.legs_from == "repo_port"].drop(columns="legs_from"); pt["bot"] = pt["bot"] + "-R3-port"
d = pd.concat([pd.read_csv(f"{R}/{f}.csv") for f in ("baseline_dev_r3", "baseline_dev_flex_r3", "final_dev_r3", "final_devres_r3",
                                                       "final_hold_r3")] + [pt], ignore_index=True)
# research rows for the earlier picks come from rounds 1/2 (research split is unchanged in round 3)
old = pd.read_csv(f"{R}/comparison_long.csv")
old = old[(old.split == "research") & old.bot.isin(["BOT-A", "BOT-B", "BOT-B-R2"])].copy()
r2 = pd.read_csv(f"{R}/final_dev_r2.csv"); old = pd.concat([old, r2[r2.split == "research"]], ignore_index=True)
old["bot"] = old["bot"].replace({"BOT-A": "BOT-A-R1", "BOT-B": "BOT-B-R1"})
d = pd.concat([d, old], ignore_index=True).drop_duplicates(["bot", "plan", "split", "cost"], keep="first")
C.d = d
d.to_csv(f"{R}/comparison_long_r3.csv", index=False)
SETS = [("BOT-A-R3", "baseline_A", "pro50", C.MA), ("BOT-A-R3-port", "baseline_A", "pro50", C.MA), ("BOT-A-R1", "baseline_A", "pro50", C.MA),
        ("BOT-B-R3", "baseline_B", "flex50", C.MB), ("BOT-B-R3-port", "baseline_B", "flex50", C.MB), ("BOT-B-R2", "baseline_B", "flex50", C.MB),
        ("BOT-B-R1", "baseline_B", "flex50", C.MB)]
if __name__ == "__main__":
    md, sf = [], []
    for bot, base, plan, ms in SETS:
        for cost in ("stress", "base"):
            t, f = C.table(base, bot, plan, cost, ms)
            md.append(f"### {bot} vs {base} ({plan}, {cost} cost)\n\n{t}\n\nShortfalls ({len(f)}): " +
                      ("; ".join(f"{s} {C.NAMES[m]} {b} -> {a}" for s, m, b, a in f) or "none"))
            sf += [dict(bot=bot, baseline=base, plan=plan, cost=cost, split=s, metric=m, baseline_value=b, bot_value=a) for s, m, b, a in f]
    open(f"{R}/comparison_r3.md", "w").write("\n\n".join(md) + "\n")
    s = pd.DataFrame(sf); s.to_csv(f"{R}/shortfalls_r3.csv", index=False)
    print(s.groupby(["bot", "cost", "split"]).size().unstack(fill_value=0).to_string())
