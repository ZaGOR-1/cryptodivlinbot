"""Application entrypoint.

Wires together :class:`Settings`, :class:`State`, :class:`MarketDataClient`, and
the command/callback handlers, then registers two recurring jobs on PTB's
``JobQueue``:

* **poll_job** — fetches top-N market data, persists prices, and dispatches
  spike alerts to all subscribed chats.
* **digest_job** — sends a periodic digest of all tracked coins.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import Forbidden, RetryAfter, TelegramError, TimedOut
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from .alerts import (
    SpikeEvent,
    detect_spike,
    format_price,
    format_signed_pct,
    is_within_cooldown,
)
from .config import SUPPORTED_LANGUAGES, Settings
from .handlers import callbacks as cb_handlers
from .handlers import commands as cmd_handlers
from .i18n import t
from .market_data import CoinSnapshot, MarketDataClient, MarketDataError
from .state import State

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BotContext:
    """Shared dependencies handed to every handler / job via ``application.bot_data``."""

    settings: Settings
    state: State
    market: MarketDataClient

    def pick_initial_language(self, telegram_lang_code: str | None) -> str:
        """Pick a starting language for a brand-new chat.

        Honour the user's Telegram client language if it's one we support, otherwise
        fall back to :attr:`Settings.default_language`.
        """
        if telegram_lang_code:
            primary = telegram_lang_code.lower().split("-", 1)[0]
            if primary in SUPPORTED_LANGUAGES:
                return primary
        return self.settings.default_language

    def build_digest_text(self, language: str) -> str | None:
        """Render the digest text for ``language`` using the cached coin metadata.

        Returns ``None`` if there's no data to show yet.
        """
        rows = self.state.list_coin_meta()
        if not rows:
            return None

        window_sec = self.settings.spike_window_min * 60
        now_ts = time.time()
        lines: list[str] = [
            t("digest_header", language, window=self.settings.spike_window_min)
        ]
        for row in rows[: self.settings.top_n_coins]:
            coin_id = str(row["coin_id"])
            history = self.state.get_recent_history(coin_id, since_ts=now_ts - window_sec)
            pct_window: float | None = None
            if len(history) >= 2:
                price_then = history[0][1]
                price_now = history[-1][1]
                if price_then > 0:
                    pct_window = (price_now - price_then) / price_then * 100.0
            lines.append(
                t(
                    "digest_line",
                    language,
                    symbol=row["symbol"],
                    price=format_price(float(row["last_price"])),
                    pct_str=format_signed_pct(pct_window),
                    window=self.settings.spike_window_min,
                    pct_24h_str=format_signed_pct(row["pct_change_24h"]),
                )
            )
        return "\n".join(lines)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
async def _safe_send(
    send: Callable[[], Awaitable[object]],
    *,
    chat_id: int,
    on_forbidden: Callable[[], None] | None = None,
) -> bool:
    """Send a message, retrying once on RetryAfter and unsubscribing on Forbidden.

    Returns ``True`` when the message was delivered.
    """
    try:
        await send()
        return True
    except RetryAfter as exc:
        logger.info("Rate limited; sleeping %.2fs", exc.retry_after)
        await asyncio.sleep(float(exc.retry_after) + 0.5)
        try:
            await send()
            return True
        except TelegramError as exc2:
            logger.warning("send failed after retry to chat %s: %s", chat_id, exc2)
            return False
    except Forbidden as exc:
        logger.info("Bot blocked or kicked from chat %s: %s", chat_id, exc)
        if on_forbidden is not None:
            on_forbidden()
        return False
    except TimedOut as exc:
        logger.warning("send timed out to chat %s: %s", chat_id, exc)
        return False
    except TelegramError as exc:
        logger.warning("send failed to chat %s: %s", chat_id, exc)
        return False


# ----------------------------------------------------------------------
# Jobs
# ----------------------------------------------------------------------
async def poll_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Poll market data and dispatch spike alerts to subscribed chats."""
    bot_ctx: BotContext = context.application.bot_data["bot_context"]
    settings = bot_ctx.settings

    try:
        snapshots = await bot_ctx.market.fetch_top_markets(settings.top_n_coins)
    except MarketDataError as exc:
        logger.warning("Market data unavailable this cycle: %s", exc)
        return
    except Exception:  # noqa: BLE001 - never let job loop die
        logger.exception("Unexpected error fetching market data")
        return

    now_ts = time.time()
    bot_ctx.state.record_prices([(s.coin_id, s.price_usd) for s in snapshots], ts=now_ts)
    for snap in snapshots:
        bot_ctx.state.upsert_coin_meta(
            snap.coin_id,
            symbol=snap.symbol,
            name=snap.name,
            rank=snap.market_cap_rank,
            pct_change_24h=snap.pct_change_24h,
            last_price=snap.price_usd,
        )

    # Periodic GC: keep at most 24h of history.
    bot_ctx.state.prune_history(older_than_ts=now_ts - 24 * 3600)

    chats = bot_ctx.state.list_subscribed_chats()
    if not chats:
        return

    window_sec = settings.spike_window_min * 60
    cooldown_sec = settings.alert_cooldown_min * 60

    for snap in snapshots:
        history = bot_ctx.state.get_recent_history(
            snap.coin_id, since_ts=now_ts - window_sec
        )
        for chat in chats:
            threshold = chat.threshold_pct or settings.spike_threshold_pct
            event = detect_spike(
                history,
                window_sec=window_sec,
                threshold_pct=threshold,
                now_ts=now_ts,
            )
            if event is None:
                continue
            last_alert = bot_ctx.state.get_last_alert_ts(chat.chat_id, snap.coin_id)
            if is_within_cooldown(last_alert, now_ts=now_ts, cooldown_sec=cooldown_sec):
                continue
            delivered = await _dispatch_spike(
                context, bot_ctx, chat.chat_id, chat.language, snap, event
            )
            # Only start the cooldown when the alert actually reached the chat;
            # otherwise the user would silently miss the next ALERT_COOLDOWN_MIN
            # of alerts after a transient send failure.
            if delivered:
                bot_ctx.state.set_last_alert_ts(chat.chat_id, snap.coin_id, now_ts)


async def _dispatch_spike(
    context: ContextTypes.DEFAULT_TYPE,
    bot_ctx: BotContext,
    chat_id: int,
    language: str,
    snap: CoinSnapshot,
    event: SpikeEvent,
) -> bool:
    """Send a single spike alert, returning ``True`` iff Telegram accepted it."""
    key = "spike_alert_up" if event.pct_change >= 0 else "spike_alert_down"
    text = t(
        key,
        language,
        symbol=snap.symbol,
        name=snap.name,
        pct=abs(event.pct_change),
        window=bot_ctx.settings.spike_window_min,
        price=format_price(snap.price_usd),
    )

    async def _send() -> None:
        await context.bot.send_message(
            chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN
        )

    return await _safe_send(
        _send,
        chat_id=chat_id,
        on_forbidden=lambda: bot_ctx.state.set_subscribed(chat_id, False),
    )


async def digest_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcast the periodic digest to every subscribed chat."""
    bot_ctx: BotContext = context.application.bot_data["bot_context"]
    chats = bot_ctx.state.list_subscribed_chats()
    if not chats:
        return

    for chat in chats:
        text = bot_ctx.build_digest_text(chat.language)
        if text is None:
            continue

        async def _send(text: str = text, chat_id: int = chat.chat_id) -> None:
            await context.bot.send_message(
                chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN
            )

        await _safe_send(
            _send,
            chat_id=chat.chat_id,
            on_forbidden=lambda chat_id=chat.chat_id: bot_ctx.state.set_subscribed(
                chat_id, False
            ),
        )


# ----------------------------------------------------------------------
# Wiring
# ----------------------------------------------------------------------
def _register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", cmd_handlers.start))
    application.add_handler(CommandHandler("menu", cmd_handlers.menu))
    application.add_handler(CommandHandler("help", cmd_handlers.help_cmd))
    application.add_handler(CommandHandler("status", cmd_handlers.status))
    application.add_handler(CommandHandler("subscribe", cmd_handlers.subscribe))
    application.add_handler(CommandHandler("unsubscribe", cmd_handlers.unsubscribe))
    application.add_handler(CommandHandler("coins", cmd_handlers.coins))
    application.add_handler(CommandHandler("digest", cmd_handlers.digest))
    application.add_handler(CommandHandler("language", cmd_handlers.language))
    application.add_handler(CommandHandler("setlang", cmd_handlers.setlang))
    application.add_handler(CommandHandler("setthreshold", cmd_handlers.setthreshold))
    application.add_handler(CommandHandler("ping", cmd_handlers.ping))
    application.add_handler(CallbackQueryHandler(cb_handlers.on_callback))


async def _on_startup(application: Application) -> None:
    bot_ctx: BotContext = application.bot_data["bot_context"]
    settings = bot_ctx.settings
    jq = application.job_queue
    if jq is None:  # pragma: no cover - PTB always provides this with [job-queue] extra
        raise RuntimeError(
            "JobQueue is unavailable. Install python-telegram-bot[job-queue]."
        )
    jq.run_repeating(
        poll_job,
        interval=settings.poll_interval_sec,
        first=5,
        name="poll_job",
    )
    jq.run_repeating(
        digest_job,
        interval=settings.digest_interval_min * 60,
        first=settings.digest_interval_min * 60,
        name="digest_job",
    )
    logger.info(
        "Started: top_n=%d threshold=%.2f%% window=%dm digest=%dm",
        settings.top_n_coins,
        settings.spike_threshold_pct,
        settings.spike_window_min,
        settings.digest_interval_min,
    )


async def _on_shutdown(application: Application) -> None:
    bot_ctx: BotContext = application.bot_data.get("bot_context")  # type: ignore[assignment]
    if bot_ctx is None:
        return
    try:
        await bot_ctx.market.aclose()
    except Exception:  # noqa: BLE001 - shutdown best-effort
        logger.exception("Error closing market client")
    try:
        bot_ctx.state.close()
    except Exception:  # noqa: BLE001
        logger.exception("Error closing state")


def build_application(settings: Settings | None = None) -> Application:
    """Construct (but do not start) the configured :class:`Application`."""
    settings = settings or Settings.from_env()
    state = State(settings.db_path)
    market = MarketDataClient(
        coingecko_base_url=settings.coingecko_base_url,
        binance_base_url=settings.binance_base_url,
        coingecko_api_key=settings.coingecko_api_key,
        timeout_sec=settings.http_timeout_sec,
    )
    bot_ctx = BotContext(settings=settings, state=state, market=market)

    application = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .post_init(_on_startup)
        .post_shutdown(_on_shutdown)
        .build()
    )
    application.bot_data["bot_context"] = bot_ctx
    _register_handlers(application)
    return application


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)


def run() -> None:
    """Blocking entry point used by ``python -m cryptodivlinbot`` and the console script."""
    settings = Settings.from_env()
    _configure_logging(settings.log_level)
    application = build_application(settings)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":  # pragma: no cover
    run()
