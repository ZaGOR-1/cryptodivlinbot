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
