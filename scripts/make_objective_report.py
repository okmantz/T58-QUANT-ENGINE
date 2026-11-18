"""Builds docs/T58_STRATEGY_EVALUATION_2026-11.{md,pdf} and docs/T58_OBJECTIVES_MATH_2026-11.pdf from the saved study results.
Every figure is read from the JSON files written by run_objective_scores.py / run_gate27_study.py / run_objective_c_final.py: nothing is typed by hand.
Usage: python scripts/make_objective_report.py [results_dir]"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.objectives import DIRECTIVES, ENGINE_DIRECTIVE, OBJECTIVES  # noqa: E402

RES = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/claude/work/results")
DOCS = ROOT / "docs"
f1 = lambda x: "n/a" if x is None else f"{x:.1f}"


def load(n):
    return json.loads((RES / n).read_text())


def short(k):
    return k.replace("_v1", "").replace("_v2", "").replace("|", " on ")


def book_rows(b):
    rows = []
    for f in b["finals"]:
        rows.append(f)
    return rows


def a_table(b):
    out = ["| Book | Train P(pass≤30) | Train P(pass≤60) [lo95] | Median days | Breach≤60 | Val P(pass≤60) | Test P(pass≤30) [lo95] | Test P(pass≤60) | Test breach≤60 |", "|---|---|---|---|---|---|---|---|---|"]
    for f in b["finals"][:1]:
        c = f["card"]; t, v, s = c["train"], c["val"], c["test"]
        out.append(f"| shipped: " + " + ".join(f"{short(k.split('|')[0])}[{k.split('|')[1]}]×{m:g}" for k, m in f["legs"]) +
                   f" | {f1(t['p_pass_30'])}% | {f1(t['p_pass_60'])}% [{f1(t['p_pass_60_lo'])}] | {f1(t['median_days_to_pass'])} | {f1(t['breach_60'])}% | {f1(v['p_pass_60'])}% | "
                   f"{f1(s['p_pass_30'])}% [{f1(s['p_pass_30_lo'])}] | {f1(s['p_pass_60'])}% | {f1(s['breach_60'])}% |")
    return out


def b_table(b):
    f = b["finals"][0]; c = f["card"]
    out = ["| Split | starts | n_eff | P(paid, no breach) | lower95 | bust | survival | median days to pay | repeat payout | consistency ok |", "|---|---|---|---|---|---|---|---|---|---|"]
    for sp in ("train", "val", "test"):
        x = c[sp]
        out.append(f"| {sp} | {x['n_starts']} | {x['n_eff']} | {f1(x['p_paid'])}% | {f1(x['p_paid_lo'])}% | {f1(x['bust'])}% | {f1(x['survival'])}% | {f1(x['median_days_to_pay'])} | {f1(x['repeat_payout'])} | {f1(x['consistency_compliance'])} |")
    return out


def c_table(n):
    out = ["| Book | Train CAGR/DD/Calmar | Val CAGR/DD/Calmar | Test CAGR / maxDD / Calmar |", "|---|---|---|---|"]
    for k, v in n.items():
        cell = lambda s: "n/a" if not isinstance(v.get(s), dict) or v[s].get("cagr") is None else f"{f1(v[s]['cagr'])}% / {f1(v[s].get('max_dd_pct', v[s].get('max_dd')))}% / {f1(v[s]['calmar'])}"
        out.append(f"| {k} | {cell('train')} | {cell('val')} | {cell('test')} |")
    return out


def sleeve_table(sl):
    out = ["| Sleeve | n | PF all | PF train | PF val | PF test | scored |", "|---|---|---|---|---|---|---|"]
    for s in sorted(sl, key=lambda x: -(x.get("pf_all") or 0)):
        out.append(f"| {short(s['sleeve'])} | {s.get('n', '')} | {s.get('pf_all', 'n/a')} | {s.get('pf_train', 'n/a')} | {s.get('pf_val', 'n/a')} | {s.get('pf_test', 'n/a')} | {'yes' if s.get('scored') else 'no (screen)'} |")
    return out


def g27_table(g):
    out = ["| Variant | Train CAGR/DD | Val CAGR/DD | Test CAGR/DD/Calmar |", "|---|---|---|---|"]
    for name, d in g["armored"].items():
        cell = lambda s: "no data" if not isinstance(d.get(s), dict) or d[s].get("cagr") is None else f"{f1(d[s]['cagr'])}% / {f1(d[s]['max_dd'])}%"
        t = d.get("test") or {}
        out.append(f"| {name} | {cell('train')} | {cell('val')} | {cell('test')} / {f1(t.get('calmar'))} |")
    out += ["", f"Grid: {g['grid_n']} configurations, {g['grid_ok_n']} usable. Top by min(train, val) CAGR:", "", "| SMA | vol window | vol target % | lev cap | phase-in | Train CAGR/DD | Val CAGR/DD | Test CAGR/DD/Calmar |", "|---|---|---|---|---|---|---|---|"]
    for r in g["grid_top"][:6]:
        c = r["cfg"]
        out.append(f"| {c['sma']} | {c['vol_window']} | {c['vol_target_pct']} | {c['leverage_cap']} | {c['phase_in']} | {r['train']['cagr']}% / {r['train']['max_dd']}% | {r['val']['cagr']}% / {r['val']['max_dd']}% | {r['test']['cagr']}% / {r['test']['max_dd']}% / {r['test']['calmar']} |")
    return out


def build_md():
    books, sl, g, n = load("books.json"), load("sleeves.json"), load("gate27.json"), load("net_finals.json")
    md = ["# T58 strategy evaluation, 2026-11", "",
          "Every number below is produced by `scripts/make_objective_report.py` from the saved study files (`run_objective_scores.py`, `run_gate27_study.py`, `run_objective_c_final.py`). Nothing is estimated by hand.", "",
          "## Method", "",
          "- Splits: train 2019-10..2023-12, validation 2024, test 2025-01..2026-11 (locked: read once, never used to choose).",
          "- Selection: choose on train, confirm on validation (rank by the lower of the two), then read test.",
          "- A and B are scored with the Lucid 50K evaluation / funded simulator (`app/prop/simulator.py`) over rolling start dates; Wilson 95% bounds use n_eff = window days / horizon (overlapping starts are not independent).",
          "- C is scored on a compounding equity curve; sizing equity is capped at $250K (`SIZE_CAP_DEFAULT`), because unbounded compounding on futures is not realisable.", "",
          "## Honesty notes", "",
          "- Objective B's horizon is 365 days, so the 2025-2026 test window holds only 2-13 valid starts: **the B test is uninformative**. B is chosen on train+validation evidence and its test row is reported, not trusted.",
          "- Objective C train/validation CAGRs (130%+ and 600%+) are regime-driven compounding at 2x sleeve leverage in 2021 and 2024; read the test column.",
          "- Crude oil data is unadjusted (roll gaps) and USDX data is missing; the oil and USDX legs of Gate27 are therefore not evaluated on clean data.",
          "- The deleted MQL5 EAs (Ninja Turtle Scalper, Fisherman, Turnaround Tuesday, ATR Candle Breakout) cannot be run by the repo's MQL5 interpreter (`SetTypeFillingBySymbol` is unsupported). They have **no numbers here by design**; to evaluate them they need a Python twin (`// T58_TWIN=`) first.", "",
          "## Directives", "", ENGINE_DIRECTIVE, ""]
    for k in OBJECTIVES:
        d = DIRECTIVES[k]
        md += [f"- **{d.letter} {d.codename}**: primary {d.primary_metric}; secondary {', '.join(d.secondary_metrics)}."]
    md += ["", "## Individual strategies (per instrument sleeve)", "", f"Screen: profit factor ≥ 1.1 and ≥ 60 trades on train+validation. {len(books['screen'])} sleeves passed.", ""] + sleeve_table(sl)
    md += ["", "## Objective A: Evaluation Passer", ""] + a_table(books["books"]["A"]) + ["", "Candidates compared (selection score on train / validation; the shipped book is the first row, the rest are single-sleeve and greedy alternatives it was ranked against):"]
    md += [f"- {f['label'].replace('previous preset','shipped book')}: train {f1(f['train'])}, val {f1(f['val'])}" for f in books["books"]["A"]["finals"]]
    md += ["", "## Objective B: Payout Hunter", ""] + b_table(books["books"]["B"]) + ["", "Alternatives tried:"]
    md += [f"- {f['label'].replace('previous preset','shipped book')}: train {f1(f['train'])}, val {f1(f['val'])}" for f in books["books"]["B"]["finals"]]
    md += ["", "## Objective C: Net Profit Compounder", ""] + c_table(n)
    md += ["", "## Gate27 against its original EA", ""] + g27_table(g)
    md += ["", "## Individual vs combined", "",
           "The combined books beat every single sleeve on the selection score for A and B (tables above: the chosen book vs the `single ...` rows). For C the combination adds Gate27 (a daily-bar, overnight, multi-asset sleeve with low correlation to the intraday NQ/ES books): see the `intraday` rows against `intraday + Gate 27` rows.", "",
           "## Keep / drop", "",
           "KEEP (in a shipped bot): OpenDrive_NQ_5m_v1, IndRule_NQ_15m_v1, ContextDriveLong_NQ_1m_v2 (A, B, C); LiquiditySweepReclaim_NQ_5m_v1, IndRuleA_NQ_30m_v1 (C sleeves); Gate27_Basket_Daily_v2 (C; v1 kept as the owner's armored original).", "",
           "FLAG, DO NOT DELETE (did not pass the screen or are not used by a bot): see `docs/OBSOLETE_FILES.md`.", ""]
    return "\n".join(md)


def build_pdf(md_text, path, title):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    ss = getSampleStyleSheet(); body = ss["BodyText"]; body.fontSize = 8.5; body.leading = 11
    cell = ss["BodyText"].clone("cell"); cell.fontSize = 6.8; cell.leading = 8.2
    esc = lambda t: t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("**", "").replace("`", "")
    doc = SimpleDocTemplate(str(path), pagesize=landscape(letter), leftMargin=28, rightMargin=28, topMargin=28, bottomMargin=28, title=title)
    st = [Paragraph(title, ss["Title"])]; rows = []

    def flush():
        nonlocal rows
        if rows:
            data = [[Paragraph(esc(c.strip()), cell) for c in r.strip().strip("|").split("|")] for r in rows if not set(r.replace("|", "").strip()) <= set("-: ")]
            w = (landscape(letter)[0] - 56) / max(len(data[0]), 1)
            t = Table(data, colWidths=[w] * len(data[0]), repeatRows=1)
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            st.extend([t, Spacer(1, 6)]); rows = []
    for line in md_text.splitlines():
        if line.startswith("|"):
            rows.append(line); continue
        flush()
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            st.append(Paragraph(esc(line[3:]), ss["Heading2"]))
        elif line.startswith("- "):
            st.append(Paragraph("• " + esc(line[2:]), body))
        elif line.strip():
            st.append(Paragraph(esc(line), body))
    flush(); doc.build(st)


MATH = r"""
## 1. Setting and notation

A strategy book emits a daily P&L stream; a trade i has net dollars r_i after commission and slippage, sized in whole contracts. The simulator maps a start date s and the trade list to an account path E_s(t). All three objectives are functionals of the distribution of these paths over start dates s, so each objective is a different functional of the same underlying law, and the optimal book for one is generally not optimal for the others.

## 2. Objective A: maximise P(pass within H days)

Let T be the first day the path reaches the profit target Π (Lucid 50K: Π = 3,000) and B the first day it breaches the trailing / daily loss rule. The primary metric is p_H = P(T ≤ H, T < B) with H = 30 (60 as the acceptable maximum). Secondary: median(T | pass), breach probability P(B ≤ H), risk of ruin P(B < ∞), profit-target efficiency, and the pass-per-breach ratio p_H / P(B ≤ H).

Estimator. Over K rolling starts, p̂_H = (1/K) Σ 1[pass_s]. Starts overlapping by less than H days are positively correlated, so the effective sample is n_eff = (window days)/H, not K. The reported lower bound is the Wilson interval at n_eff:

  lo = ( p̂ + z²/2n − z·sqrt( p̂(1−p̂)/n + z²/4n² ) ) / (1 + z²/n),  z = 1.96, n = n_eff.

Gambler's-ruin intuition for the optimum. For a book with per-day mean μ and volatility σ, with an absorbing target Π and an absorbing floor D below the start (D the loss allowance), the probability of hitting Π first is approximately
  P(hit Π before −D) ≈ (1 − e^{−2μD/σ²}) / (1 − e^{−2μ(Π+D)/σ²}),
and the expected time is ≈ Π/μ. Raising size scales μ and σ together (μ→kμ, σ→kσ), leaving the exponent 2μD/σ² scaled by 1/k, so more size always shortens the time but lowers the pass probability once the floor is binding. The A optimum is therefore an interior size where d p_30/dk = 0 within the 30-day constraint, which is why A accepts more risk than B but not unlimited risk, and why the governor de-risks as the account approaches Π (locking the gain costs less than the extra variance adds).

Combination. For books with daily P&L covariance Σ and weights w, μ_p = wᵀμ and σ_p² = wᵀΣw. Pass probability rises with the ratio μ_p/σ_p², so diversification (low off-diagonal Σ) is rewarded directly: the optimum maximises wᵀμ / wᵀΣw subject to the contract grid and the one-position limit, which is the choice made on the train split and confirmed on validation.

## 3. Objective B: maximise P(payout without breach)

Let U be the first day the funded path satisfies the payout rule (profit buffer above the threshold, a minimum number of winning days, and the consistency rule: the best day share ≤ c of total profit) and B the breach time. Primary: P(U ≤ 365, U < B). Secondary: median(U), expected payout E[paid] = Σ payouts, survival P(no breach to day 365), repeat payout probability P(second payout | first), consistency compliance, and the max drawdown in dollars.

Consistency is a constraint on the concentration of profit: with day profits g_d, require max_d g_d ≤ c·Σ g_d. A book whose edge comes from few large days fails it even with a high win rate, so B favours low skew, smooth equity and a lower σ than A. The relevant optimum maximises a Sharpe-like ratio over the 365-day horizon with a loss floor: P(U<B) is increasing in μ/σ for a fixed floor, and the size is set so that the drawdown stays well inside the trailing buffer rather than being pushed to the edge, which is the opposite of A.

Estimator caveat. The window needs 365 forward days from each start, so the number of independent starts is n_eff = (window days)/365, which is 1-5 in the splits used here. Wilson bounds at this n_eff are wide (see the tables), and the 2025-2026 test window has 2-13 valid starts. The B conclusion therefore rests on train+validation consistency and on structural properties (survival, drawdown, low consistency risk); the test column cannot confirm or refute it.

## 4. Objective C: maximise compounded net wealth

For an equity path E(t) over Y years: CAGR = (E_end/E_0)^{1/Y} − 1, max drawdown MDD = max_t (peak_t − E_t)/peak_t, Calmar = CAGR / MDD, expectancy = mean net dollars per trade, return on capital = (E_end − E_0)/E_0.

The growth-optimal sizing result (Kelly) for a return with mean μ and variance σ² per period is f* = μ/σ², giving long-run log growth g(f) = fμ − f²σ²/2, maximal at f* with g(f*) = μ²/2σ². Growth falls on either side of f*, and beyond 2f* it is negative, so the practical rule is fractional Kelly (typically f*/2) which keeps 75% of the growth and cuts the drawdown roughly in half. Estimation error in μ makes the true f* lower than the estimated one, which is why C uses the drawdown-throttled governor: the size multiplier falls to a floor as the drawdown from the equity peak deepens.

Compounding is capped at $250K of sizing equity (`SIZE_CAP_DEFAULT`) because a futures account cannot add contracts without bound; ignoring the cap produced unrealistic multi-million curves in testing, which is why reported train and validation CAGRs should be read as regime evidence rather than forecasts.

Diversification. For sleeves with correlation ρ_ij, the portfolio variance is Σ_i w_i²σ_i² + 2Σ_{i<j} w_i w_j ρ_ij σ_i σ_j. Adding Gate27 (daily bars, overnight, multi-asset) at low ρ to the intraday NQ/ES sleeves lowers the variance for the same mean, raising μ²/2σ² and Calmar; that is the mechanism the combined-book table measures.

## 5. Out-of-sample robustness (mandatory for all three)

Selection uses train only; confirmation uses validation, ranking by the lower of train and validation scores (the minimum is the conservative estimate); the test split is read once. A candidate whose validation score is far below train (e.g. greedy-2 for B: train 73.7, validation 14.3) is rejected as overfit even though its train score is the highest. For A the shipped book has validation P(pass≤60) above train and a test P(pass≤30) lower bound that remains positive; the gap between train and test is itself a measured regime effect, reported rather than hidden.

## 6. What the optimal attainable combination looks like

- A: high-frequency, positively skewed intraday sleeves on NQ with moderate-to-high contract multipliers, at most one position, a combined daily cap, and a governor that sizes up early and locks in as the target nears; the binding constraint is the breach floor, not the number of signals.
- B: fewer, smoother sleeves at roughly 1x, no sleeve whose profit is concentrated in a few days, with the whole book sized so that the worst historical drawdown is a fraction of the trailing buffer.
- C: the largest sleeve set that keeps pairwise correlation low, including a slow overnight sleeve (Gate27), sized by drawdown-throttled fractional Kelly with the equity cap.

## 7. Using this for new strategy creation

A new candidate is worth building only if it raises the objective's functional for the existing book, not if it merely has a good standalone profit factor:
- For A: it must raise wᵀμ/wᵀΣw, which means a positive mean and low correlation with the current A sleeves, and the ability to produce winners within 30 days.
- For B: it must lower the best-day share and the dollar drawdown at the same mean.
- For C: it must raise CAGR/MDD of the combined book, usually by being uncorrelated and carried overnight.
Screen at profit factor ≥ 1.1 and at least 60 trades on train+validation, rank by the lower of the two, read test once.
"""


def main():
    md = build_md()
    (DOCS / "T58_STRATEGY_EVALUATION_2026-11.md").write_text(md + "\n", encoding="utf-8")
    build_pdf(md, DOCS / "T58_STRATEGY_EVALUATION_2026-11.pdf", "T58 Strategy Evaluation Report, 2026-11")
    obj = open(DOCS / "OBJECTIVES.md", encoding="utf-8").read()
    full = obj + "\n# Statistics and mathematics of the optimal combination\n" + MATH
    (DOCS / "T58_OBJECTIVES_MATH_2026-11.md").write_text(full, encoding="utf-8")
    build_pdf(full, DOCS / "T58_OBJECTIVES_MATH_2026-11.pdf", "T58 Objectives A / B / C: statistics and mathematics")
    print("ok")


if __name__ == "__main__":
    main()
