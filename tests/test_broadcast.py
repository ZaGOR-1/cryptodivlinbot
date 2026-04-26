"""Tests for :func:`cryptodivlinbot.bot.broadcast_to_subscribers`.

Exercises the multi-chat dispatch path without spinning up a real
Telegram :class:`Application`. The fake bot/state pair is just enough to
satisfy ``broadcast_to_subscribers``'s structural needs.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from telegram.error import Forbidden, TelegramError

from cryptodivlinbot.bot import (
    BOT_CONTEXT_KEY,
    BotContext,
    broadcast_to_subscribers,
)
from cryptodivlinbot.config import Settings
from cryptodivlinbot.market_data import MarketDataClient
from cryptodivlinbot.state import State


@dataclass
class _SentMessage:
    chat_id: int
    text: str
    parse_mode: str | None


@dataclass
class _FakeBot:
    """Mimics ``application.bot.send_message`` for tests."""

    sent: list[_SentMessage] = field(default_factory=list)
    fail_for: dict[int, BaseException] = field(default_factory=dict)

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str | None = None,
        **_: Any,
    ) -> None:
        if chat_id in self.fail_for:
            raise self.fail_for[chat_id]
        self.sent.append(
            _SentMessage(chat_id=chat_id, text=text, parse_mode=parse_mode)
        )


@dataclass
class _FakeApplication:
    bot_data: dict[str, object]


@dataclass
class _FakeContext:
    """Smallest object that quacks like ``ContextTypes.DEFAULT_TYPE``."""

    application: _FakeApplication
    bot: _FakeBot


def _make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    """Construct a valid :class:`Settings` for tests with safe defaults."""
    base: dict[str, Any] = dict(
        telegram_bot_token="test-token",
        top_n_coins=10,
        spike_threshold_pct=5.0,
        spike_window_min=5,
        poll_interval_sec=60,
        digest_interval_min=5,
        alert_cooldown_min=15,
        default_language="en",
        db_path=tmp_path / "bot.sqlite",
        coingecko_api_key=None,
        coingecko_base_url="https://api.coingecko.com/api/v3",
        binance_base_url="https://api.binance.com",
        http_timeout_sec=10.0,
        log_level="INFO",
        backup_dir=tmp_path / "backups",
        backup_interval_min=60,
        backup_retention_count=24,
        admin_chat_ids=frozenset(),
        privacy_policy_url="https://example.test/privacy",
        terms_of_service_url="https://example.test/terms",
        sentry_dsn=None,
        sentry_environment="test",
        sentry_traces_sample_rate=0.0,
    )
    base.update(overrides)
    return Settings(**base)


def _make_context(
    tmp_path: Path, *, subscribed_ids: Iterable[int]
) -> tuple[_FakeContext, State, _FakeBot]:
    settings = _make_settings(tmp_path)
    state = State(settings.db_path)
    for cid in subscribed_ids:
        state.upsert_chat(cid, default_language="en")
        state.set_subscribed(cid, True)
    market = MarketDataClient(
        coingecko_base_url=settings.coingecko_base_url,
        binance_base_url=settings.binance_base_url,
        timeout_sec=1.0,
        retry_delays=(),
    )
    bot_ctx = BotContext(settings=settings, state=state, market=market)
    bot = _FakeBot()
    app = _FakeApplication(bot_data={BOT_CONTEXT_KEY: bot_ctx})
    return _FakeContext(application=app, bot=bot), state, bot


@pytest.mark.asyncio
async def test_broadcast_no_subscribers(tmp_path: Path) -> None:
    ctx, _state, bot = _make_context(tmp_path, subscribed_ids=())
    ok, total = await broadcast_to_subscribers(ctx, text="hi")  # type: ignore[arg-type]
    assert (ok, total) == (0, 0)
    assert bot.sent == []


@pytest.mark.asyncio
async def test_broadcast_delivers_to_all_subscribers(tmp_path: Path) -> None:
    ctx, _state, bot = _make_context(tmp_path, subscribed_ids=(1, 2, 3))
    ok, total = await broadcast_to_subscribers(  # type: ignore[arg-type]
        ctx, text="<b>hello</b>"
    )
    assert (ok, total) == (3, 3)
    assert sorted(m.chat_id for m in bot.sent) == [1, 2, 3]
    # All deliveries use the configured parse_mode.
    assert {m.parse_mode for m in bot.sent} == {"HTML"}
    # Same payload reaches everyone.
    assert {m.text for m in bot.sent} == {"<b>hello</b>"}


@pytest.mark.asyncio
async def test_broadcast_unsubscribes_on_forbidden(tmp_path: Path) -> None:
    ctx, state, bot = _make_context(tmp_path, subscribed_ids=(1, 2, 3))
    bot.fail_for[2] = Forbidden("blocked")

    ok, total = await broadcast_to_subscribers(ctx, text="hi")  # type: ignore[arg-type]
    assert (ok, total) == (2, 3)
    # The blocked chat must be auto-unsubscribed by the on_forbidden
    # callback wired up inside ``broadcast_to_subscribers``.
    chat = state.get_chat(2)
    assert chat is not None
    assert chat.subscribed is False
    # The other two are still subscribed.
    assert {c.chat_id for c in state.list_subscribed_chats()} == {1, 3}


@pytest.mark.asyncio
async def test_broadcast_partial_failure_counts_correctly(tmp_path: Path) -> None:
    ctx, _state, bot = _make_context(tmp_path, subscribed_ids=(1, 2, 3, 4))
    bot.fail_for[3] = TelegramError("boom")

    ok, total = await broadcast_to_subscribers(ctx, text="hi")  # type: ignore[arg-type]
    assert (ok, total) == (3, 4)


@pytest.mark.asyncio
async def test_broadcast_chunks_long_payload(tmp_path: Path) -> None:
    ctx, _state, bot = _make_context(tmp_path, subscribed_ids=(1,))
    # Build a payload that's longer than Telegram's 4096-char cap so
    # ``chunk_for_telegram`` produces multiple chunks. Use newlines so the
    # chunker can split cleanly.
    line = "x" * 1000
    payload = "\n".join([line] * 6)  # ~6006 chars

    ok, total = await broadcast_to_subscribers(ctx, text=payload)  # type: ignore[arg-type]
    assert (ok, total) == (1, 1)
    assert len(bot.sent) >= 2  # split into ≥ 2 chunks
    for sent in bot.sent:
        assert len(sent.text) <= 4096
        assert sent.chat_id == 1


@pytest.mark.asyncio
async def test_broadcast_stops_chunks_after_first_failure(tmp_path: Path) -> None:
    """If the first chunk fails for a chat, the remaining chunks for that
    chat are skipped (so we don't keep hammering an unreachable chat)."""
    ctx, _state, bot = _make_context(tmp_path, subscribed_ids=(7,))
    bot.fail_for[7] = TelegramError("first fails")
    payload = ("x" * 1000 + "\n") * 6  # forces chunking
    ok, total = await broadcast_to_subscribers(ctx, text=payload)  # type: ignore[arg-type]
    assert (ok, total) == (0, 1)
    # Even though the payload would chunk into ≥ 2 messages, no chunk made
    # it through, so ``sent`` is empty.
    assert bot.sent == []


# Silence "callable not awaited" warnings for the dummy market client we
# never actually use.
@pytest.fixture(autouse=True)
def _silence_unused_market_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop() -> None:  # pragma: no cover - never invoked here
        return None

    # Provide a no-op aclose so closing the unused client does not warn.
    fns: list[Callable[[], None]] = []
    monkeypatch.setattr(
        "cryptodivlinbot.market_data.MarketDataClient.aclose",
        lambda self: _noop(),  # type: ignore[arg-type]
    )
    yield
    for fn in fns:
        fn()
