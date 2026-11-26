"""Round 3: score every finalist with identical code on the extended validation (dev) or on the fresh H2 holdout (hold).
Usage: T58_R3=1 python3 final_score_r3.py dev|hold
devres: research 2020-2023 for the round-3 picks only -> research/final_devres_r3.csv
dev : validation 2024-01-01 .. 2026-03-02 (round-1/2 holdout folded in), base + stress -> research/final_dev_r3.csv
hold: the single read of Owen's Mar..Nov 2026 pack (sessions 2026-03-02 .. 2026-11-20) -> research/final_hold_r3.csv.
      Requires research/FROZEN_PICKS_R3.sha256 and refuses to run twice."""
import sys, os, pandas as pd
from multiprocessing import Pool
sys.path.insert(0, "research/t58_final_bots/engine")
import data as D
assert D.R3, "set T58_R3=1"
import search as S, score, firm, picks, picks_r2, picks_r3, filters, baseline as BL, legs as LG
from policy import Pol
OUT = "research/t58_final_bots/research"
SPL = {"research": S.RES, "validation": S.VAL, "holdout": ("2026-03-02", "2026-11-21")}
WHO = {"BOT-A-R1": picks.BOT_A, "BOT-B-R1": picks.BOT_B, "BOT-B-R2": picks_r2.BOT_B,
       "BOT-A-R3": picks_r3.BOT_A, "BOT-B-R3": picks_r3.BOT_B}
def plan_of(name, cost):
    return firm.Plan(cost=cost) if name == "pro50" else firm.Plan.flex50(cost=cost)
def book_pol(who, p, sealed):
    if who.endswith("-port"):          # the same pick with its factory legs replaced by the repo-style files (strategies/python/*_1m_v1.py)
        keep = dict(LG.CAND); LG.use_ports(); S._B.clear()
        try: return book_pol(who[:-5], p, sealed)
        finally: LG.CAND.clear(); LG.CAND.update(keep); S._B.clear()
    if who.startswith("baseline"):
        obj = who[-1]; return BL.bot_book(BL.LEGS_A if obj == "A" else BL.LEGS_B, sealed=sealed), BL.policy(obj, BL.lite(p))
    pk = WHO[who]
    if pk.get("spec") is not None or pk.get("legspec") is not None:
        bk = filters.bot(pk["legs"], max_open=pk["max_open"], spec=pk.get("spec"), legspec=pk.get("legspec"), sealed=sealed)
    else:
        bk = S.bot(pk["legs"], max_open=pk["max_open"], sealed=sealed)
    return bk, Pol(**pk["policy"])
def job(a):
    who, planname, sp, cost, sealed = a
    p = plan_of(planname, cost); x, y = SPL[sp]; bk, pol = book_pol(who, p, sealed)
    r = score.full(bk, pol, p, x, y, stride=1); r.update(score.sustained_block(bk, pol, p, x, y))
    r.update(bot=who, plan=planname, split=sp, cost=cost)
    return r
def roster():
    out = [("baseline_A", "pro50"), ("baseline_B", "flex50"), ("baseline_A", "flex50"), ("baseline_B", "pro50")]
    for w in WHO:
        if w.endswith("-R3") and WHO[w] is WHO[w.replace("-R3", "-R1")]: continue      # R3 pick identical to an earlier pick: score once
        if w.endswith("-R3") and w.startswith("BOT-B") and WHO[w] is WHO["BOT-B-R2"]: continue
        out += [(w, "pro50"), (w, "flex50")]
    out += [("BOT-A-R3-port", "pro50"), ("BOT-B-R3-port", "flex50")]
    return out
if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "hold":
        assert os.path.exists(f"{OUT}/FROZEN_PICKS_R3.sha256"), "freeze R3 picks first"
        assert not os.path.exists(f"{OUT}/final_hold_r3.csv"), "H2 already read once; it is not read again"
    sps = {"dev": ("validation",), "devres": ("research",), "hold": ("holdout",)}[mode]
    jobs = [(w, pl, sp, c, mode == "hold") for w, pl in roster() for sp in sps for c in ("base", "stress")]
    if mode == "dev": jobs = [j for j in jobs if not j[0].startswith("baseline")]     # baseline rows: research/baseline_dev*_r3.csv
    if mode == "devres": jobs = [j for j in jobs if j[0].endswith("-R3")]             # research rows of the earlier picks: final_dev.csv, final_dev_r2.csv
    with Pool(4) as pool: rows = pool.map(job, jobs)
    pd.DataFrame(rows).to_csv(f"{OUT}/final_{mode}_r3.csv", index=False); print("done", len(rows))
