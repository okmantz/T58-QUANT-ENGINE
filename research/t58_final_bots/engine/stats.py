"""Statistics for the factory (Statistical_Methodology.md 3): HAC t, deflated Sharpe, PBO by CSCV, block bootstrap. Written here (no statsmodels)."""
from __future__ import annotations
import math, itertools
import numpy as np
from scipy import stats as ss


def nw_t(x, lag=5):
    """Newey-West HAC t-stat of the mean of x."""
    x = np.asarray(x, float); x = x[np.isfinite(x)]; n = len(x)
    if n < 10: return np.nan
    e = x - x.mean(); g0 = e @ e / n; v = g0
    for k in range(1, min(lag, n - 1) + 1):
        v += 2 * (1 - k / (lag + 1)) * (e[k:] @ e[:-k]) / n
    return float(x.mean() / math.sqrt(v / n)) if v > 0 else np.nan


def sharpe(x):
    x = np.asarray(x, float)
    s = x.std(ddof=1)
    return float(x.mean() / s) if s > 0 else 0.0


def dsr(x, n_trials, sr_var):
    """Deflated Sharpe ratio (Bailey & Lopez de Prado 2014). x: per-period returns of the chosen config; n_trials: effective number of
    trials; sr_var: variance of per-period Sharpe across the trials. Returns P(true SR > SR0)."""
    x = np.asarray(x, float); T = len(x)
    if T < 30: return np.nan
    sr = sharpe(x); sk = ss.skew(x); ku = ss.kurtosis(x, fisher=False)
    g = 0.5772156649
    n = max(n_trials, 2)
    sr0 = math.sqrt(max(sr_var, 1e-12)) * ((1 - g) * ss.norm.ppf(1 - 1 / n) + g * ss.norm.ppf(1 - 1 / (n * math.e)))
    den = math.sqrt(max(1 - sk * sr + (ku - 1) / 4 * sr * sr, 1e-12))
    return float(ss.norm.cdf((sr - sr0) * math.sqrt(T - 1) / den))


def n_eff(R):
    """Effective number of independent trials from the correlation of the trial return matrix (T x N): N_eff = N / (1 + (N-1) rho_bar)."""
    N = R.shape[1]
    if N < 2: return 1.0
    C = np.corrcoef(R.T); rho = (C.sum() - N) / (N * (N - 1))
    return float(max(1.0, N / (1 + (N - 1) * max(rho, 0.0))))


def pbo(R, S=16):
    """Probability of backtest overfitting by CSCV. R: T x N per-period returns (rows = time). Best-in-sample by Sharpe; PBO = share of the
    C(S, S/2) splits where its out-of-sample rank is at or below the median."""
    T, N = R.shape
    if N < 2: return np.nan
    blocks = np.array_split(np.arange(T), S)
    s1 = np.array([R[b].sum(0) for b in blocks]); s2 = np.array([(R[b] ** 2).sum(0) for b in blocks]); nb = np.array([len(b) for b in blocks])
    logits = []
    for comb in itertools.combinations(range(S), S // 2):
        m = np.zeros(S, bool); m[list(comb)] = True
        def sr(mask):
            n = nb[mask].sum(); mu = s1[mask].sum(0) / n; var = s2[mask].sum(0) / n - mu ** 2
            return mu / np.sqrt(np.maximum(var, 1e-18))
        a, b = sr(m), sr(~m)
        best = int(np.argmax(a))
        rank = (b < b[best]).sum() + 0.5 * ((b == b[best]).sum() - 1)
        w = (rank + 1) / (N + 1)
        logits.append(math.log(w / (1 - w)))
    return float(np.mean(np.array(logits) <= 0))


def block_boot(x, n=2000, block=10, seed=0, stat=np.mean):
    x = np.asarray(x, float); T = len(x); rng = np.random.default_rng(seed)
    k = int(math.ceil(T / block)); out = np.empty(n)
    for j in range(n):
        st = rng.integers(0, T, k)
        idx = (st[:, None] + np.arange(block)[None, :]).ravel()[:T] % T
        out[j] = stat(x[idx])
    return out
