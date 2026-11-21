import warnings; warnings.filterwarnings("ignore")
import pandas as pd, dev
SRC_LB = dev.REPO / "strategies/python/LevelBreakout_ESNQ_15m_v1.py"
ONB = dict(MODE="on", TREND_N=20, STOP_ATR=0.3, TGT_R=2.0)
LIB = {  # key: (stem, inst)
 "OD_NQ": ("OpenDrive_NQ_5m_v1", "NQ"), "IR_NQ": ("IndRule_NQ_15m_v1", "NQ"), "CDL_NQ": ("ContextDriveLong_NQ_1m_v2", "NQ"),
 "CDLB_NQ": ("ContextDriveLongBracket_NQ_1m_v1", "NQ"), "IRA_NQ": ("IndRuleA_NQ_30m_v1", "NQ"), "IRB_NQ": ("IndRuleB_NQ_30m_v1", "NQ"),
 "LSR_NQ": ("LiquiditySweepReclaim_NQ_5m_v1", "NQ"), "TM_NQ": ("TrendMomentum_NQ_5m_v1", "NQ"), "ORBC_NQ": ("ORBCompression_ESNQ_15m_v1", "NQ"),
 "OD_ES": ("OpenDrive_NQ_5m_v1", "ES"), "IR_ES": ("IndRule_NQ_15m_v1", "ES"), "CDL_ES": ("ContextDriveLong_NQ_1m_v2", "ES"),
 "CDLB_ES": ("ContextDriveLongBracket_NQ_1m_v1", "ES"), "IRA_ES": ("IndRuleA_NQ_30m_v1", "ES"), "IRB_ES": ("IndRuleB_NQ_30m_v1", "ES"),
 "COB_ES": ("CompressionORB_ES_5m_v1", "ES"), "ORBC_ES": ("ORBCompression_ESNQ_15m_v1", "ES"),
 "ONB_NQ": ("LB_on_20_0.3_2.0", "NQ"), "ONB_ES": ("LB_on_20_0.3_2.0", "ES"),
}
def get(key, holdout=False):
    stem, inst = LIB[key]
    return dev.load(stem, inst, holdout)
if __name__ == "__main__":
    rows = []
    for k in LIB:
        d = get(k); r = dict(leg=k)
        for sp in ("train", "val"):
            for kk, v in dev.stats(d, sp).items(): r[f"{sp}_{kk}"] = v
        rows.append(r)
    df = pd.DataFrame(rows); pd.set_option("display.width", 250); print(df.to_string())
    df.to_csv("/mnt/project-files/t58-new-bots/results/leg_library_dev.csv", index=False)
