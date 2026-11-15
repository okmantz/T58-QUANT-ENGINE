# Research intake, 2026-11-15: what was added, what was verified, what was not

## Verified status of each strategy (run through this engine, not just written)
| Item | Result |
|---|---|
| GAD (MNQ1! Gap Aligned Drive RW Tight Stop 1m) | **Fixed.** The genetic search moved `FLAT_MIN` / `SESSION_MIN` (session-grid constants) to values the day grid cannot hold (`index 390 is out of bounds`). They are now non-tunable expressions and the flat slot is clamped. Full Pipeline with the GA on completes: ladder LEAD, EV verdict FORWARD-TEST CANDIDATE. Needs a **1-minute** dataset (clear error otherwise). |
| TSMOM (`ES1! TSMOM V1 1d`) | Runs; was failing the lookahead prefix check on the last bar (a position opened on the final bar lost its signal) - fixed. Clean at every cut. Pooled ES+NQ+GC Net Profit test: INSUFFICIENT DATA (91 trades, Sharpe 0.54, t 1.17). Monthly strategy + ~5y of data cannot reach the 100-trade preflight on one market, so Full Pipeline stops at preflight by design. Prop presets with a session-flatten rule (e.g. Lucid) correctly block a months-long hold. |
| Gate 27 | EA renamed `GATE 27 MT5 EA US500 XAUUSD USOIL USDX D1.mq5`, logic untouched. `scripts/run_gate27_basket.py` runs the frozen basket: US500+GOLD legs on repo data = +$49k on $100k (2020-09 to 2026-09), Sharpe 0.67, max DD -13.1%. OIL/USD legs need your own daily CSV (`--oil-csv/--usd-csv` or `--prices-csv`). Not a single-instrument strategy, so it cannot go through the bar engine. |
| Six EA twins | All run, lookahead-clean, Net Profit tester returns a verdict. At the vendor-style defaults on ES they come out FAIL (Go Long +$8.3k, Turnaround Tuesday +$2.6k, the other four lose). Defaults are untuned. |
| Six MQL5 EAs | **Written from the input PDFs, NOT compiled** (no MetaEditor here). Static checks only (balanced braces, helpers defined). Compile and run the Strategy Tester before trusting them. |
| IV Wall Reaction 5m | Runs, lookahead-clean. Walls are a PRIOR-SESSION HIGH/LOW PROXY unless real `gex_call_wall`/`gex_put_wall` columns are present. Proxy mode loses (273 trades, -$12k on ES): no evidence either way about real IV walls. |

## Added to the engine
- `app/data/gamma_data.py`: Black-Scholes gamma fallback when a chain has IV but no gamma.
- `app/data/gex_conversion.py`: daily OLS ETF-to-futures level conversion (SPY->ES, QQQ->NQ, GLD->GC).
- `app/validation/cost_headroom.py`: break-even cost multiple (how many times today's friction before net profit is zero). Go Long on the last 300k bars: 2.14x.
- `app/search/seed_data/graveyard_research_priors.jsonl` + `app/discovery_engine/research_priors.py`: 24 distilled experiment verdicts + a summary record, mapped to engine strategy families.

## Day Trader and falsification kit: what was and was not worth adding
Already in the engine: gap-through stop fills, null-edge / random-entry test, SPRT monitor, pre-registered hypotheses, fill ledger, planted-edge check, cost stress at fixed multiples. Added: break-even cost multiple. Not ported on purpose: Day Trader's win-rate adaptive tuner and strategy router (live-bot logic; win-rate-chasing is exactly what the graveyard's own tuner experiment questions), circuit breaker / dynamic exit (the engine already has daily-loss and exit machinery), Alpaca/Finnhub plumbing.

## Licence caution (graveyard archive)
The archive says: personal use and study, NO redistribution, NO use in marketing or anything sold. Only distilled verdicts and lesson text were added (no code, no data). If this repo is shared or sold, confirm terms with Colin first.

## Not done
- The six `.mq5` files and Gate 27 EA were never compiled or run in MT5.
- `T58 TSMOM V6.pine` was copied in but not validated in TradingView.
- IV Walls with real options data: needs chain history (Alpha Vantage / ORATS / CBOE) and futures-space conversion; nothing was backtested on real walls.
