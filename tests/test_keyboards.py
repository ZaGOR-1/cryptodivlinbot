"""Tests for the keyboard factories — both inline and persistent reply."""
from __future__ import annotations

import pytest

from cryptodivlinbot import keyboards
from cryptodivlinbot.config import SUPPORTED_LANGUAGES
from cryptodivlinbot.i18n import t


class TestMainReplyKeyboard:
    @pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
    def test_persistent_and_resized(self, language: str) -> None:
        kb = keyboards.main_reply_keyboard(language)
        # Both flags drive the user-visible behaviour the user explicitly
        # asked for: pinned at the bottom, fitting the screen width.
        assert kb.is_persistent is True
        assert kb.resize_keyboard is True

    @pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
    def test_buttons_are_localized(self, language: str) -> None:
        kb = keyboards.main_reply_keyboard(language)
        labels = [btn.text for row in kb.keyboard for btn in row]
        # Every label is the localized translation of the corresponding key.
        expected = [t(key, language) for key in keyboards.REPLY_BUTTON_KEYS]
        assert labels == expected

    def test_layout_is_3_rows_of_two_plus_help(self) -> None:
        kb = keyboards.main_reply_keyboard("en")
        rows = [list(row) for row in kb.keyboard]
        assert len(rows) == 4
        assert [len(r) for r in rows] == [2, 2, 2, 1]


class TestMatchReplyButton:
    @pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
    @pytest.mark.parametrize("key", keyboards.REPLY_BUTTON_KEYS)
    def test_round_trip_for_every_locale_and_key(
        self, language: str, key: str
    ) -> None:
        # Whatever locale produced the label, the reverse-lookup must
        # recover the canonical key — that's how the dispatcher routes
        # taps to the right handler.
        label = t(key, language)
        assert keyboards.match_reply_button(label) == key

    def test_unknown_text_returns_none(self) -> None:
        assert keyboards.match_reply_button("hello world") is None
        assert keyboards.match_reply_button("") is None
        assert keyboards.match_reply_button("/digest") is None
