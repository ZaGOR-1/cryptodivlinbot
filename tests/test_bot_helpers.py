"""Tests for the small pure helpers added to :mod:`cryptodivlinbot.bot`."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from cryptodivlinbot.bot import (
    BOT_CONTEXT_KEY,
    TELEGRAM_MAX_MESSAGE_LEN,
    chunk_for_telegram,
    get_bot_context,
    mask_chat_id,
)


class TestMaskChatId:
    def test_short_chat_id_unchanged(self):
        # IDs ≤ 4 chars don't have anything meaningful to redact.
        assert mask_chat_id(7) == "7"
        assert mask_chat_id(1234) == "1234"

    def test_long_chat_id_only_keeps_tail(self):
        assert mask_chat_id(123456789) == "…6789"
        assert mask_chat_id(987654321012345) == "…2345"

    def test_negative_group_chat_id(self):
        # Telegram negates group chat ids; the helper still keeps the trailing
        # 4 chars (``-...0001`` would not collide with ``...0001``).
        assert mask_chat_id(-100123456789) == "…6789"


class TestChunkForTelegram:
    def test_short_text_is_passed_through(self):
        assert chunk_for_telegram("hello") == ["hello"]

    def test_split_at_line_boundary(self):
        # 5 lines of 1000 chars + 4 newlines = 5004 chars, must split.
        line = "x" * 1000
        text = "\n".join([line] * 5)
        chunks = chunk_for_telegram(text, max_len=2500)
        assert all(len(c) <= 2500 for c in chunks)
        # Reassembling preserves content (joined with \n at chunk boundaries).
        rebuilt = "\n".join(chunks)
        assert rebuilt == text

    def test_hard_cuts_a_line_longer_than_max(self):
        text = "y" * 5000
        chunks = chunk_for_telegram(text, max_len=2000)
        assert all(len(c) <= 2000 for c in chunks)
        assert "".join(chunks) == text

    def test_default_max_matches_telegram_limit(self):
        # The constant exposed for callers should be Telegram's hard cap.
        assert TELEGRAM_MAX_MESSAGE_LEN == 4096
        text = "z" * (TELEGRAM_MAX_MESSAGE_LEN + 100)
        chunks = chunk_for_telegram(text)
        assert all(len(c) <= TELEGRAM_MAX_MESSAGE_LEN for c in chunks)


class TestGetBotContext:
    def test_returns_value_when_initialized(self):
        sentinel = object()
        application = SimpleNamespace(bot_data={BOT_CONTEXT_KEY: sentinel})
        # ``get_bot_context`` is typed against PTB's Application; in practice
        # it just reads ``bot_data[BOT_CONTEXT_KEY]`` so SimpleNamespace works.
        assert get_bot_context(application) is sentinel  # type: ignore[arg-type]

    def test_raises_runtime_error_when_missing(self):
        application = SimpleNamespace(bot_data={})
        with pytest.raises(RuntimeError, match=BOT_CONTEXT_KEY):
            get_bot_context(application)  # type: ignore[arg-type]
