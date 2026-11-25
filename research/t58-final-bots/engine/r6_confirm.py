"""Round 6 stride-1 confirm. Usage: python3 r6_confirm.py dev|h6  -> research/final_dev_r6.csv | research/final_h6_r6.csv
Bots: baselines, round-4 picks, round-6 A pick (A59, Pro 100K knobs x1.75), Pro-B alternative (B785, documented only)."""
import sys, json, time, copy
sys.path.insert(0, "research/t58_final_bots/engine")
import r6, picks_r4, pandas as pd
from multiprocessing import Pool
def cfg(obj, cid):
    pk = next(json.loads(l)["pk"] for l in open(f"{r6.OUT}/runs/r6_{obj}.jsonl") if json.loads(l)["cid"] == cid)
    for k, v in pk.get("fspec", {}).items(): pk["fspec"][k] = [tuple(x) for x in v]
    return pk
A6 = cfg("A", "A59"); A6["k100"] = 1.75
B6 = cfg("B", "B785"); B6["k100"] = 1.5
A4 = copy.deepcopy(picks_r4.BOT_A); A4["k100"] = 1.5
WHO = {"baseline_A": "baseline_A", "BOT-A-R4": A4, "BOT-A-R6": A6, "baseline_B": "baseline_B", "BOT-B-R4": picks_r4.BOT_B, "BOT-B-R6alt": B6}
def job(a):
    who, plan, sp, cost = a
    return dict(bot=who, plan=plan, split=sp, cost=cost, **r6.run(WHO[who], plan, sp, cost, stride=1, sustained=True))
if __name__ == "__main__":
    t0 = time.time(); mode = sys.argv[1]
    wins = ["W1", "W2", "h3", "research", "validation"] if mode == "dev" else ["H6"]
    jobs = [(w, pl, sp, c) for c in ("stress", "base") for sp in wins for pl in ("pro50", "pro100") for w in WHO]
    jobs += [(w, "flex50", sp, c) for c in ("stress", "base") for sp in wins for w in ("baseline_B", "BOT-B-R4")]
    with Pool(4) as p: rows = p.map(job, jobs, chunksize=1)
    d = pd.DataFrame(rows); d.to_csv(f"{r6.OUT}/final_{'dev' if mode == 'dev' else 'h6'}_r6.csv", index=False)
    print("rows", len(d), "secs", round(time.time() - t0)); print("done")
