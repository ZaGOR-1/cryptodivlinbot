"""Settings.from_env validation tests."""
from __future__ import annotations

import pytest

from cryptodivlinbot.config import Settings


def _set_env(monkeypatch, **values):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test:token")
    for k, v in values.items():
        monkeypatch.setenv(k, str(v))


def test_defaults(monkeypatch):
    _set_env(monkeypatch)
    monkeypatch.delenv("DEFAULT_LANGUAGE", raising=False)
    s = Settings.from_env()
    assert s.telegram_bot_token == "test:token"
    assert s.top_n_coins == 10
    assert s.spike_threshold_pct == 5.0
    assert s.spike_window_min == 5
    assert s.poll_interval_sec == 60
    assert s.digest_interval_min == 5
    assert s.alert_cooldown_min == 15
    assert s.default_language == "uk"
    assert s.coingecko_api_key is None


def test_missing_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        Settings.from_env()


def test_invalid_threshold(monkeypatch):
    _set_env(monkeypatch, SPIKE_THRESHOLD_PCT="0")
    with pytest.raises(ValueError, match="SPIKE_THRESHOLD_PCT"):
        Settings.from_env()


def test_invalid_top_n(monkeypatch):
    _set_env(monkeypatch, TOP_N_COINS="0")
    with pytest.raises(ValueError, match="TOP_N_COINS"):
        Settings.from_env()


def test_invalid_default_language(monkeypatch):
    _set_env(monkeypatch, DEFAULT_LANGUAGE="zz")
    with pytest.raises(ValueError, match="DEFAULT_LANGUAGE"):
        Settings.from_env()


def test_non_numeric_threshold(monkeypatch):
    _set_env(monkeypatch, SPIKE_THRESHOLD_PCT="abc")
    with pytest.raises(ValueError, match="SPIKE_THRESHOLD_PCT"):
        Settings.from_env()


def test_backup_defaults(monkeypatch):
    _set_env(monkeypatch)
    s = Settings.from_env()
    assert s.backup_interval_min == 60
    assert s.backup_retention_count == 24
    # ``Path("backups")`` — the ``backups/`` directory next to the bot's CWD.
    assert s.backup_dir.name == "backups"
    assert s.admin_chat_ids == frozenset()


def test_admin_chat_ids_parsing(monkeypatch):
    _set_env(monkeypatch, ADMIN_CHAT_IDS=" 111, 222, -333 , ")
    s = Settings.from_env()
    assert s.admin_chat_ids == frozenset({111, 222, -333})


def test_admin_chat_ids_rejects_garbage(monkeypatch):
    _set_env(monkeypatch, ADMIN_CHAT_IDS="111,not-a-number")
    with pytest.raises(ValueError, match="ADMIN_CHAT_IDS"):
        Settings.from_env()


def test_invalid_backup_interval(monkeypatch):
    _set_env(monkeypatch, BACKUP_INTERVAL_MIN="0")
    with pytest.raises(ValueError, match="BACKUP_INTERVAL_MIN"):
        Settings.from_env()


def test_invalid_backup_retention(monkeypatch):
    _set_env(monkeypatch, BACKUP_RETENTION_COUNT="0")
    with pytest.raises(ValueError, match="BACKUP_RETENTION_COUNT"):
        Settings.from_env()
