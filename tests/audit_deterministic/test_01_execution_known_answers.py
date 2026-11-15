"""Deterministic known-answer tests for the bar execution engine.

Common setup (see synth.run): ES-like contract ($50/pt), zero friction, risk budget $1,050, stop 10 pts => whole-contract
sizing floor(1050 / (10 * 50)) = 2 contracts. Signal first non-zero on bar 1 => entry fills at the OPEN of bar 2 (100.0).
Therefore stop = 90, target = 120 (default tp=20), and P&L = price_move * 50 * 2.
"""
import pytest
from synth import F, run

STOP, TGT = 90.0, 120.0


def first(bars, **kw):
    trades, df, _ = run(bars, **kw)
    assert trades, "expected at least one trade"
    return trades[0], df


def test_entry_is_next_bar_open_and_sized_to_two_contracts():
    t, df = first([F, F, F, (100, 100.5, 89.5, 95), F, F])
    assert t.entry_time == df.timestamp[2]
    assert t.entry_price == 100.0
    assert t.size == 100.0                      # 2 contracts x 50 units


def test_entry_price_is_the_open_of_the_bar_after_the_signal_not_the_close():
    # distinct opens so a wrong bar is detectable: signal at bar 1 -> fill must be open[2] = 102.0
    bars = [(100, 100.1, 99.9, 100), (101, 101.1, 100.9, 101), (102, 102.1, 101.9, 102), (103, 103.1, 102.9, 103),
            (104, 104.1, 103.9, 104), (105, 105.1, 104.9, 105)]
    t, df = first(bars, sl=10, tp=50)
    assert t.entry_time == df.timestamp[2] and t.entry_price == 102.0


def test_long_stop_fills_exactly_at_the_stop_level():
    # bar 3 low 89.5 < 90: stop at 90.0 exactly, 10 pts x $50 x 2 = -$1,000
    t, df = first([F, F, F, (100, 100.5, 89.5, 95), F, F])
    assert (t.exit_reason, t.exit_price, round(t.pnl, 6)) == ("stop_loss", 90.0, -1000.0)
    assert t.exit_time == df.timestamp[3]


def test_long_target_fills_exactly_at_the_target_level():
    t, _ = first([F, F, F, (100, 120.5, 99.9, 119), F, F])
    assert (t.exit_reason, t.exit_price, round(t.pnl, 6)) == ("take_profit", TGT, 2000.0)


def test_stop_and_target_in_the_same_bar_resolves_to_the_stop_pessimistic():
    t, _ = first([F, F, F, (100, 125, 85, 100), F, F])
    assert t.exit_reason == "stop_loss" and t.exit_price == STOP and round(t.pnl, 6) == -1000.0


def test_gap_down_through_the_stop_fills_at_the_open_not_the_stop():
    # bar 3 opens at 80 (below the 90 stop): fill 80.0 => -20 x 50 x 2 = -$2,000
    t, _ = first([F, F, F, (80, 81, 79, 80), F, F])
    assert (t.exit_reason, t.exit_price, round(t.pnl, 6)) == ("stop_loss", 80.0, -2000.0)


def test_gap_up_through_the_target_is_filled_at_the_target_conservative_convention():
    """DOCUMENTED CONVENTION (not a defect, but a pessimistic one): a resting limit sell at 120 that opens at 130 would
    fill at 130 in reality; this engine fills at 120. Pin it so a change is a conscious decision."""
    t, _ = first([F, F, F, (130, 131, 129, 130), F, F])
    assert (t.exit_reason, t.exit_price) == ("take_profit", TGT)


def test_short_mirror_stop_and_target():
    t, _ = first([F, F, F, (100, 110.5, 99, 105), F, F], direction=-1)            # short from 100: stop 110, target 80
    assert (t.exit_reason, t.exit_price, round(t.pnl, 6)) == ("stop_loss", 110.0, -1000.0)
    t, _ = first([F, F, F, (100, 100.5, 79.5, 85), F, F], direction=-1)
    assert (t.exit_reason, t.exit_price, round(t.pnl, 6)) == ("take_profit", 80.0, 2000.0)


def test_short_gap_up_through_stop_fills_at_the_open():
    t, _ = first([F, F, F, (120, 121, 119, 120), F, F], direction=-1)
    assert (t.exit_reason, t.exit_price, round(t.pnl, 6)) == ("stop_loss", 120.0, -2000.0)


def test_trailing_stop_ratchets_to_high_minus_distance_and_never_widens():
    # trail 5 pts. bar3 high 110 (low 106 stays above the new 105 stop) => stop 105. bar4 low 104 => exit at 105: +5 x 50 x 2.
    t, _ = first([F, F, F, (108, 110, 106, 109), (109, 109, 104, 105), F, F], trail=5, tp=50)
    assert (t.exit_reason, t.exit_price, round(t.pnl, 6)) == ("stop_loss", 105.0, 500.0)


def test_breakeven_moves_the_stop_to_entry_after_plus_1r():
    # +1R = 10 pts. bar3 high 111 triggers; bar4 low 99 < 100 => exit at the entry price, P&L exactly 0 with zero friction.
    t, _ = first([F, F, F, (100, 111, 100.5, 110), (110, 110, 99, 100), F, F], be=1.0, tp=50)
    assert t.exit_price == 100.0 and abs(t.pnl) < 1e-9


def test_costs_slippage_and_per_contract_commission_exact():
    """slippage 0.25 pt per side, commission $2.50 per contract, 2 fixed contracts.
    entry = 100 + 0.25 = 100.25; stop = 100.25 - 10 = 90.25; exit = 90.25 - 0.25 = 90.00.
    P&L = (90.00 - 100.25) x 50 x 2 - 2.50 x 2 = -1025 - 5 = -$1,030."""
    t, _ = first([F, F, F, (100, 100.5, 89.5, 95), F, F], sizing_mode="fixed_contracts", fixed_contracts=2,
                 slippage_pips=0.25, commission_per_contract=2.5)
    assert t.entry_price == 100.25 and t.exit_price == 90.0 and round(t.pnl, 6) == -1030.0


def test_spread_is_charged_per_side_documented_convention():
    """spread_pips=1.0 => entry 101.0 (+1), stop 91.0, exit 90.0 (-1): the FULL spread is charged on EACH side
    (round trip = 2x spread_pips). For ES with the registry default (1 tick spread + 1 tick slippage) this is 4 ticks
    round trip. Pinned so the convention cannot change silently; see audit report section 3."""
    t, _ = first([F, F, F, (100, 100.5, 89.5, 95), F, F], sizing_mode="fixed_contracts", fixed_contracts=2, spread_pips=1.0)
    assert t.entry_price == 101.0 and t.exit_price == 90.0 and round(t.pnl, 6) == -1100.0


def test_whole_contract_sizing_floor_and_skip_when_budget_too_small():
    # budget 1050, 10pt stop, $50/pt => 2.1 -> 2 contracts. budget 450 => 0.9 -> 0 contracts => signal skipped (no trade)
    t, _ = first([F, F, F, (100, 100.5, 89.5, 95), F, F])
    assert t.size == 100.0
    trades, _, _ = run([F, F, F, (100, 100.5, 89.5, 95), F, F], risk_value=450.0)
    assert trades == []


def test_no_signal_no_trade_and_flat_equity():
    trades, df, eq = run([F] * 6, start=10)
    assert trades == [] and float(eq["equity"].iloc[-1]) == 50000.0
