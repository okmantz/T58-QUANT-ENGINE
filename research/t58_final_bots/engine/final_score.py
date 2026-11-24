"""Score the frozen picks and the baseline with identical code. Usage: python3 final_score.py dev|hold
dev: research + validation, base + stress, stride 1 -> research/final_dev.csv.
hold: the single holdout read (2025-09-01 .. 2026-03-01, NQ data end) -> research/final_holdout.csv. Requires FROZEN_PICKS.sha256."""
import sys, pandas as pd
from multiprocessing import Pool
sys.path.insert(0, "research/t58_final_bots/engine")
import search as S, score, firm, picks, baseline as BL
from policy import Pol
OUT = "research/t58_final_bots/research"
SPL = {"research": S.RES, "validation": S.VAL, "holdout": ("2025-09-01", "2026-03-01")}
def plan_of(name, cost):
    return firm.Plan(cost=cost) if name == "pro50" else firm.Plan.flex50(cost=cost)
def job(a):
    who, planname, sp, cost, sealed = a
    p = plan_of(planname, cost); x, y = SPL[sp]
    if who.startswith("baseline"):
        obj = who[-1]; bk = BL.bot_book(BL.LEGS_A if obj == "A" else BL.LEGS_B, sealed=sealed); pol = BL.policy(obj, BL.lite(p))
    else:
        pk = picks.BOT_A if who == "BOT-A" else picks.BOT_B
        bk = S.bot(pk["legs"], max_open=pk["max_open"], sealed=sealed); pol = Pol(**pk["policy"])
    r = score.full(bk, pol, p, x, y, stride=1); r.update(score.sustained_block(bk, pol, p, x, y))
    r.update(bot=who, plan=planname, split=sp, cost=cost)
    return r
if __name__ == "__main__":
    mode = sys.argv[1]
    sps = ("research", "validation") if mode == "dev" else ("holdout",)
    jobs = [(w, pl, sp, c, mode == "hold") for w, pl in (("baseline_A", "pro50"), ("BOT-A", "pro50"), ("baseline_B", "flex50"), ("BOT-B", "flex50"),
                                                      ("baseline_B", "pro50"), ("BOT-B", "pro50"), ("baseline_A", "flex50"), ("BOT-A", "flex50"))
            for sp in sps for c in ("base", "stress")]
    if mode == "dev":
        jobs = [j for j in jobs if j[0].startswith("BOT")]       # baseline dev rows already in baseline_dev*.csv (same code, stride 1)
    with Pool(4) as pool:
        rows = pool.map(job, jobs)
    pd.DataFrame(rows).to_csv(f"{OUT}/final_{mode}.csv", index=False)
    print("done", len(rows))
