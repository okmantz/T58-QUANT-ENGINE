from app.validation.cost_headroom import find_breakeven_multiple


def test_finds_linear_breakeven():
    r = find_breakeven_multiple(lambda m: 1000.0 - 500.0 * (m - 1.0))   # zero at m = 3.0
    assert r.breakeven_multiple is not None and abs(r.breakeven_multiple - 3.0) < 0.1
    assert r.band in ("modest", "comfortable")


def test_unprofitable_at_baseline():
    r = find_breakeven_multiple(lambda m: -5.0)
    assert r.band == "unprofitable" and r.breakeven_multiple == 0.0 and "unprofitable" in r.summary()


def test_thin_edge():
    r = find_breakeven_multiple(lambda m: 100.0 - 80.0 * (m - 1.0))             # zero at m = 2.25 -> modest; use steeper below
    r2 = find_breakeven_multiple(lambda m: 100.0 - 400.0 * (m - 1.0))           # zero at m = 1.25
    assert r2.band == "thin" and 1.1 < r2.breakeven_multiple < 1.4
    assert r.band == "modest"


def test_never_breaks_even():
    r = find_breakeven_multiple(lambda m: 1e9)
    assert r.breakeven_multiple is None and r.band == "comfortable"
