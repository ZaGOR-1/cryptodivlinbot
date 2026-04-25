"""Tests for the ``_safe_send`` helper in :mod:`cryptodivlinbot.bot`.

Exercises the success / RetryAfter / Forbidden / TimedOut / TelegramError
branches without spinning up a real Telegram client.
"""
from __future__ import annotations

import pytest
from telegram.error import Forbidden, RetryAfter, TelegramError, TimedOut

from cryptodivlinbot.bot import _safe_send


class TestSafeSend:
    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        calls = 0

        async def send():
            nonlocal calls
            calls += 1

        result = await _safe_send(send, chat_id=1)
        assert result is True
        assert calls == 1

    @pytest.mark.asyncio
    async def test_retries_once_on_retry_after(self, monkeypatch):
        # Don't actually wait the requested seconds in tests.
        sleeps: list[float] = []

        async def fake_sleep(s):
            sleeps.append(s)

        monkeypatch.setattr("cryptodivlinbot.bot.asyncio.sleep", fake_sleep)

        calls = 0

        async def send():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RetryAfter(0.01)

        result = await _safe_send(send, chat_id=1)
        assert result is True
        assert calls == 2
        assert sleeps and sleeps[0] >= 0.01

    @pytest.mark.asyncio
    async def test_returns_false_when_retry_also_fails(self, monkeypatch):
        async def fake_sleep(_):
            return None

        monkeypatch.setattr("cryptodivlinbot.bot.asyncio.sleep", fake_sleep)

        async def send():
            raise RetryAfter(0.01)

        result = await _safe_send(send, chat_id=1)
        assert result is False

    @pytest.mark.asyncio
    async def test_invokes_on_forbidden_callback(self):
        triggered: list[int] = []

        async def send():
            raise Forbidden("blocked")

        def on_forbidden():
            triggered.append(1)

        result = await _safe_send(send, chat_id=42, on_forbidden=on_forbidden)
        assert result is False
        assert triggered == [1]

    @pytest.mark.asyncio
    async def test_invokes_on_forbidden_callback_when_retry_hits_forbidden(
        self, monkeypatch
    ):
        """RetryAfter → retry that gets Forbidden must still unsubscribe the chat."""

        async def fake_sleep(_):
            return None

        monkeypatch.setattr("cryptodivlinbot.bot.asyncio.sleep", fake_sleep)

        triggered: list[int] = []

        calls = 0

        async def send():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RetryAfter(0.01)
            raise Forbidden("blocked between attempts")

        result = await _safe_send(
            send, chat_id=99, on_forbidden=lambda: triggered.append(1)
        )
        assert result is False
        assert triggered == [1]

    @pytest.mark.asyncio
    async def test_returns_false_on_timeout(self):
        async def send():
            raise TimedOut("slow")

        assert await _safe_send(send, chat_id=1) is False

    @pytest.mark.asyncio
    async def test_returns_false_on_generic_telegram_error(self):
        async def send():
            raise TelegramError("boom")

        assert await _safe_send(send, chat_id=1) is False
