"""Repo library strategies as F0 trials in the same ledger (books from book.points on zero-friction engine trades)."""
import sys, csv, json, time, pickle
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
import data as D, book, screen, factory as F
fh = screen.LEDGER.open("a", newline=""); w = csv.DictWriter(fh, screen.COLS, extrasaction="ignore")
for inst in ("NQ", "ES", "GC"):
    f = F.feats(inst); days = f["M"]["days"]; spl = f["split"]
    dres, dval = days[(spl == "res") & f["ok"]], days[(spl == "val") & f["ok"]]
    mat, ids = [], []
    for p in sorted(book.STRAT.glob("*.py")):
        b = book.points(book.gen(p.stem, inst), inst, name=f"{p.stem}@{inst}")
        i = screen.tid("F0_repo", inst, {"stem": p.stem})
        if b is None: continue
        sp = D.split_of(b["day"])
        for nm, mask, dd in (("res", sp == "res", dres), ("val", sp == "val", dval)):
            st = screen.split_stats(b, mask, dd)
            if nm == "res" and "_dr" in st: mat.append(st["_dr"]); ids.append(i)
            st.pop("_dr", None)
            w.writerow(dict(trial_id=i, ts=time.strftime("%Y-%m-%d %H:%M"), family="F0_repo", inst=inst, params=json.dumps({"stem": p.stem}),
                            name=b["leg"][0], split=nm, **st))
    pickle.dump(dict(ids=ids, R=np.array(mat).T, days=dres), (screen.DAILY / f"F0_repo__{inst}.pkl").open("wb"))
fh.close()
