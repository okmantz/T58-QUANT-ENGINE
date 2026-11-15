"""2026-11-14 audit fixes for lifecycle_v2: per-firm payout terms and an explicit floor-lock flag."""
import numpy as np

from app.prop.lifecycle_v2 import V2Rules, payout_terms_from_rules, simulate
from app.prop.presets import get_preset


def test_payout_terms_follow_the_firm_not_the_lucid_assumption():
    r = V2Rules.from_prop_rules(get_preset("lucid_50k").to_prop_rules())
    assert r.payout.cap == 2000.0 and r.payout.buffer_above_floor == 2100.0
    assert r.payout.cumulative_min == 2600.0            # $500 goal + $2,100 buffer, as PropAccount requires
    assert r.payout.sourced is True
    t = V2Rules.from_prop_rules(get_preset("topstep_50k").to_prop_rules())
    assert t.payout.cap == 2000.0 and t.payout.qualifying_days == 5


def test_explicit_payout_terms_still_win():
    from app.prop.lifecycle_v2 import PayoutTerms
    custom = PayoutTerms(cap=123.0)
    r = V2Rules.from_prop_rules(get_preset("lucid_50k").to_prop_rules(), payout=custom)
    assert r.payout.cap == 123.0


def test_lock_flag_is_explicit_even_when_the_offset_is_zero():
    r = V2Rules.from_prop_rules(get_preset("topstep_50k").to_prop_rules())
    assert r.lock_floor is True and r.lock_floor_offset == 0.0    # Topstep locks AT the start balance
    # A zero offset used to read as "no lock": the floor kept trailing past the start balance.
    rules = V2Rules(lock_floor=True, lock_floor_offset=0.0, trailing=True)
    from app.prop.lifecycle_v2 import _floor_update
    floor, mx = _floor_update(np.array([48000.0]), np.array([50000.0]), np.array([56000.0]), rules, 50000.0)
    assert float(floor[0]) == 50000.0
    unlocked = V2Rules(lock_floor=False, trailing=True)
    floor2, _ = _floor_update(np.array([48000.0]), np.array([50000.0]), np.array([56000.0]), unlocked, 50000.0)
    assert float(floor2[0]) == 54000.0


def test_tier_scales_cap_and_keeps_lock_flag():
    r = V2Rules.from_prop_rules(get_preset("lucid_50k").to_prop_rules()).tier(100_000)
    assert r.lock_floor is True and r.payout.cap == 4000.0


def test_simulation_runs_with_a_firm_rule_set():
    r = V2Rules.from_prop_rules(get_preset("lucid_50k").to_prop_rules())
    rng = np.random.default_rng(1)
    dm = rng.choice([-1.0, 2.0], size=(300, 3), p=[0.55, 0.45])
    res = simulate(dm, r, n_paths=500, seed=3)
    assert res.terms_sourced is True and 0 <= res.p_pass <= 100
