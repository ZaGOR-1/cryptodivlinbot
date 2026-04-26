"""Tests for the optional Sentry integration in :mod:`cryptodivlinbot.monitoring`.

These tests run with sentry-sdk installed (it's a test-only dep; tests
that exercise the no-sentry-sdk branch monkeypatch the import).
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import pytest

from cryptodivlinbot import monitoring


@pytest.fixture(autouse=True)
def _reset_sentry_state() -> None:
    """Reset the module-level ``_sentry_initialized`` flag before each test."""
    monitoring.reset_for_tests()
    yield
    monitoring.reset_for_tests()


def test_init_sentry_returns_false_with_empty_dsn() -> None:
    assert monitoring.init_sentry(dsn=None, environment="test", traces_sample_rate=0.0) is False
    assert monitoring.init_sentry(dsn="", environment="test", traces_sample_rate=0.0) is False
    assert monitoring.is_initialized() is False


def test_init_sentry_warns_and_returns_false_when_sdk_missing(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the user sets SENTRY_DSN but didn't install the extras, we warn and continue."""
    # Pretend ``import sentry_sdk`` raises ImportError. We can't easily
    # uninstall sentry-sdk in the middle of a test run, so we shadow the
    # module name with a stub that raises on import.
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)

    with caplog.at_level(logging.WARNING, logger="cryptodivlinbot.monitoring"):
        ok = monitoring.init_sentry(
            dsn="https://public@sentry.example/1",
            environment="test",
            traces_sample_rate=0.0,
        )

    assert ok is False
    assert monitoring.is_initialized() is False
    assert any("sentry-sdk is not installed" in rec.message for rec in caplog.records)


def test_init_sentry_initializes_when_dsn_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The happy path: sentry-sdk is importable and DSN is set."""
    captured: dict[str, Any] = {}

    class _FakeSentry:
        @staticmethod
        def init(**kwargs: Any) -> None:
            captured.update(kwargs)

    class _FakeIntegration:
        def __init__(self, *, level: int, event_level: int | None) -> None:
            captured["integration_level"] = level
            captured["integration_event_level"] = event_level

    fake_logging_module = type(sys)("sentry_sdk.integrations.logging")
    fake_logging_module.LoggingIntegration = _FakeIntegration  # type: ignore[attr-defined]
    fake_integrations_module = type(sys)("sentry_sdk.integrations")
    fake_integrations_module.logging = fake_logging_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentry_sdk", _FakeSentry())
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations", fake_integrations_module)
    monkeypatch.setitem(
        sys.modules, "sentry_sdk.integrations.logging", fake_logging_module
    )

    ok = monitoring.init_sentry(
        dsn="https://public@sentry.example/1",
        environment="staging",
        traces_sample_rate=0.25,
        release="cryptodivlinbot@0.2.0",
    )

    assert ok is True
    assert monitoring.is_initialized() is True
    assert captured["dsn"] == "https://public@sentry.example/1"
    assert captured["environment"] == "staging"
    assert captured["traces_sample_rate"] == 0.25
    assert captured["release"] == "cryptodivlinbot@0.2.0"
    assert captured["send_default_pii"] is False
    # The LoggingIntegration must not turn logger.exception() into a
    # Sentry event — otherwise every explicit capture_exception() call
    # in bot.py produces a duplicate. event_level=None disables event
    # creation while still keeping INFO+ logs as breadcrumbs.
    assert captured["integration_level"] == logging.INFO
    assert captured["integration_event_level"] is None


def test_init_sentry_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling :func:`init_sentry` twice does not re-initialize."""
    init_calls: list[dict[str, Any]] = []

    class _FakeSentry:
        @staticmethod
        def init(**kwargs: Any) -> None:
            init_calls.append(kwargs)

    class _FakeIntegration:
        def __init__(self, *, level: int, event_level: int | None) -> None:
            pass

    fake_logging_module = type(sys)("sentry_sdk.integrations.logging")
    fake_logging_module.LoggingIntegration = _FakeIntegration  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentry_sdk", _FakeSentry())
    monkeypatch.setitem(
        sys.modules, "sentry_sdk.integrations.logging", fake_logging_module
    )

    monitoring.init_sentry(
        dsn="https://x@s.example/1", environment="t", traces_sample_rate=0.0
    )
    monitoring.init_sentry(
        dsn="https://x@s.example/1", environment="t", traces_sample_rate=0.0
    )
    assert len(init_calls) == 1


def test_capture_exception_no_op_when_uninitialized() -> None:
    # Should not raise and should not require sentry_sdk to be importable
    monitoring.capture_exception(RuntimeError("boom"))


def test_capture_exception_forwards_to_sentry_with_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_excs: list[BaseException] = []
    captured_tags: list[dict[str, Any]] = []

    class _FakeScope:
        def __init__(self) -> None:
            self.tags: dict[str, Any] = {}

        def set_tag(self, key: str, value: Any) -> None:
            self.tags[key] = value

        def __enter__(self) -> _FakeScope:
            return self

        def __exit__(self, *args: Any) -> None:
            captured_tags.append(self.tags)

    class _FakeSentry:
        @staticmethod
        def init(**_: Any) -> None:
            pass

        @staticmethod
        def capture_exception(exc: BaseException) -> None:
            captured_excs.append(exc)

        @staticmethod
        def new_scope() -> _FakeScope:
            return _FakeScope()

    class _FakeIntegration:
        def __init__(self, *, level: int, event_level: int | None) -> None:
            pass

    fake_logging_module = type(sys)("sentry_sdk.integrations.logging")
    fake_logging_module.LoggingIntegration = _FakeIntegration  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentry_sdk", _FakeSentry())
    monkeypatch.setitem(
        sys.modules, "sentry_sdk.integrations.logging", fake_logging_module
    )

    monitoring.init_sentry(
        dsn="https://x@s.example/1",
        environment="prod",
        traces_sample_rate=0.0,
    )

    err = ValueError("oops")
    monitoring.capture_exception(err, job="poll_job")
    assert captured_excs == [err]
    assert captured_tags == [{"job": "poll_job"}]


def test_capture_exception_without_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_excs: list[BaseException] = []

    class _FakeSentry:
        @staticmethod
        def init(**_: Any) -> None:
            pass

        @staticmethod
        def capture_exception(exc: BaseException) -> None:
            captured_excs.append(exc)

    class _FakeIntegration:
        def __init__(self, *, level: int, event_level: int | None) -> None:
            pass

    fake_logging_module = type(sys)("sentry_sdk.integrations.logging")
    fake_logging_module.LoggingIntegration = _FakeIntegration  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentry_sdk", _FakeSentry())
    monkeypatch.setitem(
        sys.modules, "sentry_sdk.integrations.logging", fake_logging_module
    )

    monitoring.init_sentry(
        dsn="https://x@s.example/1",
        environment="prod",
        traces_sample_rate=0.0,
    )

    err = RuntimeError("plain")
    monitoring.capture_exception(err)
    assert captured_excs == [err]
