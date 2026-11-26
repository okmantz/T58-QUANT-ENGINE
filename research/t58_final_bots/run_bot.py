"""Engine-compatible runner for the frozen T58 bots. Research and scoring only: it places no orders anywhere.
Usage:
  python3 final/run_bot.py A [from] [to] [base|stress] [pro50|flex50]
  python3 final/run_bot.py B 2024-01-01 2026-11-21 stress flex50 [--ports]
Builds the bot from final/BOT-<X>/params.json (round 4; earlier picks: params_r1.json, params_r2.json, params_r3.json) with the same
code that produced every number in final/COMPARISON.md (code/legs.py signal legs -> code/regime.py / code/filters.py -> code/book.py
arbiter -> code/policy.py sizing -> code/firm.py Lucid simulator -> code/score.py metrics), through code/r4.py.
Round-4 windows: research 2020-01-01 .. 2024-01-01, validation 2024-01-01 .. 2026-11-21. A window that starts before 2020-01-02 reads
the 2016-2019 holdout (H3), which needs research/FROZEN_PICKS_R4.sha256 (it exists: H3 was read once on 2026-11-24).
Add --ports to use the repo-format leg files. Prints the Phase 0 metric set as JSON."""
import os, sys, json
from pathlib import Path
os.environ.setdefault("T58_R4", "1")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "engine"))
import repo_setup; repo_setup.ensure()
import search as S, score, firm, legs as LG, r4

PORTS = "--ports" in sys.argv
sys.argv = [x for x in sys.argv if x != "--ports"]

def build(which, p, sealed=False):
    pk = json.loads((ROOT / f"BOT-{which}" / "params.json").read_text())
    if PORTS:                                # use the repo-format strategy files (strategies/python/*_1m_v1.py) for the new legs
        LG.use_ports(); S._B.clear()
    bk, pol = r4.book_pol(pk, p, sealed=sealed)
    return bk, pol, pk["plan"]

if __name__ == "__main__":
    which = sys.argv[1].upper()
    a = sys.argv[2] if len(sys.argv) > 2 else "2024-01-01"
    b = sys.argv[3] if len(sys.argv) > 3 else "2026-11-21"
    cost = sys.argv[4] if len(sys.argv) > 4 else "stress"
    plan = sys.argv[5] if len(sys.argv) > 5 else json.loads((ROOT / f"BOT-{which}" / "params.json").read_text())["plan"]
    p = firm.Plan(cost=cost) if plan == "pro50" else firm.Plan.flex50(cost=cost)
    bk, pol, _ = build(which, p, sealed=a < "2020-01-02")
    r = score.full(bk, pol, p, a, b, stride=1); r.update(score.sustained_block(bk, pol, p, a, b))
    print(json.dumps({k: (round(float(v), 4) if isinstance(v, (int, float)) else v) for k, v in r.items()}, indent=1))
