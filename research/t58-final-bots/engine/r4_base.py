"""Round 4 dev scores of the baselines and the earlier picks (research + new validation to 2026-11-20), stride 1, base + stress."""
import sys; sys.path.insert(0, "research/t58_final_bots/engine")
import os; os.environ["T58_R4"] = "1"
import pandas as pd
from multiprocessing import Pool
import r4, picks, picks_r2, picks_r3
WHO = {"baseline_A": "baseline_A", "baseline_B": "baseline_B", "BOT-A-R3": picks_r3.BOT_A, "BOT-B-R3": picks_r3.BOT_B, "BOT-B-R2": picks_r2.BOT_B,
       "BOT-A-R1": picks.BOT_A}
def job(a):
    who, plan, sp, cost = a
    r = r4.run(WHO[who], plan, sp, cost); r.update(bot=who, plan=plan, split=sp, cost=cost); return r
if __name__ == "__main__":
    jobs = [(w, pl, sp, c) for w, pl in [("baseline_A", "pro50"), ("baseline_B", "flex50"), ("BOT-A-R3", "pro50"), ("BOT-B-R3", "flex50"),
                                          ("BOT-B-R2", "flex50"), ("BOT-A-R1", "pro50")]
            for sp in ("research", "validation") for c in ("stress", "base")]
    with Pool(3) as pool: rows = pool.map(job, jobs, chunksize=1)
    pd.DataFrame(rows).to_csv(f"{r4.OUT}/dev_r4_prior.csv", index=False); print("done")
