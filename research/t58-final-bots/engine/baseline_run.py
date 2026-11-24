"""Write the baseline tables (research + validation) for both plans: research/baseline_dev.csv (Pro base + stress) and
research/baseline_dev_flex.csv (Flex base + stress), each with the sustained-payout block."""
import sys, pandas as pd
sys.path.insert(0, "research/t58_final_bots/engine")
import baseline as B, score, firm, data as D
SPL = {"research": ("2020-01-01", "2024-01-01"), "validation": ("2024-01-01", "2026-03-02" if D.R3 else "2025-09-01")}
SFX = "_r3" if D.R3 else ""
def table(plans, out):
    rows = []
    for pn, p in plans:
        for obj, legs in (("A", B.LEGS_A), ("B", B.LEGS_B)):
            bk = B.bot_book(legs)
            for sp, (a, b) in SPL.items():
                pol = B.policy(obj, B.lite(p))
                r = score.full(bk, pol, p, a, b); r.update(score.sustained_block(bk, pol, p, a, b))
                r.update(bot="baseline_" + obj, plan=pn, cost=p.cost, split=sp); rows.append(r)
    pd.DataFrame(rows).to_csv(out, index=False)
if "flexonly" not in sys.argv: table([("pro50", firm.Plan()), ("pro50", firm.Plan(cost="stress"))], "research/t58_final_bots/research/baseline_dev" + SFX + ".csv")
table([("flex50", firm.Plan.flex50()), ("flex50", firm.Plan.flex50(cost="stress"))], "research/t58_final_bots/research/baseline_dev_flex" + SFX + ".csv")
