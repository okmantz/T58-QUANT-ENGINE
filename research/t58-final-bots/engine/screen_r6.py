"""Round 6 energy screen (research/PREREG_R6.md): every grid point of the factory families on CL and NG (MCL / MNG micros), research
2021-01-04 .. 2024-07-15 and validation 2024-07-16 .. 2026-01-04 only (H6 sealed). F9 gap and the trend-only variants are left out on NG
and F9 on CL: they read prior closes, which jump at unadjusted rolls. Ledger: research/strategy_ledger_r6.csv (append-only)."""
import os, sys, csv, json, time, pickle
os.environ["T58_R6"] = "1"; sys.path.insert(0, "research/t58_final_bots/engine")
import numpy as np
import data as D, factory as F, screen
LEDGER = D.WORK / "research" / "strategy_ledger_r6.csv"
SKIP = {"CL": {"F9_gap"}, "NG": {"F9_gap", "F10_mtf"}}
def plist_for(fam, inst, plist):
    if inst == "NG": plist = [p for p in plist if p.get("trend", "or") != "daily" and p.get("filt") != "trend"]
    return plist
if __name__ == "__main__":
    new = not LEDGER.exists(); fh = LEDGER.open("a", newline=""); w = csv.DictWriter(fh, screen.COLS, extrasaction="ignore")
    if new: w.writeheader()
    for fam, fn, _, plist in F.grids():
        if fn is F.fam_gold: continue
        for inst in D.ENERGY:
            if fam in SKIP[inst]: continue
            f = F.feats(inst); days = f["M"]["days"]; spl = f["split"]
            dres, dval = days[(spl == "res") & f["ok"]], days[(spl == "val") & f["ok"]]
            mat, ids, t0 = [], [], time.time()
            pl = plist_for(fam, inst, plist)
            for p in pl:
                try: b = fn(inst, **p)
                except Exception as e: print(fam, inst, p, "ERR", repr(e)[:150], flush=True); continue
                i = screen.tid(fam, inst, p)
                if b is None:
                    w.writerow(dict(trial_id=i, ts=time.strftime("%Y-%m-%d %H:%M"), family=fam, inst=inst, params=json.dumps(p, default=str), split="res", n=0, note="no trades")); continue
                sp = np.where(b["day"] >= D.E_VAL_FROM, "val", "res")
                for nm, mask, dd in (("res", sp == "res", dres), ("val", sp == "val", dval)):
                    st = screen.split_stats(b, mask, dd)
                    if nm == "res" and "_dr" in st: mat.append(st["_dr"]); ids.append(i)
                    st.pop("_dr", None)
                    w.writerow(dict(trial_id=i, ts=time.strftime("%Y-%m-%d %H:%M"), family=fam, inst=inst, params=json.dumps(p, default=str), name=b["leg"][0], split=nm, **st))
            fh.flush()
            if mat: pickle.dump(dict(ids=ids, R=np.array(mat).T, days=dres), (screen.DAILY / f"r6_{fam}__{inst}.pkl").open("wb"))
            print(fam, inst, len(pl), "trials", round(time.time() - t0, 1), "s", flush=True)
    fh.close(); print("done")
