"""Round 5 helpers (env T58_R5=1, which implies T58_R4). Dev = H3 2016-11-24..2019-12-31 + research 2020-2023 + validation 2024-01-01..2026-11-20.
All three dev splits were already read (H3 once in round 4; validation contains H2, read in round 3). Holdout H4 = sessions < 2016-11-24, only if
Owen sends that data; sealed in data_holdout4/SEAL.sha256 before any price read. Same scoring code as round 4 (r4.run)."""
import os, sys
os.environ["T58_R5"] = "1"; os.environ["T58_R4"] = "1"; sys.path.insert(0, "research/t58_final_bots/engine")
import r4
r4.SPL["h3"] = ("2016-11-24", "2020-01-02")
r4.SPL["h4"] = ("2000-01-01", "2016-11-24")
DEV = ("h3", "research", "validation")
run, a_bar, OUT, book_pol = r4.run, r4.a_bar, r4.OUT, r4.book_pol
