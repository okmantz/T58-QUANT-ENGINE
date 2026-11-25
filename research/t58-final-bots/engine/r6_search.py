"""Round 6 search (research/PREREG_R6.md section 7 + addendum 2). Usage: python3 r6_search.py A|B N seed
Every config is logged to research/bot_trials_r6.csv; scores in research/runs/r6_<obj>.jsonl. Stress cost, stride 3, cells W1/W2 x pro50/pro100."""
import sys, json, copy, random, time, os
sys.path.insert(0, "research/t58_final_bots/engine")
import r6, picks_r4, numpy as np, pandas as pd
from multiprocessing import Pool
ADM = {'CDL_ES': [('vix_term', 'skip_low', 0.8354), ('va_dir', 'skip_inside', 0.0)], 'CDL_NQ': [('vix_chg5', 'skip_low', 0.9581), ('gap_abs', 'skip_low', 0.2054), ('va_dir', 'skip_inside', 0.0)], 'CORB_ES': [('gap_abs', 'skip_low', 0.1528)], 'GAP_GC': [('vix_chg5', 'skip_low', 0.9582)], 'IR_NQ': [('vix_term', 'skip_high', 0.9124), ('onr', 'skip_high', 0.7301), ('va_dir', 'skip_against', -1.0), ('va_dir', 'skip_inside', 0.0)], 'OD_NQ': [('tick', 'skip_low', -80.0), ('gap_abs', 'skip_low', 0.1944), ('va_dir', 'skip_inside', 0.0)], 'ORB15C_ES': [('vix_term', 'skip_low', 0.8412), ('gap_abs', 'skip_high', 0.4721), ('va_dir', 'skip_with', 1.0)], 'ORB15C_NQ': [('tick_dir', 'skip_low', -113.0), ('onr', 'skip_low', 0.4654)], 'ORB30T_NQ': [('vix_pct', 'skip_low', 0.6341), ('gap_abs', 'skip_low', 0.1738), ('va_dir', 'skip_inside', 0.0)], 'VWPB_NQ': [('tick', 'skip_low', -58.0), ('tick_dir', 'skip_low', -61.0), ('gap_abs', 'skip_low', 0.1591)]}
THEMES = {"gap": ("gap_abs", "skip_low"), "va": ("va_dir", "skip_inside")}
STRIDE = 3; K100 = (1.5, 1.75, 2.0)

def rand_fspec(rng, legs, p_none=0.5):
    fs = {}
    for k in legs:
        if k in ADM and rng.random() > p_none: fs[k] = [rng.choice(ADM[k])]
    return fs

def theme_fspec(legs, names):
    fs = {}
    for k in legs:
        for nm in names:
            for f in ADM.get(k, []):
                if (f[0], f[1]) == THEMES[nm]: fs.setdefault(k, []).append(f)
    return fs

def configs(obj, N, seed):
    rng = random.Random(seed); out = []
    if obj == "A":
        base = copy.deepcopy(picks_r4.BOT_A); legs = list(base["legs"])
        fixed = [{}, theme_fspec(legs, ["gap"]), theme_fspec(legs, ["va"]), theme_fspec(legs, ["gap", "va"]), {k: [ADM[k][0]] for k in legs if k in ADM}]
        while len(out) < N:
            fs = fixed[len(out)] if len(out) < len(fixed) else rand_fspec(rng, legs)
            for rm in ((1.0, 1.15) if len(out) >= len(fixed) else (1.0, 1.15, 1.3)):
                pk = copy.deepcopy(base); pk["fspec"] = fs; pk["policy"]["r_eval"] = base["policy"]["r_eval"] * rm; pk["rm"] = rm; out.append(pk)
    else:
        A, B = picks_r4.BOT_A, picks_r4.BOT_B; extra = [k for k in B["legs"] if k not in A["legs"]]
        while len(out) < N:
            u = rng.random()
            if u < 0.3: legs = dict(A["legs"])
            elif u < 0.5: legs = dict(B["legs"])
            else:
                legs = dict(A["legs"])
                for k in extra:
                    w = rng.choice((0, 0, 0.5, 1.0))
                    if w: legs[k] = w
            pol = copy.deepcopy(A["policy"])
            pol.update(r_eval=rng.choice((600, 800, 1000)), r_fund=rng.choice((250, 300, 400)), fund_day_cap=rng.choice((400, 500, 700)),
                       fund_day_stop=rng.choice((300, 400, 600)), fund_f_cush=rng.choice((0.2, 0.3, 0.4)))
            pk = dict(plan="pro", max_open=rng.choice((2, 3, 4)), spec={"one_per_inst": True}, legs=legs, policy=pol,
                      fspec=rand_fspec(rng, legs, 0.6) if rng.random() < 0.7 else {})
            if "ORB15C_ES" in legs and rng.random() < 0.5: pk["rspec"] = {"ORB15C_ES": {"eq": 10}}
            out.append(pk)
    for i, pk in enumerate(out): pk["cid"] = f"{obj}{i}"
    return out[:N] if obj == "B" else out

def score_cfg(pk):
    res = {}
    for plan, sp in r6.CELLS:
        ks = K100 if plan == "pro100" else (None,)
        for k in ks:
            q = dict(pk)
            if k: q["k100"] = k
            res[f"{plan}|{sp}|{k}"] = r6.run(q, plan, sp, "stress", stride=STRIDE, sustained=OBJ == "B")
    return pk, res

def base_rows():
    rows = {}
    for who in ("baseline_A", "baseline_B"):
        for plan, sp in r6.CELLS: rows[(who, plan, sp)] = r6.run(who, plan, sp, "stress", stride=STRIDE, sustained=True)
    return rows

if __name__ == "__main__":
    OBJ, N, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); t0 = time.time()
    bf = f"{r6.OUT}/runs/r6_base_stride{STRIDE}.json"
    if not os.path.exists(bf):
        br = base_rows(); json.dump({"|".join(k): v for k, v in br.items()}, open(bf, "w"), default=float)
    cf = configs(OBJ, N, seed)
    if OBJ == "B": cf = [dict(copy.deepcopy(picks_r4.BOT_A), cid="B-A4ref"), dict(copy.deepcopy(picks_r4.BOT_B), cid="B-B4ref")] + cf
    print(OBJ, "configs", len(cf), flush=True)
    led = f"{r6.OUT}/bot_trials_r6.csv"; new = not os.path.exists(led)
    with open(led, "a") as fh:
        if new: fh.write("ts,obj,cid,config\n")
        for pk in cf: fh.write(f"{time.strftime('%Y-%m-%d %H:%M')},{OBJ},{pk['cid']},\"{json.dumps(pk, default=str).replace(chr(34), chr(39))}\"\n")
    out = open(f"{r6.OUT}/runs/r6_{OBJ}.jsonl", "a")
    with Pool(4) as p:
        for j, (pk, res) in enumerate(p.imap_unordered(score_cfg, cf, chunksize=1)):
            out.write(json.dumps(dict(cid=pk["cid"], pk=pk, res=res), default=float) + "\n"); out.flush()
            if j % 20 == 0: print(j, round(time.time() - t0), flush=True)
    print("secs", round(time.time() - t0)); print("done")
