"""Build final/T58-QUANT-ENGINE_t58_final_bots.zip: files laid out like the T58-QUANT-ENGINE repo, ready to copy over a checkout.
Run after the round-3 holdout read: T58_R3=1 python3 build_repo_zip.py"""
import json, os, re, shutil, sys, zipfile, hashlib
from pathlib import Path
sys.path.insert(0, "research/t58_final_bots/engine")
import picks_r3
W = Path("research/t58_final_bots"); Z = W / "repo_zip"; R = W / "research"; FIN = W / "final"
LEG = {   # key -> (strategy path under strategies/, label, symbol, lookback calendar days, note)
    "CDL_NQ": ("python/ContextDriveLong_NQ_1m_v2.py", "Context Drive Long", "NQ", 500, "Repo strategy, unchanged."),
    "CDL_ES": ("python/ContextDriveLong_NQ_1m_v2.py", "Context Drive Long ES", "ES", 500, "Repo strategy, unchanged, on ES."),
    "IR_NQ": ("python/IndRule_NQ_15m_v1.py", "Ind Rule", "NQ", 15, "Repo strategy, unchanged."),
    "OD_NQ": ("python/OpenDrive_NQ_5m_v1.py", "Open Drive", "NQ", 45, "Repo strategy, unchanged."),
    "OD_ES": ("python/OpenDrive_NQ_5m_v1.py", "Open Drive ES", "ES", 45, "Repo strategy, unchanged, on ES."),
    "CORB_ES": ("python/CompressionORB_ES_5m_v1.py", "Compression ORB", "ES", 30, "Repo strategy, unchanged."),
    "CDLB_NQ": ("python/ContextDriveLongBracket_NQ_1m_v1.py", "Context Drive Long Bracket", "NQ", 500, "Repo strategy, unchanged."),
    "ORB15C_NQ": ("python/ORB15Compression_NQ_1m_t58.py", "ORB15 compression NQ", "NQ", 30, "New (T58 final bots): 15m ORB after a compressed day, 3R."),
    "ORB15C_ES": ("python/ORB15Compression_ES_1m_t58.py", "ORB15 compression ES", "ES", 30, "New (T58 final bots): 15m ORB after a compressed day, 2R."),
    "ORB30T_NQ": ("python/ORB30Trend_NQ_1m_t58.py", "ORB30 with trend NQ", "NQ", 45, "New (T58 final bots): 30m ORB with the 20-day trend, 3R."),
    "VWPB_NQ": ("python/VWAPPullback_NQ_1m_t58.py", "VWAP pullback NQ", "NQ", 45, "New (T58 final bots): VWAP pullback in the daily trend, 2R."),
    "GAP_GC": ("python/GapTrend_GC_1m_t58.py", "Gap with trend GC", "GC", 45, "New (T58 final bots): opening gap with the 20-day trend, 3R."),
    "PDLB_GC": ("python/PriorDayBreak_GC_1m_t58.py", "Prior-day break GC", "GC", 200, "New (T58 final bots): prior-day break in a quiet regime, 3R."),
}
ENGINE = ["data.py", "book.py", "factory.py", "legs.py", "filters.py", "policy.py", "firm.py", "score.py", "search.py", "baseline.py",
          "baseline_run.py", "picks.py", "picks_r2.py", "picks_r3.py", "final_score.py", "final_score_r2.py", "final_score_r3.py", "mc.py",
          "compare.py", "compare_r2.py", "compare_r3.py", "reports_r3.py", "confirm.py", "run_r3.py", "data_h2.py", "port_legs.py", "verify_ports.py",
          "verify_port_bots.py", "stats.py", "gates.py", "build_repo_zip.py"]
def relpath(txt):
    txt = txt.replace('Path(__import__("os").environ.get("T58_REPO", "."))', 'Path(__import__("os").environ.get("T58_REPO", "."))')
    txt = txt.replace('Path(__import__("os").environ.get("T58_CACHE", "research/t58_final_bots/.cache"))', 'Path(__import__("os").environ.get("T58_CACHE", "research/t58_final_bots/.cache"))')
    txt = txt.replace("research/t58_final_bots/engine", "research/t58_final_bots/engine")
    txt = txt.replace("strategies/python/", "strategies/python/")
    txt = txt.replace("research/t58_final_bots", "research/t58_final_bots")
    return txt
def bot_py():
    bots = {"A": picks_r3.BOT_A, "B": picks_r3.BOT_B}
    lines = ['"""T58 final bots (research, 2026-11-24): BOT-A for passing a LucidPro 50K evaluation, BOT-B for LucidFlex 50K payouts.',
             "", "Not seeded as presets: load with ``next(c for c in t58_final_configs() if c.id == 'bot-t58-final-a')``.",
             "Every number in docs/T58_FINAL_BOTS_PERFORMANCE_2026-11-24.md comes from the research engine in research/t58_final_bots/engine",
             "(firm simulator + the sizing policy in T58_POLICY below). The GovernorConfig here is the closest setting of the repo's own",
             "governor; it has NOT been validated and will not reproduce those numbers exactly. Use the research engine's policy for that.",
             '"""', "from __future__ import annotations", "", "from app.bots.models import AccountLink, BotConfig, BotLeg",
             "from app.bots.risk_governor import GovernorConfig", ""]
    lines.append("T58_PICKS = " + json.dumps(bots, indent=1).replace("null", "None").replace("true", "True").replace("false", "False"))
    lines.append("T58_POLICY = {k: v['policy'] for k, v in T58_PICKS.items()}   # exact sizing used in research (research/t58_final_bots/engine/policy.py)")
    lines.append("T58_FILTERS = {k: v.get('spec') for k, v in T58_PICKS.items()}   # crash: size x0.5 when the 504-day return < 0 and 126-day vol > its median")
    lines.append("LEG_FILES = " + json.dumps({k: list(v) for k, v in LEG.items()}, indent=1))
    lines += ["", "", "def _legs(obj: str) -> list:",
              "    out = []",
              "    for prio, (k, w) in enumerate(T58_PICKS[obj]['legs'].items()):",
              "        if w <= 0:", "            continue",
              "        path, label, sym, look, note = LEG_FILES[k]",
              "        out.append(BotLeg(path, label, sym, float(w), prio, int(look), note))",
              "    return out", "", "",
              "def t58_final_configs() -> list[BotConfig]:",
              "    pa, pb = T58_POLICY['A'], T58_POLICY['B']",
              "    gov_a = GovernorConfig(objective='A', base_risk_pct=100.0 * pa['r_eval'] / 50_000, cushion_risk_frac=pa['f_cush'],",
              "                           need_risk_mult=pa.get('k_need'), early_mult=1.0, mid_mult=1.0, late_mult=1.0, low_cushion_mult=1.0, crit_cushion_mult=1.0)",
              "    gov_b = GovernorConfig(objective='B', base_risk_pct=100.0 * pb['r_eval'] / 50_000, cushion_risk_frac=pb['f_cush'], funded_mult=pb['r_fund'] / pb['r_eval'],",
              "                           early_mult=1.0, mid_mult=1.0, late_mult=1.0, low_cushion_mult=1.0, win_day_lock_mult=(pb.get('fund_day_cap') or 0) / 150.0 or None)",
              "    return [",
              "        BotConfig(id='bot-t58-final-a', name='T58_FINAL_BOT_A', objective='A', preset_key='t58-final-a',",
              "                  tagline='Research: pass the Lucid 50K Pro evaluation (T58 final bots, 2026-11-24).',",
              "                  description='See docs/T58_FINAL_BOTS_PERFORMANCE_2026-11-24.md. Sizing: T58_POLICY[\"A\"] (research engine); governor here is an unvalidated approximation.',",
              "                  legs=_legs('A'), governor=gov_a.to_dict(), max_open_positions=int(T58_PICKS['A']['max_open']), max_trades_per_day=6,",
              "                  account=AccountLink(venue='demo', account_id='t58-demo', size=50_000.0, broker_symbol='MNQ', preset_key='lucid_50k')),",
              "        BotConfig(id='bot-t58-final-b', name='T58_FINAL_BOT_B', objective='B', preset_key='t58-final-b',",
              "                  tagline='Research: first and repeat payouts on a LucidFlex 50K account (T58 final bots, 2026-11-24).',",
              "                  description='See docs/T58_FINAL_BOTS_PERFORMANCE_2026-11-24.md. Sizing: T58_POLICY[\"B\"] and T58_FILTERS[\"B\"] (research engine); governor here is an unvalidated approximation.',",
              "                  legs=_legs('B'), governor=gov_b.to_dict(), max_open_positions=int(T58_PICKS['B']['max_open']), max_trades_per_day=6,",
              "                  account=AccountLink(venue='demo', account_id='t58-demo', size=50_000.0, broker_symbol='MNQ', preset_key='lucid_flex_50k')),",
              "    ]", ""]
    return "\n".join(lines)
TEST = '''"""T58 final bots (2026-11-24): every leg's strategy file exists and loads, and the configs build."""
import importlib.util
from pathlib import Path
from app.bots.t58_final_bots import t58_final_configs, T58_PICKS, LEG_FILES
from app.bots.presets import preset_configs

ROOT = Path(__file__).resolve().parents[2]


def test_configs_build_and_do_not_clash_with_presets():
    cs = t58_final_configs()
    assert {c.id for c in cs} == {"bot-t58-final-a", "bot-t58-final-b"}
    assert not {c.id for c in cs} & {c.id for c in preset_configs()}


def test_every_leg_file_exists_and_has_generate_signals():
    for obj, pk in T58_PICKS.items():
        for k, w in pk["legs"].items():
            if w <= 0:
                continue
            p = ROOT / "strategies" / LEG_FILES[k][0]
            assert p.exists(), p
            spec = importlib.util.spec_from_file_location(p.stem, p)
            m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
            assert callable(m.generate_signals)


def test_new_strategies_are_flat_on_tiny_data():
    import numpy as np, pandas as pd
    ts = pd.date_range("2026-01-05 14:30", periods=400, freq="1min", tz="UTC")
    px = 100 + np.cumsum(np.random.default_rng(0).normal(0, 0.1, len(ts)))
    df = pd.DataFrame({"timestamp": ts, "open": px, "high": px + 0.1, "low": px - 0.1, "close": px, "volume": 1.0})
    for p in (ROOT / "strategies" / "python").glob("*_t58.py"):
        spec = importlib.util.spec_from_file_location(p.stem, p)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        s = m.generate_signals(df)
        assert len(s) == len(df) and (s == 0).all()      # no prior sessions -> no ATR -> no trades
'''
REPO_SETUP = '''"""First-run setup inside the T58-QUANT-ENGINE repo: builds the session matrices the engine reads (mat_<I>_dev2.pkl = every session
before 2026-03-02) from the repo's own data/raw files. The Mar-Nov 2026 holdout (mat_<I>_full2.pkl) is NOT rebuilt here: put Owen's three
2026-03-01..2026-11-24 parquet files in research/t58_final_bots/data_holdout2/ (they must match SEAL.sha256 there) and run
engine/data_h2.py to rebuild it."""
import pickle, numpy as np
import data as D

def ensure():
    D.CACHE.mkdir(parents=True, exist_ok=True)
    for inst in D.FILES:
        p = D.CACHE / f"mat_{inst}_dev2.pkl"
        if p.exists(): continue
        d = D._build(inst); keep = d["days"] < np.datetime64("2026-03-02")
        dev = {k: (v[keep] if isinstance(v, np.ndarray) and len(v) == len(d["days"]) else v) for k, v in d.items()}
        pickle.dump(dev, open(p, "wb"), protocol=4)
'''
def build():
    E = Z / "research/t58_final_bots/engine"; E.mkdir(parents=True, exist_ok=True)
    for f in ENGINE:
        src = W / "code" / f
        if src.exists(): (E / f).write_text(relpath(src.read_text()))
    for sub in ("tests",):
        if (W / "code" / sub).exists():
            shutil.copytree(W / "code" / sub, E / sub, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    RB = Z / "research/t58_final_bots"
    for f in ("FROZEN_PICKS.md", "FROZEN_PICKS_R2.md", "FROZEN_PICKS_R3.md", "gate_ladder_log.md", "STATE.md", "papers_notes.md"):
        for base in (R, W, FIN):
            if (base / f).exists(): shutil.copy(base / f, RB / f); break
    for d in ("BOT-A", "BOT-B"):
        shutil.copytree(FIN / d, RB / d, dirs_exist_ok=True)
    rb = relpath((FIN / "run_bot.py").read_text()).replace('ROOT / "code"', 'ROOT / "engine"').replace('ROOT / "final" / f"BOT-{which}"', 'ROOT / f"BOT-{which}"')
    rb = rb.replace("ROOT = Path(__file__).resolve().parents[1]", "ROOT = Path(__file__).resolve().parent")
    rb = rb.replace("import search as S", "import repo_setup; repo_setup.ensure()\nimport search as S")
    (RB / "run_bot.py").write_text(rb)
    (E / "repo_setup.py").write_text(REPO_SETUP)
    (RB / "research").mkdir(exist_ok=True)
    for f in R.glob("FROZEN_PICKS*"): shutil.copy(f, RB / "research" / f.name)   # data.load checks the seal files here
    (RB / "data_holdout2").mkdir(exist_ok=True); shutil.copy(W / "data_holdout2/SEAL.sha256", RB / "data_holdout2/SEAL.sha256")
    RS = Z / "results/t58_final_bots"; RS.mkdir(parents=True, exist_ok=True)
    for f in sorted(R.glob("*.csv")) + sorted(FIN.glob("*.csv")):
        shutil.copy(f, RS / f.name)
    (Z / "app/bots").mkdir(parents=True, exist_ok=True); (Z / "app/bots/t58_final_bots.py").write_text(bot_py())
    (Z / "tests/bots").mkdir(parents=True, exist_ok=True); (Z / "tests/bots/test_t58_final_bots.py").write_text(TEST)
    (Z / "strategies/pinescript").mkdir(parents=True, exist_ok=True)
    shutil.copy(FIN / "pine/T58_BOT.pine", Z / "strategies/pinescript/T58_FINAL_BOT_AB.pine")
    (Z / "scripts").mkdir(parents=True, exist_ok=True)
    (Z / "scripts/run_t58_final_bots.py").write_text('''"""Reproduce the T58 final bots' scores from the repo root.
  python scripts/run_t58_final_bots.py A|B [stress]   -> research + validation scores of the frozen pick (research engine)
Needs data/raw/{NQ1!,ES1!,GC1!}/futures_X.F_1m.parquet (the repo's data). First run builds session matrices in research/t58_final_bots/.cache."""
import runpy, sys
sys.argv = ["run_bot.py"] + sys.argv[1:]
runpy.run_path("research/t58_final_bots/run_bot.py", run_name="__main__")
''')
    for f in ("T58_FINAL_BOTS_PERFORMANCE_2026-11-24.md", "T58_FINAL_BOTS_COMPARISON_2026-11-24.md"):
        if (FIN / f).exists(): (Z / "docs").mkdir(exist_ok=True); shutil.copy(FIN / f, Z / "docs" / f)
    if (FIN / "PASTE_INTO_REPO.md").exists(): shutil.copy(FIN / "PASTE_INTO_REPO.md", Z / "PASTE_INTO_REPO.md")
    out = FIN / "T58-QUANT-ENGINE_t58_final_bots.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(Z.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and ".cache" not in p.parts:
                zf.write(p, p.relative_to(Z))
    print(out, out.stat().st_size, hashlib.sha256(out.read_bytes()).hexdigest()[:16])
if __name__ == "__main__":
    build()
