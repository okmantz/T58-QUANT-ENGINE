"""Bot builder: everything the "New bot" wizard needs, as plain functions with no Flask in them.

  strategy_catalog()    every strategy a bot can follow (library files), with instrument, timeframe, a one-line idea and whether the bot engine can run it
  RISK_STYLES / style_governor()   Conservative / Balanced / Aggressive risk settings for each of the three goals (A, B, NET)
  GOVERNOR_FIELDS       the advanced risk knobs, each with a plain-words label, help text, range and the goals it applies to
  build_config()        a posted form (name, goal, strategies, risk, limits, account) -> a validated ``BotConfig`` plus errors and warnings
  describe()            the plain-words summary shown before the bot is created ("risks $500 per trade, 25% of your loss limit ...")
  add_strategy()        save a pasted / uploaded strategy file into the library so it shows up in the catalog

Numbers outside their allowed range are clamped and reported as warnings (never a dead end); problems that make a bot unrunnable
(no strategies, an unknown file, a daily-bar strategy, a broker account with no account picked) are errors.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any, Optional

from app.bots.models import AccountLink, BotConfig, BotLeg
from app.bots.risk_governor import GovernorConfig
from app.bots.signals import STRATEGIES_DIR
from app.objectives import OBJECTIVES, SPECS, normalize_objective

MAX_LEGS = 8
ALLOWED_SUFFIXES = (".py", ".pine", ".mq5")
INSTRUMENTS = {
    "NQ": {"name": "Nasdaq-100 futures", "micro": "MNQ"},
    "ES": {"name": "S&P 500 futures", "micro": "MES"},
    "GC": {"name": "Gold futures", "micro": "MGC"},
}
RISK_STYLES = ("conservative", "balanced", "aggressive")
STYLE_LABELS = {
    "conservative": "Conservative: smaller size, slower, much less likely to breach",
    "balanced": "Balanced: the shipped calibration for this goal",
    "aggressive": "Aggressive: bigger size, faster, a real chance of breaching",
}

# --------------------------------------------------------------------------------------------------------------- risk styles
_STYLE_KW: dict[str, dict[str, dict]] = {
    "A": {
        "conservative": dict(base_risk_pct=0.5, early_mult=1.0, mid_mult=0.9, late_mult=0.5, need_risk_mult=1.0, day_stop_frac=0.30, cushion_risk_frac=0.5),
        "balanced": dict(base_risk_pct=1.0, early_mult=1.0, mid_mult=1.0, late_mult=0.7, need_risk_mult=1.0, day_stop_frac=0.40, cushion_risk_frac=None),
        "aggressive": dict(base_risk_pct=1.5, early_mult=1.0, mid_mult=1.0, late_mult=1.0, need_risk_mult=None, day_stop_frac=0.55, cushion_risk_frac=None),
    },
    "B": {
        "conservative": dict(base_risk_pct=0.5, cushion_risk_frac=0.15, day_stop_frac=0.25, funded_mult=0.8),
        "balanced": dict(base_risk_pct=1.0, cushion_risk_frac=0.25, day_stop_frac=0.30, funded_mult=1.0),
        "aggressive": dict(base_risk_pct=1.0, cushion_risk_frac=0.40, day_stop_frac=0.40, funded_mult=1.0),
    },
    "NET": {
        "conservative": dict(base_risk_pct=0.5, compounding=True, dd_throttle_tol_pct=6.0, min_risk_dollars=1.0, cushion_risk_frac=None),
        "balanced": dict(base_risk_pct=1.0, compounding=True, dd_throttle_tol_pct=10.0, min_risk_dollars=1.0, cushion_risk_frac=None),
        "aggressive": dict(base_risk_pct=1.5, compounding=True, dd_throttle_tol_pct=15.0, min_risk_dollars=1.0, cushion_risk_frac=None),
    },
}


def style_governor(objective: str, style: str = "balanced") -> GovernorConfig:
    """The governor for a goal and a risk style (unknown style -> balanced)."""
    o = normalize_objective(objective, default="A")
    o = o if o in OBJECTIVES else "A"
    st = style if style in RISK_STYLES else "balanced"
    return GovernorConfig(objective=o, **_STYLE_KW[o][st])


# ---------------------------------------------------------------------------------------------------------- governor field spec
# kind: pct = percent number, frac = 0..1 share, mult = multiplier, usd = dollars, int, bool. optional: blank means "off".
GOVERNOR_FIELDS: list[dict] = [
    dict(key="base_risk_pct", label="Risk per trade (% of account)", kind="pct", lo=0.05, hi=3.0, step=0.05, goals=["A", "B", "NET"], optional=False, advanced=False,
         help="How much one full-size trade may lose at its stop. The bot scales this up and down on its own with progress, room left and drawdown."),
    dict(key="day_stop_frac", label="Stop for the day after losing (share of the daily limit)", kind="frac", lo=0.05, hi=1.0, step=0.05, goals=["A", "B"], optional=False, advanced=False,
         help="0.40 means: once today's realised loss reaches 40% of the firm's daily limit, no more entries today."),
    dict(key="cushion_risk_frac", label="Never risk more than this share of the room above the loss floor", kind="frac", lo=0.05, hi=1.0, step=0.05, goals=["A", "B", "NET"], optional=True, advanced=False,
         help="0.25 means a trade can never risk more than a quarter of the money between you and the breach line. Blank = no cap."),
    dict(key="dd_throttle_tol_pct", label="Shrink size as drawdown approaches (% of equity)", kind="pct", lo=2.0, hi=40.0, step=1.0, goals=["NET"], optional=False, advanced=False,
         help="Size falls steadily to its minimum as the drawdown from the equity peak reaches this percentage."),
    dict(key="compounding", label="Compound: size follows equity", kind="bool", goals=["NET"], optional=False, advanced=False,
         help="On: risk is a share of current equity (winners grow size, losers shrink it). Off: a share of the starting account."),
    dict(key="day_profit_lock_frac", label="Stop for the day after winning (share of the target / payout goal)", kind="frac", lo=0.05, hi=1.5, step=0.05, goals=["A", "B"], optional=True, advanced=True,
         help="Bank a great day instead of giving it back. Useful for consistency rules that cap how much one day may contribute. Blank = off."),
    dict(key="early_mult", label="Size multiplier: early (progress below the first mark)", kind="mult", lo=0.1, hi=1.5, step=0.05, goals=["A", "B"], optional=False, advanced=True,
         help="Applied while progress to the target (or payout goal) is below the first mark."),
    dict(key="mid_mult", label="Size multiplier: middle", kind="mult", lo=0.1, hi=1.5, step=0.05, goals=["A", "B"], optional=False, advanced=True,
         help="Applied between the first and second marks."),
    dict(key="late_mult", label="Size multiplier: late (close to the target)", kind="mult", lo=0.1, hi=1.5, step=0.05, goals=["A", "B"], optional=False, advanced=True,
         help="Trim size as the target nears: the last dollars are not worth a breach."),
    dict(key="p1", label="First progress mark", kind="frac", lo=0.05, hi=0.9, step=0.05, goals=["A", "B"], optional=False, advanced=True,
         help="Share of the target made before the 'middle' multiplier starts."),
    dict(key="p2", label="Second progress mark", kind="frac", lo=0.1, hi=0.98, step=0.05, goals=["A", "B"], optional=False, advanced=True,
         help="Share of the target made before the 'late' multiplier starts. Must be above the first mark."),
    dict(key="low_cushion_frac", label="Low-room line (share of the loss limit)", kind="frac", lo=0.1, hi=0.9, step=0.05, goals=["A", "B"], optional=False, advanced=True,
         help="Below this much room above the loss floor, size is cut by the low-room multiplier."),
    dict(key="low_cushion_mult", label="Low-room size multiplier", kind="mult", lo=0.1, hi=1.0, step=0.05, goals=["A", "B"], optional=False, advanced=True,
         help="Applied under the low-room line."),
    dict(key="crit_cushion_frac", label="Critical-room line (share of the loss limit)", kind="frac", lo=0.05, hi=0.6, step=0.05, goals=["A", "B"], optional=False, advanced=True,
         help="Below this the account is close to breaching and size is cut hard."),
    dict(key="crit_cushion_mult", label="Critical-room size multiplier", kind="mult", lo=0.05, hi=1.0, step=0.05, goals=["A", "B"], optional=False, advanced=True,
         help="Applied under the critical-room line."),
    dict(key="need_risk_mult", label="Cap risk at this multiple of what is left to reach the target", kind="mult", lo=0.2, hi=3.0, step=0.1, goals=["A"], optional=True, advanced=True,
         help="1.0 means: never risk more than the profit still needed to pass. Blank = off."),
    dict(key="funded_mult", label="Size multiplier once funded", kind="mult", lo=0.1, hi=1.5, step=0.05, goals=["A", "B"], optional=False, advanced=True,
         help="After the evaluation is passed the bot can trade smaller: payouts reward staying alive."),
    dict(key="min_mult", label="Smallest size multiplier (drawdown throttle floor)", kind="mult", lo=0.05, hi=1.0, step=0.05, goals=["NET"], optional=False, advanced=True,
         help="The drawdown throttle never shrinks size below this share of normal."),
    dict(key="max_mult", label="Largest size multiplier", kind="mult", lo=0.5, hi=5.0, step=0.1, goals=["A", "B", "NET"], optional=False, advanced=True,
         help="Upper cap on any size multiplier."),
    dict(key="min_risk_dollars", label="Skip a trade if its risk is below ($)", kind="usd", lo=1.0, hi=500.0, step=1.0, goals=["A", "B", "NET"], optional=False, advanced=True,
         help="About the cost of one micro contract at a typical stop. Below this the trade is skipped rather than rounded up."),
    dict(key="max_risk_dollars", label="Never risk more than ($) on one trade", kind="usd", lo=25.0, hi=50_000.0, step=25.0, goals=["A", "B", "NET"], optional=True, advanced=True,
         help="A hard dollar ceiling per trade. Blank = no ceiling."),
]
_FIELD = {f["key"]: f for f in GOVERNOR_FIELDS}


def fields_for(goal: str) -> list[dict]:
    return [f for f in GOVERNOR_FIELDS if goal in f["goals"]]


# -------------------------------------------------------------------------------------------------------------- strategy catalog
_TF_PY = re.compile(r"^\s*TIMEFRAME\s*=\s*[\"']([^\"']+)[\"']", re.M)
_TF_HDR = re.compile(r"T58_TIMEFRAME\s*=\s*(\S+)")
_INSTR = re.compile(r"(?<![A-Za-z])(MNQ|MES|MGC|NQ|ES|GC)\s*1?!?(?![A-Za-z])")
_CATALOG_CACHE: dict = {}


def _tf_label(text: str) -> str:
    m = _TF_PY.search(text) or _TF_HDR.search(text)
    return (m.group(1).strip().lower() if m else "")


def _is_daily(tf: str) -> bool:
    return tf.endswith("d") or tf.endswith("w") or tf in ("d", "w", "1440", "daily")


def _first_line(text: str, suffix: str) -> str:
    if suffix == ".py":
        m = re.search(r'^\s*(?:r|u)?("""|\'\'\')(.*?)\1', text, re.S)
        if m:
            lines = [ln.strip() for ln in m.group(2).strip().splitlines() if ln.strip()]
            for ln in lines:
                if not ln.lower().startswith(("t58", "futures_", "found by")) or len(lines) == 1:
                    return ln[:200]
            return lines[0][:200] if lines else ""
        return ""
    for ln in text.splitlines()[:40]:
        s = re.sub(r"^[\s/|*+#=\-]+", "", ln).strip(" |*-+/")
        if len(s) > 25 and re.search(r"[A-Za-z]{4}", s) and not s.startswith(("T58_", "property", "@version", "strategy(", "indicator(", "Copyright")):
            return s[:200]
    return ""


def _guess_instrument(name: str, text: str, meta: dict) -> str:
    m = str(meta.get("market") or "").upper()
    for k in ("NQ", "ES", "GC"):
        if k in m:
            return k
    hits = [h.upper().lstrip("M") if h.upper() in ("MNQ", "MES", "MGC") else h.upper() for h in _INSTR.findall(name)]
    hits = [h for h in hits if h in INSTRUMENTS]
    return hits[0] if hits else ""


def _short_label(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"^(?:MNQ|NQ|ES|GC|MES|MGC)\s*1?!?\s*(?:&\s*(?:NQ|ES)\s*1?!?\s*)?", "", stem).strip()
    stem = re.sub(r"\s+\d+[mhd]\b.*$", "", stem).strip() or stem
    stem = re.sub(r"\b(EA|v\d+)\b", "", stem).strip()
    return (stem or Path(name).stem)[:28]


def _library_roots() -> list[tuple[str, Path]]:
    roots = [("repo", STRATEGIES_DIR)]
    try:
        from app.strategy.library import get_strategy_library_dir
        lib = Path(get_strategy_library_dir())
        if lib.resolve() != STRATEGIES_DIR.resolve():
            roots.append(("library", lib))
    except Exception:  # noqa: BLE001 - the catalog must never fail to render
        pass
    return roots


def strategy_catalog(*, include_unsupported: bool = True) -> list[dict]:
    """Every strategy file a bot can follow. ``id`` is the path relative to the strategies folder (what ``BotLeg.strategy`` stores)."""
    out, seen = [], set()
    for _src, root in _library_roots():
        for sub in ("python", "pinescript", "mql5"):
            d = root / sub
            if not d.is_dir():
                continue
            for f in sorted(d.iterdir()):
                if f.suffix not in ALLOWED_SUFFIXES or f.name.endswith(".meta.json"):
                    continue
                sid = f"{sub}/{f.name}"
                if sid in seen:
                    continue
                seen.add(sid)
                try:
                    st = f.stat()
                    key = (str(f), st.st_mtime_ns, st.st_size)
                    row = _CATALOG_CACHE.get(key)
                    if row is None:
                        text = f.read_text(encoding="utf-8", errors="replace")
                        meta = {}
                        mp = f.with_name(f.name + ".meta.json")
                        if mp.exists():
                            import json
                            try:
                                meta = json.loads(mp.read_text(encoding="utf-8"))
                            except Exception:  # noqa: BLE001
                                meta = {}
                        tf = _tf_label(text[:6000])
                        inst = _guess_instrument(f.name, text[:3000], meta)
                        daily = _is_daily(tf) or ("daily" in f.name.lower()) or bool(re.search(r"\b1D\b", f.name))
                        reasons = []
                        if daily:
                            reasons.append("Daily-bar strategy: the bot engine trades intraday strategies.")
                        row = {"id": sid, "name": f.stem, "file": f.name, "type": sub, "label": _short_label(f.name), "instrument": inst,
                               "timeframe": tf or ("5m" if sub == "python" else ""), "idea": _first_line(text[:4000], f.suffix),
                               "supported": not reasons, "reason": " ".join(reasons),
                               "experimental": sub != "python",
                               "lookback_days": 500 if "context aligned" in f.name.lower() else (45 if "open drive" in f.name.lower() else 30),
                               "status": str(meta.get("status") or "")}
                        _CATALOG_CACHE[key] = row
                    out.append(dict(row))
                except OSError:
                    continue
    if not include_unsupported:
        out = [r for r in out if r["supported"]]
    out.sort(key=lambda r: (not r["supported"], r["instrument"] or "zz", r["name"].lower()))
    return out


def _catalog_by_id() -> dict[str, dict]:
    return {r["id"]: r for r in strategy_catalog()}


def prop_rule_sets() -> list[dict]:
    """Prop-firm rule sets a bot can protect, for the account picker (key, label, size)."""
    out = [{"key": "lucid_50k", "label": "Lucid Pro 50K (T58 demo default)", "size": 50_000}]
    try:
        from app.prop.presets import list_presets
        for p in list_presets():
            if p.key != "lucid_50k":
                out.append({"key": p.key, "label": p.label, "size": float(p.account_size)})
    except Exception:  # noqa: BLE001
        pass
    return out


# ------------------------------------------------------------------------------------------------------------------- validation
def _num(v: Any) -> Optional[float]:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, bool):
        return float(v)
    return float(v)


def _hhmm(s: Any, default: str) -> str:
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(s or ""))
    if not m:
        return default
    h, mi = int(m.group(1)), int(m.group(2))
    return f"{h:02d}:{mi:02d}" if 0 <= h < 24 and 0 <= mi < 60 else default


def _clean_name(s: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[<>\"'`]", "", str(s or ""))).strip()[:60]


def build_config(payload: dict, *, existing: Optional[BotConfig] = None) -> tuple[Optional[BotConfig], list[str], list[str]]:
    """(config or None, errors, warnings). ``existing`` keeps the id, creation time and shipped-preset marker when a bot is being edited."""
    p = dict(payload or {})
    errors: list[str] = []
    warnings: list[str] = []

    name = _clean_name(p.get("name")) or (existing.name if existing else "")
    if not name:
        errors.append("Give the bot a name.")
    goal = normalize_objective(p.get("objective") or (existing.objective if existing else ""), default="")
    if goal not in OBJECTIVES:
        errors.append("Pick a goal: pass the evaluation (A), get paid (B) or net profit.")
        goal = "A"

    instrument = str(p.get("instrument") or "").strip().upper()
    if instrument and instrument not in INSTRUMENTS:
        errors.append(f"Instrument '{instrument}' has no bundled history. Choose NQ, ES or GC.")
        instrument = ""

    # ---- strategies
    cat = _catalog_by_id()
    raw = p.get("strategies")
    if raw is None and existing is not None:
        raw = [{"strategy": lg.strategy, "label": lg.label, "weight": lg.weight, "priority": lg.priority, "note": lg.note} for lg in existing.legs]
    raw = raw if isinstance(raw, list) else []
    legs: list[BotLeg] = []
    used_labels: set[str] = set()
    used_ids: set[str] = set()
    if not raw:
        errors.append("Pick at least one strategy for the bot to follow.")
    if len(raw) > MAX_LEGS:
        errors.append(f"A bot can follow at most {MAX_LEGS} strategies.")
        raw = raw[:MAX_LEGS]
    for i, item in enumerate(raw):
        item = {"strategy": item} if isinstance(item, str) else dict(item or {})
        sid = str(item.get("strategy") or item.get("id") or "").replace("\\", "/").strip()
        if not sid or sid.startswith("/") or ".." in sid.split("/"):
            errors.append(f"Strategy {i + 1}: pick a file from the list.")
            continue
        entry = cat.get(sid)
        if entry is None:
            errors.append(f"Strategy '{sid}' is not in the library (it may have been renamed or deleted).")
            continue
        if sid in used_ids:
            errors.append(f"'{entry['label']}' is listed twice. Use the weight to size a strategy up or down.")
            continue
        used_ids.add(sid)
        if not entry["supported"]:
            errors.append(f"{entry['label']}: {entry['reason']}")
            continue
        if entry["experimental"]:
            warnings.append(f"{entry['label']} runs through the app's {'Pine' if entry['type'] == 'pinescript' else 'MQL5'} interpreter; entry parity with the backtest has not been verified for this file.")
        label = _clean_name(item.get("label")) or entry["label"]
        base, n = label, 2
        while label in used_labels:
            label, n = f"{base} {n}", n + 1
        used_labels.add(label)
        try:
            w = _num(item.get("weight", 1.0)) or 1.0
        except (TypeError, ValueError):
            w, _ = 1.0, errors.append(f"{label}: weight must be a number.")
        w2 = min(max(w, 0.1), 3.0)
        if w2 != w:
            warnings.append(f"{label}: weight adjusted to {w2:g} (allowed 0.1 to 3).")
        try:
            pr = int(_num(item.get("priority", i)) or 0)
        except (TypeError, ValueError):
            pr = i
        legs.append(BotLeg(strategy=sid, label=label, symbol="NQ", weight=w2, priority=min(max(pr, 0), 20),
                           lookback_days=int(entry["lookback_days"]), note=str(item.get("note") or entry["idea"] or "")[:200]))
        if entry["lookback_days"] >= 400:
            warnings.append(f"{label} needs about {entry['lookback_days']} days of history to warm up, so it runs in simulation but not on a short live feed.")
        if entry["instrument"] and instrument and entry["instrument"] != instrument:
            warnings.append(f"{label} was written for {entry['instrument']}; this bot trades {instrument}. It will run, but its parameters were not tuned for {instrument}.")
        if not instrument and entry["instrument"]:
            instrument = entry["instrument"]
    instrument = instrument or "NQ"
    for lg in legs:
        lg.symbol = instrument

    # ---- risk
    style = str(p.get("style") or "")
    gov = style_governor(goal, style if style in RISK_STYLES else "balanced")
    if existing is not None and not style and not p.get("reset_risk"):
        gov = GovernorConfig.from_dict(existing.governor).with_(objective=goal) if existing.objective == goal else gov
    risk_in = p.get("risk") if isinstance(p.get("risk"), dict) else {}
    kw: dict = {}
    for key, val in risk_in.items():
        f = _FIELD.get(key)
        if f is None:
            continue
        if f["kind"] == "bool":
            kw[key] = bool(val)
            continue
        try:
            n = _num(val)
        except (TypeError, ValueError):
            errors.append(f"'{f['label']}' must be a number.")
            continue
        if n is None:
            if f["optional"]:
                kw[key] = None
            continue
        c = min(max(n, f["lo"]), f["hi"])
        if c != n:
            warnings.append(f"'{f['label']}' adjusted to {c:g} (allowed {f['lo']:g} to {f['hi']:g}).")
        kw[key] = int(c) if f["kind"] == "int" else c
    gov = gov.with_(**kw)
    if gov.p2 <= gov.p1:
        gov = gov.with_(p2=min(0.98, gov.p1 + 0.1))
        warnings.append("The second progress mark must be above the first; it was moved up.")
    if gov.crit_cushion_frac >= gov.low_cushion_frac:
        gov = gov.with_(crit_cushion_frac=max(0.05, gov.low_cushion_frac - 0.1))
        warnings.append("The critical-room line must be below the low-room line; it was moved down.")

    # ---- limits
    lim = p.get("limits") if isinstance(p.get("limits"), dict) else {}
    base_cfg = existing or BotConfig()

    def _lim(key, default, lo, hi, cast=float):
        v = lim.get(key, getattr(base_cfg, key, default))
        try:
            n = cast(_num(v))
        except (TypeError, ValueError):
            errors.append(f"'{key}' must be a number.")
            return default
        c = min(max(n, lo), hi)
        if c != n:
            warnings.append(f"'{key}' adjusted to {c:g} (allowed {lo:g} to {hi:g}).")
        return c

    max_trades = int(_lim("max_trades_per_day", 6, 1, 50, int))
    day_cap = float(_lim("daily_loss_cap_pct_of_soft", 40.0, 5.0, 100.0, float))
    flat = _hhmm(lim.get("flatten_hhmm_et", base_cfg.flatten_hhmm_et), "16:45")
    reopen = _hhmm(lim.get("reopen_hhmm_et", base_cfg.reopen_hhmm_et), "18:00")

    # ---- account
    acc_in = p.get("account") if isinstance(p.get("account"), dict) else {}
    a = AccountLink.from_dict(existing.account.__dict__) if existing is not None else AccountLink(venue="paper", account_id="", size=50_000.0, preset_key="")
    if existing is None:
        a.venue = "paper"
    venue = str(acc_in.get("venue") or a.venue)
    if venue not in ("demo", "paper", "broker"):
        errors.append("Where it trades must be the T58 demo account, the bot sandbox or a connected broker account.")
        venue = "paper"
    a.venue = venue
    if venue == "demo":
        a.account_id = "t58-demo"
        a.preset_key = a.preset_key or "lucid_50k"
        a.size = 50_000.0
    elif venue == "broker":
        aid = str(acc_in.get("account_id") or a.account_id or "")
        if not aid or aid == "t58-demo":
            errors.append("Pick a connected broker account (add one under 'Connect a prop-firm or live account').")
        a.account_id = aid
    else:
        a.account_id = a.account_id or "sandbox"
    if venue != "demo":
        if existing is None and not a.preset_key and "preset_key" not in acc_in and goal in ("A", "B"):
            a.preset_key = "lucid_50k"
        if "size" in acc_in and acc_in["size"] not in (None, ""):
            try:
                n = _num(acc_in["size"])
                a.size = min(max(float(n), 1_000.0), 5_000_000.0)
                if a.size != n:
                    warnings.append(f"Account size adjusted to ${a.size:,.0f}.")
            except (TypeError, ValueError):
                errors.append("Account size must be a number.")
        if "preset_key" in acc_in:
            a.preset_key = str(acc_in.get("preset_key") or "")
    if a.preset_key:
        keys = {r["key"] for r in prop_rule_sets()}
        if a.preset_key not in keys:
            warnings.append(f"Rule set '{a.preset_key}' is not known; the bot will use the default Lucid-shaped rules scaled to the account size.")
        else:
            row = next(r for r in prop_rule_sets() if r["key"] == a.preset_key)
            if venue != "demo" and not acc_in.get("size") and existing is None:
                a.size = float(row["size"])
    a.broker_symbol = INSTRUMENTS[instrument]["micro"]
    if goal == "NET" and venue == "demo":
        warnings.append("The T58 demo account has prop-firm rules. A net-profit bot on it can still breach the loss floor; choose the bot sandbox with 'No prop rules' to test pure net profit.")
    if goal in ("A", "B") and venue != "demo" and not a.preset_key:
        warnings.append("Goals A and B protect a prop-firm rule set. Pick one under 'Rules to protect' or the bot will use generic rules scaled to the account size.")

    if errors:
        return None, errors, warnings
    cfg = BotConfig(
        id=(existing.id if existing else uuid.uuid4().hex[:10]), name=name, objective=goal,
        tagline=str(p.get("tagline") or (existing.tagline if existing else "") or SPECS[goal].question)[:140],
        description=str(p.get("description") or (existing.description if existing else "") or "")[:400],
        preset_key=(existing.preset_key if existing else ""), legs=legs, governor=gov.to_dict(), account=a,
        daily_loss_cap_pct_of_soft=day_cap, flatten_hhmm_et=flat, reopen_hhmm_et=reopen, max_trades_per_day=max_trades,
        created_at=(existing.created_at if existing else BotConfig().created_at))
    return cfg, errors, warnings


# --------------------------------------------------------------------------------------------------------------------- summary
def describe(cfg: BotConfig) -> dict:
    """Plain-words summary and the dollar numbers behind it, shown before (and after) a bot is created."""
    from app.bots.engine import rules_for_account
    g = cfg.governor_cfg()
    try:
        rules, max_minis, max_micros = rules_for_account(cfg.account, objective=cfg.objective)
    except Exception:  # noqa: BLE001 - e.g. no demo account file yet
        from app.bots.risk_governor import AccountRulesLite
        rules, max_minis, max_micros = AccountRulesLite.tier(cfg.account.size), 4, 40
    rule_free = rules.profit_target >= 1e11
    size = float(cfg.account.size) if cfg.account.venue != "demo" else float(rules.account_size)
    risk = size * g.base_risk_pct / 100.0
    lines = []
    legs = ", ".join(lg.label for lg in cfg.legs) or "no strategies"
    lines.append(f"{cfg.name} follows {legs} on {cfg.legs[0].symbol if cfg.legs else 'NQ'} and trades {cfg.account.broker_symbol} micros first, minis when the stop is tight.")
    goal = SPECS.get(cfg.objective)
    lines.append(f"Goal: {goal.name if goal else cfg.objective}.")
    lines.append(f"A full-size trade risks about ${risk:,.0f} ({g.base_risk_pct:g}% of ${size:,.0f}).")
    warn: list[str] = []
    if not rule_free and rules.loss_limit > 0:
        share = risk / rules.loss_limit
        lines.append(f"That is {share:.0%} of the ${rules.loss_limit:,.0f} loss limit, so about {max(1, int(rules.loss_limit // max(risk, 1)))} full losses in a row would breach.")
        if share > 0.5:
            warn.append(f"One full-size loss would use {share:.0%} of the loss limit. Two in a row would nearly breach: lower the risk per trade.")
        if cfg.objective in ("A", "B"):
            lines.append(f"The bot stands down for the day after losing {g.day_stop_frac:.0%} of the ${rules.soft_daily_limit:,.0f} daily limit (about ${g.day_stop_frac * rules.soft_daily_limit:,.0f}).")
            if g.cushion_risk_frac:
                lines.append(f"It never risks more than {g.cushion_risk_frac:.0%} of the room above the loss floor.")
    elif rule_free:
        lines.append("No prop-firm rules apply: there is no profit target to pass and no trailing floor, only the drawdown throttle protects the account.")
        lines.append(f"Size shrinks as drawdown from the equity peak approaches {g.dd_throttle_tol_pct:g}%" + ("; risk compounds with equity." if g.compounding else "."))
    lines.append(f"At most {cfg.max_trades_per_day} trades a day; flat by {cfg.flatten_hhmm_et} ET, no new entries until {cfg.reopen_hhmm_et} ET.")
    return {"lines": lines, "warnings": warn, "risk_dollars": round(risk, 2), "risk_pct": g.base_risk_pct,
            "loss_limit": None if rule_free else round(float(rules.loss_limit), 2), "rule_free": rule_free,
            "max_minis": max_minis, "max_micros": max_micros}


# ----------------------------------------------------------------------------------------------------------- adding a strategy
def add_strategy(filename: str, code: str, strategy_type: str = "") -> tuple[Optional[dict], str]:
    """Save a pasted or uploaded strategy into the library and prove it loads. Returns (catalog row, error message)."""
    from app.strategy import library
    fn = Path(str(filename or "")).name.strip()
    code = str(code or "")
    if not fn or not code.strip():
        return None, "Give the strategy a file name and paste its code."
    if len(code) > 400_000:
        return None, "That file is too large (limit 400 KB)."
    suffix = Path(fn).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        return None, "Strategy files end in .py (Python), .pine (Pine Script) or .mq5 (MQL5)."
    stype = {".py": "python", ".pine": "pinescript", ".mq5": "mql5"}[suffix]
    if strategy_type and strategy_type != stype:
        return None, f"A {suffix} file is a {stype} strategy."
    try:
        path = library.save_strategy_text(code, fn, stype, overwrite=False)
    except library.StrategyAlreadyExists:
        return None, f"'{fn}' is already in the library. Rename the file or pick the existing one."
    except Exception as exc:  # noqa: BLE001
        return None, f"Could not save the file: {exc}"
    sid = f"{stype}/{path.name}"
    try:
        from app.bots.signals import load_strategy
        load_strategy(sid)
    except Exception as exc:  # noqa: BLE001 - an unreadable file never stays in the library
        try:
            library.delete_saved_strategy(stype, path.name)
        except Exception:  # noqa: BLE001
            pass
        return None, f"The file was not accepted: {type(exc).__name__}: {str(exc)[:200]}"
    row = _catalog_by_id().get(sid)
    return (row or {"id": sid, "label": path.stem}), ""
