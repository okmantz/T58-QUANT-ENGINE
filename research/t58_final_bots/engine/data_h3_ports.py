"""H3 trades for the repo-style port files (strategies/python/*_t58.py), built exactly as data_h3.py built them for the repo strategies:
repo engine on the combined new+old 1m file, H3 entries kept, prices shifted onto the adjusted basis. Prints counts only."""
import sys, pickle, json
sys.path.insert(0, "research/t58_final_bots/engine")
import data as D, book, data_h3 as H, legs as LG
info = json.load(open(D.WORK / "research/data_h3_info.json"))
assert H.check_seal() == 5
out = {}
for key, stem in LG.PORTS.items():
    inst = LG.CAND[key][2]; off = info[inst]["offset"]; p = H.combined(inst)
    rows = book.gen(stem, inst, tag=f"{stem}_port__cmb4", src=LG.PORT_DIR + stem + ".py", datafile=str(p))
    keep = []
    for r in rows:
        sd, _ = book._sess([r["entry"]])
        if sd[0] < H.H3_TO:
            r = dict(r); r.update(ep=r["ep"] + off, xp=r["xp"] + off, worst=r["worst"] + off); keep.append(r)
    pickle.dump(keep, open(D.CACHE / "raw" / f"{stem}_port__{inst}__h3.pkl", "wb")); out[f"{stem}@{inst}"] = len(keep)
info["port_h3_trade_rows"] = out
json.dump(info, open(D.WORK / "research/data_h3_info.json", "w"), indent=1, default=str)
print(out)
