"""Optional Sentry / GlitchTip integration.

The bot ships :mod:`sentry-sdk` only as an *optional* dependency
(``pip install '.[monitoring]'``) so a no-monitoring deploy stays
zero-dependency. The exposed surface is exactly two functions:

* :func:`init_sentry` — call once at startup. If ``SENTRY_DSN`` is empty
  this is a no-op. If the env var is set but ``sentry-sdk`` isn't
  installed, we log a clear warning instead of crashing — the operator
  asked for monitoring, but we can still keep the bot running.
* :func:`capture_exception` — exception sink used by tests and any
  callsite that wants a clean indirection. It silently drops the
  exception when sentry isn't configured, so handlers can call it
  unconditionally.

The PTB ``Application.add_error_handler`` integration lives in
:mod:`cryptodivlinbot.bot` because it needs the application instance.
"""
from __future__ import annotations

import logging
from typing import Any

from . import __version__

logger = logging.getLogger(__name__)

# Module-level flag toggled by :func:`init_sentry` so callers don't need
# to keep their own state. Tests reset this via ``monkeypatch``.
_sentry_initialized: bool = False


def init_sentry(
    *,
    dsn: str | None,
    environment: str,
    traces_sample_rate: float,
    release: str | None = None,
) -> bool:
    """Initialize Sentry if a DSN is provided. Returns ``True`` on success.

    Safe to call multiple times — the second call short-circuits without
    re-initializing.
    """
    global _sentry_initialized

    if not dsn:
        # Empty DSN explicitly disables monitoring; not an error.
        return False

    if _sentry_initialized:
        return True

    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:  # pragma: no cover - exercised when extras aren't installed
        logger.warning(
            "SENTRY_DSN is set but sentry-sdk is not installed. "
            "Install with `pip install '.[monitoring]'` to enable error "
            "reporting. Continuing without Sentry."
        )
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        release=release or f"cryptodivlinbot@{__version__}",
        # Use the LoggingIntegration only for breadcrumbs (INFO and up),
        # NOT for event creation. Bot job/handler errors are forwarded
        # explicitly via :func:`capture_exception` so they carry useful
        # scope tags (``job=poll_job``, ``update_type=...``). Letting the
        # integration also turn every ``logger.exception()`` call into a
        # Sentry event would produce duplicate events for every error.
        integrations=[
            LoggingIntegration(level=logging.INFO, event_level=None),
        ],
        # The bot stores chat ids per user; redact them from default PII
        # capture. Sentry's ``send_default_pii`` is False by default, but
        # we set it explicitly for clarity.
        send_default_pii=False,
    )
    _sentry_initialized = True
    logger.info(
        "Sentry initialized (env=%s, traces=%.2f, release=%s)",
        environment,
        traces_sample_rate,
        release or f"cryptodivlinbot@{__version__}",
    )
    return True


def is_initialized() -> bool:
    """Whether :func:`init_sentry` succeeded earlier in the process."""
    return _sentry_initialized


def capture_exception(exc: BaseException, **scope: Any) -> None:
    """Forward ``exc`` to Sentry if it's initialized, otherwise drop silently.

    Extra ``scope`` kwargs are attached as Sentry tags / context. Keeping
    this indirection means callers don't need to import sentry_sdk
    conditionally.
    """
    if not _sentry_initialized:
        return
    try:
        import sentry_sdk
    except ImportError:  # pragma: no cover - already filtered by init
        return
    if scope:
        with sentry_sdk.push_scope() as s:
            for key, value in scope.items():
                s.set_tag(key, value)
            sentry_sdk.capture_exception(exc)
    else:
        sentry_sdk.capture_exception(exc)


def reset_for_tests() -> None:
    """Test-only helper: clear the initialized flag.

    Called by pytest fixtures to keep the global state isolated between
    tests. Not exposed in the public API.
    """
    global _sentry_initialized
    _sentry_initialized = False
