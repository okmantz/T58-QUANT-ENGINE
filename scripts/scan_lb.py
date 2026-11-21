import itertools, warnings; warnings.filterwarnings("ignore")
import pandas as pd, dev
SRC = dev.REPO / "strategies/python/LevelBreakout_ESNQ_15m_v1.py"
rows = []
for mode, tn, sa, tg, inst in itertools.product(["on", "pd"], [0, 20], [0.2, 0.3], [1.5, 2.0, 3.0], ["ES", "NQ"]):
    tag = f"LB_{mode}_{tn}_{sa}_{tg}"
    d = dev.run_variant(SRC, inst, dict(MODE=mode, TREND_N=tn, STOP_ATR=sa, TGT_R=tg), tag)
    r = dict(tag=tag, inst=inst)
    for sp in ("train", "val"):
        for k, v in dev.stats(d, sp).items(): r[f"{sp}_{k}"] = v
    rows.append(r)
df = pd.DataFrame(rows); df.to_csv("/mnt/project-files/t58-new-bots/results/scan_levelbreakout.csv", index=False)
pd.set_option("display.width", 250); print(df.sort_values("train_t", ascending=False).to_string())
