"""The three shipped bots, calibrated from the Game Plan and re-tested with the bot risk governor
(see docs/T58_BOT_RESEARCH.md). Each one runs the same NQ strategy family with a different risk brain."""
from __future__ import annotations

from app.bots.models import AccountLink, BotConfig, BotLeg
from app.bots.risk_governor import GovernorConfig

OD = BotLeg("python/NQ1! Open Drive Continuation 5m.py", "Open Drive", "NQ", 1.0, 0, 45,
            "Opening-drive continuation, one shot a day.")
IR = BotLeg("python/NQ1! Ind Rule 15m.py", "Ind Rule", "NQ", 1.0, 1, 15, "Trend rule on 15m; also trades Globex.")
CAD = BotLeg("python/NQ1! Context Aligned Drive 1m v2.py", "Context Drive", "NQ", 1.0, 0, 500,
             "Drive aligned with higher-timeframe context (needs ~500 days of history to warm up).")
GAD = BotLeg("python/MNQ1! Gap Aligned Drive RW Tight Stop 1m.py", "Gap Drive", "NQ", 1.0, 1, 30,
             "Gap-aligned drive with a tight stop.")
LSR = BotLeg("python/NQ1! Liquidity Sweep Reclaim 5m.py", "Sweep Reclaim", "NQ", 1.0, 3, 30,
             "Liquidity sweep and reclaim; low-priority filler.")


def _acct() -> AccountLink:
    return AccountLink(venue="demo", account_id="t58-demo", size=50_000.0, broker_symbol="MNQ", preset_key="lucid_50k")


def preset_configs() -> list[BotConfig]:
    gov_a = GovernorConfig(objective="A", base_risk_pct=1.0, early_mult=1.0, mid_mult=1.0, late_mult=0.7,
                           need_risk_mult=1.0, day_stop_frac=0.40)
    gov_b = GovernorConfig(objective="B", base_risk_pct=1.0, cushion_risk_frac=0.25, day_stop_frac=0.30)
    gov_n = GovernorConfig(objective="NET", base_risk_pct=1.0, compounding=True, dd_throttle_tol_pct=10.0,
                           min_risk_dollars=1.0, cushion_risk_frac=0.5)
    return [
        BotConfig(id="bot-pass", name="Evaluation Passer", objective="A", preset_key="pass",
                  tagline="Pass the prop-firm evaluation fast.",
                  description="Four strategies, full size early, trimming as the target nears. Risk is capped by the cushion "
                              "above the drawdown floor and the day stops at 40% of the daily limit.",
                  legs=[OD, IR, CAD, GAD], governor=gov_a.to_dict(), account=_acct()),
        BotConfig(id="bot-payout", name="Payout Hunter", objective="B", preset_key="payout",
                  tagline="Get to the first payout without busting.",
                  description="Three strategies with risk limited to a quarter of the cushion, a tighter day stop and "
                              "smaller size once funded. Built for payouts per year, not speed.",
                  legs=[OD, IR, CAD], governor=gov_b.to_dict(), account=_acct()),
        BotConfig(id="bot-profit", name="Net Profit Compounder", objective="NET", preset_key="profit",
                  tagline="Maximise net profit per unit of drawdown.",
                  description="Five strategies, size follows equity and shrinks automatically as drawdown deepens. "
                              "On a prop account it also never risks more than half the cushion; its research numbers assume no prop limits.",
                  legs=[OD, IR, CAD, GAD, LSR], governor=gov_n.to_dict(), account=_acct()),
    ]
