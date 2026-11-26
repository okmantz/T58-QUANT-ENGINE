#!/usr/bin/env python3
"""One-shot repo cleanup for T58-QUANT-ENGINE (2026-11-25). Paste the changed files from this delivery FIRST, then run this once from the repo root:

    python scripts/cleanup_repo.py            # show what would go (touches nothing)
    python scripts/cleanup_repo.py --apply    # do it: `git rm` / `git mv`, so everything stays recoverable from git history

What goes, and why (nothing below is read by the app, the tests, the build or the CI; the full test suite and the web smoke test pass without it):
  * research/t58_final_bots (stale round-5 copy) is replaced by research/t58-final-bots (the newer round-6 copy, renamed onto the underscore name the research code uses)
    and trimmed to the engine modules round 6 imports; results/ keeps only round 6 (+ the baselines); old bot-search scripts, reports, docs and unused app files are removed.
  * strategies nobody trades (no bot uses them) and unused templates / static scripts / modules.
This script deletes itself last (`--apply`), since it only makes sense once."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip())
APPLY = "--apply" in sys.argv
OLD, NEW = "research/t58-final-bots", "research/t58_final_bots"

STALE_COPY = [
    "research/t58_final_bots",
]

AFTER_RENAME = [
    "research/t58_final_bots/engine/baseline_run.py",
    "research/t58_final_bots/engine/build_repo_zip.py",
    "research/t58_final_bots/engine/check_flex_lock.py",
    "research/t58_final_bots/engine/compare.py",
    "research/t58_final_bots/engine/compare_r2.py",
    "research/t58_final_bots/engine/compare_r3.py",
    "research/t58_final_bots/engine/compare_r4.py",
    "research/t58_final_bots/engine/confirm.py",
    "research/t58_final_bots/engine/data_h2.py",
    "research/t58_final_bots/engine/data_h2_ports.py",
    "research/t58_final_bots/engine/data_h3.py",
    "research/t58_final_bots/engine/data_h3_ports.py",
    "research/t58_final_bots/engine/final_score.py",
    "research/t58_final_bots/engine/final_score_r2.py",
    "research/t58_final_bots/engine/gates.py",
    "research/t58_final_bots/engine/picks_r5.py",
    "research/t58_final_bots/engine/port_legs.py",
    "research/t58_final_bots/engine/r4_base.py",
    "research/t58_final_bots/engine/r4_legregime.py",
    "research/t58_final_bots/engine/r4_search.py",
    "research/t58_final_bots/engine/r5_pick.py",
    "research/t58_final_bots/engine/r5_search.py",
    "research/t58_final_bots/engine/reports_r3.py",
    "research/t58_final_bots/engine/reports_r4.py",
    "research/t58_final_bots/engine/reports_r5.py",
    "research/t58_final_bots/engine/run_r3.py",
    "research/t58_final_bots/engine/stats.py",
    "research/t58_final_bots/engine/verify_port_bots.py",
    "research/t58_final_bots/engine/verify_ports.py",
    "research/t58_final_bots/BOT-A/params_r1.json",
    "research/t58_final_bots/BOT-A/params_r3.json",
    "research/t58_final_bots/BOT-A/README_r1.md",
    "research/t58_final_bots/BOT-A/README_r3.md",
    "research/t58_final_bots/BOT-B/params_r1.json",
    "research/t58_final_bots/BOT-B/params_r2.json",
    "research/t58_final_bots/BOT-B/params_r3.json",
    "research/t58_final_bots/BOT-B/params_r5_alt.json",
    "research/t58_final_bots/BOT-B/README_r1.md",
    "research/t58_final_bots/BOT-B/README_r2.md",
    "research/t58_final_bots/BOT-B/README_r3.md",
    "research/t58_final_bots/FROZEN_PICKS.md",
    "research/t58_final_bots/FROZEN_PICKS_R2.md",
    "research/t58_final_bots/FROZEN_PICKS_R3.md",
    "research/t58_final_bots/FROZEN_PICKS_R4.md",
    "research/t58_final_bots/FROZEN_PICKS_R5.md",
    "research/t58_final_bots/FROZEN_PICKS_R6.md",
    "research/t58_final_bots/PREREG_R5.md",
    "research/t58_final_bots/gate_ladder_log.md",
    "research/t58_final_bots/papers_notes.md",
    "research/t58_final_bots/data_holdout2",
    "research/t58_final_bots/BOT-A/.gitkeep",
    "research/t58_final_bots/BOT-B/.gitkeep",
    "research/t58_final_bots/engine/tests/.gitkeep",
    "research/t58_final_bots/research/.gitkeep",
]

OTHER = [
    "license_sheet/.gitkeep",
    "results/t58-final-bots",
    "results/L120.out",
    "results/L60.out",
    "results/holdout_H1.json",
    "results/holdout_H1.out",
    "results/holdout_extra.json",
    "results/leg_library_dev.csv",
    "results/lifecycle_H1_120.json",
    "results/lifecycle_H1_60.json",
    "results/lifecycle_dev.json",
    "results/lifecycle_dev120.json",
    "results/lifecycle_dev120x.json",
    "results/lifecycle_dev120y.json",
    "results/lifecycle_dev60.json",
    "results/localA.out",
    "results/localB.out",
    "results/scan_levelbreakout.csv",
    "results/searchA_log.jsonl",
    "results/searchB_log.jsonl",
    "results/tsmom_filter_dev.csv",
    "results/t58_final_bots/bot_trials.csv",
    "results/t58_final_bots/bot_trials_r2_confirm.csv",
    "results/t58_final_bots/bot_trials_r3.csv",
    "results/t58_final_bots/bot_trials_r4.csv",
    "results/t58_final_bots/bot_trials_r5.csv",
    "results/t58_final_bots/comparison_long.csv",
    "results/t58_final_bots/comparison_long_r3.csv",
    "results/t58_final_bots/comparison_long_r4.csv",
    "results/t58_final_bots/dev_r4_prior.csv",
    "results/t58_final_bots/final_dev.csv",
    "results/t58_final_bots/final_dev_r2.csv",
    "results/t58_final_bots/final_dev_r3.csv",
    "results/t58_final_bots/final_dev_r3_prepicks.csv",
    "results/t58_final_bots/final_dev_r4.csv",
    "results/t58_final_bots/final_dev_r5.csv",
    "results/t58_final_bots/final_devres_r3.csv",
    "results/t58_final_bots/final_hold.csv",
    "results/t58_final_bots/final_hold_r2.csv",
    "results/t58_final_bots/final_hold_r3.csv",
    "results/t58_final_bots/final_hold_r4.csv",
    "results/t58_final_bots/flex_lock_check.csv",
    "results/t58_final_bots/mc.csv",
    "results/t58_final_bots/mc_r2.csv",
    "results/t58_final_bots/mc_r3.csv",
    "results/t58_final_bots/mc_r4.csv",
    "results/t58_final_bots/mc_r5.csv",
    "results/t58_final_bots/pbo_by_family.csv",
    "results/t58_final_bots/plateau_r5_B.csv",
    "results/t58_final_bots/port_bots_check.csv",
    "results/t58_final_bots/port_check.csv",
    "results/t58_final_bots/r4_leg_regime.csv",
    "results/t58_final_bots/shortfalls_r3.csv",
    "results/t58_final_bots/shortfalls_r4.csv",
    "results/t58_final_bots/strategy_ledger.csv",
    "results/t58_final_bots/top5_per_objective.csv",
    "results/t58_final_bots/top5_per_objective_r3.csv",
    "results/t58_final_bots/a_bar_r4.csv",
    "results/t58_final_bots/baseline_dev_flex_r3.csv",
    "results/t58_final_bots/baseline_dev_r3.csv",
    "results/t58_final_bots/baseline_dev_sustained.csv",
    "reports/prop30",
    "reports/t58_hypotheses",
    "strategies/python/ContextDriveLongBracket_NQ_1m_v1.py",
    "strategies/python/IndRuleB_NQ_30m_v1.py",
    "strategies/python/LevelBreakout_ESNQ_15m_v1.py",
    "strategies/python/TrendMomentum_NQ_5m_v1.py",
    "strategies/mql5/GoLong_ESNQ_5m_v1.mq5",
    "strategies/mql5/RangeBreakout_NQ_5m_v1.mq5",
    "strategies/mql5/Gate27_Basket_Daily_v2.mq5",
    "strategies/pinescript/TSMOM_ES_Daily_v6.pine",
    "app/bots/t58_final_bots.py",
    "app/web/templates/demo_account.html",
    "app/web/templates/notification_settings.html",
    "app/web/templates/rulebook.html",
    "app/web/templates/trader_profile.html",
    "app/web/templates/user_manual.html",
    "app/web/static/pg-arcade.js",
    "app/web/static/pg-fidgets.js",
    "app/web/static/pg-puzzles.js",
    "app/web/static/pg-quantum.js",
    "app/data/data_rules.py",
    "app/data/downloader.py",
    "app/strategy/ctrader_export.py",
    "app/forward_test/paper.py",
    "app/journal/state.py",
    "scripts/acct.py",
    "scripts/audit_gad_engine.py",
    "scripts/bench_audit_2026_11.py",
    "scripts/bench_speed_run_phase2.py",
    "scripts/cands.py",
    "scripts/dev.py",
    "scripts/evalL.py",
    "scripts/gate_kill_histogram.py",
    "scripts/holdout.py",
    "scripts/lib.py",
    "scripts/life.py",
    "scripts/localA.py",
    "scripts/localB.py",
    "scripts/make_objective_report.py",
    "scripts/make_t58_report.py",
    "scripts/msw.py",
    "scripts/rescore_floating_presets.py",
    "scripts/run_bot_optimization.py",
    "scripts/run_ga_vs_random.py",
    "scripts/run_gate27_basket.py",
    "scripts/run_gate27_study.py",
    "scripts/run_objective_c_final.py",
    "scripts/run_objective_scores.py",
    "scripts/run_objective_study.py",
    "scripts/run_objectives_research.py",
    "scripts/run_preregistered_families.py",
    "scripts/run_prop30_research.py",
    "scripts/run_t58_bot_replays.py",
    "scripts/run_t58_engine_grid.py",
    "scripts/run_t58_hypotheses.py",
    "scripts/scan_lb.py",
    "scripts/searchA.py",
    "scripts/searchB.py",
    "scripts/sharpe.py",
    "scripts/sim.py",
    "scripts/snapshot_gex.py",
    "scripts/strategy_evidence.py",
    "scripts/t58_ir_search.py",
    "scripts/t58_lab.py",
    "scripts/t58_sleeve_template.py",
    "scripts/tsmom.py",
    "scripts/generate_scene_backdrops.py",
    "tests/bots/test_ab_combo_bots.py",
    "tests/bots/test_research_bots.py",
    "tests/bots/test_t58_final_bots.py",
    "docs/OBSOLETE_FILES.md",
    "docs/REPO_AUDIT.md",
    "docs/RESEARCH_INTAKE_2026-11.md",
    "docs/T58_BOT_AB_COMBOS_2026-11-19.md",
    "docs/T58_BOT_OPTIMIZATION_2026-11.md",
    "docs/T58_BOT_RESEARCH.md",
    "docs/T58_FINAL_BOTS_COMPARISON_2026-11-24.md",
    "docs/T58_FINAL_BOTS_ROUND5_2026-11-24.md",
    "docs/T58_Game_Plan.pdf",
    "docs/T58_HYPOTHESIS_REPORT.md",
    "docs/T58_NEW_BOTS_2026-11-21.md",
    "docs/T58_OBJECTIVES_MATH_2026-11.md",
    "docs/T58_OBJECTIVES_MATH_2026-11.pdf",
    "docs/T58_OBJECTIVES_RESEARCH_2026-11-18.md",
    "docs/T58_STRATEGY_DISCOVERY_2026-11.md",
    "docs/T58_STRATEGY_EVALUATION_2026-11.md",
    "docs/T58_STRATEGY_EVALUATION_2026-11.pdf",
    "docs/T58_Strategy_Evaluation_Report.pdf",
    "docs/T58_Strategy_Testing_Plan.pdf",
    "HOW TO OPEN ON YOUR PHONE.md",
]


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)


def remove(rel: str) -> None:
    p = ROOT / rel
    if not p.exists():
        return
    print(("rm   " if APPLY else "would rm   ") + rel)
    if APPLY:
        git("rm", "-r", "-q", "-f", "--ignore-unmatch", "--", rel)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()


def main() -> int:
    if (ROOT / OLD).is_dir():                                   # guard: safe to re-run
        for p in STALE_COPY:
            remove(p)
        print(("mv   " if APPLY else "would mv   ") + f"{OLD} -> {NEW}")
        if APPLY:
            r = git("mv", OLD, NEW)
            if r.returncode:
                print(r.stderr); return 1
    for p in AFTER_RENAME:
        if APPLY or not (ROOT / OLD).is_dir():
            remove(p)
        elif (ROOT / p.replace(NEW, OLD)).exists():              # dry run: the rename has not happened yet
            print("would rm   " + p)
    for p in OTHER:
        remove(p)
    if APPLY:
        me = Path(__file__).resolve()
        git("rm", "-q", "-f", "--ignore-unmatch", "--", str(me.relative_to(ROOT)))
        me.unlink(missing_ok=True)
        print("done. Next: python scripts/run_tests.py --fast && python scripts/web_smoke_test.py, then commit.")
    else:
        print("(dry run: nothing changed; add --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
