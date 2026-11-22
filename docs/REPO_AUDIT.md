# Repo audit: what is in the app vs. what is in the repo

Generated while redesigning the app (Nov 2026). Nothing below was deleted for you; this is the list of what you can safely remove and what you should keep.

## What the app is made of
| Area | Where | Notes |
|---|---|---|
| Web app (Flask) | `app/web/` (server, blueprints, templates, static) | The whole UI. Sidebar is `_sidebar.html`; Deploy is `forward_test.html` + `_demo_account_panel.html` + `deploy_live.html`. |
| Engines | `app/` (backtest, optimize, validate, champion, forward test, live deploy, demo account, bots, webhook relay, AI coach) | Imported by the web layer. Keep. |
| Trading bots | `app/bots/` | Three default bots (Pass, Payout, Profit), runner, venues (Demo / Paper / Broker). Keep. |
| Strategies | `strategies/` | Shipped example strategies. Keep. |
| Tests | `tests/`, `scripts/run_tests.py`, `scripts/web_smoke_test.py` | Keep. |
| Packaging | `build_tools/`, `launchers/`, `license_server/`, `license_sheet/` | Needed only for shipping the installer and licensing. Keep if you sell it. |

## Safe to remove (nothing in the app or tests references them)
1. **Unused templates** (no `render_template`, `include` or `extends` anywhere):
   `app/web/templates/demo_account.html`, `notification_settings.html`, `rulebook.html`, `trader_profile.html`, `user_manual.html`.
   (`/demo-account` now redirects into Deploy; the others were replaced by Account settings / the Rulebook inside the app.)
2. **Unused static files**: `app/web/static/pg-arcade.js`, `pg-fidgets.js`, `pg-puzzles.js`, `pg-quantum.js` (old playground scripts, never loaded).
   `icon-maskable-192.png` / `icon-maskable-512.png` are used by `manifest.json`: keep.
3. **Research PDFs**: `research/papers/**` (~39 MB, 130 MB with history). Reading material only; the app never opens them. Move to a separate repo or a Drive folder.
4. **Run output**: `results/` (~5 MB, e.g. `searchA_log.jsonl`) and `reports/` (~12 MB). Generated output; add to `.gitignore` and untrack.
5. **Never commit**: `data/config/` (created at runtime; holds settings and possibly credentials). Make sure it stays in `.gitignore`. It showed up as untracked during testing.

## Heavy, but needed (consider Git LFS instead of removal)
- `data/raw/*/*.parquet` (NQ 30 MB, ES 29 MB, GC 25 MB): the 1-minute history the backtests, bots and demo account run on. Required. Move to Git LFS or a release download so clones stay small.

## Keep (looks unused, is not)
- Redirect-only routes such as `/demo-account` and legacy page paths: old bookmarks and tests rely on them.
- `docs/`: user-facing documentation.

## Suggested cleanup commands
```
git rm app/web/templates/{demo_account,notification_settings,rulebook,trader_profile,user_manual}.html
git rm app/web/static/pg-{arcade,fidgets,puzzles,quantum}.js
git rm -r --cached results reports research && printf 'results/\nreports/\nresearch/\n' >> .gitignore
```
Run `python scripts/run_tests.py` afterwards to confirm nothing referenced them.
