"""Round 3 search (research + extended validation 2024-01..2026-03, stress cost, stride 2), aimed at the cells the round-2 picks still lose:
B: trade count (trades_pm) without giving back anything else. A: PF / expectancy R / Sharpe / Sortino at stress cost.
Usage: T58_R3=1 python3 run_r3.py A|B -> research/runs/r3_<obj>.pkl ; every row also goes to research/bot_trials_r3.csv."""
import sys, itertools, pickle, json, time, os
from multiprocessing import Pool
import pandas as pd
sys.path.insert(0, "research/t58_final_bots/engine")
import data as D; assert D.R3
import search as S, score, firm, filters, picks, picks_r2, confirm as C
from policy import Pol
OUT = "research/t58_final_bots/research"
def variants(obj):
    if obj == "B":
        b = picks_r2.BOT_B
        extras = [{}, {"OD_NQ": .25}, {"OD_NQ": .5}, {"CORB_ES": .5}, {"GAP_GC": .5}, {"ORB15N_NQ": .5}, {"TOD10_NQ": .5}, {"CDLB_NQ": .5},
                  {"OD_NQ": .25, "CORB_ES": .5}, {"OD_NQ": .25, "GAP_GC": .5}, {"CORB_ES": .5, "GAP_GC": .5}, {"OD_NQ": .25, "CORB_ES": .5, "GAP_GC": .5},
                  {"OD_ES": .5}, {"OD_ES": .5, "OD_NQ": .25}]
        for ex, mo, opi, fdc, fx, ds in itertools.product(extras, (3, 4), (True, False), (200, 260, None), (3.0, None), (220, 300)):
            legs = dict(b["legs"], **ex); spec = dict(b["spec"], one_per_inst=opi)
            pol = dict(b["policy"], fund_day_cap=fdc, floor_x=fx, day_stop=ds, fund_day_stop=ds)
            yield dict(plan="flex50", max_open=mo, spec=spec, legs=legs, policy=pol)
    else:
        a = picks.BOT_A
        extras = [{}, {"OD_ES": .25}, {"OD_ES": .5}, {"PDLB_GC": .5}, {"PDLB_GC": 1.0}, {"VWPB_NQ": .5}, {"ORB30T_NQ": .5},
                  {"OD_ES": .25, "PDLB_GC": .5}, {"PDLB_GC": .5, "VWPB_NQ": .5}, {"OD_NQ": 0}, {"OD_NQ": 0, "PDLB_GC": .5}]
        for ex, mo, sp, re_, dl, ds in itertools.product(extras, (2, 3), (None, {"crash": .5}), (600, 800, 1000), (1200, 1600), (500, 650)):
            legs = {k: v for k, v in dict(a["legs"], **ex).items() if v > 0}
            pol = dict(a["policy"], r_eval=re_, dd_lvl=dl, day_stop=ds)
            yield dict(plan="pro50", max_open=mo, spec=sp, legs=legs, policy=pol)
def variants_b2():
    """Stage 2 (after r3_B): the stage-1 survivors all lose research trade count only; stack more legs at small weight."""
    b = picks_r2.BOT_B
    base_ex = {"OD_NQ": .25, "CORB_ES": .5, "GAP_GC": .5}
    adds = [{}, {"ORB15N_NQ": .25}, {"ORB15N_NQ": .5}, {"TOD10_NQ": .25}, {"CDLB_NQ": .25}, {"CDLB_NQ": .5}, {"ORB15N_NQ": .25, "TOD10_NQ": .25},
            {"ORB15N_NQ": .25, "CDLB_NQ": .25}, {"ORB15N_NQ": .25, "CDLB_NQ": .25, "TOD10_NQ": .25}, {"OD_NQ": .5}]
    for ad, mo, fdc, ds, dl, rf in itertools.product(adds, (3, 4), (200, 260), (300, 400), (400, 300), (250, 200)):
        legs = {**b["legs"], **base_ex, **ad}; spec = dict(b["spec"], one_per_inst=False)
        pol = dict(b["policy"], fund_day_cap=fdc, floor_x=3.0, day_stop=ds, fund_day_stop=ds, dd_lvl=dl, r_fund=rf)
        yield dict(plan="flex50", max_open=mo, spec=spec, legs=legs, policy=pol)
def variants_a2():
    """Stage 2 for A (after r3_A): best stage-1 = R1 A + PDLB_GC .5, r_eval 1000, dd_lvl 1200; still short on research PF and the funded
    metrics (days to payout, consistency blocks) and validation exp_R. Tune the funded half and the eval risk around it."""
    a = picks.BOT_A
    for re_, dl, rf, ck, fdc, ds, pw, od in itertools.product((1000, 1200), (1000, 1200), (200, 300), (0.4, 0.55), (None, 500), (650, 800), (0.5, 0.75), (0, 0.25)):
        legs = {k: v for k, v in dict(a["legs"], PDLB_GC=pw, OD_ES=od).items() if v > 0}
        pol = dict(a["policy"], r_eval=re_, dd_lvl=dl, r_fund=rf, cons_k=ck, fund_day_cap=fdc, day_stop=ds)
        yield dict(plan="pro50", max_open=2, spec=None, legs=legs, policy=pol)
def job(pk):
    obj = "B" if pk["plan"] == "flex50" else "A"; sus = obj == "B"
    bk = filters.bot(pk["legs"], max_open=pk["max_open"], spec=pk["spec"]); pol = Pol(**pk["policy"])
    out = {}
    for sp, (x, y) in (("research", S.RES), ("validation", S.VAL)):
        p = firm.Plan(cost="stress") if obj == "A" else firm.Plan.flex50(cost="stress")
        r = score.full(bk, pol, p, x, y, stride=2)
        if sus: r.update(score.sustained_block(bk, pol, p, x, y))
        out[sp] = r
    return pk, out
if __name__ == "__main__":
    obj = sys.argv[1]; tag = obj
    if obj == "B2": obj, V = "B", list(variants_b2())
    elif obj == "A2": obj, V = "A", list(variants_a2())
    else: V = list(variants(obj))
    sus = obj == "B"; print(len(V), flush=True)
    base = C.base_all("flex50" if sus else "pro50", obj)
    with Pool(4) as pool: res = pool.map(job, V, chunksize=4)
    pickle.dump(res, open(f"{OUT}/runs/r3_{tag}.pkl", "wb"))
    rows = []
    for pk, o in res:
        bad = {sp: S.beats(o[sp], base[(sp, "stress")], sustained=sus) for sp in o}
        rows.append(dict(obj=obj, pick=json.dumps(pk), nbad=sum(len(v) for v in bad.values()), bad_res=",".join(bad["research"]), bad_val=",".join(bad["validation"]),
                         **{f"{sp}_{k}": o[sp].get(k) for sp in o for k in ("p_pass", "p_payout", "f90_paid", "pf", "sharpe", "max_dd", "trades_pm")}))
    df = pd.DataFrame(rows).assign(ts=time.strftime("%Y-%m-%d %H:%M"), cost="stress", stride=2)
    f = f"{OUT}/bot_trials_r3.csv"; df.to_csv(f, mode="a", header=not os.path.exists(f), index=False)
    df = df.sort_values("nbad"); print(df.nbad.value_counts().sort_index().to_dict())
    print((df.bad_res + "|" + df.bad_val).str.split(r"[,|]").explode().value_counts().head(12).to_dict())
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
    print(df.head(12).drop(columns=["pick"]).to_string())
