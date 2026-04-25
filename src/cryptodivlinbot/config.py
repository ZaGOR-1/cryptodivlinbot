"""Environment-driven configuration for cryptodivlinbot.

All tunables live here behind a single :class:`Settings` dataclass. The dataclass is
the single source of truth — handlers and jobs receive the parsed instance instead of
re-reading the environment.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

SUPPORTED_LANGUAGES: Final[frozenset[str]] = frozenset({"en", "uk", "ru"})


def _load_env() -> None:
    """Load ``.env`` from CWD if present. Idempotent."""
    load_dotenv(override=False)


def _get_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw


def _get_int(name: str, default: int, *, lo: int | None = None, hi: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        value = default
    else:
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if lo is not None and value < lo:
        raise ValueError(f"{name} must be >= {lo}, got {value}")
    if hi is not None and value > hi:
        raise ValueError(f"{name} must be <= {hi}, got {value}")
    return value


def _get_float(
    name: str,
    default: float,
    *,
    lo: float | None = None,
    hi: float | None = None,
) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        value = default
    else:
        try:
            value = float(raw)
        except ValueError as exc:
            raise ValueError(f"{name} must be a number, got {raw!r}") from exc
    if lo is not None and value < lo:
        raise ValueError(f"{name} must be >= {lo}, got {value}")
    if hi is not None and value > hi:
        raise ValueError(f"{name} must be <= {hi}, got {value}")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated runtime settings loaded from environment variables."""

    telegram_bot_token: str
    top_n_coins: int
    spike_threshold_pct: float
    spike_window_min: int
    poll_interval_sec: int
    digest_interval_min: int
    alert_cooldown_min: int
    default_language: str
    db_path: Path
    coingecko_api_key: str | None
    coingecko_base_url: str
    binance_base_url: str
    http_timeout_sec: float
    log_level: str

    @classmethod
    def from_env(cls) -> Settings:
        _load_env()

        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN is required. Get one from @BotFather and set it in .env"
            )

        default_lang = _get_str("DEFAULT_LANGUAGE", "uk").strip().lower()
        if default_lang not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"DEFAULT_LANGUAGE must be one of {sorted(SUPPORTED_LANGUAGES)}, "
                f"got {default_lang!r}"
            )

        return cls(
            telegram_bot_token=token,
            top_n_coins=_get_int("TOP_N_COINS", 10, lo=1, hi=50),
            spike_threshold_pct=_get_float("SPIKE_THRESHOLD_PCT", 5.0, lo=0.1, hi=100.0),
            spike_window_min=_get_int("SPIKE_WINDOW_MIN", 5, lo=1, hi=1440),
            poll_interval_sec=_get_int("POLL_INTERVAL_SEC", 60, lo=15, hi=3600),
            digest_interval_min=_get_int("DIGEST_INTERVAL_MIN", 5, lo=1, hi=1440),
            alert_cooldown_min=_get_int("ALERT_COOLDOWN_MIN", 15, lo=0, hi=1440),
            default_language=default_lang,
            db_path=Path(_get_str("DB_PATH", "cryptodivlinbot.sqlite")),
            coingecko_api_key=os.getenv("COINGECKO_API_KEY") or None,
            coingecko_base_url=_get_str(
                "COINGECKO_BASE_URL", "https://api.coingecko.com/api/v3"
            ).rstrip("/"),
            binance_base_url=_get_str(
                "BINANCE_BASE_URL", "https://api.binance.com"
            ).rstrip("/"),
            http_timeout_sec=_get_float("HTTP_TIMEOUT_SEC", 10.0, lo=1.0, hi=120.0),
            log_level=_get_str("LOG_LEVEL", "INFO").upper(),
        )
