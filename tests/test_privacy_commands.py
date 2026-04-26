"""Tests for ``/privacy``, ``/terms``, and ``/forgetme`` handlers.

The handlers depend only on a :class:`BotContext` and an
:class:`Update`/:class:`ContextTypes.DEFAULT_TYPE`. We assemble both with
the smallest fakes that satisfy the call-sites — no real Telegram
``Application`` is built.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from cryptodivlinbot.bot import BOT_CONTEXT_KEY, BotContext
from cryptodivlinbot.config import Settings
from cryptodivlinbot.handlers import commands as cmd_handlers
from cryptodivlinbot.market_data import MarketDataClient
from cryptodivlinbot.state import State


@dataclass
class _Reply:
    text: str
    parse_mode: str | None
    reply_markup: object | None
    disable_web_page_preview: bool | None


@dataclass
class _FakeMessage:
    text: str
    replies: list[_Reply] = field(default_factory=list)

    async def reply_text(
        self,
        text: str,
        *,
        parse_mode: str | None = None,
        reply_markup: object | None = None,
        disable_web_page_preview: bool | None = None,
        **_: Any,
    ) -> None:
        self.replies.append(
            _Reply(
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview,
            )
        )


@dataclass
class _FakeUser:
    language_code: str | None = None


@dataclass
class _FakeChat:
    id: int


@dataclass
class _FakeUpdate:
    effective_chat: _FakeChat
    effective_user: _FakeUser
    effective_message: _FakeMessage


@dataclass
class _FakeApplication:
    bot_data: dict[str, object]


@dataclass
class _FakeContext:
    application: _FakeApplication
    args: list[str] | None = None


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(
        telegram_bot_token="t",
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
        privacy_policy_url="https://example.test/privacy.md",
        terms_of_service_url="https://example.test/terms.md",
        sentry_dsn=None,
        sentry_environment="test",
        sentry_traces_sample_rate=0.0,
    )


def _make_context_and_update(
    tmp_path: Path,
    chat_id: int = 555,
    *,
    args: list[str] | None = None,
    text: str = "",
) -> tuple[_FakeUpdate, _FakeContext, BotContext]:
    settings = _make_settings(tmp_path)
    state = State(settings.db_path)
    market = MarketDataClient(
        coingecko_base_url=settings.coingecko_base_url,
        binance_base_url=settings.binance_base_url,
        timeout_sec=1.0,
        retry_delays=(),
    )
    bot_ctx = BotContext(settings=settings, state=state, market=market)
    app = _FakeApplication(bot_data={BOT_CONTEXT_KEY: bot_ctx})
    update = _FakeUpdate(
        effective_chat=_FakeChat(id=chat_id),
        effective_user=_FakeUser(language_code="en"),
        effective_message=_FakeMessage(text=text),
    )
    ctx = _FakeContext(application=app, args=args)
    return update, ctx, bot_ctx


@pytest.mark.asyncio
async def test_privacy_replies_with_summary_and_url(tmp_path: Path) -> None:
    update, ctx, _ = _make_context_and_update(tmp_path)
    await cmd_handlers.privacy(update, ctx)  # type: ignore[arg-type]
    assert len(update.effective_message.replies) == 1
    reply = update.effective_message.replies[0]
    assert "Privacy policy" in reply.text
    assert "https://example.test/privacy.md" in reply.text
    assert reply.parse_mode == "HTML"
    assert reply.disable_web_page_preview is True


@pytest.mark.asyncio
async def test_terms_replies_with_summary_and_url(tmp_path: Path) -> None:
    update, ctx, _ = _make_context_and_update(tmp_path)
    await cmd_handlers.terms(update, ctx)  # type: ignore[arg-type]
    assert len(update.effective_message.replies) == 1
    reply = update.effective_message.replies[0]
    assert "Terms of service" in reply.text
    assert "https://example.test/terms.md" in reply.text
    assert reply.parse_mode == "HTML"


@pytest.mark.asyncio
async def test_forgetme_first_call_asks_for_confirmation(tmp_path: Path) -> None:
    update, ctx, bot_ctx = _make_context_and_update(tmp_path)
    await cmd_handlers.forgetme(update, ctx)  # type: ignore[arg-type]
    reply = update.effective_message.replies[0]
    assert "/forgetme yes" in reply.text
    # Chat row was created by _resolve_chat — but not deleted yet.
    assert bot_ctx.state.get_chat(555) is not None


@pytest.mark.asyncio
async def test_forgetme_with_confirmation_deletes_chat(tmp_path: Path) -> None:
    update, ctx, bot_ctx = _make_context_and_update(tmp_path, args=["yes"])
    bot_ctx.state.set_subscribed(555, True)
    bot_ctx.state.set_last_alert_ts(555, "bitcoin", 1.0)

    await cmd_handlers.forgetme(update, ctx)  # type: ignore[arg-type]

    assert bot_ctx.state.get_chat(555) is None
    assert bot_ctx.state.get_last_alert_ts(555, "bitcoin") is None
    reply = update.effective_message.replies[0]
    # ReplyKeyboardRemove was sent so the persistent keyboard goes away.
    assert reply.reply_markup is not None


@pytest.mark.asyncio
async def test_forgetme_alternate_confirmation_word(tmp_path: Path) -> None:
    update, ctx, bot_ctx = _make_context_and_update(tmp_path, args=["Y"])
    await cmd_handlers.forgetme(update, ctx)  # type: ignore[arg-type]
    assert bot_ctx.state.get_chat(555) is None


@pytest.mark.asyncio
async def test_forgetme_unknown_arg_still_asks_for_confirmation(tmp_path: Path) -> None:
    update, ctx, bot_ctx = _make_context_and_update(tmp_path, args=["please"])
    await cmd_handlers.forgetme(update, ctx)  # type: ignore[arg-type]
    assert bot_ctx.state.get_chat(555) is not None
    assert "/forgetme yes" in update.effective_message.replies[0].text
