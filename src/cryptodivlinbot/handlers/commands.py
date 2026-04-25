"""Slash-command handlers.

Each handler is intentionally small: it fetches/updates state via the shared
:class:`State` and replies using strings from :mod:`i18n`. Long-running work like
broadcasting digests is delegated to :mod:`bot` so handlers stay snappy and easy
to test.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .. import keyboards
from ..alerts import format_price, format_signed_pct
from ..config import SUPPORTED_LANGUAGES
from ..i18n import LANGUAGE_NAMES, t
from ..state import ChatPrefs

if TYPE_CHECKING:
    from ..bot import BotContext

logger = logging.getLogger(__name__)


def _ctx(context: ContextTypes.DEFAULT_TYPE) -> BotContext:
    """Pull the shared :class:`BotContext` out of ``application.bot_data``."""
    bot_ctx = context.application.bot_data.get("bot_context")
    if bot_ctx is None:  # pragma: no cover - defensive
        raise RuntimeError("BotContext is not initialized in application.bot_data")
    return bot_ctx


def _resolve_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> ChatPrefs | None:
    """Ensure a ``ChatPrefs`` row exists for the incoming chat and return it."""
    if update.effective_chat is None:
        return None
    bot_ctx = _ctx(context)
    user_lang = update.effective_user.language_code if update.effective_user else None
    initial_lang = bot_ctx.pick_initial_language(user_lang)
    return bot_ctx.state.upsert_chat(update.effective_chat.id, default_language=initial_lang)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    bot_ctx = _ctx(context)
    text = t(
        "start_greeting",
        chat.language,
        top_n=bot_ctx.settings.top_n_coins,
        threshold=bot_ctx.settings.spike_threshold_pct,
        window=bot_ctx.settings.spike_window_min,
        digest=bot_ctx.settings.digest_interval_min,
    )
    await update.effective_message.reply_text(
        text,
        reply_markup=keyboards.main_menu(chat.language, subscribed=chat.subscribed),
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    await update.effective_message.reply_text(
        t("menu_title", chat.language),
        reply_markup=keyboards.main_menu(chat.language, subscribed=chat.subscribed),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    await update.effective_message.reply_text(t("help", chat.language))


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    bot_ctx = _ctx(context)
    threshold = chat.threshold_pct or bot_ctx.settings.spike_threshold_pct
    text = t(
        "status",
        chat.language,
        subscription=t(
            "status_subscribed" if chat.subscribed else "status_not_subscribed",
            chat.language,
        ),
        top_n=bot_ctx.settings.top_n_coins,
        threshold=f"{threshold:g}",
        window=bot_ctx.settings.spike_window_min,
        digest=bot_ctx.settings.digest_interval_min,
        cooldown=bot_ctx.settings.alert_cooldown_min,
        language=LANGUAGE_NAMES.get(chat.language, chat.language),
    )
    await update.effective_message.reply_text(text)


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    bot_ctx = _ctx(context)
    if chat.subscribed:
        await update.effective_message.reply_text(t("already_subscribed", chat.language))
        return
    bot_ctx.state.set_subscribed(chat.chat_id, True)
    await update.effective_message.reply_text(t("subscribed", chat.language))


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    bot_ctx = _ctx(context)
    if not chat.subscribed:
        await update.effective_message.reply_text(t("not_subscribed", chat.language))
        return
    bot_ctx.state.set_subscribed(chat.chat_id, False)
    await update.effective_message.reply_text(t("unsubscribed", chat.language))


async def coins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    bot_ctx = _ctx(context)
    rows = bot_ctx.state.list_coin_meta()
    if not rows:
        await update.effective_message.reply_text(t("coins_empty", chat.language))
        return
    lines = [t("coins_header", chat.language, top_n=bot_ctx.settings.top_n_coins)]
    for row in rows[: bot_ctx.settings.top_n_coins]:
        rank = row["rank"] if row["rank"] is not None else "—"
        lines.append(
            f"{rank}. {row['symbol']} ({row['name']}) — "
            f"${format_price(float(row['last_price']))} "
            f"({format_signed_pct(row['pct_change_24h'])} 24h)"
        )
    await update.effective_message.reply_text("\n".join(lines))


async def digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    bot_ctx = _ctx(context)
    text = bot_ctx.build_digest_text(chat.language)
    if text is None:
        await update.effective_message.reply_text(t("digest_empty", chat.language))
        return
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    await update.effective_message.reply_text(
        t("language_pick", chat.language),
        reply_markup=keyboards.language_menu(chat.language),
    )


async def setlang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    bot_ctx = _ctx(context)
    args = context.args or []
    if not args:
        await update.effective_message.reply_text(t("language_hint", chat.language))
        return
    code = args[0].strip().lower()
    if code not in SUPPORTED_LANGUAGES:
        await update.effective_message.reply_text(t("bad_language", chat.language))
        return
    bot_ctx.state.set_language(chat.chat_id, code)
    await update.effective_message.reply_text(
        t("language_set", code, lang=LANGUAGE_NAMES[code])
    )


async def setthreshold(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    bot_ctx = _ctx(context)
    args = context.args or []
    if not args:
        await update.effective_message.reply_text(t("threshold_usage", chat.language))
        return
    try:
        value = float(args[0].replace(",", "."))
    except ValueError:
        await update.effective_message.reply_text(t("bad_number", chat.language))
        return
    if not 0.1 <= value <= 100.0:
        await update.effective_message.reply_text(t("bad_threshold_range", chat.language))
        return
    bot_ctx.state.set_threshold(chat.chat_id, value)
    await update.effective_message.reply_text(
        t("threshold_set", chat.language, value=f"{value:g}")
    )


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    await update.effective_message.reply_text(t("pong", chat.language))
