"""Engine-compatible runner for the frozen T58 bots. Research and scoring only: it places no orders anywhere.
Usage:
  python3 final/run_bot.py A [from] [to] [base|stress] [pro50|flex50]
  python3 final/run_bot.py B 2024-01-01 2026-03-02 stress flex50 [--ports]
Builds the bot from final/BOT-<X>/params.json (round 3; earlier picks: BOT-A/params_r1.json, BOT-B/params_r1.json and params_r2.json) with the same code that produced every number in final/COMPARISON.md
(code/legs.py signal legs -> code/book.py arbiter -> code/policy.py sizing -> code/firm.py Lucid simulator -> code/score.py metrics).
Windows that reach past 2026-03-02 read the sealed Mar-Nov 2026 holdout. Add --ports to use the repo-format leg files. Prints the Phase 0 metric set as JSON."""
import os, sys, json
from pathlib import Path
os.environ.setdefault("T58_R3", "1")          # round 3: validation runs to 2026-03-01; Mar-Nov 2026 is the sealed holdout
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "engine"))
import repo_setup; repo_setup.ensure()
import search as S, score, firm, filters, legs as LG
from policy import Pol

PORTS = "--ports" in sys.argv
sys.argv = [x for x in sys.argv if x != "--ports"]

def build(which, sealed=False):
    pk = json.loads((ROOT / f"BOT-{which}" / "params.json").read_text())
    if PORTS:                                # use the repo-format strategy files (strategies/python/*_t58.py) for the new legs
        LG.use_ports()
    if pk.get("spec"):                       # round 2: regime filters (code/filters.py) before the arbiter
        bk = filters.bot(pk["legs"], max_open=pk["max_open"], spec=pk["spec"], sealed=sealed)
    else:
        bk = S.bot(pk["legs"], max_open=pk["max_open"], sealed=sealed)
    return bk, Pol(**pk["policy"]), pk["plan"]

if __name__ == "__main__":
    which = sys.argv[1].upper()
    a = sys.argv[2] if len(sys.argv) > 2 else "2024-01-01"
    b = sys.argv[3] if len(sys.argv) > 3 else "2026-03-02"
    cost = sys.argv[4] if len(sys.argv) > 4 else "stress"
    bk, pol, plan = build(which, sealed=b > "2026-03-02")
    plan = sys.argv[5] if len(sys.argv) > 5 else plan
    p = firm.Plan(cost=cost) if plan == "pro50" else firm.Plan.flex50(cost=cost)
    r = score.full(bk, pol, p, a, b, stride=1); r.update(score.sustained_block(bk, pol, p, a, b))
    print(json.dumps({k: (round(float(v), 4) if isinstance(v, (int, float)) else v) for k, v in r.items()}, indent=1))
