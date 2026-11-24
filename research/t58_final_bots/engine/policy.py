"""BOT-A / BOT-B sizing policy (risk dollars at the stop for the next trade). Pure function of the account state the firm engine keeps:
no future information. Parameters are frozen per bot in final/*/params.json."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import numpy as np
from firm import PVM, cost_per_micro
CPM = {c: {k: cost_per_micro(k, c) for k in PVM} for c in ("base", "stress", "none")}


@dataclass
class Pol:
    r_eval: float = 600.0        # base risk per trade in the evaluation ($, x leg weight)
    r_fund: float = 400.0        # base risk per trade once funded
    f_cush: float = 0.35         # never more than this share of the cushion (balance - floor - open risk)
    k_need: float | None = 0.6   # eval: never more than k_need x the dollars still needed (but at least r_min): finish, don't overshoot
    r_min: float = 150.0
    day_stop: float = 900.0      # no new trades once the day is down this much
    eval_day_cap: float | None = None   # eval: stand down once the day is up this much (Flex 40% eval rule)
    fund_day_cap: float | None = 900.0  # funded: stand down once the day is up this much (Pro 40% payout rule / Flex win-day bank)
    fund_day_stop: float | None = None  # funded day stop (None = day_stop)
    fund_f_cush: float | None = None    # funded cushion share (None = f_cush)
    streak: int | None = None    # after this many losses in a row ...
    streak_mult: float = 0.5     # ... size x this
    dd_mult: float = 1.0         # below 50% of the starting cushion, size x this (drawdown throttle)
    floor_cush: float = 0.35     # one-micro minimum allowed while one micro risks at most this share of the cushion
    day_room: bool = True        # cap open risk by what is left of the day stop
    dd_lvl: float | None = None  # drawdown throttle: when equity (balance + payouts) is this far below its EOD peak ...
    dd_k: float = 0.5            # ... size x this
    cons_k: float | None = None  # funded (Pro 40% rule): keep today's profit under max(cons_min, cons_k x cycle profit so far) ...
    cons_min: float = 250.0
    cons_g: float = 0.0          # ... or this share of what the cycle must reach to be payable (first cycle: +$2,600), whichever is larger
    cons_R: float = 2.0          # ... by sizing so a cons_R x risk winner still fits in what is left
    fund_legs: dict | None = None # round 2: funded phase trades only these legs, weight x the given multiplier (None = all legs as in eval)
    floor_x: float | None = None # round 2: the one-micro floor applies only while one micro risks <= floor_x x the budget (None = always);
                                 # without it a drawdown throttle or a small r_eval is overridden by the one-micro minimum
    # round 4 (research/PREREG_R4.md): barrier-aware eval sizing. Defaults reproduce round 3 exactly.
    cush_a: float = 0.0          # eval: risk x (cushion / MLL) ^ cush_a   (ease off as the account nears the drawdown floor)
    prog_b: float = 0.0          # eval: risk x (1 + prog_b x clip(profit / target, 0, 1))   (press, or ease, into the target)
    pace_c: float = 0.0          # eval: risk x clip(share of target still needed / share of time left, .7, 1.5) ^ pace_c
    pace_H: int = 30             # eval horizon for the pace term (calendar days)

    def __post_init__(self):
        self.w = None
        self.book = None

    def __call__(self, st, p, i, open_risk):
        funded = st.phase == "funded"
        ds = self.fund_day_stop if (funded and self.fund_day_stop is not None) else self.day_stop
        if st.day_pnl <= -ds:
            return 0.0
        cap = self.fund_day_cap if funded else self.eval_day_cap
        if cap is not None and st.day_pnl >= cap:
            return 0.0
        w = self.w[i] if self.w is not None else 1.0
        if funded and self.fund_legs is not None:
            w = w * self.fund_legs.get(str(self.book["leg"][i]), 0.0) if self.book is not None else w
            if w <= 0:
                return 0.0
        risk = (self.r_fund if funded else self.r_eval) * w
        cush = st.bal - st.floor - open_risk
        if not funded and (self.cush_a or self.prog_b or self.pace_c):
            if self.cush_a:
                risk *= max(min((st.bal - st.floor) / p.mll, 1.5), 0.0) ** self.cush_a
            if self.prog_b:
                risk *= max(1.0 + self.prog_b * min(max((st.bal - p.S0) / p.target, 0.0), 1.0), 0.1)
            if self.pace_c and st.day is not None:
                left = 1.0 - min(float((np.datetime64(st.day, "D") - np.datetime64(st.start_day, "D")) / np.timedelta64(1, "D")) / self.pace_H, 0.95)
                need = min(max((p.S0 + p.target - st.bal) / p.target, 0.0), 1.0)
                risk *= min(max(need / left, 0.7), 1.5) ** self.pace_c
        if cush < 0.5 * p.mll:
            risk *= self.dd_mult
        if self.dd_lvl is not None and st.peak_eq > 0 and st.peak_eq - (st.bal + sum(a for _, a in st.payouts)) >= self.dd_lvl:
            risk *= self.dd_k
        if self.streak and st.loss_streak >= self.streak:
            risk *= self.streak_mult
        if not funded and self.k_need is not None:
            need = p.S0 + p.target - st.bal
            risk = min(risk, max(need * self.k_need, self.r_min))
        fc = self.fund_f_cush if (funded and self.fund_f_cush is not None) else self.f_cush
        risk = min(risk, fc * cush)
        if funded and self.cons_k is not None and p.cons is not None and p.kind == "pro":
            cyc = st.bal - st.cycle_start_bal
            need_cyc = max(p.goal, p.buffer + 500.0 - st.cycle_start_bal)
            room = max(self.cons_min, self.cons_k * cyc, self.cons_g * need_cyc) - st.day_pnl
            if room <= 0:
                return 0.0
            risk = min(risk, room / self.cons_R)
        if self.day_room:            # all open risk together never exceeds what is left of today's stop: worst day ~ -day_stop
            risk = min(risk, ds + st.day_pnl - open_risk)
        # one micro minimum: if the budget is below one micro at this trade's stop, take one micro while it is a small share of the cushion
        if self.book is not None and risk > 0:
            per = self.book["risk_pts"][i] * PVM[self.book["inst"][i]] + CPM[p.cost][self.book["inst"][i]]
            if risk < per <= self.floor_cush * cush and (not self.day_room or per <= ds + st.day_pnl - open_risk) and (self.floor_x is None or per <= self.floor_x * risk):
                risk = per
        return max(0.0, risk)

    def dict(self):
        return asdict(self)
