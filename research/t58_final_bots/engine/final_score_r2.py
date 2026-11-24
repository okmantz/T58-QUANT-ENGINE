"""Round 2: score the new BOT-B (picks_r2.BOT_B, built with filters.bot) with the same code as final_score.py.
Usage: python3 final_score_r2.py dev|hold. hold = the single holdout read of BOT-B round 2 -> research/final_hold_r2.csv.
Requires FROZEN_PICKS_R2.sha256. The holdout window is the same one round 1 read (2025-09-01 .. 2026-03-01): it has now been read twice."""
import sys, os, pandas as pd
from multiprocessing import Pool
sys.path.insert(0, "research/t58_final_bots/engine")
import search as S, score, firm, picks_r2, filters
from policy import Pol
from final_score import SPL, plan_of
OUT = "research/t58_final_bots/research"
def job(a):
    planname, sp, cost, sealed = a
    p = plan_of(planname, cost); x, y = SPL[sp]; pk = picks_r2.BOT_B
    bk = filters.bot(pk["legs"], max_open=pk["max_open"], spec=pk["spec"], sealed=sealed); pol = Pol(**pk["policy"])
    r = score.full(bk, pol, p, x, y, stride=1); r.update(score.sustained_block(bk, pol, p, x, y))
    r.update(bot="BOT-B-R2", plan=planname, split=sp, cost=cost)
    return r
if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "hold": assert os.path.exists(f"{OUT}/FROZEN_PICKS_R2.sha256")
    sps = ("research", "validation") if mode == "dev" else ("holdout",)
    jobs = [(pl, sp, c, mode == "hold") for pl in ("flex50", "pro50") for sp in sps for c in ("base", "stress")]
    with Pool(4) as pool: rows = pool.map(job, jobs)
    pd.DataFrame(rows).to_csv(f"{OUT}/final_{mode}_r2.csv", index=False); print("done", len(rows))
