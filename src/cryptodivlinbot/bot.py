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
from typing import Any, cast

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import Forbidden, RetryAfter, TelegramError, TimedOut
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .alerts import (
    SpikeEvent,
    detect_spike,
    escape_html,
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

# Key under which the shared :class:`BotContext` lives in PTB's
# ``application.bot_data`` mapping. Always prefer :func:`get_bot_context` over
# touching ``application.bot_data`` directly so a typo can't slip past mypy.
BOT_CONTEXT_KEY: str = "bot_context"

# Telegram caps a single ``send_message`` call at 4096 UTF-16 code units. We
# chunk anything longer at line boundaries to stay safely below the limit.
TELEGRAM_MAX_MESSAGE_LEN: int = 4096

# Cap on concurrent ``send_message`` calls inside a single ``poll_job`` /
# ``digest_job`` cycle. Keeps us friendly to Telegram's per-bot rate limit
# (~30 msg/s overall) while still using parallelism for big chat lists.
_DISPATCH_CONCURRENCY: int = 20


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
                    # The line is interpolated into a HTML-parsed message;
                    # escape special chars in case CoinGecko returns a name
                    # like "Wrapped <ETH>" — which would otherwise be parsed
                    # as a (rejected) HTML tag.
                    symbol=escape_html(str(row["symbol"])),
                    price=format_price(float(row["last_price"])),
                    pct_str=format_signed_pct(pct_window),
                    window=self.settings.spike_window_min,
                    pct_24h_str=format_signed_pct(row["pct_change_24h"]),
                )
            )
        return "\n".join(lines)


def get_bot_context(application: Application[Any, Any, Any, Any, Any, Any]) -> BotContext:
    """Return the shared :class:`BotContext` stored in ``application.bot_data``.

    This indirection keeps the magic-string key in exactly one place and
    raises a clear error if the bot was set up incorrectly, instead of the
    cryptic ``KeyError: 'bot_context'`` you'd get from a direct lookup.
    """
    bot_ctx = application.bot_data.get(BOT_CONTEXT_KEY)
    if bot_ctx is None:  # pragma: no cover - defensive: build_application always sets this
        raise RuntimeError(
            f"BotContext is not initialized in application.bot_data[{BOT_CONTEXT_KEY!r}]"
        )
    return cast(BotContext, bot_ctx)


def mask_chat_id(chat_id: int) -> str:
    """Return a privacy-preserving short identifier for ``chat_id`` in logs.

    Telegram chat ids are personal identifiers — they uniquely link to a user
    or group. We only ever log a ``…NNNN`` tail so log dumps don't leak the
    full id while still leaving enough signal to correlate consecutive lines
    about the same chat.
    """
    s = str(chat_id)
    if len(s) <= 4:
        return s
    return "…" + s[-4:]


def chunk_for_telegram(text: str, *, max_len: int = TELEGRAM_MAX_MESSAGE_LEN) -> list[str]:
    """Split ``text`` into a list of pieces, each ≤ ``max_len`` characters.

    Pieces are split at newline boundaries when possible so multi-line digests
    don't get bisected mid-line. As a last resort (a single line longer than
    ``max_len``) the line itself is hard-cut.
    """
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        # Hard-cut very long single lines that can't fit anywhere.
        while len(line) > max_len:
            head, line = line[:max_len], line[max_len:]
            if current:
                chunks.append(current)
                current = ""
            chunks.append(head)
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > max_len:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


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
    log_id = mask_chat_id(chat_id)
    try:
        await send()
        return True
    except RetryAfter as exc:
        logger.info("Rate limited; sleeping %.2fs", exc.retry_after)
        await asyncio.sleep(float(exc.retry_after) + 0.5)
        try:
            await send()
            return True
        except Forbidden as exc2:
            # Forbidden is a TelegramError subclass — handle it explicitly so the
            # on_forbidden callback (auto-unsubscribe) runs even when the chat
            # blocks us between the rate-limit and the retry.
            logger.info("Bot blocked or kicked from chat %s on retry: %s", log_id, exc2)
            if on_forbidden is not None:
                on_forbidden()
            return False
        except TelegramError as exc2:
            logger.warning("send failed after retry to chat %s: %s", log_id, exc2)
            return False
    except Forbidden as exc:
        logger.info("Bot blocked or kicked from chat %s: %s", log_id, exc)
        if on_forbidden is not None:
            on_forbidden()
        return False
    except TimedOut as exc:
        logger.warning("send timed out to chat %s: %s", log_id, exc)
        return False
    except TelegramError as exc:
        logger.warning("send failed to chat %s: %s", log_id, exc)
        return False


# ----------------------------------------------------------------------
# Jobs
# ----------------------------------------------------------------------
async def poll_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Poll market data and dispatch spike alerts to subscribed chats."""
    bot_ctx = get_bot_context(context.application)
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

    # Build the list of (chat, snap, event) tuples first so detection happens
    # synchronously (cheap) and only delivery is parallelised.
    pending: list[tuple[int, str, CoinSnapshot, SpikeEvent]] = []
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
            pending.append((chat.chat_id, chat.language, snap, event))

    if not pending:
        return

    # Bounded-concurrency dispatch: a Semaphore limits how many `send_message`
    # calls run in parallel so we don't burst past Telegram's per-bot rate
    # limit when broadcasting to thousands of chats.
    semaphore = asyncio.Semaphore(_DISPATCH_CONCURRENCY)

    async def _one(
        chat_id: int, language: str, snap: CoinSnapshot, event: SpikeEvent
    ) -> None:
        async with semaphore:
            delivered = await _dispatch_spike(
                context, bot_ctx, chat_id, language, snap, event
            )
        # Only start the cooldown when the alert actually reached the chat;
        # otherwise the user would silently miss the next ALERT_COOLDOWN_MIN
        # of alerts after a transient send failure.
        if delivered:
            bot_ctx.state.set_last_alert_ts(chat_id, snap.coin_id, now_ts)

    await asyncio.gather(
        *(_one(cid, lang, snap, ev) for cid, lang, snap, ev in pending),
        return_exceptions=False,
    )


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
        # symbol/name go inside <b>…</b> markup; escape any HTML-special
        # chars they might contain so a stray `<` doesn't make Telegram
        # reject the entire message.
        symbol=escape_html(snap.symbol),
        name=escape_html(snap.name),
        pct=abs(event.pct_change),
        window=bot_ctx.settings.spike_window_min,
        price=format_price(snap.price_usd),
    )

    async def _send() -> None:
        await context.bot.send_message(
            chat_id=chat_id, text=text, parse_mode=ParseMode.HTML
        )

    return await _safe_send(
        _send,
        chat_id=chat_id,
        on_forbidden=lambda: bot_ctx.state.set_subscribed(chat_id, False),
    )


async def broadcast_to_subscribers(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    text: str,
    parse_mode: str | None = ParseMode.HTML,
) -> tuple[int, int]:
    """Send ``text`` to every subscribed chat with bounded concurrency.

    Returns ``(ok, total)`` — number of chats that successfully received the
    message and the total that were attempted. Long messages are split via
    :func:`chunk_for_telegram`; if any chunk fails the rest is skipped for
    that chat (so we don't spam half-broken broadcasts).
    """
    bot_ctx = get_bot_context(context.application)
    chats = bot_ctx.state.list_subscribed_chats()
    if not chats:
        return (0, 0)

    semaphore = asyncio.Semaphore(_DISPATCH_CONCURRENCY)
    chunks = chunk_for_telegram(text)

    async def _one(chat_id: int) -> bool:
        def _on_forbidden(cid: int = chat_id) -> None:
            bot_ctx.state.set_subscribed(cid, False)

        async with semaphore:
            for chunk in chunks:

                async def _send(payload: str = chunk, cid: int = chat_id) -> None:
                    await context.bot.send_message(
                        chat_id=cid, text=payload, parse_mode=parse_mode
                    )

                ok = await _safe_send(
                    _send, chat_id=chat_id, on_forbidden=_on_forbidden
                )
                if not ok:
                    return False
            return True

    results = await asyncio.gather(
        *(_one(chat.chat_id) for chat in chats),
        return_exceptions=False,
    )
    return (sum(1 for r in results if r), len(results))


async def backup_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Take a rotated SQLite backup. Errors are logged but never raised."""
    bot_ctx = get_bot_context(context.application)
    settings = bot_ctx.settings
    try:
        # Module-level import would create a cycle with the test harness,
        # but a function-level one keeps ``backup`` discoverable for mypy.
        from . import backup as backup_module

        await asyncio.to_thread(
            backup_module.run_backup,
            db_path=settings.db_path,
            backup_dir=settings.backup_dir,
            retention_count=settings.backup_retention_count,
        )
    except Exception:  # noqa: BLE001 - never let the job loop die
        logger.exception("Backup job failed")


async def digest_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcast the periodic digest to every subscribed chat."""
    bot_ctx = get_bot_context(context.application)
    chats = bot_ctx.state.list_subscribed_chats()
    if not chats:
        return

    semaphore = asyncio.Semaphore(_DISPATCH_CONCURRENCY)

    async def _one(chat_id: int, language: str) -> None:
        digest_text = bot_ctx.build_digest_text(language)
        if digest_text is None:
            return

        def _on_forbidden(cid: int = chat_id) -> None:
            bot_ctx.state.set_subscribed(cid, False)

        async with semaphore:
            for chunk in chunk_for_telegram(digest_text):

                async def _send(
                    payload: str = chunk, cid: int = chat_id
                ) -> None:
                    await context.bot.send_message(
                        chat_id=cid, text=payload, parse_mode=ParseMode.HTML
                    )

                ok = await _safe_send(
                    _send, chat_id=chat_id, on_forbidden=_on_forbidden
                )
                if not ok:
                    # The chat is unreachable (blocked, kicked, transient
                    # failure) — stop sending the remaining chunks so we
                    # don't spam retries.
                    break

    await asyncio.gather(
        *(_one(chat.chat_id, chat.language) for chat in chats),
        return_exceptions=False,
    )


# ----------------------------------------------------------------------
# Wiring
# ----------------------------------------------------------------------
def _register_handlers(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
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
    application.add_handler(CommandHandler("broadcast", cmd_handlers.broadcast))
    application.add_handler(CallbackQueryHandler(cb_handlers.on_callback))
    # Catch text messages that match a persistent reply-keyboard label and
    # route them to the matching command handler. Plain chat messages fall
    # through silently.
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, cmd_handlers.on_reply_button)
    )


async def _on_startup(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
    bot_ctx = get_bot_context(application)
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
    jq.run_repeating(
        backup_job,
        interval=settings.backup_interval_min * 60,
        # Run the first backup soon after startup so even a short-lived
        # process leaves at least one snapshot behind.
        first=30,
        name="backup_job",
    )
    logger.info(
        "Started: top_n=%d threshold=%.2f%% window=%dm digest=%dm "
        "backup=%dm retention=%d admins=%d",
        settings.top_n_coins,
        settings.spike_threshold_pct,
        settings.spike_window_min,
        settings.digest_interval_min,
        settings.backup_interval_min,
        settings.backup_retention_count,
        len(settings.admin_chat_ids),
    )


async def _on_shutdown(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
    bot_ctx = cast(
        "BotContext | None", application.bot_data.get(BOT_CONTEXT_KEY)
    )
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


def build_application(
    settings: Settings | None = None,
) -> Application[Any, Any, Any, Any, Any, Any]:
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
    application.bot_data[BOT_CONTEXT_KEY] = bot_ctx
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
