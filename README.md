# cryptodivlinbot

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
pytest -q
```

## License

MIT — see source headers if a license file is added later.
