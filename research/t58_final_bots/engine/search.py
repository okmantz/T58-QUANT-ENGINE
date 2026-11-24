"""Phase 4-5 search at bot level: leg subsets x weights x policy grid, scored on RESEARCH with the firm engine, then confirmed on
VALIDATION. Every bot-level configuration is a trial: counted in research/bot_trials.csv (append-only)."""
import sys, json, itertools, time, csv
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import firm, score, book, legs as LG
from policy import Pol
RES, VAL = ("2020-01-01", "2024-01-01"), ("2024-01-01", "2025-09-01")
import data as _D
if _D.R3: VAL = ("2024-01-01", "2026-03-02")          # round 3: the round-1/2 holdout window joins validation
if _D.R4: VAL = ("2024-01-01", "2026-11-21")          # round 4: H2 (read once in round 3) joins validation
LOG = Path("research/t58_final_bots/research/bot_trials.csv")
_B = {}
def leg(k, sealed=False):
    if (k, sealed) not in _B: _B[(k, sealed)] = LG.get(k, sealed=sealed)
    return _B[(k, sealed)]

def bot(ws, max_open=2, hedge=True, sealed=False):
    return book.merge([(leg(k, sealed), w, j) for j, (k, w) in enumerate(ws.items()) if w > 0], max_open=max_open, max_per_day=6, one_per_inst=True,
                      hedge_guard=hedge)

def log(obj, ws, pol, plan, sp, r, extra=""):
    new = not LOG.exists()
    with LOG.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new: w.writerow(["ts", "objective", "legs", "policy", "plan", "split", "metrics", "note"])
        w.writerow([time.strftime("%Y-%m-%d %H:%M"), obj, json.dumps(ws), json.dumps(pol.dict()), plan.name, sp,
                    json.dumps({k: (round(float(v), 4) if isinstance(v, (int, float, np.floating)) else v) for k, v in r.items()}), extra])

HIGHER = ["p_pass", "p_payout", "ev", "pf", "exp_R", "sharpe", "sortino", "worst_day", "trades_pm"]
LOWER = ["med_days_pass", "med_days_payout", "bust", "max_dd", "cons_blocks_per30", "cons_block_rate", "fund_bust"]
HIGHER_B = ["f90_payouts", "f90_paid", "f90_p2"]
LOWER_B = ["f90_bust"]

def beats(new, base, tol=0.0, sustained=False):
    """List of metrics where ``new`` fails to beat-or-tie ``base``. NaN median days count as a fail unless base is NaN too."""
    bad = []
    hi, lo = (HIGHER + HIGHER_B, LOWER + LOWER_B) if sustained else (HIGHER, LOWER)
    for k in hi:
        a, b = new.get(k, np.nan), base.get(k, np.nan)
        if np.isnan(b): continue
        if np.isnan(a) or a < b - tol * abs(b): bad.append(k)
    for k in lo:
        a, b = new.get(k, np.nan), base.get(k, np.nan)
        if np.isnan(b): continue
        if np.isnan(a) or a > b + tol * abs(b): bad.append(k)
    return bad

def baseline_metrics(plan_name="pro50", obj="A"):
    f = Path("research/t58_final_bots/research") / ("baseline_dev.csv" if plan_name == "pro50" else "baseline_dev_flex.csv")
    d = pd.read_csv(f)
    d = d[(d.bot == "baseline_" + obj) & (d.cost == "base")]
    return {sp: d[d.split == sp].iloc[0].to_dict() for sp in ("research", "validation")}
