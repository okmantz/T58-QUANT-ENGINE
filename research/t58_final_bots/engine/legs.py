"""Candidate legs (Phase 4 inputs) chosen from the screen: positive at stress cost in research (HAC t >= 1.5) AND in validation (t >= 1),
favouring plateaus (neighbouring parameters also positive). Each entry: key -> (builder, kwargs, instrument)."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
import factory as F, book, baseline as B

CAND = {
    "OD_NQ":     ("repo", "OpenDrive_NQ_5m_v1", "NQ"),
    "CDL_NQ":    ("repo", "ContextDriveLong_NQ_1m_v2", "NQ"),
    "IR_NQ":     ("repo", "IndRule_NQ_15m_v1", "NQ"),
    "CDL_ES":    ("repo", "ContextDriveLong_NQ_1m_v2", "ES"),
    "ORB15_NQ":  ("fam", (F.fam_orb, dict(k=15, stop="opp", R=2.0, filt="none", cut=150)), "NQ"),
    "ORB30T_NQ": ("fam", (F.fam_orb, dict(k=30, stop="opp", R=3.0, cut=150, trend_only=True)), "NQ"),
    "ORB15C_NQ": ("fam", (F.fam_orb, dict(k=15, stop="atr", R=3.0, filt="comp", cut=150)), "NQ"),
    "ORB15C_ES": ("fam", (F.fam_orb, dict(k=15, stop="atr", R=2.0, filt="comp", cut=150)), "ES"),
    "VWPB_NQ":   ("fam", (F.fam_vwap_pb, dict(R=2.0, sm=0.35, t1=1260, trend="daily")), "NQ"),
    "TOD10_NQ":  ("fam", (F.fam_tod, dict(sig_m=990, hold_to=1314, sm=0.2, mode="rth", thr=0.0)), "NQ"),
    # round 2 additions (ledger: positive at stress cost in research and validation, or the gold candidates)
    "ORB15N_NQ": ("fam", (F.fam_orb, dict(k=15, stop="atr", R=3.0, filt="none", cut=150)), "NQ"),
    "OD_ES":     ("repo", "OpenDrive_NQ_5m_v1", "ES"),
    "CORB_ES":   ("repo", "CompressionORB_ES_5m_v1", "ES"),
    "PDLB_GC":   ("fam", (F.fam_pdl_break, dict(R=3.0, sm=0.5, vol="low", t0=960)), "GC"),
    "GAP_GC":    ("fam", (F.fam_gap, dict(g=0.4, sm=0.5, R=3.0, with_trend=True)), "GC"),
}

PORT_DIR = "strategies/python/"
PORTS = {"ORB15C_NQ": "ORB15Compression_NQ_1m_v1", "ORB15C_ES": "ORB15Compression_ES_1m_v1", "ORB30T_NQ": "ORB30Trend_NQ_1m_v1",
         "VWPB_NQ": "VWAPPullback_NQ_1m_v1", "PDLB_GC": "PriorDayBreak_GC_1m_v1",
         "GAP_GC": "GapTrend_GC_1m_v1"}
def use_ports():
    for k, stem in PORTS.items(): CAND[k] = ("port", stem, CAND[k][2])

def get(key, sealed=False):
    kind, spec, inst = CAND[key]
    if kind == "repo":
        b = book.points(book.gen(spec, inst), inst, sealed=sealed, name=key)
    elif kind == "port":      # the repo-style file written by port_legs.py, run through the repo engine (verify_port_bots.py)
        b = book.points(book.gen(spec, inst, src=PORT_DIR + spec + ".py", tag=spec + "_port"), inst, sealed=sealed, name=key)
    else:
        fn, kw = spec
        b = fn(inst, sealed=sealed, **kw)
        b["leg"] = np.array([key] * len(b["day"]))
    return b
