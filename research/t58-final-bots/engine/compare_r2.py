"""Round 2 comparison: baseline B vs BOT-B-R2 (research/final_dev_r2.csv, final_hold_r2.csv), same table code as compare.py.
Usage: python3 compare_r2.py -> prints markdown tables; appends the R2 rows to research/comparison_long.csv."""
import pandas as pd
import compare as C
R = C.R
r2 = pd.concat([pd.read_csv(f"{R}/final_dev_r2.csv"), pd.read_csv(f"{R}/final_hold_r2.csv")], ignore_index=True)
C.d = pd.concat([C.d[C.d.bot != "BOT-B-R2"], r2], ignore_index=True)
C.d.to_csv(f"{R}/comparison_long.csv", index=False)
if __name__ == "__main__":
    for cost in ("stress", "base"):
        t, f = C.table("baseline_B", "BOT-B-R2", "flex50", cost, C.MB)
        print(f"\n### BOT-B-R2 vs baseline_B (flex50, {cost} cost)\n\n{t}\n\nFails ({len(f)}): " + "; ".join(f"{s} {m} {b}->{a}" for s, m, b, a in f))
