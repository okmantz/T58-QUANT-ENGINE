"""Dev-only access to engine trades. Rows with entry >= 2025-01-01 are dropped HERE; the 1x scale (avg loss -> $500) is computed on dev rows only."""
import sys, pickle, re, tempfile
from pathlib import Path
import numpy as np, pandas as pd
REPO = Path("/home/claude/t58-quant-engine"); sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts"))
CACHE = Path("/home/user/work/cache/trades")
CUT = pd.Timestamp("2025-01-01")
SPL = {"train": ("2020-01-01", "2024-01-01"), "val": ("2024-01-01", "2025-01-01")}

def frame(tr):
    import run_objective_scores as ros
    return ros.sc.frame(tr)

def scale_dev(d):
    dd = d[d.entry < CUT]
    neg = dd.loc[dd.pnl < 0, "pnl"]
    m = 500.0 / float(-neg.mean()) if len(neg) else 0.0
    out = d.copy(); out["pnl"] = out["pnl"] * m; out.attrs["scale"] = m
    return out

def load(stem, inst, holdout=False):
    p = CACHE / f"{stem}__{inst}.pkl"
    d = frame(pickle.load(p.open("rb")))
    d["inst"] = inst
    d = scale_dev(d)
    if not holdout:
        d = d[d.entry < CUT].reset_index(drop=True)
    return d

def run_variant(src, inst, consts, tag, holdout=False):
    """Run a strategy file with module constants replaced (research variants). Cached by tag."""
    out = CACHE / f"{tag}__{inst}.pkl"
    if not out.exists():
        txt = Path(src).read_text()
        for k, v in consts.items():
            txt, nsub = re.subn(rf"^{k}\s*=.*$", f"{k} = {v!r}", txt, flags=re.M)
            assert nsub == 1, k
        tmp = Path(tempfile.mkdtemp()) / (tag + ".py"); tmp.write_text(txt)
        import bundle_research as br
        from app.data.importer import import_csv
        df = import_csv(str(REPO / br.DATA[inst])).dataframe.reset_index(drop=True)
        tr = br.run_trades(tmp, inst, df)
        pickle.dump(tr, out.open("wb"))
    return load(tag, inst, holdout)

def stats(d, sp):
    a, b = SPL[sp]; x = d[(d.entry >= a) & (d.entry < b)]
    if len(x) < 5: return dict(n=len(x))
    r = x.pnl.to_numpy() / 500.0
    day = (x.entry - pd.Timedelta(hours=17)).dt.normalize()
    dr = pd.Series(r, index=day.values).groupby(level=0).sum()
    t = dr.mean() / (dr.std(ddof=1) / np.sqrt(len(dr))) if len(dr) > 2 and dr.std(ddof=1) > 0 else np.nan
    g, ls = r[r > 0].sum(), -r[r < 0].sum()
    return dict(n=len(x), mR=round(r.mean(), 3), t=round(t, 2), pf=round(g / ls, 2) if ls else np.inf, wr=round((r > 0).mean(), 2), perM=round(len(x) / ((pd.Timestamp(b) - pd.Timestamp(a)).days / 30.4), 1))
