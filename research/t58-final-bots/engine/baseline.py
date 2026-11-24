"""Current bots (repo app/bots/presets.py, PRESET_REV 5, the t58-new-bots 2026-11-21 package) on the identical engine, costs and firm rules."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import data as D, book, firm
sys.path.insert(0, str(D.REPO)); sys.path.insert(0, str(D.REPO / "scripts"))
from app.bots.risk_governor import GovernorConfig, AccountRulesLite
from policies import repo_policy

GOV_A = GovernorConfig(objective="A", base_risk_pct=0.75, early_mult=1.3, mid_mult=1.0, late_mult=0.7, need_risk_mult=1.0, day_stop_frac=0.40,
                       cushion_risk_frac=0.75, pace_max_mult=1.5, pace_min_mult=0.85)
GOV_B = GovernorConfig(objective="B", base_risk_pct=1.0, cushion_risk_frac=0.10, day_stop_frac=0.30, funded_mult=1.0, early_mult=1.0, mid_mult=1.0,
                       late_mult=1.0, low_cushion_mult=1.0, streak_mult=None, pace_max_mult=1.3, pace_min_mult=0.85, win_day_lock_mult=1.0)
LEGS_A = [("OpenDrive_NQ_5m_v1", "NQ", 1.0, 0), ("IndRule_NQ_15m_v1", "NQ", 3.0, 1), ("ContextDriveLong_NQ_1m_v2", "NQ", 1.0, 2)]
LEGS_B = [("OpenDrive_NQ_5m_v1", "NQ", 0.25, 0), ("IndRule_NQ_15m_v1", "NQ", 2.0, 1), ("OpenDrive_NQ_5m_v1", "ES", 0.25, 2),
          ("CompressionORB_ES_5m_v1", "ES", 0.5, 3)]


def leg_book(stem, inst, sealed=False):
    return book.points(book.gen(stem, inst), inst, sealed=sealed, name=f"{stem}@{inst}")


def bot_book(legs, sealed=False):
    return book.merge([(leg_book(s, i, sealed), w, pr) for s, i, w, pr in legs], max_open=2, max_per_day=6, one_per_inst=True)


def policy(obj, lite=None):
    return repo_policy(GOV_A if obj == "A" else GOV_B, lite or AccountRulesLite.lucid_50k())


def lite(plan):
    if plan.kind == "flex":
        return AccountRulesLite(eval_consistency=0.40).with_winning_days_payout(5, 150.0)
    return AccountRulesLite.lucid_50k()
