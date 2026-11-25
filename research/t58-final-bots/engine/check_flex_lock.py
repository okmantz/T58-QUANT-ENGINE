"""What-if, validation split only (2024-01-01 .. 2026-03-01; the sealed holdout is not read): score the Flex bots under the current
model (firm.py) and with Lucid's 'payout request locks the MLL at $50,100' rule (firm_lockpay.py). Writes research/flex_lock_check.csv."""
import os, sys, importlib
os.environ["T58_R3"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
rows = []
for variant in ("current_model", "lock_on_payout"):
    for m in [k for k in list(sys.modules) if k in ("firm", "score", "search", "final_score_r3", "baseline", "filters", "policy")]:
        del sys.modules[m]
    if variant == "lock_on_payout":
        import firm_lockpay; sys.modules["firm"] = firm_lockpay
    import final_score_r3 as F, score
    for who in ("baseline_B", "BOT-B-R2", "BOT-B-R3", "BOT-B-R3-port"):
        p = F.plan_of("flex50", "stress"); bk, pol = F.book_pol(who, p, False)
        r = score.full(bk, pol, p, "2024-01-01", "2026-03-02", stride=1); r.update(score.sustained_block(bk, pol, p, "2024-01-01", "2026-03-02"))
        r.update(bot=who, variant=variant); rows.append(r); print(variant, who, round(r["p_payout"], 3), round(r["fund_bust"], 3), round(r["f90_bust"], 3), round(r["f90_paid"]), flush=True)
pd.DataFrame(rows).to_csv("research/t58_final_bots/research/flex_lock_check.csv", index=False)
