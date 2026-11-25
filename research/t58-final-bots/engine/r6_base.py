"""Round 6: baselines and the round-4 picks on Pro 50K / Pro 100K (and Flex 50K for B, continuity), every window, stress + base, stride 1.
-> research/r6_base.csv. ES/NQ/GC only: every window here is in-sample (already read)."""
import sys, time
sys.path.insert(0, "research/t58_final_bots/engine")
import r6, picks_r4, pandas as pd
from multiprocessing import Pool
WHO = {"baseline_A": "baseline_A", "BOT-A-R4": picks_r4.BOT_A, "baseline_B": "baseline_B", "BOT-B-R4": picks_r4.BOT_B}
def job(a):
    who, plan, sp, cost = a
    return dict(bot=who, plan=plan, split=sp, cost=cost, **r6.run(WHO[who], plan, sp, cost, stride=int(sys.argv[1]), sustained=True))
if __name__ == "__main__":
    t0 = time.time(); stride = int(sys.argv[1]); costs = sys.argv[2].split(",")
    wins = sys.argv[3].split(",") if len(sys.argv) > 3 else ["W1", "W2", "H6", "h3", "research", "validation"]
    jobs = [(w, pl, sp, c) for c in costs for sp in wins for pl in ("pro50", "pro100", "flex50") for w in WHO if not (pl == "flex50" and w[-1] == "4" and "A" in w) and not (pl == "flex50" and w == "baseline_A")]
    with Pool(4) as p: rows = p.map(job, jobs, chunksize=1)
    d = pd.DataFrame(rows); d.to_csv(f"{r6.OUT}/r6_base_s{stride}.csv", index=False); print("rows", len(d), "secs", round(time.time() - t0)); print("done")
