"""Round 5 overfitting checks 1 and 3 (research/PREREG_R5.md). No holdout: every split here was already read.
  confirm: stride 1, stress + base cost, splits h3/research/validation, for baselines, R4 picks and the round-5 B pick.
  plateau: one-step neighbours of the round-5 B pick, stride 2, stress, shortfall cells vs baseline_B.
Usage: python3 r5_confirm.py confirm|plateau"""
import sys, json, copy, time, os
sys.path.insert(0, "research/t58_final_bots/engine")
import r5
import pandas as pd, numpy as np
from multiprocessing import Pool
import picks_r4, search as S
PB = json.load(open(f"{r5.OUT}/runs/r5_B2_top.json"))[0]; PB.pop("vid", None)
WHO = {"baseline_A": ("baseline_A", "pro50"), "BOT-A-R4": (picks_r4.BOT_A, "pro50"),
       "baseline_B": ("baseline_B", "flex50"), "BOT-B-R4": (picks_r4.BOT_B, "flex50"), "BOT-B-R5": (PB, "flex50")}
def cj(a):
    who, sp, cost = a; pk, plan = WHO[who]
    return dict(bot=who, split=sp, cost=cost, **r5.run(pk, plan, sp, cost, stride=1, sustained=plan == "flex50"))
def neighbours():
    out, L = [], (0, .25, .5, 1)
    for k, w in PB["legs"].items():
        i = min(range(4), key=lambda j: abs(L[j] - w))
        for j in (i - 1, i + 1):
            if 0 <= j < 4:
                pk = copy.deepcopy(PB)
                if L[j] == 0: del pk["legs"][k]
                else: pk["legs"][k] = L[j]
                out.append((f"leg {k} {w}->{L[j]}", pk))
    steps = {"r_fund": (200, 250, 300), "day_stop": (220, 300, 380), "fund_day_cap": (200, None), "f_cush": (.3, .4, .5),
             "fund_f_cush": (.2, .3, .4), "r_eval": (250, 300, 350), "max_open": (3, 4, 5)}
    for k, vals in steps.items():
        cur = PB["max_open"] if k == "max_open" else PB["policy"][k]
        i = vals.index(cur)
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals):
                pk = copy.deepcopy(PB); v = vals[j]
                if k == "max_open": pk["max_open"] = v
                else:
                    pk["policy"][k] = v
                    if k == "day_stop": pk["policy"]["fund_day_stop"] = v
                out.append((f"{k} {cur}->{v}", pk))
    return out
def pj(a):
    name, pk = a
    return name, {sp: r5.run(pk, "flex50", sp, "stress", stride=2, sustained=True) for sp in r5.DEV}
if __name__ == "__main__":
    t0 = time.time()
    if sys.argv[1] == "confirm":
        jobs = [(w, sp, c) for w in WHO for sp in r5.DEV for c in ("stress", "base")]
        with Pool(4) as p: rows = p.map(cj, jobs, chunksize=1)
        d = pd.DataFrame(rows); d.to_csv(f"{r5.OUT}/final_dev_r5.csv", index=False)
        for c in ("stress", "base"):
            for sp in r5.DEV:
                g = d[(d.cost == c) & (d.split == sp)].set_index("bot")
                bA, bB = g.loc["baseline_A"].to_dict(), g.loc["baseline_B"].to_dict()
                print(c, sp, "A-R4", r5.a_bar(g.loc["BOT-A-R4"].to_dict(), bA),
                      "| B-R4", S.beats(g.loc["BOT-B-R4"].to_dict(), bB, sustained=True),
                      "| B-R5", S.beats(g.loc["BOT-B-R5"].to_dict(), bB, sustained=True), flush=True)
    else:
        nb = neighbours(); print("neighbours", len(nb), flush=True)
        with Pool(4) as p: res = p.map(pj, nb, chunksize=1)
        base = __import__("r5_search").base_rows(); rows = []
        for name, o in res:
            bad = {sp: S.beats(o[sp], base[(base.bot == "baseline_B") & (base.split == sp)].iloc[0].to_dict(), sustained=True) for sp in o}
            rows.append(dict(step=name, nbad=sum(map(len, bad.values())), bad=json.dumps(bad)))
        d = pd.DataFrame(rows); d.to_csv(f"{r5.OUT}/plateau_r5_B.csv", index=False); print(d.to_string())
    print("secs", round(time.time() - t0)); print("done")
