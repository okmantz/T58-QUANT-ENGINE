"""Firm-engine unit tests (Statistical_Methodology.md 2.4). Run: python3 -m pytest -q tests (from code/)."""
import sys, numpy as np
sys.path.insert(0, ".")
import firm

def book(days_pnl, inst="NQ", mae=None):
    n = len(days_pnl)
    days = np.array([np.datetime64("2024-01-01") + np.timedelta64(k, "D") for k in range(n)])
    ent = np.array([np.datetime64(str(d) + "T15:00") for d in days]); ex = ent + np.timedelta64(60, "m")
    return dict(entry=ent, exit=ex, day=days, inst=np.array([inst] * n), pts=np.array(days_pnl, float) / firm.PVM[inst],
                risk_pts=np.ones(n), mae_pts=np.array(mae if mae is not None else [0.0] * n, float), w=np.ones(n))

one = lambda st, p, i, o: firm.PVM["NQ"] * 1.0   # exactly one micro
P0 = dict(cost="none", dll=None)

def test_spec_2_6_example():
    tr = book([800, -500, 1900, 800])
    daily = []
    o = firm.run(tr, "2024-01-01", 30, firm.Plan(**P0), one, daily=daily)
    assert o["pass_day"] == 3 and o["breach_day"] is None and abs(o["profit_at_pass"] - 3000) < 1e-6

def test_floor_locks_and_never_exceeds_lock():
    tr = book([2100, 2000, -3900])          # high 54,100 -> floor locked 50,100; balance 50,200 survives
    p = firm.Plan(target=1e9, **P0)
    o = firm.run(tr, "2024-01-01", 30, p, one)
    assert o["breach_day"] is None and abs(o["final_bal"] - 50_200) < 1e-6

def test_breach_exactly_at_floor():
    tr = book([-2000])
    o = firm.run(tr, "2024-01-01", 30, firm.Plan(**P0), one)
    assert o["breach_day"] == 0

def test_intraday_mae_breach_and_eod_switch():
    tr = book([100], mae=[1000.0 / 2])      # MAE of $1,000? no: 500 pts * $2 = $1,000 ... use 2,000
    tr["mae_pts"] = np.array([1000.0])      # $2,000 adverse -> touches the floor
    assert firm.run(tr, "2024-01-01", 30, firm.Plan(**P0), one)["breach_day"] == 0
    assert firm.run(tr, "2024-01-01", 30, firm.Plan(breach_check="eod", **P0), one)["breach_day"] is None

def test_target_exactly_met():
    o = firm.run(book([3000]), "2024-01-01", 30, firm.Plan(**P0), one)
    assert o["pass_day"] == 0

def test_dll_soft_cut():
    tr = book([-1500, 100]); tr["mae_pts"] = np.array([750.0, 0])
    o = firm.run(tr, "2024-01-01", 30, firm.Plan(cost="none", dll=1200.0, target=1e9), one)
    assert o["breach_day"] is None and abs(o["final_bal"] - (50_000 - 1200 + 100)) < 1e-6 and o["dll_hits"] == 1

def test_payout_at_exact_balance_and_consistency():
    # funded: four days of +650 -> cycle 2,600, best day 25% -> eligible at 52,600 for a $500 request
    o = firm.run(book([650, 650, 650, 650]), "2024-01-01", 30, firm.Plan(**P0), one, phase="funded")
    assert o["payouts"] == [(3, 500.0)]
    # one big day: 2,000 + 300 + 300 -> best share 77% -> blocked
    o = firm.run(book([2000, 300, 300]), "2024-01-01", 30, firm.Plan(**P0), one, phase="funded")
    assert o["payouts"] == [] and o["cons_block"] >= 1

def test_payout_cap_and_buffer():
    o = firm.run(book([1100] * 5), "2024-01-01", 30, firm.Plan(**P0), one, phase="funded")
    d, amt = o["payouts"][0]
    assert amt <= 2000 + 1e-9 and o["final_bal"] >= 52_100 - 1e-9

def test_joint_lifecycle_same_path():
    o = firm.run(book([3000, 650, 650, 650, 650]), "2024-01-01", 30, firm.Plan(**P0), one, stop_at_pass=False)
    assert o["pass_day"] == 0 and o["funded_day"] == 1 and o["payouts"] and o["payouts"][0][0] == 4

def test_scale_invariance():
    a = firm.run(book([800, -500, 1900, 800]), "2024-01-01", 30, firm.Plan(**P0), one)
    two = lambda st, p, i, o: 2 * firm.PVM["NQ"]
    b = firm.run(book([400, -250, 950, 400]), "2024-01-01", 30, firm.Plan(**P0), two)
    assert a["pass_day"] == b["pass_day"]

def test_contract_cap():
    big = lambda st, p, i, o: 1e9
    tr = book([10.0]); o = firm.run(tr, "2024-01-01", 30, firm.Plan(cost="none", dll=None, target=1e9), big)
    assert abs(o["final_bal"] - 50_000 - 40 * 10.0) < 1e-6

def test_flex_eval_consistency_and_payout():
    p = firm.Plan.flex50(cost="none", dll=None)
    o = firm.run(book([3000, 100, 100]), "2024-01-01", 30, p, one)       # $3,000 day is > 40% of profit -> not passed
    assert o["pass_day"] is None
    o = firm.run(book([1000, 1000, 1000]), "2024-01-01", 30, p, one)
    assert o["pass_day"] == 2
    o = firm.run(book([200] * 5), "2024-01-01", 30, p, one, phase="funded")
    assert o["payouts"] == [(4, 500.0)]                                   # 50% of $1,000
