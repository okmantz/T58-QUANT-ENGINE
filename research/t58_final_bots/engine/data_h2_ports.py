"""H2 trades for the repo-style port files (strategies/python/*_t58.py), built exactly as data_h2.py built them for the repo strategies:
repo engine on the combined old+new 1m file, H2 entries kept, prices shifted onto the old adjusted basis. Prints counts only."""
import sys, pickle, json
sys.path.insert(0, "research/t58_final_bots/engine")
import data as D, book, data_h2 as H, legs as LG
info = json.load(open(D.WORK / "research/data_h2_info.json"))
assert H.check_seal() == 5
out = {}
for key, stem in LG.PORTS.items():
    inst = LG.CAND[key][2]; off = info[inst]["offset"]; p = H.combined(inst)
    rows = book.gen(stem, inst, tag=f"{stem}_port__cmb", src=LG.PORT_DIR + stem + ".py", datafile=str(p))
    keep = []
    for r in rows:
        sd, _ = book._sess([r["entry"]])
        if sd[0] >= H.H2_FROM:
            r = dict(r); r.update(ep=r["ep"] + off, xp=r["xp"] + off, worst=r["worst"] + off); keep.append(r)
    pickle.dump(keep, open(D.CACHE / "raw" / f"{stem}_port__{inst}__h2.pkl", "wb")); out[f"{stem}@{inst}"] = len(keep)
info["port_h2_trade_rows"] = out
json.dump(info, open(D.WORK / "research/data_h2_info.json", "w"), indent=1, default=str)
print(out)
