"""Inline keyboard factories.

Callback data follows ``"<scope>:<action>[:<arg>]"`` so callbacks.py can dispatch
with a single split.
"""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

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
