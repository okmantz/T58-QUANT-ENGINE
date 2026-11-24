"""Run each ported strategy file through the repo engine (book.gen, zero friction) and compare it with the factory book it replaces,
research + validation only (sessions before the holdout). Writes research/port_check.csv."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "research/t58_final_bots/engine")
import book, legs as LG
P = "strategies/python/"
PORTS = {"ORB15C_NQ": ("ORB15Compression_NQ_1m_t58", "NQ"), "ORB15C_ES": ("ORB15Compression_ES_1m_t58", "ES"),
         "ORB30T_NQ": ("ORB30Trend_NQ_1m_t58", "NQ"), "VWPB_NQ": ("VWAPPullback_NQ_1m_t58", "NQ"), "PDLB_GC": ("PriorDayBreak_GC_1m_t58", "GC"),
         "GAP_GC": ("GapTrend_GC_1m_t58", "GC")}
rows = []
for key, (stem, inst) in PORTS.items():
    if len(sys.argv) > 1 and key not in sys.argv[1:]: continue
    f = LG.get(key)
    p = book.points(book.gen(stem, inst, src=P + stem + ".py", tag=stem + "_port"), inst, name=key)
    fd = {(d, int(x)): (pt, r) for d, x, pt, r in zip(f["day"], f["dir"], f["pts"], f["risk_pts"])}
    pdd = {(d, int(x)): (pt, r) for d, x, pt, r in zip(p["day"], p["dir"], p["pts"], p["risk_pts"])}
    both = sorted(set(fd) & set(pdd))
    a = np.array([fd[k][0] / fd[k][1] for k in both]); b = np.array([pdd[k][0] / pdd[k][1] for k in both])
    fr = np.array([v[0] / v[1] for v in fd.values()]); pr = np.array([v[0] / v[1] for v in pdd.values()])
    rows.append(dict(leg=key, file=stem, factory_trades=len(fd), port_trades=len(pdd), same_day_dir=len(both),
                     match_of_factory=len(both) / max(len(fd), 1), r_corr_matched=float(np.corrcoef(a, b)[0, 1]) if len(both) > 2 else np.nan,
                     factory_mean_R=float(fr.mean()), port_mean_R=float(pr.mean()), matched_mean_R_factory=float(a.mean()), matched_mean_R_port=float(b.mean())))
    print(rows[-1], flush=True)
out = "research/t58_final_bots/research/port_check.csv"
import os
old = pd.read_csv(out) if os.path.exists(out) else pd.DataFrame()
new = pd.DataFrame(rows)
if len(old): old = old[~old.leg.isin(new.leg)]
pd.concat([old, new]).to_csv(out, index=False)
