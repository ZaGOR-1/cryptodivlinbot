# cryptodivlinbot

[![CI](https://github.com/ZaGOR-1/cryptodivlinbot/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ZaGOR-1/cryptodivlinbot/actions/workflows/ci.yml)

A Telegram bot that tracks the top-N cryptocurrencies by market cap, alerts
subscribed chats when a coin's price moves more than a configurable percent
within a short window, and broadcasts a regular digest of where the market
stands. Multilingual interface in **English**, **Українська**, and **Русский**.

This is a clean, well-structured MVP — designed to be improved and extended.
Every change Devin makes is logged in [`CHANGELOG.md`](./CHANGELOG.md).

> 📑 Localized usage guides: [🇺🇦 Українська](./docs/USAGE_UK.md) · [🇷🇺 Русский](./docs/USAGE_RU.md)

## Features

- **Spike alerts**: instant notification when a tracked coin moves more than
  the configured threshold (default `5%`) over a configurable window (default
  `5 min`), with a per-chat / per-coin cooldown so chats are never spammed.
- **Periodic digest**: every `DIGEST_INTERVAL_MIN` minutes (default `5`),
  subscribed chats receive a digest with each coin's current price, its move
  over the last `SPIKE_WINDOW_MIN`, and its 24h change.
- **Top-N coins**: data sourced from CoinGecko's `/coins/markets` endpoint
  (ordered by market cap), with a Binance `ticker/price` fallback if
  CoinGecko is unreachable.
- **Multilingual UI**: every string is translated into UA / RU / EN. New chats
  start in their Telegram client language if it's supported; otherwise the
  configured `DEFAULT_LANGUAGE` is used. Users can switch at any time with
  buttons or `/setlang`.
- **Inline buttons**: the main menu has Subscribe / Unsubscribe, Status,
  Digest, Coins, Language, Help, and Close buttons — no commands required.
- **Per-chat threshold override**: `/setthreshold 3.5` lets a chat tighten or
  relax its own spike threshold without affecting others.
- **Persistent state**: SQLite (WAL mode) — chats, prices, cooldowns, and the
  coin metadata cache survive restarts.

## Quick start

```bash
git clone https://github.com/ZaGOR-1/cryptodivlinbot.git
cd cryptodivlinbot
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]

cp .env.example .env
# put your @BotFather token in TELEGRAM_BOT_TOKEN

python -m cryptodivlinbot
```

Then open a chat with the bot, send `/start`, and tap **Subscribe** (or
`/subscribe`).

## Configuration

All settings are loaded from environment variables (and from `.env` if
present). Defaults are sensible — the only required variable is
`TELEGRAM_BOT_TOKEN`.

| Variable | Default | Description |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | _(required)_ | Bot token from `@BotFather`. |
| `TOP_N_COINS` | `10` | How many top coins by market cap to track. |
| `SPIKE_THRESHOLD_PCT` | `5.0` | Default percent threshold for spike alerts. |
| `SPIKE_WINDOW_MIN` | `5` | Window over which the spike percent is measured. |
| `POLL_INTERVAL_SEC` | `60` | How often the bot polls market data. |
| `DIGEST_INTERVAL_MIN` | `5` | How often the periodic digest is sent. |
| `ALERT_COOLDOWN_MIN` | `15` | Per-chat / per-coin cooldown after a spike alert. |
| `DEFAULT_LANGUAGE` | `uk` | Fallback UI language (`en`, `uk`, or `ru`). |
| `DB_PATH` | `cryptodivlinbot.sqlite` | SQLite file path. |
| `COINGECKO_API_KEY` | _(empty)_ | Optional CoinGecko Pro key. |
| `COINGECKO_BASE_URL` | `https://api.coingecko.com/api/v3` | Override for self-hosted proxies. |
| `BINANCE_BASE_URL` | `https://api.binance.com` | Binance fallback base URL. |
| `HTTP_TIMEOUT_SEC` | `10` | HTTP request timeout. |
| `LOG_LEVEL` | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `BACKUP_DIR` | `backups` | Directory for rotated SQLite snapshots (created if missing). |
| `BACKUP_INTERVAL_MIN` | `60` | How often the bot snapshots the SQLite DB. |
| `BACKUP_RETENTION_COUNT` | `24` | Maximum number of snapshots to retain. |
| `ADMIN_CHAT_IDS` | _(empty)_ | Comma-separated chat ids allowed to use `/broadcast`. |
| `PRIVACY_POLICY_URL` | _GitHub `docs/PRIVACY_POLICY.md`_ | URL the `/privacy` reply links to. |
| `TERMS_OF_SERVICE_URL` | _GitHub `docs/TERMS_OF_SERVICE.md`_ | URL the `/terms` reply links to. |
| `SENTRY_DSN` | _(empty)_ | Optional Sentry / GlitchTip DSN. Empty disables monitoring (graceful no-op). Requires `pip install '.[monitoring]'`. |
| `SENTRY_ENVIRONMENT` | `production` | Sentry environment tag. |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.0` | Sentry performance traces sample rate (`0.0`–`1.0`). |

## Commands

| Command | Description |
| --- | --- |
| `/start` | Greeting + main menu. |
| `/menu` | Inline keyboard of quick actions. |
| `/help` | Full command list. |
| `/status` | Subscription state and current settings. |
| `/subscribe` / `/unsubscribe` | Toggle alerts for the current chat. |
| `/coins` | List of currently tracked coins. |
| `/digest` | Send the digest right now. |
| `/language` | Inline language picker. |
| `/setlang <en\|uk\|ru>` | Set the chat language directly. |
| `/setthreshold <percent>` | Override the spike threshold for this chat. |
| `/ping` | Health check (`pong`). |
| `/privacy` | Short privacy summary plus link to the full [Privacy Policy](docs/PRIVACY_POLICY.md). |
| `/terms` | Short Terms-of-Service summary plus link to the full [Terms](docs/TERMS_OF_SERVICE.md). |
| `/forgetme` | GDPR right-to-be-forgotten. First call asks to confirm; `/forgetme yes` deletes everything tied to the chat. |
| `/broadcast <text>` | **Admin only.** Send `<text>` (HTML allowed) to every subscribed chat. The chat id of the sender must appear in `ADMIN_CHAT_IDS`. |

## Project layout

```
src/cryptodivlinbot/
├── __init__.py
├── __main__.py            # python -m cryptodivlinbot entrypoint
├── bot.py                 # Application + jobs + wiring
├── config.py              # Settings dataclass / env parsing
├── i18n.py                # UA / RU / EN translations
├── alerts.py              # pure spike-detection helpers
├── market_data.py         # CoinGecko + Binance async clients
├── state.py               # SQLite persistence (WAL mode)
├── keyboards.py           # inline keyboard factories
└── handlers/
    ├── __init__.py
    ├── commands.py        # slash-command handlers
    └── callbacks.py       # inline-button callbacks
tests/                     # pytest suite
```

## Development

```bash
pip install -e .[dev]
ruff check .
mypy src/cryptodivlinbot
pytest -q
```

The codebase passes `mypy --strict`. The configuration lives in
`pyproject.toml` under `[tool.mypy]` (`strict = true`,
`warn_unused_ignores`, `warn_unreachable`, etc.).

## Backups

The bot snapshots its SQLite DB on a schedule using SQLite's online backup
API (`Connection.backup`). Snapshots are written to `${BACKUP_DIR}` as
`cryptodivlinbot-YYYYMMDDTHHMMSSZ.sqlite` (UTC), and the directory is
auto-rotated to keep at most `BACKUP_RETENTION_COUNT` files.

Defaults give you 24 hours of hourly history (`24 × 60 min`). To restore,
stop the bot, copy a snapshot over the live DB (`cp backups/cryptodivlinbot-*.sqlite cryptodivlinbot.sqlite`), and start the
bot again. Schemas are versioned via `PRAGMA user_version`, so a snapshot
from an earlier release will be auto-migrated forward on the first start.

For Docker deployments, snapshots land at `/data/backups` inside the
container (also on the persistent volume) — see `BACKUP_DIR` in
[`docker-compose.yml`](./docker-compose.yml).

## Admin / `/broadcast`

The `/broadcast <text>` command is restricted to chat ids listed in
`ADMIN_CHAT_IDS`. When invoked it broadcasts the rest of the message
(HTML formatting allowed) to every currently subscribed chat, with the
same bounded-concurrency dispatch path that the periodic digest uses, and
reports a `delivered N/M, failed K` summary back to the admin. Chats that
have blocked the bot are auto-unsubscribed mid-broadcast.

Find your numeric chat id by sending `/start` to
[@userinfobot](https://t.me/userinfobot), then add it to `ADMIN_CHAT_IDS`:

```env
ADMIN_CHAT_IDS=123456789
```

Multiple admins are comma-separated. With `ADMIN_CHAT_IDS` empty (the
default), `/broadcast` is fully disabled.

## Privacy, Terms, and `/forgetme`

The bot stores only the bare minimum it needs to talk to your chat —
chat id, language, alert threshold, subscription state, and short-lived
cooldown timestamps. No usernames, names, phone numbers, or message
content is kept.

- [`docs/PRIVACY_POLICY.md`](docs/PRIVACY_POLICY.md) — full policy in
  English. Ukrainian and Russian translations live alongside as
  `_UK.md` and `_RU.md`.
- [`docs/TERMS_OF_SERVICE.md`](docs/TERMS_OF_SERVICE.md) — short ToS
  in EN/UK/RU.
- `/privacy` and `/terms` send a localized summary plus the link to
  the URLs configured by `PRIVACY_POLICY_URL` and `TERMS_OF_SERVICE_URL`.
- `/forgetme` is a two-step GDPR right-to-be-forgotten command. The
  first call shows a confirmation prompt; `/forgetme yes` (or
  `/forgetme y`) deletes the chat row and every cooldown row tied to
  it. Shared `price_history` and `coins_meta` tables are not chat-scoped
  and are intentionally left intact.

If you self-host the documents on a website, override the two URLs:

```env
PRIVACY_POLICY_URL=https://your-domain.example/privacy.html
TERMS_OF_SERVICE_URL=https://your-domain.example/terms.html
```

## Error monitoring (optional)

The bot ships an opt-in [`monitoring`](src/cryptodivlinbot/monitoring.py)
module that can forward unhandled exceptions to Sentry, GlitchTip, or
any Sentry-protocol-compatible backend. It is disabled by default — the
base install does not pull `sentry-sdk` and the bot starts and runs
fine without it.

To enable:

1. Install the optional extra:
   ```bash
   pip install '.[monitoring]'
   ```
2. Set `SENTRY_DSN` (and optionally `SENTRY_ENVIRONMENT`,
   `SENTRY_TRACES_SAMPLE_RATE`) in `.env`.
3. Restart the bot. The startup log line confirms whether Sentry was
   initialized; if `SENTRY_DSN` is set but `sentry-sdk` is missing,
   the module logs a single warning and continues without monitoring
   (no crash).

The `LoggingIntegration` is wired with `level=INFO` /
`event_level=ERROR`, so existing `logger.exception(...)` calls become
Sentry events automatically. A global PTB error handler additionally
forwards every uncaught handler/job exception with an `update_type=...`
scope tag.

## Run with Docker

The repo ships a multi-stage [`Dockerfile`](./Dockerfile) and a
[`docker-compose.yml`](./docker-compose.yml) for production deploys:

```bash
cp .env.example .env             # then edit .env and set TELEGRAM_BOT_TOKEN
docker compose up -d --build
docker compose logs -f bot       # tail logs
```

State (the SQLite DB) lives in the named volume `cryptodivlinbot_data`, so
container restarts do not lose subscriptions or price history. The image
runs as an unprivileged `app` user, declares a lightweight `HEALTHCHECK`,
caps memory at 256 MB by default, and rotates JSON logs (10 MB × 5 files).

To stop and remove the container (volume kept):

```bash
docker compose down
```

To wipe state too:

```bash
docker compose down -v
```

## Continuous Integration

Every push to `main` and every pull request runs
[`.github/workflows/ci.yml`](./.github/workflows/ci.yml). The workflow:

1. Checks out the repo.
2. Spins up a matrix of **Python 3.11** and **Python 3.12** on Ubuntu.
3. Installs the package with the `dev` extras (`pip install -e '.[dev]'`),
   using GitHub's pip cache keyed on `pyproject.toml`.
4. Runs `python -m ruff check .` (lint).
5. Runs `python -m mypy src/cryptodivlinbot` (`--strict` via
   `pyproject.toml`).
6. Runs `python -m pytest -q` (the full 56-test suite).

A green check on the PR means **both** Python versions passed lint and
tests. The matrix is `fail-fast: false`, so if one version fails the other
still finishes — that makes diagnosing version-specific issues easier.

The badge at the top of this README links straight to the latest run.

## License

MIT — see source headers if a license file is added later.
