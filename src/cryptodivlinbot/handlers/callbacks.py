"""Inline-button callback handlers.

The same actions exposed by the slash commands are mirrored here so users can
operate the bot purely via the keyboard.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import CallbackQuery, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from .. import keyboards
from ..i18n import LANGUAGE_NAMES, t

if TYPE_CHECKING:
    from ..bot import BotContext

logger = logging.getLogger(__name__)


def _ctx(context: ContextTypes.DEFAULT_TYPE) -> BotContext:
    # Local import to avoid an import cycle on ``..bot`` at module load.
    from ..bot import get_bot_context

    return get_bot_context(context.application)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or update.effective_chat is None:
        return
    bot_ctx = _ctx(context)
    user_lang = update.effective_user.language_code if update.effective_user else None
    initial_lang = bot_ctx.pick_initial_language(user_lang)
    chat = bot_ctx.state.upsert_chat(update.effective_chat.id, default_language=initial_lang)
    data = (query.data or "").strip()

    # Answer the callback exactly once so the spinner clears. The Telegram API
    # only allows answering a query once — calling answer() again later (e.g.
    # to show an alert popup) raises BadRequest, so each branch must produce
    # its own response via _safe_edit instead.
    await query.answer()

    if data.startswith(keyboards.CB_LANG_PREFIX):
        new_lang = data[len(keyboards.CB_LANG_PREFIX) :]
        if new_lang not in LANGUAGE_NAMES:
            await _safe_edit(
                query,
                t("bad_language", chat.language),
                reply_markup=keyboards.language_menu(chat.language),
            )
            return
        bot_ctx.state.set_language(chat.chat_id, new_lang)
        await _safe_edit(
            query,
            t("language_set", new_lang, lang=LANGUAGE_NAMES[new_lang]),
            reply_markup=keyboards.main_menu(new_lang, subscribed=chat.subscribed),
        )
        # edit_message_text can't carry a ReplyKeyboardMarkup — send a tiny
        # follow-up message so the persistent reply keyboard re-renders with
        # labels in the new language.
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=t("language_set", new_lang, lang=LANGUAGE_NAMES[new_lang]),
            reply_markup=keyboards.main_reply_keyboard(new_lang),
        )
        return

    if data == keyboards.CB_SUBSCRIBE:
        if not chat.subscribed:
            bot_ctx.state.set_subscribed(chat.chat_id, True)
        await _safe_edit(
            query,
            t("subscribed", chat.language),
            reply_markup=keyboards.main_menu(chat.language, subscribed=True),
        )
        return

    if data == keyboards.CB_UNSUBSCRIBE:
        if chat.subscribed:
            bot_ctx.state.set_subscribed(chat.chat_id, False)
        await _safe_edit(
            query,
            t("unsubscribed", chat.language),
            reply_markup=keyboards.main_menu(chat.language, subscribed=False),
        )
        return

    if data == keyboards.CB_STATUS:
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
        await _safe_edit(query, text, reply_markup=keyboards.back_only(chat.language))
        return

    if data == keyboards.CB_COINS:
        rows = bot_ctx.state.list_coin_meta()
        if not rows:
            await _safe_edit(
                query,
                t("coins_empty", chat.language),
                reply_markup=keyboards.back_only(chat.language),
            )
            return
        from ..alerts import format_price, format_signed_pct  # local to avoid cycle
        lines = [t("coins_header", chat.language, top_n=bot_ctx.settings.top_n_coins)]
        for row in rows[: bot_ctx.settings.top_n_coins]:
            rank = row["rank"] if row["rank"] is not None else "—"
            lines.append(
                f"{rank}. {row['symbol']} ({row['name']}) — "
                f"${format_price(float(row['last_price']))} "
                f"({format_signed_pct(row['pct_change_24h'])} 24h)"
            )
        await _safe_edit(
            query, "\n".join(lines), reply_markup=keyboards.back_only(chat.language)
        )
        return

    if data == keyboards.CB_DIGEST:
        digest_text = bot_ctx.build_digest_text(chat.language)
        if digest_text is None:
            await _safe_edit(
                query,
                t("digest_empty", chat.language),
                reply_markup=keyboards.back_only(chat.language),
            )
            return
        # The digest may exceed Telegram's 4096-char ceiling once
        # ``TOP_N_COINS`` is bumped up. We can only edit ONE message, so
        # truncate when we can't fit the full payload.
        from ..bot import chunk_for_telegram  # local import to avoid cycle

        chunks = chunk_for_telegram(digest_text)
        first = chunks[0]
        if len(chunks) > 1:
            first = first.rstrip() + "\n…"
        await _safe_edit(
            query,
            first,
            reply_markup=keyboards.back_only(chat.language),
            parse_mode=ParseMode.HTML,
        )
        return

    if data == keyboards.CB_LANGUAGE:
        await _safe_edit(
            query,
            t("language_pick", chat.language),
            reply_markup=keyboards.language_menu(chat.language),
        )
        return

    if data == keyboards.CB_HELP:
        await _safe_edit(
            query, t("help", chat.language), reply_markup=keyboards.back_only(chat.language)
        )
        return

    if data == keyboards.CB_BACK:
        await _safe_edit(
            query,
            t("menu_title", chat.language),
            reply_markup=keyboards.main_menu(chat.language, subscribed=chat.subscribed),
        )
        return

    if data == keyboards.CB_CLOSE:
        try:
            await query.delete_message()
        except BadRequest:
            await _safe_edit(query, t("menu_title", chat.language), reply_markup=None)
        return

    logger.debug("Unknown callback data: %r", data)


async def _safe_edit(
    query: CallbackQuery,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> None:
    """Edit the message in place, swallowing the 'Message is not modified' error."""
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest as exc:
        if "not modified" in str(exc).lower():
            return
        logger.warning("edit_message_text failed: %s", exc)
