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


def _get_int_set(name: str) -> frozenset[int]:
    """Parse a comma-separated list of integers from ``${name}``.

    Empty / unset → empty frozenset. Whitespace and a trailing comma are
    tolerated. Anything that does not parse as an int raises ``ValueError``
    so misconfiguration is caught at startup, not at first use.
    """
    raw = os.getenv(name, "").strip()
    if not raw:
        return frozenset()
    out: set[int] = set()
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            out.add(int(token))
        except ValueError as exc:
            raise ValueError(
                f"{name} must be a comma-separated list of integers; "
                f"got {token!r} as one of the entries"
            ) from exc
    return frozenset(out)


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
    backup_dir: Path
    backup_interval_min: int
    backup_retention_count: int
    admin_chat_ids: frozenset[int]
    privacy_policy_url: str
    terms_of_service_url: str
    sentry_dsn: str | None
    sentry_environment: str
    sentry_traces_sample_rate: float

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
            backup_dir=Path(_get_str("BACKUP_DIR", "backups")),
            backup_interval_min=_get_int("BACKUP_INTERVAL_MIN", 60, lo=1, hi=10080),
            backup_retention_count=_get_int(
                "BACKUP_RETENTION_COUNT", 24, lo=1, hi=10000
            ),
            admin_chat_ids=_get_int_set("ADMIN_CHAT_IDS"),
            privacy_policy_url=_get_str(
                "PRIVACY_POLICY_URL",
                "https://github.com/ZaGOR-1/cryptodivlinbot/blob/main/docs/PRIVACY_POLICY.md",
            ),
            terms_of_service_url=_get_str(
                "TERMS_OF_SERVICE_URL",
                "https://github.com/ZaGOR-1/cryptodivlinbot/blob/main/docs/TERMS_OF_SERVICE.md",
            ),
            sentry_dsn=os.getenv("SENTRY_DSN") or None,
            sentry_environment=_get_str("SENTRY_ENVIRONMENT", "production"),
            sentry_traces_sample_rate=_get_float(
                "SENTRY_TRACES_SAMPLE_RATE", 0.0, lo=0.0, hi=1.0
            ),
        )
