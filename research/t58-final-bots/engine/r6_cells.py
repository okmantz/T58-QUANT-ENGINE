import sys, json
sys.path.insert(0, "research/t58_final_bots/engine")
import r6, pandas as pd
f = sys.argv[1]; d = pd.read_csv(f"{r6.OUT}/{f}")
out = []
for (plan, sp, cost), g in d.groupby(["plan", "split", "cost"]):
    g = g.set_index("bot")
    for who in g.index:
        if who.startswith("baseline"): continue
        obj = "A" if "-A-" in who else "B"; bl = g.loc[f"baseline_{obj}"].to_dict(); r = g.loc[who].to_dict()
        if obj == "A": pf, lf = r6.a_bar(r, bl); fl = pf + lf
        else: fl = r6.b_bar(r, bl)
        out.append(dict(bot=who, plan=plan, split=sp, cost=cost, nfail=len(fl), fails=",".join(fl)))
o = pd.DataFrame(out); o.to_csv(f"{r6.OUT}/shortfalls_{f}", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 120)
print(o[o.cost == sys.argv[2]].sort_values(["bot", "plan", "split"]).to_string())
