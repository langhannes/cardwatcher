# CardWatcher — Action Plan: reliability, automation, SQLite metrics, backtesting

> Roadmap doc for upcoming work. Pick up the work packages (WPs) in order in a new
> session. Each WP lists goal, key files, approach, tests, and deliverable.

## Context

CardWatcher has grown into a useful trading-intelligence tool, but the engine
underneath has weaknesses that block the next round of features:

- **No tests** — changes have been verified by hand. We need a safety net before
  refactoring import/download/storage.
- **Import is fragile and synchronous** — `import_all_pages()` runs in the `/`
  route on every page load (`cardwatcher.py:62,83`) and parses every file with no
  per-file/per-row isolation, so one bad page 500s the app (the `aria-label` bug).
- **No real download queue** — `DownloadManager.download_single_page()`
  (`app/download_manager.py:138`) runs **synchronously on the request thread** and
  is rejected if any download is in progress; there is no queue or prioritisation.
- **Metrics live in one big `price_history.json`** rewritten wholesale; this is
  also where backtest time-series would have to go, and it may outgrow the git
  data repo.

Goal: a tested codebase where imports run automatically and safely off the request
path, individual updates are queued and prioritised, metrics live in a SQLite DB
with a git-friendly text backup, and the market-price methods / signals are
validated by backtests.

### Confirmed decisions

- **SQLite scope:** metrics only. `pages/*.json`, archive, images, and the
  collection JSON stay as files; only current metrics + a daily metric time-series
  + backtest data move into the DB.
- **Backup:** local `cardwatcher.db` is source of truth; a compact gzipped text
  export is committed to the data repo via the existing sync. DB is rebuildable.
- **Daily run:** catch-up on launch (if last successful run > ~24h ago) **plus** a
  daily timer while running, gated by a setting, tracked via a `last_auto_run`
  timestamp.

Recommended order: **WP1 → WP2 → WP3 → WP4 → WP5 → WP6.** WP2 can ship on its own;
WP3 should precede WP6; WP4 and WP5 are best done together (same module + route).

---

## WP1 — Testing suite (do first)

**Goal:** lock current behaviour so the refactors below are verifiable.

- Add `pytest` to a new `requirements-dev.txt` (NOT `requirements.txt` — keep the
  build whitelist clean so the exe stays ~28 MB). Add a `tests/` package and a
  `pytest.ini`/`pyproject` config setting `pythonpath = .`.
- Fixtures in `tests/fixtures/`: copy 1–2 real `pages/*.json` and one saved
  CardMarket `.htm` (a server-rendered one with `title=` tooltips, to lock the
  `aria-label`/`title` fallback) so tests don't depend on the live data dir.
- Tests to write (pure logic, no browser/Flask):
  - `app/listing.py`: `tooltip_label()` fallbacks, `parse_from_row()` on the HTML
    fixture, `from_json`/`to_json` round-trip.
  - `app/page.py`: `update_page()` matching (continuing / relisted / ended),
    `calculate_price_average_robust()` (IQR).
  - `app/watcherbase.py`: `calculate_price_average_time_weighted`,
    `calculate_market_prices` (blend/sold/floor + dominant language),
    `calculate_all_period_averages` shape, `calculate_historical_min`.
  - `app/dashboard.py`: pressure bucketing (coiling/overbought/cooling) and movers
    ranking with synthetic `price_history` dicts.
- **Run:** `python -m pytest`. **Deliverable:** green suite + a one-line note in
  README/BUILD on how to run it.

## WP2 — Isolate import failures

**Goal:** one bad page or row never takes down import or the app.

- In `watcherbase.import_all_pages()` (`app/watcherbase.py`, ~line 660): wrap the
  per-file body in try/except; on failure, log, move the offending `.htm` to a new
  `downloads/failed/` folder (don't silently delete), and continue.
- In `app/listing.py` `Page`/row parsing: wrap per-row parsing so a single bad row
  is skipped and counted, not fatal.
- Return/accumulate an import report `{imported, skipped, failed:[...]}`; surface
  counts in the download status so the UI can show "N failed".
- **Tests:** feed a deliberately malformed row/file fixture and assert the rest
  still import and the failure is recorded. **Deliverable:** import is crash-proof.

## WP3 — SQLite metrics store (+ text backup)

**Goal:** replace `price_history.json` with a local SQLite DB and record a daily
metric time-series for backtests, with a git-friendly export.

- New `app/db.py`: a thin data-access layer over `sqlite3` at
  `DATA_DIR/cardwatcher.db` (path in `app/config.py`). Schema:
  - `card_metrics` — current snapshot per card (the fields in `price_history.json`
    today: current_avg/min/ended_avg/available, market blend/sold/floor, per-period
    blocks, last_download). One row per canonical name; JSON columns for the nested
    period/market blobs to keep the migration 1:1.
  - `metric_history` — `(canonical, date, blend, sold, floor, avg, ended_avg, min,
    available, added, removed)`; one row per card per import day. This is the
    backtest time-series and the part that genuinely grows.
  - `backtest_results` — cached outputs (WP6).
- Replace the `price_history.json` read/write sites with `db.py` calls (keep
  function names/shapes so callers barely change):
  - writers: `watcherbase.calculate_all_period_averages` consumers in
    `import_all_pages` (~line 814), `watcherbase.update_price_history_for_page`,
    `app/recalculate_metrics.py`.
  - readers: `app/watchersearch.py` (~line 40), `app/dashboard.py`
    (`build_dashboard`), `cardwatcher.py` page route (~line 120).
  - On each metrics write, also upsert today's `metric_history` row.
- **One-time migration:** `scripts/migrate_to_sqlite.py` that loads the existing
  `price_history.json` into `card_metrics` (and backfills `metric_history` from the
  reconstructable history via `calculate_market_prices(page, at_time=...)` over a
  date range, so backtests have data immediately).
- **Backup/sync (text export in git):**
  - `db.export_text()` → gzipped NDJSON (one file per table) under
    `DATA_DIR/db-export/`; `db.import_text()` rebuilds the DB from it.
  - Hook into `app/sync.py`: `full_sync()` calls `export_text()` before commit;
    `pull_only()` calls `import_text()` after pull. Commit the
    `db-export/*.ndjson.gz` (diffs small); add `cardwatcher.db` to the data repo's
    `.gitignore`.
- **Tests:** round-trip `export_text`→`import_text`; a metrics upsert + read-back;
  `migrate_to_sqlite` on the fixture. **Deliverable:** app reads/writes metrics
  from SQLite; `price_history.json` retired; export committed on sync.

## WP4 — Download queue + prioritised individual updates

**Goal:** turn `DownloadManager` into one persistent worker draining a priority
queue; individual updates jump ahead and run ASAP instead of blocking/being
rejected.

- Refactor `app/download_manager.py`: a single long-lived worker thread that blocks
  on a `queue.PriorityQueue` of jobs. Job kinds:
  - `FULL_REFRESH` (low priority) — enqueues all stale pages (reuse existing
    `get_already_downloaded()` / mtime logic from `_download_worker`).
  - `SINGLE_PAGE` (high priority) — one card, runs next after the in-flight
    download finishes.
  - Inter-download waits (rate limiting) apply to bulk jobs; a high-priority single
    job is not made to wait behind the full-refresh backoff.
- `download_single_page()` / `download_from_url()` become **non-blocking enqueue**
  calls returning `{queued: true, position}`; the API routes
  (`cardwatcher.py:195,211`) return immediately.
- After each successful download the worker imports (via WP2's safe import).
- `get_status()` reports queue length, current job, and per-job kind; the header
  download bar JS (in `templates/*.htm`) shows "queued / k ahead".
- **Tests:** enqueue ordering (single jumps ahead of full refresh), status shape
  (mock the selenium calls). **Deliverable:** individual "Download" never blocks and
  runs ASAP; bulk still rate-limited.

## WP5 — Automated daily refresh (+ setting, remove page-load import)

**Goal:** the full refresh runs by itself; the `/` route stops importing.

- New settings in `config.DEFAULT_SETTINGS`: `auto_import_enabled` (bool, default
  False) and internal `last_auto_run` (timestamp). Add a toggle to
  `templates/settings.htm` (generic save route already persists any key).
- New `app/scheduler.py` (daemon thread, started from `cardwatcher.py` after data
  dir init): on start, if `auto_import_enabled` and `now - last_auto_run > 24h`,
  enqueue a `FULL_REFRESH`; then loop with a daily timer doing the same; update
  `last_auto_run` on successful completion.
- When `auto_import_enabled` is True, **remove the import from the main page**:
  guard the `import_all_pages()` calls in the `/` route (`cardwatcher.py:62,83`) so
  they no-op (the queue worker + scheduler own importing). Keep a manual "Refresh
  now" / "Import downloads" affordance for ad-hoc manual HTML saves. When disabled,
  current behaviour is unchanged.
- **Tests:** scheduler decision logic (catch-up vs skip) with a faked clock and a
  mock queue. **Deliverable:** enable the setting → daily auto-refresh; main page no
  longer blocks on import.

## WP6 — Backtests & tuning

**Goal:** validate which market-price method is most representative and whether the
signals lead price, then tune the constants from data.

- New `app/backtest.py` reading `metric_history` (WP3):
  - **Method accuracy:** for each card/day, compare each method (blend/sold/floor)
    against the *subsequent* realized `sold` average; report error per method.
  - **Signal lead:** label past days by bucket (coiling/overbought/cooling using
    the same thresholds as `dashboard.py`) and measure forward N-day blend change;
    report hit-rate / average move per bucket.
  - Store outputs in `backtest_results`; expose a simple `/backtest` page (or a
    section) summarising the tables.
- **Tuning:** the constants already centralised on `watcherbase` (BLEND weights,
  `FLOOR_PERCENTILE`, `GOOD_CONDITIONS`) and in `dashboard.py` (thresholds) get set
  from the backtest findings; re-run to confirm improvement.
- **Tests:** backtest math on a small synthetic `metric_history`. **Deliverable:**
  a data-backed answer to "which price is the real one" and tuned thresholds.

---

## Verification (end to end)

1. `python -m pytest` green after each WP (the suite grows with each).
2. WP2: drop a malformed `.htm` in `downloads/`, load a page → app stays up, file
   lands in `downloads/failed/`, status shows the failure.
3. WP3: run `scripts/migrate_to_sqlite.py`; confirm dashboard/search/detail render
   identical numbers from the DB; `Full Sync` writes `db-export/*.ndjson.gz`.
4. WP4: click a card's **Download** while a full refresh is queued → returns
   immediately and runs next; status shows queue depth.
5. WP5: enable `auto_import_enabled`, set `last_auto_run` to >24h ago, restart →
   refresh auto-starts; `/` no longer calls import.
6. WP6: open the backtest summary; confirm method-accuracy and bucket-lead tables
   populate; adjust a constant and see the numbers move.
7. Rebuild exe via the clean venv and smoke-test `GET / → 200`.

## Notes

- `pages/*.json` staying as files means the git data repo still carries the listing
  history; the SQLite work targets the metrics/time-series specifically. If repo
  size later becomes the pain point, a follow-up could move listings into the DB too
  (the "everything" option) — out of scope here.
- Keep `pytest`/dev deps out of `cardwatcher.spec`'s build environment so the exe
  stays ~28 MB.