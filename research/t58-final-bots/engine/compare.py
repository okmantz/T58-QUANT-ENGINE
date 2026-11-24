"""Build final/COMPARISON tables from research/baseline_dev*.csv, final_dev.csv, final_hold.csv (same scoring code throughout).
Usage: python3 compare.py -> prints markdown tables, writes research/comparison_long.csv"""
import pandas as pd, numpy as np
R = "research/t58_final_bots/research"
d = pd.concat([pd.read_csv(f"{R}/baseline_dev.csv"), pd.read_csv(f"{R}/baseline_dev_flex.csv"), pd.read_csv(f"{R}/final_dev.csv"),
               pd.read_csv(f"{R}/final_hold.csv")], ignore_index=True)
d.to_csv(f"{R}/comparison_long.csv", index=False)
HI = ["p_pass", "p_payout", "ev", "pf", "exp_R", "sharpe", "sortino", "worst_day", "trades_pm", "f90_payouts", "f90_paid", "f90_p2"]
LO = ["med_days_pass", "med_days_payout", "bust", "fund_bust", "max_dd", "cons_blocks_per30", "f90_bust"]
NAMES = dict(p_pass="P(pass in 30d)", med_days_pass="Median days to pass", bust="Eval bust", p_payout="P(first payout in 30d, funded)",
             med_days_payout="Median days to first payout", fund_bust="Funded bust", ev="90-day EV net of fees and resets ($)",
             pf="Profit factor", exp_R="Expectancy (R)", sharpe="Sharpe", sortino="Sortino", max_dd="Max drawdown ($)",
             worst_day="Worst day ($)", cons_blocks_per30="Consistency blocks per 30d", trades_pm="Trades a month",
             f90_payouts="Payouts in 90 funded days", f90_paid="$ paid in 90 funded days", f90_p2="P(2+ payouts in 90d)", f90_bust="90d funded bust")
def ok(m, a, b):
    if pd.isna(b): return pd.isna(a) or True if m not in ("med_days_pass", "med_days_payout") else True
    if pd.isna(a): return False
    return a >= b - 1e-9 if m in HI else a <= b + 1e-9
def fmt(m, v):
    if pd.isna(v): return "n/a"
    if m in ("p_pass", "p_payout", "bust", "fund_bust", "f90_p2", "f90_bust"): return f"{100*v:.1f}%"
    if m in ("ev", "max_dd", "worst_day", "f90_paid"): return f"{v:,.0f}"
    return f"{v:.2f}"
def table(base, bot, plan, cost, metrics):
    out = [f"| Metric | Research base | Research {bot} | Validation base | Validation {bot} | Holdout base | Holdout {bot} |", "|---|---|---|---|---|---|---|"]
    fails = []
    for m in metrics:
        row = [NAMES[m]]
        for sp in ("research", "validation", "holdout"):
            g = lambda who: d[(d.bot == who) & (d.plan == plan) & (d.split == sp) & (d.cost == cost)]
            a, b = g(bot), g(base)
            if a.empty or b.empty: row += ["", ""]; continue
            av, bv = a[m].iloc[0], b[m].iloc[0]; good = ok(m, av, bv)
            if not good: fails.append((sp, m, fmt(m, bv), fmt(m, av)))
            row += [fmt(m, bv), fmt(m, av) + ("" if good else " ✗")]
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out), fails
MA = ["p_pass", "med_days_pass", "bust", "p_payout", "med_days_payout", "ev", "pf", "exp_R", "sharpe", "sortino", "max_dd", "worst_day", "cons_blocks_per30", "trades_pm"]
MB = MA + ["f90_payouts", "f90_paid", "f90_p2", "f90_bust"]
if __name__ == "__main__":
    for bot, base, plan, ms in (("BOT-A", "baseline_A", "pro50", MA), ("BOT-B", "baseline_B", "flex50", MB)):
        for cost in ("stress", "base"):
            t, f = table(base, bot, plan, cost, ms)
            print(f"\n### {bot} vs {base} ({plan}, {cost} cost)\n\n{t}\n\nFails ({len(f)}): " + "; ".join(f"{s} {m} {b}->{a}" for s, m, b, a in f))
