"""Round 6 plateau check (PREREG_R6 7d): one-step neighbours of a candidate. Usage: python3 r6_plateau.py A|B cid k100"""
import sys, json, copy, time
sys.path.insert(0, "research/t58_final_bots/engine")
import r6_search as RS, r6
from multiprocessing import Pool
OBJ, CID, K = sys.argv[1], sys.argv[2], float(sys.argv[3]); RS.OBJ = OBJ
pk0 = next(json.loads(l)["pk"] for l in open(f"{r6.OUT}/runs/r6_{OBJ}.jsonl") if json.loads(l)["cid"] == CID)
for k, v in pk0.get("fspec", {}).items(): pk0["fspec"][k] = [tuple(x) for x in v]
nb = []
def add(name, pk): pk = copy.deepcopy(pk); pk["cid"] = f"{CID}~{name}"; pk["k100"] = K; nb.append(pk)
for leg in list(pk0.get("fspec", {})):
    q = copy.deepcopy(pk0); del q["fspec"][leg]; add(f"drop:{leg}", q)
    for f in RS.ADM.get(leg, []):
        if tuple(f) not in [tuple(x) for x in pk0["fspec"][leg]]:
            q = copy.deepcopy(pk0); q["fspec"][leg] = [tuple(f)]; add(f"swap:{leg}:{f[0]}:{f[1]}", q)
for leg in pk0["legs"]:
    if leg in RS.ADM and leg not in pk0.get("fspec", {}):
        for f in RS.ADM[leg]:
            q = copy.deepcopy(pk0); q.setdefault("fspec", {})[leg] = [tuple(f)]; add(f"add:{leg}:{f[0]}:{f[1]}", q)
pol = pk0["policy"]
for kn, steps in (("r_eval", (0.87, 1.15)), ("r_fund", (0.83, 1.33)), ("fund_day_cap", (0.8, 1.4)), ("fund_day_stop", (0.75, 1.5))):
    for s in steps:
        q = copy.deepcopy(pk0); q["policy"][kn] = pol[kn] * s; add(f"{kn}x{s}", q)
for mo in (pk0["max_open"] - 1, pk0["max_open"] + 1):
    if mo >= 2: q = copy.deepcopy(pk0); q["max_open"] = mo; add(f"max_open{mo}", q)
def job(pk):
    pk = dict(pk); K_ = pk.pop("k100"); RS.K100 = (K_,); return RS.score_cfg(pk)
if __name__ == "__main__":
    t0 = time.time(); print("neighbours", len(nb), flush=True)
    with Pool(4) as p, open(f"{r6.OUT}/runs/r6_{OBJ}_plateau_{CID}.jsonl", "w") as out:
        for pk, res in p.imap_unordered(job, nb):
            out.write(json.dumps(dict(cid=pk["cid"], pk=pk, res=res), default=float) + "\n"); out.flush()
    print("secs", round(time.time() - t0)); print("done")
