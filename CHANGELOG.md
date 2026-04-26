# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Each entry below corresponds to one self-contained change made by Devin while
implementing the bot. New entries should be appended at the bottom of
`[Unreleased]` and graduated into a versioned section on each release tag.

## [Unreleased]

### Added
- **Project scaffold**: `pyproject.toml`, `requirements.txt`, `.gitignore`,
  `.env.example`, and a `src/cryptodivlinbot/` package layout with a `tests/`
  directory at the repo root.
- **`config.Settings`**: typed, validated settings loaded from environment
  variables (with `.env` autoload), covering Telegram token, threshold, window,
  poll/digest intervals, cooldown, default language, DB path, CoinGecko/Binance
  URLs, HTTP timeout, and log level. Includes range checks and clear errors.
- **`i18n` module**: full UA / RU / EN translations for every user-facing string,
  with a forgiving `t()` helper that falls back to English and then the key
  itself, plus `normalize_language()` for handling Telegram's `xx-YY` codes.
- **`market_data` module**: async CoinGecko `/coins/markets` client (top-N by
  market cap with current USD price + 24h change), plus a Binance
  `ticker/price` fallback over a static well-known coin list when CoinGecko is
  unavailable. Encapsulated in a `MarketDataClient` that can be passed an
  injected `httpx.AsyncClient` for tests.
- **`state` module**: thread-safe SQLite layer with WAL journal mode, used as
  a single shared connection guarded by a re-entrant lock. Tables for chats
  (per-chat language / subscription / threshold), `price_history`, alert
  cooldowns, and a coins-metadata cache; with prune helpers and per-coin
  retention caps to keep the DB compact.
- **`alerts` module**: pure spike-detection helpers (`detect_spike`,
  `is_within_cooldown`, `percent_change`, `format_price`,
  `format_signed_pct`).
- **`keyboards` module**: inline keyboards for the main menu, language menu,
  and back-only screens, with structured `scope:action[:arg]` callback data.
- **Telegram handlers**: `/start`, `/menu`, `/help`, `/status`, `/subscribe`,
  `/unsubscribe`, `/coins`, `/digest`, `/language`, `/setlang`,
  `/setthreshold`, `/ping`, plus a single `CallbackQueryHandler` covering
  every button.
- **`bot` orchestration**: `BotContext`, two `JobQueue` recurring jobs
  (`poll_job` and `digest_job`), a `_safe_send` wrapper that handles
  `RetryAfter` (sleep + retry), `Forbidden` (auto-unsubscribe the chat),
  `TimedOut`, and other `TelegramError`s, and a `build_application()` factory
  used by both the entrypoint and the smoke test.
- **Tests**: pytest suite covering alerts logic (spikes / cooldowns /
  formatting), config validation, i18n key parity & fallbacks, state
  persistence (chats, price history pruning, cooldowns, coin meta), and
  market-data parsing with both CoinGecko success and Binance fallback paths
  (using `httpx.MockTransport`).
- **`README.md`**: setup, configuration, command reference, and architecture
  overview.

### Notes
- The bot is multilingual (UA / RU / EN) and persists every per-chat setting
  in SQLite, so restarts are non-destructive.
- The default 5-minute window matches the digest cadence: the same data the
  digest broadcasts is what the spike detector compares against the
  configurable per-chat threshold.

### Fixed (PR #1 review feedback)
- **Double `query.answer()` in the language-prefix callback branch**: the
  Telegram API only allows answering a callback query once, so calling
  `query.answer(text, show_alert=True)` after the eager silent
  `query.answer()` raised `BadRequest`. The bad-language branch now uses
  `_safe_edit` to display the error in the message body, and a comment in
  `on_callback` documents the single-answer invariant.
- **Spike-alert cooldown set even when delivery failed**: `_dispatch_spike`
  now returns `bool` (propagating `_safe_send`'s success flag) and the poll
  job only writes `last_alerts` when the alert actually reached the chat —
  preventing a transient `RetryAfter` / `TimedOut` from silencing a chat for
  the configured `ALERT_COOLDOWN_MIN` (default 15 min).
- New unit tests in `tests/test_safe_send.py` cover the success, retry,
  forbidden-callback, timeout, and generic-error branches of `_safe_send`.

### Documentation
- **`docs/USAGE_UK.md`**: повна україномовна інструкція — встановлення,
  створення Telegram-бота через `@BotFather`, налаштування `.env`, повний
  довідник параметрів, команд та кнопок, опис того, як працюють
  spike-алерти і дайджест, типові задачі (зміна порога, перемикання мови,
  перегляд SQLite), розробка / тести, troubleshooting та плани розвитку.
- **`docs/USAGE_RU.md`**: то же самое на русском, со зеркальной структурой.
- **`README.md`**: link to both localized usage guides at the top.

### Fixed (post-merge follow-up)
- **`_safe_send` swallowed `Forbidden` raised on the retry path**: in the
  inner `try/except` of the `RetryAfter` branch, `Forbidden` was caught by
  the generic `except TelegramError` clause and the `on_forbidden` callback
  (auto-unsubscribe) never ran. The retry path now catches `Forbidden`
  explicitly *before* the generic `TelegramError` handler, mirroring the
  outer `try/except`. Added a regression test
  `test_invokes_on_forbidden_callback_when_retry_hits_forbidden`.

### CI / Tooling
- **`.github/workflows/ci.yml`**: GitHub Actions pipeline that runs on every
  pull request and every push to `main`. Single `lint-and-test` job runs on
  a Python `3.11` / `3.12` matrix (`fail-fast: false`), uses the official
  pip cache keyed on `pyproject.toml`, installs the package with the `dev`
  extras, then runs `ruff check .` and `pytest -q`. Concurrency is scoped
  per `(workflow, ref)` with `cancel-in-progress: true` so older runs on
  the same PR are auto-cancelled. Workflow declares
  `permissions: contents: read` (least privilege).
- **`README.md`**: CI status badge linking to the workflow, plus a new
  "Continuous Integration" section explaining what the pipeline does.
- **`docs/USAGE_UK.md` / `docs/USAGE_RU.md`**: new "GitHub Actions CI"
  section (UA "Безперервна інтеграція", RU "Непрерывная интеграция") with
  step-by-step description of the pipeline, how concurrency works, how to
  read the result on a PR, how to run the same checks locally, and the
  permissions model. Roadmap section updated to mark CI as done.

### Docker / Deployment
- **`Dockerfile`**: multi-stage build. Stage 1 (`builder`) starts from
  `python:3.12-slim`, installs `build-essential`, creates a venv at
  `/opt/venv`, then installs the project (and only its runtime
  dependencies — `pytest` / `ruff` are not in the runtime image). Stage 2
  (`runtime`) is a clean `python:3.12-slim` that copies the venv from the
  builder, creates an unprivileged `app:app` user/group, declares
  `VOLUME /data`, and runs `python -m cryptodivlinbot` as that user. A
  `HEALTHCHECK` runs `python -c "import cryptodivlinbot, cryptodivlinbot.config"`
  every 30 s. Final image size ≈ 134 MB.
- **`.dockerignore`**: excludes `.git`, `.venv`, caches, `*.sqlite`,
  `.env*` (except `.env.example`), `docs/`, `tests/` and `CHANGELOG.md`
  from the build context — both for speed and to keep secrets out.
- **`docker-compose.yml`**: production-grade defaults — `restart:
  unless-stopped`, `env_file: .env`, `cryptodivlinbot_data` named volume
  mounted at `/data`, `DB_PATH` pinned to that volume, memory cap of 256
  MB, and `json-file` log rotation (10 MB × 5 files). Echoes the
  Dockerfile `HEALTHCHECK` so `docker compose ps` shows
  healthy/unhealthy.
- **`README.md`**: new "Run with Docker" section with quick-start
  commands.
- **`docs/USAGE_UK.md` / `docs/USAGE_RU.md`**: new section "Запуск через
  Docker" — quick start, what each stage of the Dockerfile does, every
  setting in `docker-compose.yml` explained, useful operational commands
  (`logs`, `restart`, `down`, `down -v`, `exec`), how to test the image
  without compose, and a Docker-specific troubleshooting table. Roadmap
  updated to mark Docker as done; section numbering shifted accordingly
  (CI section moved to §12, "Що далі" / "Что дальше" to §13).

### Type Safety (`mypy --strict`)
- **`pyproject.toml`**: added `mypy>=1.11,<2.0` to the `dev` extra and a
  new `[tool.mypy]` section that enables `strict = true`,
  `warn_unused_ignores`, `warn_redundant_casts`, `warn_unreachable`,
  `show_error_codes`, and `pretty`. Targets `src/cryptodivlinbot`.
- **`.github/workflows/ci.yml`**: added a `Mypy (--strict)` step between
  `Ruff` and `Pytest`. The whole pipeline is now lint → mypy → tests on
  the Python 3.11 / 3.12 matrix.
- **`src/cryptodivlinbot/bot.py`**: parameterised every `Application`
  with the six-tuple of generic types it actually exposes
  (`Application[Any, Any, Any, Any, Any, Any]`); replaced the
  `# type: ignore` in `_on_shutdown` with a proper `cast` to
  `BotContext | None`; rewrote the `digest_job` closure to narrow
  `bot_ctx.build_digest_text()` (which returns `str | None`) once before
  capturing it as a `str` default in the inner `_send` and `_on_forbidden`
  callbacks (mypy can't infer the captured-default type otherwise).
- **`src/cryptodivlinbot/handlers/commands.py` &
  `…/handlers/callbacks.py`**: `_ctx()` now `cast`s the result of
  `application.bot_data.get("bot_context")` to `BotContext` (the dict
  is `dict[str, Any]`, so without the cast mypy reports `no-any-return`).
  Renamed the local `text` variable in the `CB_DIGEST` branch to
  `digest_text` to keep its narrowed `str` type — the previous name
  shadowed the surrounding `str` parameter.
- **`…/handlers/callbacks.py::_safe_edit`**: now fully annotated
  (`query: CallbackQuery`, `reply_markup: InlineKeyboardMarkup | None`,
  `parse_mode: str | None`).
- **`README.md`**: added `mypy src/cryptodivlinbot` to the Development
  recipe and to the CI section.
- **`docs/USAGE_UK.md` / `docs/USAGE_RU.md`**: documented the mypy step
  in the local-development instructions and in the CI section.

### Fixed
- **Markdown parse failure in spike alerts and digest** (reported live:
  `Can't parse entities: can't find end of the entity starting at byte
  offset 383`). Coin symbols/names that contain `_`, `*`, `` ` ``, or
  `[` (e.g. `WETH_ETH`, `FOO*`) opened an unbalanced Markdown entity in
  the formatted message, causing Telegram to reject the *whole* digest
  or alert. Added a small `escape_md()` helper in
  `src/cryptodivlinbot/alerts.py` and applied it to `symbol` / `name`
  before they get interpolated into any template sent with
  `parse_mode=ParseMode.MARKDOWN` (`_dispatch_spike` and
  `BotContext.build_digest_text`). 7 new unit tests in
  `tests/test_alerts.py::TestEscapeMd` cover the special-char set and
  the no-op case for plain alphanumerics + safe punctuation.

### Persistent ReplyKeyboard (pinned at the bottom of the chat)
- **`src/cryptodivlinbot/keyboards.py`**: new `main_reply_keyboard(language)`
  factory returning `ReplyKeyboardMarkup(rows, resize_keyboard=True,
  is_persistent=True)` — the buttons stay visible alongside the system
  keyboard between messages, which is what the user asked for. Layout is
  3 rows of two (`Subscribe / Unsubscribe`, `Status / Digest`,
  `Coins / Language`) plus a final single `Help` row.
  Also added `match_reply_button(text)` reverse-lookup that scans every
  supported locale for a tap originating from a button, and a public
  `REPLY_BUTTON_KEYS` tuple driving both the layout and the lookup.
- **`src/cryptodivlinbot/handlers/commands.py`**:
  - `/start` now attaches the persistent reply keyboard to the greeting
    instead of the inline menu — `/menu` retains the inline flow.
  - `/setlang <code>` re-sends the keyboard so the labels switch to the
    new language immediately.
  - new `on_reply_button` coroutine + `_REPLY_BUTTON_HANDLERS` mapping
    that translates a tapped label back to the matching command handler
    (subscribe, unsubscribe, status, digest, coins, language, help).
  - imported `Awaitable` / `Callable` for a small `_CommandHandler`
    type alias used by the dispatch table — keeps `mypy --strict` happy.
- **`src/cryptodivlinbot/handlers/callbacks.py`**: after a successful
  inline language change (`lang:<code>`), follow up with a fresh
  `send_message` carrying `main_reply_keyboard(new_lang)` — Telegram's
  `edit_message_text` cannot replace a `ReplyKeyboardMarkup`, so a
  separate message is the only way to refresh the persistent keyboard.
- **`src/cryptodivlinbot/bot.py`**: registered a
  `MessageHandler(filters.TEXT & ~filters.COMMAND, on_reply_button)` so
  taps on the reply keyboard get routed exactly like the equivalent
  slash commands. Plain chat messages fall through silently.
- **`tests/test_keyboards.py`**: 29 new tests — every locale × every
  reply-button key round-trips through `match_reply_button`, the
  keyboard always has `is_persistent=True` / `resize_keyboard=True`,
  and the layout is locked at `[2, 2, 2, 1]`. Also covers the
  `match_reply_button` no-op for ordinary text.
- **`docs/USAGE_UK.md` / `docs/USAGE_RU.md`**: section §6 ("Кнопки")
  rewritten — now explicitly distinguishes §6.1 the persistent
  ReplyKeyboard from §6.2 the inline menu, lists the slash-command
  equivalent for every reply button, and documents that the labels
  auto-translate after `/setlang` or an inline language change.

### Hardening (8 small bugs / risks fixed in one batch)

This batch addresses the eight near-term reliability and safety issues called
out in an internal code review. None of them changed the bot's user-facing
behaviour; together they make the bot more resilient at scale and keep its
schema upgrade-safe.

1. **Telegram 4096-character message limit** — added
   `chunk_for_telegram(text, max_len=4096)` in `src/cryptodivlinbot/bot.py`
   that splits at line boundaries (and hard-cuts overlong single lines as a
   last resort). Wired into `digest_job`, `/digest`, and `/coins` so a high
   `TOP_N_COINS` no longer makes Telegram silently reject the whole digest.
   The inline-menu digest (`CB_DIGEST` callback) shows the first chunk plus a
   `…` marker, since `edit_message_text` can only replace one message.
2. **Database migrations** — `src/cryptodivlinbot/state.py` now tracks
   `PRAGMA user_version` and applies an ordered list of `_MIGRATIONS` exactly
   once each on startup. The current schema graduates to v1; future schema
   changes must append new migrations rather than editing v1. Exposed
   `SCHEMA_VERSION` constant + `State.schema_version()` accessor.
3. **`bot_context` magic string** — replaced three hard-coded
   `"bot_context"` lookups with a single `BOT_CONTEXT_KEY` constant +
   typed `get_bot_context(application) -> BotContext` accessor in
   `src/cryptodivlinbot/bot.py`. Both handler modules
   (`handlers/commands.py`, `handlers/callbacks.py`) now route through it.
4. **Exponential backoff on CoinGecko 5xx / 429** —
   `src/cryptodivlinbot/market_data.py` gained `_get_with_retry` with a
   default schedule of `(0.5, 1.5, 4.0)` s. Retries cover 5xx, 429, and
   `httpx.RequestError`; 4xx (other than 429) and successes return
   immediately. Made `retry_delays` a constructor parameter so tests can
   pass `()` or `(0, 0, 0)` to skip wall-clock sleeps.
5. **Concurrent dispatch** — `poll_job` and `digest_job` no longer
   serialise per-chat `send_message` calls. They now build the work list
   synchronously and dispatch it through `asyncio.gather` bounded by an
   `asyncio.Semaphore(_DISPATCH_CONCURRENCY=20)` so we stay friendly to
   Telegram's per-bot rate cap while parallelising broadcasts.
6. **Chat-id PII masking in logs** — added `mask_chat_id(chat_id)` that
   returns `…NNNN` (last 4 chars) for ids longer than 4 characters. All
   `_safe_send` log lines that previously included the raw `chat_id` now
   route through it. Negative group-chat ids are masked the same way.
7. **`last_alerts` uniqueness** — verified the table already has
   `PRIMARY KEY (chat_id, coin_id)` and added a regression test that
   asserts a literal duplicate insert raises `sqlite3.IntegrityError`.
8. **Markdown → HTML parse mode** — switched every `parse_mode=` site
   from `ParseMode.MARKDOWN` to `ParseMode.HTML`. Templates in
   `src/cryptodivlinbot/i18n.py` now use `<b>…</b>` instead of `*…*` for
   the spike alerts (EN / UK / RU). Replaced
   `alerts.escape_md` with `alerts.escape_html` (delegates to
   `html.escape(value, quote=False)`) so the only special characters left
   to escape are `<`, `>`, `&` — the previous fragility around dashes,
   parentheses, and unbalanced underscores in coin names is gone.

#### Tests
- New `tests/test_bot_helpers.py` covers `mask_chat_id`,
  `chunk_for_telegram` (passthrough, line-boundary split, hard-cut of
  oversize line, default == `TELEGRAM_MAX_MESSAGE_LEN`), and
  `get_bot_context` (sentinel return + `RuntimeError` when missing).
- `tests/test_state.py` extended with `test_schema_version_is_set_on_fresh_db`,
  `test_migrations_are_idempotent`,
  `test_migrations_apply_to_legacy_unversioned_db`, and
  `test_last_alerts_unique_per_chat_and_coin`.
- `tests/test_market_data.py` gained
  `test_coingecko_retries_on_5xx_then_succeeds`,
  `test_coingecko_retries_on_429_rate_limit`, and
  `test_coingecko_retries_exhaust_then_falls_back_to_binance`.
  Existing fallback tests now pass `retry_delays=()` to keep the suite fast.
- `tests/test_alerts.py`: replaced `TestEscapeMd` with `TestEscapeHtml`
  covering `<>&` escaping, "md specials are no longer touched", and
  `quote=False` behaviour.
- Total: 109 tests, all passing under `pytest`, `ruff check`, and
  `mypy --strict`.

### Added (Backups + `/broadcast`)
- **`backup` module**: `run_backup()` takes an online SQLite snapshot
  using `Connection.backup` (safe under WAL — no locks against writers),
  writes it to `${BACKUP_DIR}/cryptodivlinbot-YYYYMMDDTHHMMSSZ.sqlite`,
  then prunes the directory to keep only the newest
  `${BACKUP_RETENTION_COUNT}` files (sorted by mtime). Two backups within
  the same UTC second are disambiguated with a numeric suffix; unrelated
  files in the directory are never touched. Defaults give 24h of hourly
  history.
- **`backup_job`** registered on PTB's JobQueue at startup with
  `interval=BACKUP_INTERVAL_MIN * 60` and `first=30s` so even a
  short-lived process leaves at least one snapshot behind. SQLite's
  blocking `backup()` call is dispatched via `asyncio.to_thread` to keep
  the event loop responsive. Errors are logged but never raised — the
  job loop survives transient I/O issues.
- **`/broadcast <text>` admin command**: relays the rest of the message
  (HTML formatting allowed) to every currently subscribed chat using the
  same bounded-concurrency dispatch path as the periodic digest. Honours
  the 4096-char ceiling via `chunk_for_telegram`, auto-unsubscribes
  blocked chats mid-broadcast, and replies to the admin with a
  `delivered N/M, failed K` summary. Permission is gated on the new
  `ADMIN_CHAT_IDS` setting (frozenset for O(1) membership check); with
  the default empty set, the command is fully disabled.
- **`broadcast_to_subscribers(context, text=…)`** helper in `bot.py` —
  reusable from any future admin / scheduled job, returns
  `(delivered, total)`.
- **`config.Settings`**: four new env-backed fields:
  - `BACKUP_DIR` (`Path`, default `backups`)
  - `BACKUP_INTERVAL_MIN` (int, 1–10080, default 60)
  - `BACKUP_RETENTION_COUNT` (int, 1–10000, default 24)
  - `ADMIN_CHAT_IDS` (`frozenset[int]`, comma-separated, default empty)
- **i18n**: `broadcast_usage`, `broadcast_started`, `broadcast_done`,
  `broadcast_no_subscribers` keys added in EN/UK/RU.
- **Docker**: `docker-compose.yml` now sets `BACKUP_DIR=/data/backups`
  so snapshots persist on the same named volume as the live DB.
- **Tests**:
  - `tests/test_backup.py` — 6 tests covering snapshot creation,
    no-source-DB no-op, `retention_count=0` rejection, rotation
    correctness across multiple cycles, same-second filename
    disambiguation, and "rotation never deletes unrelated files".
  - `tests/test_broadcast.py` — 6 async tests covering the no-subscribers
    short-circuit, all-deliver happy path, `Forbidden` →
    auto-unsubscribe, partial-failure counting, oversized payload
    chunking, and "stop chunks after first failure".
  - `tests/test_config.py` — 5 new tests covering backup defaults,
    `ADMIN_CHAT_IDS` parsing (with whitespace and trailing commas),
    `ADMIN_CHAT_IDS` rejection of non-integer entries, and out-of-range
    `BACKUP_INTERVAL_MIN` / `BACKUP_RETENTION_COUNT`.
- **Docs**: README gains a "Backups" section (rotation policy, restore
  recipe, schema-migration note) and an "Admin / `/broadcast`" section
  (chat-id discovery via `@userinfobot`, configuration, dispatch
  semantics). USAGE_UK.md and USAGE_RU.md mirror the new env vars and
  command in their parameter / command tables.
- Total: 126 tests passing, `ruff` and `mypy --strict` green.

### Added (Privacy/ToS + Sentry monitoring)
- **Privacy Policy / Terms of Service**: full Markdown documents for
  EN/UK/RU under `docs/PRIVACY_POLICY*.md` and `docs/TERMS_OF_SERVICE*.md`.
  The privacy policy enumerates exactly which fields are stored
  (chat id, language, threshold, subscription state, last-alert
  timestamps), retention horizons (per-chat data until `/forgetme` or
  `/unsubscribe`; rolling 24-hour price history; auto-expiring
  cooldown timestamps), and the user's GDPR rights. The terms cover
  acceptable use, the explicit "not financial advice" disclaimer, and
  the operator's liability limits.
- **`/privacy`, `/terms`, and `/forgetme` commands**:
  - `/privacy` — short HTML-formatted summary plus a clickable link to
    the full document configured via `PRIVACY_POLICY_URL`.
  - `/terms` — the same shape for the ToS, configured via
    `TERMS_OF_SERVICE_URL`.
  - `/forgetme` — two-step GDPR right-to-be-forgotten command. The
    first call shows a confirmation prompt; `/forgetme yes` (or
    `/forgetme y`) actually deletes everything tied to the chat
    (`chats` row + every `last_alerts` row). The bot's persistent
    reply keyboard is dismissed on completion via
    `ReplyKeyboardRemove`.
- **`Settings.privacy_policy_url`** and **`Settings.terms_of_service_url`**:
  defaulted to the markdown files in this repository on `main`. Override
  with `PRIVACY_POLICY_URL` / `TERMS_OF_SERVICE_URL` env vars when
  hosting the documents elsewhere.
- **`State.delete_chat(chat_id)`**: irreversibly drops the chat row and
  every cooldown row tied to that chat. Returns whether the chat
  existed. The shared `price_history` and `coins_meta` tables are
  intentionally left intact since they are not chat-scoped.
- **`monitoring` module**: optional Sentry / GlitchTip integration.
  `init_sentry(*, dsn, environment, traces_sample_rate, release=None)`
  is idempotent, no-ops when the DSN is empty, and warns (without
  crashing) when `SENTRY_DSN` is set but `sentry-sdk` was not installed.
  `capture_exception(exc, **scope)` forwards the exception with optional
  scope tags or silently no-ops when uninitialized. `is_initialized()`
  exposes the global flag for tests/diagnostics. The `LoggingIntegration`
  is wired with `level=INFO` and `event_level=None` so logger calls
  become Sentry breadcrumbs but never standalone events — Sentry events
  are produced exclusively by explicit `capture_exception(...)` calls,
  which keeps event counts honest and preserves scope tags.
- **`Settings.sentry_dsn`** / **`sentry_environment`** /
  **`sentry_traces_sample_rate`**: three new env-backed knobs. DSN
  empty by default — leaving the bot a graceful no-op for users who
  don't want monitoring. Sample rate is range-checked to `[0.0, 1.0]`.
- **Optional `[monitoring]` extras**: install with
  `pip install '.[monitoring]'`. Pulls `sentry-sdk>=2.0,<3.0`. The base
  install does NOT pull sentry-sdk, so production deploys without
  monitoring stay slim.
- **Sentry init wiring** in `bot.run()` — happens before
  `build_application()` so even errors during startup get captured.
  A global `application.add_error_handler` forwards every uncaught
  handler/job exception to `capture_exception` with an
  `update_type=...` scope tag, in addition to the existing
  `logger.exception(...)` log line.
- **`/start` and `/help`** updated in EN/UK/RU to mention `/privacy`,
  `/terms`, and `/forgetme`.

### Tests
- `tests/test_monitoring.py` — 7 tests covering: empty-DSN no-op,
  warn-and-continue when `sentry-sdk` is missing, happy-path init with
  a stubbed `sentry_sdk` (asserting DSN/env/traces_sample_rate/release/
  send_default_pii), idempotent init, no-op `capture_exception` when
  uninitialized, and `capture_exception` forwarding the exception and
  scope tags to a stubbed `push_scope().set_tag()`.
- `tests/test_privacy_commands.py` — 6 async handler tests covering:
  `/privacy` and `/terms` reply text, parse mode, and configured URL;
  `/forgetme` first-call confirmation prompt; `/forgetme yes` actually
  deleting the chat row and last-alert rows and dismissing the reply
  keyboard; `/forgetme Y` alternate-confirmation; and
  `/forgetme please` not deleting anything (still asks for `yes`).
- `tests/test_state.py` — 2 new tests for `delete_chat`: verifies the
  chat row + its `last_alerts` rows are gone while a sibling chat
  survives; and that calling on a missing chat returns `False` rather
  than raising.
- `tests/test_broadcast.py` — `_make_settings` extended with the five
  new fields so the existing six broadcast tests continue to pass.
- Total: **141 tests passing**, `ruff` and `mypy --strict` green.

### Docs / config
- `.env.example` documents `PRIVACY_POLICY_URL`, `TERMS_OF_SERVICE_URL`,
  `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, and `SENTRY_TRACES_SAMPLE_RATE`,
  including the install hint for the optional extra.
- `pyproject.toml` declares the `monitoring` extras and a
  `[[tool.mypy.overrides]]` block for `sentry_sdk*` so strict type
  checking still passes when the optional dependency isn't installed.

### Added (Auto-restart for crash recovery)
- **Hardened `docker-compose.yml`**: keeps `restart: unless-stopped`
  (Docker auto-recovers from process crashes, OOM kills, daemon
  restarts, and host reboots while still respecting an explicit
  `docker stop`), and adds `init: true` so `tini` runs as PID 1 and
  forwards SIGTERM to the Python process — letting PTB shut down
  gracefully (drain the JobQueue, close the SQLite WAL) instead of
  being SIGKILL'd. `stop_grace_period: 30s` gives PTB enough headroom
  to complete the in-flight poll cycle before Docker tears it down.
- **`deploy/cryptodivlinbot.service`**: a hardened systemd unit for
  bare-metal / VPS / Raspberry Pi deploys without Docker. Runs the bot
  under a dedicated unprivileged `cryptodivlinbot` user with a strong
  sandbox (`ProtectSystem=strict`, `ProtectHome`, `NoNewPrivileges`,
  `SystemCallFilter=@system-service ~@privileged @resources`,
  `PrivateTmp`, `PrivateDevices`, `LockPersonality`, etc.). Auto-restart
  is wired with `Restart=on-failure`, `RestartSec=10s`, and a
  crash-loop guard (`StartLimitBurst=5` within
  `StartLimitIntervalSec=60`) so a misconfigured deploy fails loudly
  in `systemctl status` instead of churning silently. `KillSignal=SIGINT`
  + `TimeoutStopSec=30s` mirror PTB's expected graceful-shutdown signal.
  Inline install instructions in the unit file's header comment cover
  user creation, venv install, env file path (`/etc/cryptodivlinbot/env`),
  and `systemctl enable --now`.
- **README + USAGE_UK + USAGE_RU**: new "Run as a systemd service"
  section in README, expanded "What's in docker-compose.yml" sections
  in both translations to call out the new keys (`init`, `stop_grace_period`)
  and explain why `unless-stopped` is preferred over `always`.

### Notes
- No Python source / dependency changes — this is an ops-only PR.
  All 143 tests still pass; `ruff` and `mypy --strict` remain green.
