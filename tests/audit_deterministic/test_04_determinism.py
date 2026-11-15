"""Same data + same strategy + same config => byte-identical trades, across repeated runs AND across processes with different
hash seeds (catches set/dict-ordering and unseeded-RNG nondeterminism)."""
import hashlib, json, os, subprocess, sys
from pathlib import Path
import pytest
from conftest import REPO

SCRIPT = r'''
import sys, json, hashlib, warnings
sys.path.insert(0, sys.argv[1])
import numpy as np, pandas as pd
warnings.simplefilter("ignore")
from app.backtest.execution import run_execution
from app.backtest.risk import RiskConfig
rng = np.random.default_rng(1234)
n = 4000
c = 4000 + np.cumsum(rng.normal(0, 2.0, n)); o = np.r_[c[0], c[:-1]]
h = np.maximum(o, c) + np.abs(rng.normal(0, 1, n)); l = np.minimum(o, c) - np.abs(rng.normal(0, 1, n))
df = pd.DataFrame(dict(timestamp=pd.date_range("2024-03-04 14:30", periods=n, freq="1min"), open=o, high=h, low=l, close=c, volume=100.0))
sig = pd.Series(np.where(pd.Series(c).rolling(5).mean() > pd.Series(c).rolling(20).mean(), 1, -1)).fillna(0).astype(int)
risk = RiskConfig(initial_balance=50000.0, risk_mode="fixed", risk_value=500.0, pip_size=1.0, contract_size=50.0,
                  commission_per_contract=2.0, slippage_pips=0.25, spread_pips=0.25, sizing_mode="fit_stop", max_trades_per_day=20)
tr, eq = run_execution(df, sig, risk, stop_loss_pips=8.0, take_profit_pips=12.0)
payload = [(str(t.entry_time), str(t.exit_time), t.direction, repr(t.entry_price), repr(t.exit_price), repr(t.size), repr(t.pnl), t.exit_reason) for t in tr]
print(len(tr), hashlib.sha256(json.dumps(payload).encode()).hexdigest(), hashlib.sha256(eq["equity"].round(6).astype(str).str.cat().encode()).hexdigest())
'''

def _run(seed):
    env = dict(os.environ, PYTHONHASHSEED=str(seed))
    out = subprocess.run([sys.executable, "-I", "-c", SCRIPT, str(REPO)], capture_output=True, text=True, env=env, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    return out.stdout.strip().splitlines()[-1]


def test_identical_across_processes_and_hash_seeds():
    results = {s: _run(s) for s in (0, 1, 12345)}
    assert len(set(results.values())) == 1, results
    assert int(next(iter(results.values())).split()[0]) > 20, "sanity: the determinism fixture must actually trade"
