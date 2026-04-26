"""Slash-command handlers.

Each handler is intentionally small: it fetches/updates state via the shared
:class:`State` and replies using strings from :mod:`i18n`. Long-running work like
broadcasting digests is delegated to :mod:`bot` so handlers stay snappy and easy
to test.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
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

_CommandHandler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]


def _ctx(context: ContextTypes.DEFAULT_TYPE) -> BotContext:
    """Pull the shared :class:`BotContext` out of ``application.bot_data``."""
    # Local import keeps ``handlers.commands`` free of an import cycle on
    # ``..bot`` at module-load time.
    from ..bot import get_bot_context

    return get_bot_context(context.application)


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
    # Persistent ReplyKeyboard pinned at the bottom of the chat — the user
    # asked for buttons that stay in place between messages. The inline
    # menu remains available via /menu for the collapsible flow.
    await update.effective_message.reply_text(
        text,
        reply_markup=keyboards.main_reply_keyboard(chat.language),
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
    # /coins is plain-text, not HTML; chunk to stay below Telegram's 4096-char
    # ceiling when the user has bumped TOP_N_COINS up.
    from ..bot import chunk_for_telegram  # local import to avoid cycle at module load

    for chunk in chunk_for_telegram("\n".join(lines)):
        await update.effective_message.reply_text(chunk)


async def digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    bot_ctx = _ctx(context)
    text = bot_ctx.build_digest_text(chat.language)
    if text is None:
        await update.effective_message.reply_text(t("digest_empty", chat.language))
        return
    from ..bot import chunk_for_telegram  # local import to avoid cycle at module load

    for chunk in chunk_for_telegram(text):
        await update.effective_message.reply_text(chunk, parse_mode=ParseMode.HTML)


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
    # Refresh the persistent ReplyKeyboard so the labels switch language too.
    await update.effective_message.reply_text(
        t("language_set", code, lang=LANGUAGE_NAMES[code]),
        reply_markup=keyboards.main_reply_keyboard(code),
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


async def privacy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show a short privacy summary plus the link to the full document."""
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    bot_ctx = _ctx(context)
    await update.effective_message.reply_text(
        t("privacy_policy", chat.language, url=bot_ctx.settings.privacy_policy_url),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def terms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show a short ToS summary plus the link to the full document."""
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    bot_ctx = _ctx(context)
    await update.effective_message.reply_text(
        t("terms_of_service", chat.language, url=bot_ctx.settings.terms_of_service_url),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def forgetme(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """GDPR-style data-deletion command. Two-step to avoid accidents.

    First call (``/forgetme``) shows a confirmation prompt. Second call
    (``/forgetme yes``) actually deletes every row tied to the chat id.
    """
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    bot_ctx = _ctx(context)

    args = context.args or []
    confirmed = bool(args) and args[0].strip().lower() in {"yes", "y"}
    if not confirmed:
        await update.effective_message.reply_text(
            t("forget_confirm", chat.language),
            parse_mode=ParseMode.HTML,
        )
        return

    bot_ctx.state.delete_chat(chat.chat_id)
    # The chat row is gone, so we no longer have a stored language; reply
    # in whatever language the chat was using right before the delete.
    await update.effective_message.reply_text(
        t("forget_done", chat.language),
        reply_markup=keyboards.remove_reply_keyboard(),
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only: relay the rest of the message to every subscribed chat.

    Permission is granted only to chat ids listed in
    :attr:`Settings.admin_chat_ids`. Without that allow-list configured,
    the command is silently inert (no-op for non-admins).
    """
    chat = _resolve_chat(update, context)
    if chat is None or update.effective_message is None:
        return
    bot_ctx = _ctx(context)

    if chat.chat_id not in bot_ctx.settings.admin_chat_ids:
        # Quiet permission_denied: don't leak that the command exists to
        # ordinary users. We *do* tell the caller something so an admin
        # debugging a misconfigured ADMIN_CHAT_IDS sees what's going on.
        await update.effective_message.reply_text(t("permission_denied", chat.language))
        return

    # Use ``message.text`` directly so the original whitespace and HTML
    # markup (e.g. ``<b>`` from Telegram's formatting toolbar) survive
    # intact. Strip the leading "/broadcast" (and optional "@botname")
    # plus exactly one whitespace, leaving the rest as the user typed it.
    full = (update.effective_message.text or "").lstrip()
    if full.lower().startswith("/broadcast"):
        body = full.split(maxsplit=1)
        payload = body[1] if len(body) > 1 else ""
    else:
        payload = " ".join(context.args or [])
    payload = payload.strip()

    if not payload:
        await update.effective_message.reply_text(t("broadcast_usage", chat.language))
        return

    from ..bot import broadcast_to_subscribers  # local import to break cycle

    bot_ctx_state = bot_ctx.state
    subscribed = bot_ctx_state.list_subscribed_chats()
    if not subscribed:
        await update.effective_message.reply_text(
            t("broadcast_no_subscribers", chat.language)
        )
        return

    await update.effective_message.reply_text(
        t("broadcast_started", chat.language, count=len(subscribed))
    )
    ok, total = await broadcast_to_subscribers(context, text=payload)
    await update.effective_message.reply_text(
        t(
            "broadcast_done",
            chat.language,
            ok=ok,
            total=total,
            failed=total - ok,
        )
    )


# Reverse mapping: persistent reply-button key → command handler.
# Telegram delivers a tap on a reply button as an ordinary text message, so we
# look up the canonical key via :func:`keyboards.match_reply_button` and
# dispatch to the same coroutine the slash command would.
_REPLY_BUTTON_HANDLERS: dict[str, _CommandHandler] = {
    "btn_subscribe": subscribe,
    "btn_unsubscribe": unsubscribe,
    "btn_status": status,
    "btn_digest": digest,
    "btn_coins": coins,
    "btn_language": language,
    "btn_help": help_cmd,
}


async def on_reply_button(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Route a tap on the persistent reply keyboard to the matching command.

    Falls through silently for ordinary text messages (no match) so the user
    can still chat with the bot without every message firing a handler.
    """
    if update.effective_message is None or update.effective_message.text is None:
        return
    key = keyboards.match_reply_button(update.effective_message.text)
    if key is None:
        return
    handler = _REPLY_BUTTON_HANDLERS.get(key)
    if handler is None:  # pragma: no cover - defensive: keys are static
        return
    await handler(update, context)
