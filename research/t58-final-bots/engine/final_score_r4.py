"""Round 4: score the finalists, the round-3 picks and the baselines with identical code.
Usage: T58_R4=1 python3 final_score_r4.py dev|hold
dev : research 2020-2023 + validation 2024-01-01 .. 2026-11-20 (H2 included), base + stress, stride 1 -> research/final_dev_r4.csv
hold: the single read of Owen's 2016-11-24 .. 2019-12-31 pack (H3) -> research/final_hold_r4.csv (+ Flex lock-on-payout rows).
      Requires research/FROZEN_PICKS_R4.sha256 and refuses to run twice."""
import sys, os, copy
os.environ["T58_R4"] = "1"; sys.path.insert(0, "research/t58_final_bots/engine")
import pandas as pd
from multiprocessing import Pool
import r4, picks_r3, picks_r4, legs as LG, search as S
WHO = {"baseline_A": "baseline_A", "baseline_B": "baseline_B", "BOT-A-R3": picks_r3.BOT_A, "BOT-B-R3": picks_r3.BOT_B,
       "BOT-A-R4": picks_r4.BOT_A, "BOT-B-R4": picks_r4.BOT_B}
ROSTER = [("baseline_A", "pro50"), ("baseline_B", "flex50"), ("BOT-A-R3", "pro50"), ("BOT-B-R3", "flex50"),
          ("BOT-A-R4", "pro50"), ("BOT-B-R4", "flex50"), ("BOT-A-R4-port", "pro50"), ("BOT-B-R4-port", "flex50")]
def job(a):
    who, plan, sp, cost, sealed, lock = a
    if lock:                                   # Flex lock-on-payout sensitivity: swap the firm module (code/firm_lockpay.py)
        import firm_lockpay, score, firm
        score.firm = firm_lockpay; r4.firm = firm_lockpay
    port = who.endswith("-port")
    if port: LG.use_ports(); S._B.clear()
    r = r4.run(WHO[who[:-5] if port else who], plan, sp, cost, stride=1, sealed=sealed)
    r.update(bot=who, plan=plan, split=sp, cost=cost, firm="lock_on_payout" if lock else "current")
    return r
if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "hold":
        assert os.path.exists(f"{r4.OUT}/FROZEN_PICKS_R4.sha256"), "freeze R4 picks first"
        assert not os.path.exists(f"{r4.OUT}/final_hold_r4.csv"), "H3 already read once; it is not read again"
        jobs = [(w, pl, "holdout", c, True, False) for w, pl in ROSTER for c in ("stress", "base")]
        jobs += [(w, "flex50", "holdout", "stress", True, True) for w in ("baseline_B", "BOT-B-R3", "BOT-B-R4")]
    else:
        jobs = [(w, pl, sp, c, False, False) for w, pl in ROSTER for sp in ("research", "validation") for c in ("stress", "base")]
        jobs += [(w, "flex50", sp, "stress", False, True) for w in ("baseline_B", "BOT-B-R3", "BOT-B-R4") for sp in ("research", "validation")]
    with Pool(4, maxtasksperchild=1) as pool: rows = pool.map(job, jobs, chunksize=1)
    pd.DataFrame(rows).to_csv(f"{r4.OUT}/final_{mode}_r4.csv", index=False); print("done", len(rows))
