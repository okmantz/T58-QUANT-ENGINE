# Files flagged as obsolete (nothing has been deleted)

Flagged 2026-11-17 for the owner to review. "Evidence" is how the flag was decided; delete only after you agree.

## Superseded documents

| File | Why flagged |
|---|---|
| `docs/T58_Strategy_Evaluation_Report.pdf` | Replaced by `docs/T58_STRATEGY_EVALUATION_2026-11.pdf` (built from the saved study results, with the A/B/C objectives, train/validation/test and Gate27 re-evaluation). Not read by any code. |
| `docs/T58_STRATEGY_DISCOVERY_2026-11.md`, `docs/T58_HYPOTHESIS_REPORT.md` | Earlier research notes, ranked on the old blended score; the evaluation report supersedes their conclusions. Still referenced by `scripts/make_t58_report.py` and `scripts/run_t58_hypotheses.py`, so keep until those scripts are retired. |
| `docs/T58_Game_Plan.pdf`, `docs/T58_Strategy_Testing_Plan.pdf` | Planning documents from before the objective directives; not referenced by code. |

## Legacy research scripts

| File | Why flagged |
|---|---|
| `scripts/run_t58_hypotheses.py`, `scripts/run_t58_engine_grid.py`, `scripts/make_t58_report.py` | Read the old trade-cache keys (`NQ1_Ind_Rule_15m`, `NQ1_Open_Drive_Continuation_5m`, ...). The current study is `scripts/run_objective_study.py` -> `run_objective_scores.py` -> `run_objective_c_final.py` -> `make_objective_report.py`. Not imported by the app or the tests. |
| `scripts/t58_ir_search.py`, `scripts/strategy_evidence.py` | One-off searches that produced the IndRule parameters; kept for provenance, not needed at runtime. |

## Strategies that cannot run or did not pass the screen

| File / strategy | Evidence |
|---|---|
| `strategies/mql5/Gate27_Basket_Daily_v1.mq5` | **Keep.** It is the owner's armored original; v2 is the tuned copy (SMA 150, vol window 40, target 1.0%). Listed so the pair is not mistaken for a duplicate. |
| `strategies/mql5/GoLong_ESNQ_5m_v1.mq5` | Profit factor 1.08 / 1.04 on NQ / ES (train+validation+test), below the 1.1 screen; not in any bot. |
| `strategies/mql5/RangeBreakout_NQ_5m_v1.mq5` | Positive on NQ (PF 1.29 all) but loses on ES (0.97) and was not selected by any objective's book. |
| `strategies/python/TrendMomentum_NQ_5m_v1.py` | PF 1.21 on NQ with test PF 1.00; not selected by any book. |
| `strategies/python/CompressionORB_ES_5m_v1.py` | ES only (357 trades, PF 1.28); not selected. |
| `strategies/python/IndRuleB_NQ_30m_v1.py` | Test PF 0.53 on NQ: fails out of sample. |
| `strategies/pinescript/TSMOM_ES_Daily_v6.pine` | Not evaluated by the trade-level study (Pine has no Python twin here). |
| Deleted EAs: Ninja Turtle Scalper, Fisherman, Turnaround Tuesday, ATR Candle Breakout | Error in the repo's MQL5 interpreter (`SetTypeFillingBySymbol` unsupported), so no numbers exist. Not restored. |

## Old file names

The renamed strategy files (old name -> new name) are listed in `DELETE_AFTER_PASTE.txt` in the delivery zip; remove the old names after pasting.
