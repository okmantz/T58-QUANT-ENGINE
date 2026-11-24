"""Score the frozen picks twice on research + validation (stress and base cost): once with the factory legs they were chosen on, once with
the legs replaced by the repo-style files in strategies/python (run through the repo engine). Writes research/port_bots_check.csv.
The gap is what changes when the bots run on the repo's own engine. Usage: [T58_R3=1] python3 verify_port_bots.py"""
import sys, pandas as pd
sys.path.insert(0, "research/t58_final_bots/engine")
import legs as LG, search as S, score, firm, filters, picks_r3
from policy import Pol
def run(tag):
    rows = []
    for obj, pk in (("A", picks_r3.BOT_A), ("B", picks_r3.BOT_B)):
        for planname in ("pro50", "flex50"):
            for sp, (x, y) in (("research", S.RES), ("validation", S.VAL)):
                for c in ("base", "stress"):
                    p = firm.Plan(cost=c) if planname == "pro50" else firm.Plan.flex50(cost=c)
                    bk = filters.bot(pk["legs"], max_open=pk["max_open"], spec=pk.get("spec")); pol = Pol(**pk["policy"])
                    r = score.full(bk, pol, p, x, y, stride=1); r.update(score.sustained_block(bk, pol, p, x, y))
                    r.update(bot="BOT-" + obj, legs_from=tag, plan=planname, split=sp, cost=c); rows.append(r)
    return rows
if __name__ == "__main__":
    a = run("factory"); LG.use_ports(); S._B.clear(); b = run("repo_port")
    pd.DataFrame(a + b).to_csv("research/t58_final_bots/research/port_bots_check.csv", index=False); print("done")
