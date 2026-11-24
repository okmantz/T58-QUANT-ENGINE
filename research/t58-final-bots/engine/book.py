"""Trade books for the firm engine (T58 final bots, 2026-11-23).

gen(): run a repo strategy file through the repo's own engine (app.backtest.engine.run_backtest) at ZERO friction, one contract, no halts,
so each trade is just its signal: entry/exit time and price, stop distance, worst price. Costs are charged once, uniformly, in firm.py
(Spec 2.3 base and 1.5x stress), so nothing is counted twice.
points(): raw trades -> points book on the session matrices: clipped to 16:45 ET (Lucid flat time), MAE from 1m bars, holdout sealed.
merge(): several legs -> one chronological book with the repo bots' arbiter (max open, trades a day, one position per instrument,
optional ES/NQ hedge guard), leg weights in ``w``.
"""
from __future__ import annotations
import sys, pickle, re, tempfile
from dataclasses import replace
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import data as D

RAW = D.CACHE / "raw"; RAW.mkdir(parents=True, exist_ok=True)
STRAT = D.REPO / "strategies" / "python"


def gen(stem, inst, consts=None, tag=None, src=None, datafile=None):
    """Raw trades (list of dicts, ET-naive times) for strategy ``stem`` on ``inst``; cached. ``consts`` overrides module constants."""
    tag = tag or stem
    out = RAW / f"{tag}__{inst}.pkl"
    if out.exists():
        return _r3(pickle.load(out.open("rb")), tag, inst)
    sys.path.insert(0, str(D.REPO)); sys.path.insert(0, str(D.REPO / "scripts"))
    from app.backtest.engine import run_backtest
    from app.backtest.risk import RiskConfig
    from app.data.instrument_specs import apply_instrument_spec
    from app.data.importer import import_csv
    import bundle_research as br
    path = Path(src) if src else STRAT / f"{stem}.py"
    if consts:
        txt = path.read_text()
        for k, v in consts.items():
            txt, nsub = re.subn(rf"^{k}\s*=.*$", f"{k} = {v!r}", txt, flags=re.M)
            assert nsub == 1, k
        path = Path(tempfile.mkdtemp()) / (tag + ".py"); path.write_text(txt)
    df = import_csv(datafile or str(D.REPO / D.FILES[inst])).dataframe.reset_index(drop=True)
    risk = apply_instrument_spec(RiskConfig(), inst)
    risk = replace(risk, initial_balance=10_000_000.0, sizing_mode="fixed_contracts", fixed_contracts=1, commission_per_trade=0.0,
                   commission_per_contract=0.0, spread_pips=0.0, slippage_pips=0.0, max_account_drawdown_pct=None, daily_loss_limit_pct=None,
                   halt_on_breach=False, reset_on_breach=False)
    for k in ("micro_commission_per_contract",):
        if hasattr(risk, k): risk = replace(risk, **{k: 0.0})
    bt = run_backtest(df, br.load_strategy(path), risk, compute_stats=False)
    rows = []
    for t in bt.trades:
        et, xt = (pd.Timestamp(x) for x in (t.entry_time, t.exit_time))
        et = et.tz_convert("America/New_York").tz_localize(None) if et.tzinfo else et
        xt = xt.tz_convert("America/New_York").tz_localize(None) if xt.tzinfo else xt
        rows.append(dict(entry=et, exit=xt, dir=int(t.direction), ep=float(t.entry_price), xp=float(t.exit_price),
                         risk=float(t.initial_risk or np.nan), worst=float(t.worst_price) if t.worst_price is not None else np.nan,
                         why=t.exit_reason))
    pickle.dump(rows, out.open("wb"))
    return _r3(rows, tag, inst)


def _r3(rows, tag, inst):
    """Round 3: old-pack trades before H2 + trades generated on the spliced file inside H2 (data_h2.py). Old-pack ES/GC files run past
    2026-03 and their trades there are dropped: H2 uses Owen's 2026-03..11 pack only."""
    if not D.R3 or tag.endswith("__cmb"):
        return rows
    keep = [r for r in rows if _sess([r["entry"]])[0][0] < D.HOLD_FROM]
    h2 = RAW / f"{tag}__{inst}__h2.pkl"
    return keep + (pickle.load(h2.open("rb")) if h2.exists() else [])


_M = {}
def mats(inst, sealed=False):
    k = (inst, sealed)
    if k not in _M:
        _M[k] = D.load(inst, sealed=sealed)
    return _M[k]


def _sess(ts):
    """ET-naive timestamps -> (session day datetime64[D], minute index since 18:00 ET)."""
    ts = pd.DatetimeIndex(ts)
    mod = ts.hour * 60 + ts.minute
    m = (np.asarray(mod) - 1080) % 1440
    cal = ts.normalize()
    sd = np.where(np.asarray(mod) >= 1080, cal + pd.Timedelta(days=1), cal)
    return pd.DatetimeIndex(sd).values.astype("datetime64[D]"), m


STOP_REPAIRS = []


def points(rows, inst, sealed=False, name=None):
    """Points book: dict of arrays sorted by entry. Trades entered at/after 16:45 ET or on non-session days are dropped; exits after 16:45
    are forced at the 16:44 close (Lucid flat rule). Holdout trades (session day >= 2025-09-01) are dropped unless sealed=True."""
    M = mats(inst, sealed)
    days = M["days"]; H, L, C = M["H"], M["L"], M["C"]
    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values("entry").reset_index(drop=True)
    sd, me = _sess(df.entry)
    xd, mx = _sess(df.exit)
    di = np.searchsorted(days, sd)
    ok = (di < len(days)) & (me < D.NMIN)
    ok &= np.where(di < len(days), days[np.minimum(di, len(days) - 1)] == sd, False)
    if not sealed:
        ok &= sd < D.HOLD_FROM
    df, sd, me, xd, mx, di = df[ok].reset_index(drop=True), sd[ok], me[ok], xd[ok], mx[ok], di[ok]
    clip = (xd > sd) | (mx >= D.NMIN)
    mx = np.where(clip, D.NMIN - 1, mx)
    n = len(df)
    xp = np.where(clip, C[di, D.NMIN - 1], df.xp.to_numpy())
    d = df.dir.to_numpy()
    mae = np.zeros(n); keep = np.ones(n, bool)
    for k in range(n):
        a, b = int(me[k]), int(mx[k])
        if b < a: b = a
        if d[k] > 0:
            w = min(L[di[k], a:b + 1].min(), df.ep[k])
            mae[k] = df.ep[k] - w
        else:
            w = max(H[di[k], a:b + 1].max(), df.ep[k])
            mae[k] = w - df.ep[k]
    risk = df.risk.to_numpy()
    # Stop-in-a-data-hole repair (round 2, logged in research/gate_ladder_log.md). The 1-minute pack has holes (NQ 2020-03-10 15:00-16:00,
    # NQ/ES 2022-09-21 14:00-14:10) that data.py forward-fills; the repo then fills a stop at the first real bar after the hole, far past
    # the stop. A stop whose first touching bar comes straight after a hole is filled at the stop; a real gap (no hole) keeps the bar open.
    O = M.get("O")
    global STOP_REPAIRS
    for k in range(n):
        if not np.isfinite(risk[k]) or risk[k] <= 0:
            continue
        a, b = int(me[k]), int(mx[k])
        if b < a: continue
        stp = df.ep[k] - d[k] * risk[k]
        seg = L[di[k], a:b + 1] <= stp if d[k] > 0 else H[di[k], a:b + 1] >= stp
        if not seg.any(): continue
        j = a + int(np.argmax(seg))
        Vd = M["V"][di[k]]
        if j > a and Vd[j - 1] == 0 and Vd[j] > 0:   # first real bar after a data hole (missing bars forward-filled): the market traded
            fill = stp                                # through the stop inside the hole, so fill at the stop (costs add the slippage)
        else:
            op = O[di[k], j] if O is not None else stp
            fill = min(stp, op) if d[k] > 0 else max(stp, op)
        if d[k] * (fill - xp[k]) > 1e-9:          # repo exit worse than the first stop touch: repair
            xp[k] = fill; mx[k] = j; clip[k] = False; STOP_REPAIRS.append((name, str(sd[k]), float(d[k] * (fill - df.ep[k]))))
    pts = d * (xp - df.ep.to_numpy())
    bad = ~np.isfinite(risk) | (risk <= 0)
    risk = np.where(bad, np.maximum(mae, D.TICK[inst] * 4), risk)       # no stop recorded: size off the realised MAE floor (flagged)
    mae = np.maximum(mae, np.maximum(-pts, 0.0))
    ent = sd.astype("datetime64[m]") - np.timedelta64(360, "m") + me.astype("timedelta64[m]")
    ex = sd.astype("datetime64[m]") - np.timedelta64(360, "m") + mx.astype("timedelta64[m]") + np.timedelta64(1, "m")
    ex = np.maximum(ex, ent + np.timedelta64(1, "m"))
    return dict(entry=ent, exit=ex, day=sd, inst=np.array([inst] * n), pts=pts.astype(float), risk_pts=risk.astype(float),
                mae_pts=mae.astype(float), dir=d, clip=clip, nostop=bad, w=np.ones(n), leg=np.array([name or "?"] * n))


KEYS = ("entry", "exit", "day", "inst", "pts", "risk_pts", "mae_pts", "dir", "clip", "nostop", "w", "leg")


def merge(legs, max_open=2, max_per_day=6, one_per_inst=True, hedge_guard=False):
    """legs: list of (book, weight, priority). Arbiter at signal level, in entry order (same minute: lower priority number first)."""
    parts = []
    for b, w, pr in legs:
        if b is None: continue
        x = {k: b[k] for k in KEYS}; x["w"] = b["w"] * w; x["prio"] = np.full(len(b["day"]), pr)
        parts.append(x)
    cat = {k: np.concatenate([p[k] for p in parts]) for k in KEYS + ("prio",)}
    o = np.lexsort((cat["prio"], cat["entry"]))
    cat = {k: v[o] for k, v in cat.items()}
    keep = np.zeros(len(o), bool); open_ = []; cnt = {}
    for k in range(len(o)):
        t = cat["entry"][k]
        open_ = [x for x in open_ if x[0] > t]
        dd = cat["day"][k]
        if cnt.get(dd, 0) >= max_per_day or len(open_) >= max_open:
            continue
        ins = cat["inst"][k]
        if one_per_inst and any(x[1] == ins for x in open_):
            continue
        if hedge_guard and ins in ("ES", "NQ") and any(x[1] in ("ES", "NQ") and x[1] != ins and x[2] != cat["dir"][k] for x in open_):
            continue
        keep[k] = True; open_.append((cat["exit"][k], ins, cat["dir"][k])); cnt[dd] = cnt.get(dd, 0) + 1
    return {k: v[keep] for k, v in cat.items()}
