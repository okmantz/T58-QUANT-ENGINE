"""Reproduce the T58 final bots' scores from the repo root.
  python scripts/run_t58_final_bots.py A|B [stress]   -> research + validation scores of the frozen pick (research engine)
Needs data/raw/{NQ1!,ES1!,GC1!}/futures_X.F_1m.parquet (the repo's data). First run builds session matrices in research/t58_final_bots/.cache."""
import runpy, sys
sys.argv = ["run_bot.py"] + sys.argv[1:]
runpy.run_path("research/t58_final_bots/run_bot.py", run_name="__main__")
