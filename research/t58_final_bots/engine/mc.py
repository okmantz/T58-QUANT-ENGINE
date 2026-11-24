"""Phase 5 Monte Carlo through the prop-barrier simulator (code/firm.py), frozen picks vs baseline, identical code.
Usage: python3 mc.py [paths=10000] [r2]  -> research/mc.csv (round 1) or research/mc_r2.csv (BOT-B-R2 only)

Resampling unit = one session day of the bot's booked trades (all trades of that day kept together, so intraday overlap,
the max-open arbiter and the day stop behave as in the real book). Each synthetic path is 70 sessions laid on consecutive
weekdays; trade timestamps are shifted to the new date. Two resamplers:
  reshuffle: days drawn i.i.d. with replacement (destroys serial dependence; the "trade reshuffle" test)
  block:     moving blocks of 10 consecutive sessions (keeps volatility clustering and regime runs)
Two pools: FULL (2020-01-01 .. 2026-03-01, research + validation + holdout) and OOS (2024-01-01 .. 2026-03-01, validation +
holdout only, i.e. the recent regime). Every path is scored at stress cost: eval P(pass <= 30d), days to pass, bust; funded
P(first payout <= 30d), days to payout; 90-day lifecycle EV net of fee and resets (same rules as score.py)."""
import sys, numpy as np, pandas as pd
from multiprocessing import Pool
sys.path.insert(0, "research/t58_final_bots/engine")
import search as S, firm, score, picks, picks_r2, filters, baseline as BL
from policy import Pol
OUT = "research/t58_final_bots/research"
POOLS = {"FULL": ("2020-01-01", "2026-03-01"), "OOS": ("2024-01-01", "2026-03-01")}
NS, BLK, D0 = 70, 10, np.datetime64("2030-01-07", "D")          # 2030-01-07 is a Monday
NEWD = np.busday_offset(D0, np.arange(NS), roll="forward")
D1 = np.timedelta64(1, "D")

R4 = len(sys.argv) > 2 and sys.argv[2] == "r4"   # round 4: run with T58_R4=1; dev pools 2020-01..2026-11-20, plus H3 once read
R3 = len(sys.argv) > 2 and sys.argv[2] == "r3"
R5 = len(sys.argv) > 2 and sys.argv[2] == "r5"   # round 5: run with T58_R5=1; no holdout left, pools are already-read data
if R5:
    import os
    assert os.environ.get("T58_R5") == "1", "set T58_R5=1"
    POOLS = {"FULL": ("2016-11-24", "2026-11-21"), "OOS": ("2024-01-01", "2026-11-21")}
elif R4:
    import os
    assert os.environ.get("T58_R4") == "1", "set T58_R4=1"
    POOLS = {"FULL": ("2020-01-01", "2026-11-21"), "OOS": ("2024-01-01", "2026-11-21")}
    if os.path.exists(f"{OUT}/final_hold_r4.csv"):  # H3 already read once by final_score_r4.py hold; MC on it chooses nothing
        POOLS["H3"] = ("2016-11-24", "2020-01-02")
if R3:                       # round 3: pools stop before the sealed Mar-Nov 2026 holdout, so the MC never touches it again
    POOLS = {"FULL": ("2020-01-01", "2026-03-02"), "OOS": ("2024-01-01", "2026-03-02")}

def make(who, planname, cost):
    p = firm.Plan(cost=cost) if planname == "pro50" else firm.Plan.flex50(cost=cost)
    if R5:
        import copy, r5_confirm as C
        bk, pol0 = C.r5.book_pol(C.WHO[who][0], p, sealed=False)
        return bk, (lambda: copy.deepcopy(pol0)), p
    if R4:
        import copy, r4, final_score_r4 as F, legs as LG
        port = who.endswith("-port")
        if port: LG.use_ports(); S._B.clear()
        bk, pol0 = r4.book_pol(F.WHO[who[:-5] if port else who], p, sealed="H3" in POOLS)
        return bk, (lambda: copy.deepcopy(pol0)), p
    if R3:
        import copy, final_score_r3 as F
        bk, pol0 = F.book_pol(who, p, False)
        return bk, (lambda: copy.deepcopy(pol0)), p
    if who.startswith("baseline"):
        obj = who[-1]; bk = BL.bot_book(BL.LEGS_A if obj == "A" else BL.LEGS_B, sealed=True); pol = lambda: BL.policy(obj, BL.lite(p))
    elif who == "BOT-B-R2":
        pk = picks_r2.BOT_B
        bk = filters.bot(pk["legs"], max_open=pk["max_open"], spec=pk["spec"], sealed=True); pol = lambda: Pol(**pk["policy"])
    else:
        pk = picks.BOT_A if who == "BOT-A" else picks.BOT_B
        bk = S.bot(pk["legs"], max_open=pk["max_open"], sealed=True); pol = lambda: Pol(**pk["policy"])
    return bk, pol, p

def life(sb, pol, p, L=90):
    """Same rules as score.life_block for one start at D0."""
    t, end, fees, pays = D0, D0 + np.timedelta64(L, "D"), p.fee, []
    while t < end:
        o = firm.run(sb, t, int((end - t) / D1), p, pol, stop_at_pass=False, stall=score.STALL)
        pays += [amt for _, amt in o["payouts"]]
        bd = next((x for x in (o["breach_day"], o["fund_breach_day"], o["stall_day"]) if x is not None), None)
        if bd is None: break
        t = t + np.timedelta64(bd + 1, "D")
        if t < end: fees += p.reset
    return p.split * sum(pays) - fees

def job(a):
    who, planname, pool, method, n, seed = a
    bk, mkpol, p = make(who, planname, "stress")
    x, y = (np.datetime64(v, "D") for v in POOLS[pool])
    m = (bk["day"] >= x) & (bk["day"] < y); bk = {k: v[m] for k, v in bk.items()}
    sess = np.arange(x, y, D1); sess = sess[np.is_busday(sess)]          # every weekday is a session, traded or not
    idx = {d: np.flatnonzero(bk["day"] == d) for d in np.unique(bk["day"])}
    rng = np.random.default_rng(seed); E = len(sess)
    res = []
    for _ in range(n):
        if method == "reshuffle":
            src = sess[rng.integers(0, E, NS)]
        else:
            st = rng.integers(0, E - BLK, NS // BLK + 1); src = np.concatenate([sess[s:s + BLK] for s in st])[:NS]
        parts, shifts = [], []
        for j, d in enumerate(src):
            ii = idx.get(d)
            if ii is not None: parts.append(ii); shifts.append(np.full(len(ii), (NEWD[j] - d) / D1))
        if not parts:
            res.append((0, np.nan, 0, 0, np.nan, -p.fee)); continue
        ii = np.concatenate(parts); sh = np.concatenate(shifts).astype("timedelta64[D]")
        sb = {k: v[ii] for k, v in bk.items()}
        sb["day"] = sb["day"] + sh; sb["entry"] = sb["entry"] + sh.astype("timedelta64[m]"); sb["exit"] = sb["exit"] + sh.astype("timedelta64[m]")
        o = np.lexsort((sb["prio"], sb["entry"])); sb = {k: v[o] for k, v in sb.items()}
        pol = score._pol(mkpol(), sb)
        e = firm.run(sb, D0, 30, p, pol)
        f = firm.run(sb, D0, 30, p, pol, phase="funded")
        ev = life(sb, pol, p)
        res.append((e["pass_day"] is not None, (e["pass_day"] + 1) if e["pass_day"] is not None else np.nan,
                    e["pass_day"] is None and e["breach_day"] is not None,
                    bool(f["payouts"]), (f["payouts"][0][0] + 1) if f["payouts"] else np.nan, ev))
    return who, planname, pool, method, res

if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
    combos = [("baseline_A", "pro50"), ("BOT-A", "pro50"), ("baseline_B", "flex50"), ("BOT-B", "flex50")]
    if len(sys.argv) > 2 and sys.argv[2] == "r2":                 # round 2: only the new finalist (its holdout already read once)
        combos = [("BOT-B-R2", "flex50")]
    if R3:
        combos = [("baseline_A", "pro50"), ("BOT-A-R3", "pro50"), ("BOT-A-R3-port", "pro50"),
                  ("baseline_B", "flex50"), ("BOT-B-R3", "flex50"), ("BOT-B-R3-port", "flex50")]
    if R4:
        combos = [("baseline_A", "pro50"), ("BOT-A-R3", "pro50"), ("BOT-A-R4", "pro50"), ("BOT-A-R4-port", "pro50"),
                  ("baseline_B", "flex50"), ("BOT-B-R3", "flex50"), ("BOT-B-R4", "flex50"), ("BOT-B-R4-port", "flex50")]
    if R5:
        combos = [("baseline_A", "pro50"), ("BOT-A-R4", "pro50"), ("baseline_B", "flex50"), ("BOT-B-R4", "flex50"), ("BOT-B-R5", "flex50")]
    CH = 8
    jobs = [(w, pl, po, me, N // CH, 1000 * c + k) for k, (w, pl) in enumerate(combos) for po in POOLS for me in ("reshuffle", "block")
            for c in range(CH)]
    if R4:   # port jobs switch legs.py to the port files for the whole worker, so they get their own pool
        outs = []
        for grp in ([j for j in jobs if not j[0].endswith("-port")], [j for j in jobs if j[0].endswith("-port")]):
            with Pool(4) as pool: outs += pool.map(job, grp, chunksize=1)
    else:
        with Pool(4) as pool:
            outs = pool.map(job, jobs)
    agg = {}
    for who, pl, po, me, r in outs: agg.setdefault((who, pl, po, me), []).extend(r)
    rows = []
    for (who, pl, po, me), r in agg.items():
        a = np.array(r, float); n = len(a)
        se = lambda q: np.sqrt(q * (1 - q) / n)
        rows.append(dict(bot=who, plan=pl, pool=po, method=me, paths=n, p_pass=a[:, 0].mean(), p_pass_se=se(a[:, 0].mean()),
                         med_days_pass=np.nanmedian(a[:, 1]) if a[:, 0].any() else np.nan, bust=a[:, 2].mean(),
                         p_payout=a[:, 3].mean(), med_days_payout=np.nanmedian(a[:, 4]) if a[:, 3].any() else np.nan,
                         ev90=np.nanmean(a[:, 5]), ev90_p5=np.nanpercentile(a[:, 5], 5), ev90_p95=np.nanpercentile(a[:, 5], 95)))
    pd.DataFrame(rows).to_csv(f"{OUT}/mc{('_' + sys.argv[2]) if len(sys.argv) > 2 else ''}.csv", index=False)
    print(pd.DataFrame(rows).to_string())
