"""Keyboard factories — both inline (per-message) and reply (persistent at the
bottom of the chat).

Inline callback data follows ``"<scope>:<action>[:<arg>]"`` so callbacks.py can
dispatch with a single split.
"""
from __future__ import annotations

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from .config import SUPPORTED_LANGUAGES
from .i18n import LANGUAGE_FLAGS, LANGUAGE_NAMES, t

CB_SUBSCRIBE = "menu:subscribe"
CB_UNSUBSCRIBE = "menu:unsubscribe"
CB_STATUS = "menu:status"
CB_DIGEST = "menu:digest"
CB_COINS = "menu:coins"
CB_LANGUAGE = "menu:language"
CB_HELP = "menu:help"
CB_CLOSE = "menu:close"
CB_BACK = "menu:back"
CB_LANG_PREFIX = "lang:"  # lang:<code>


def main_menu(language: str, *, subscribed: bool) -> InlineKeyboardMarkup:
    """Compact 3x2 grid with the most-used actions for the chat."""
    sub_button = (
        InlineKeyboardButton(t("btn_unsubscribe", language), callback_data=CB_UNSUBSCRIBE)
        if subscribed
        else InlineKeyboardButton(t("btn_subscribe", language), callback_data=CB_SUBSCRIBE)
    )
    rows = [
        [
            sub_button,
            InlineKeyboardButton(t("btn_status", language), callback_data=CB_STATUS),
        ],
        [
            InlineKeyboardButton(t("btn_digest", language), callback_data=CB_DIGEST),
            InlineKeyboardButton(t("btn_coins", language), callback_data=CB_COINS),
        ],
        [
            InlineKeyboardButton(t("btn_language", language), callback_data=CB_LANGUAGE),
            InlineKeyboardButton(t("btn_help", language), callback_data=CB_HELP),
        ],
        [InlineKeyboardButton(t("btn_close", language), callback_data=CB_CLOSE)],
    ]
    return InlineKeyboardMarkup(rows)


def language_menu(language: str) -> InlineKeyboardMarkup:
    """One button per supported locale plus a Back action."""
    rows = [
        [
            InlineKeyboardButton(
                f"{LANGUAGE_FLAGS[code]} {LANGUAGE_NAMES[code]}",
                callback_data=f"{CB_LANG_PREFIX}{code}",
            )
        ]
        for code in LANGUAGE_NAMES
    ]
    rows.append([InlineKeyboardButton(t("btn_back", language), callback_data=CB_BACK)])
    return InlineKeyboardMarkup(rows)


def back_only(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(t("btn_back", language), callback_data=CB_BACK)]]
    )


# ----------------------------------------------------------------------
# Persistent reply keyboard (pinned at the bottom of the Telegram chat)
# ----------------------------------------------------------------------
# Keys whose translation is shown on the persistent reply keyboard. Order is
# significant — it drives both the displayed layout (3×2 grid + extras) and the
# reverse lookup used by :func:`match_reply_button`.
REPLY_BUTTON_KEYS: tuple[str, ...] = (
    "btn_subscribe",
    "btn_unsubscribe",
    "btn_status",
    "btn_digest",
    "btn_coins",
    "btn_language",
    "btn_help",
)


def main_reply_keyboard(language: str) -> ReplyKeyboardMarkup:
    """Return a persistent reply keyboard with the most-used actions.

    ``is_persistent=True`` keeps it visible alongside the system keyboard;
    ``resize_keyboard=True`` auto-fits the rows to the device width.
    """
    rows = [
        [
            KeyboardButton(t("btn_subscribe", language)),
            KeyboardButton(t("btn_unsubscribe", language)),
        ],
        [
            KeyboardButton(t("btn_status", language)),
            KeyboardButton(t("btn_digest", language)),
        ],
        [
            KeyboardButton(t("btn_coins", language)),
            KeyboardButton(t("btn_language", language)),
        ],
        [KeyboardButton(t("btn_help", language))],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)


def match_reply_button(text: str) -> str | None:
    """Reverse-map a tapped reply-button label back to its canonical key.

    The bot has no way of knowing which language a tapped label came from
    (Telegram delivers a plain text message), so we scan all supported locales
    and return the matching ``btn_*`` key, or ``None`` if the text is just an
    ordinary user message.
    """
    for code in SUPPORTED_LANGUAGES:
        for key in REPLY_BUTTON_KEYS:
            if t(key, code) == text:
                return key
    return None
