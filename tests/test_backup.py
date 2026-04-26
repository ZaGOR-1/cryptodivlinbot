"""SQLite online-backup helper tests."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from cryptodivlinbot import backup as backup_module
from cryptodivlinbot.state import State


def _seed_db(path: Path) -> None:
    """Create a populated SQLite file via :class:`State` so we exercise the
    real schema (tables, WAL mode, etc.)."""
    state = State(path)
    try:
        state.upsert_chat(101, default_language="uk")
        state.set_subscribed(101, True)
        state.record_prices([("bitcoin", 50000.0)], ts=time.time())
    finally:
        state.close()


def test_run_backup_creates_snapshot(tmp_path: Path) -> None:
    db = tmp_path / "bot.sqlite"
    backups = tmp_path / "backups"
    _seed_db(db)

    out = backup_module.run_backup(
        db_path=db, backup_dir=backups, retention_count=5
    )

    assert out is not None
    assert out.exists()
    assert out.parent == backups
    assert out.name.startswith("bot-")
    assert out.suffix == ".sqlite"

    # Snapshot must contain the same data as the live DB.
    raw = sqlite3.connect(out)
    try:
        rows = raw.execute(
            "SELECT chat_id, language, subscribed FROM chats"
        ).fetchall()
    finally:
        raw.close()
    assert rows == [(101, "uk", 1)]


def test_run_backup_returns_none_when_source_missing(tmp_path: Path) -> None:
    out = backup_module.run_backup(
        db_path=tmp_path / "nope.sqlite",
        backup_dir=tmp_path / "backups",
        retention_count=3,
    )
    assert out is None


def test_run_backup_rejects_zero_retention(tmp_path: Path) -> None:
    db = tmp_path / "bot.sqlite"
    _seed_db(db)
    with pytest.raises(ValueError):
        backup_module.run_backup(
            db_path=db, backup_dir=tmp_path / "backups", retention_count=0
        )


def test_run_backup_rotation_keeps_only_n_newest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Calling ``run_backup`` more than ``retention_count`` times must
    leave at most ``retention_count`` snapshot files behind, and the
    survivors must be the newest by mtime."""
    import os
    from datetime import UTC, datetime, timedelta

    db = tmp_path / "bot.sqlite"
    backups = tmp_path / "backups"
    _seed_db(db)

    # Drive the clock so each call gets a fresh timestamp suffix and the
    # backups don't collide on filename. Without this, two backups within
    # the same UTC second would share a basename and rotation would race
    # against re-creation in the next iteration.
    base = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    counter = {"i": 0}

    def fake_now() -> datetime:
        out = base + timedelta(seconds=counter["i"])
        counter["i"] += 1
        return out

    monkeypatch.setattr(backup_module, "_utc_now", fake_now)

    keep = 3
    created: list[Path] = []
    # Pin each backup's mtime to its fake creation time so rotation (which
    # sorts by mtime) sees a strict total order matching iteration index.
    for i in range(keep + 2):
        out = backup_module.run_backup(
            db_path=db, backup_dir=backups, retention_count=keep
        )
        assert out is not None
        created.append(out)
        epoch = (base + timedelta(seconds=i)).timestamp()
        os.utime(out, (epoch, epoch))

    surviving = sorted(backups.glob("bot-*.sqlite"))
    assert len(surviving) == keep, surviving

    # The first two creations should have been pruned (oldest mtimes).
    assert not created[0].exists()
    assert not created[1].exists()
    # And the last ``keep`` should still exist.
    for path in created[-keep:]:
        assert path.exists(), path


def test_run_backup_disambiguates_simultaneous_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two backups in the same UTC second must not collide on filename."""
    from datetime import UTC, datetime

    db = tmp_path / "bot.sqlite"
    _seed_db(db)
    fixed = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(backup_module, "_utc_now", lambda: fixed)

    a = backup_module.run_backup(
        db_path=db, backup_dir=tmp_path / "b", retention_count=10
    )
    b = backup_module.run_backup(
        db_path=db, backup_dir=tmp_path / "b", retention_count=10
    )

    assert a is not None
    assert b is not None
    assert a != b
    assert a.exists() and b.exists()


def test_run_backup_ignores_unrelated_files(tmp_path: Path) -> None:
    """Pruning must only delete files matching the DB stem pattern."""
    db = tmp_path / "bot.sqlite"
    backups = tmp_path / "backups"
    _seed_db(db)
    backups.mkdir()
    keepme = backups / "important.txt"
    keepme.write_text("not a backup")

    backup_module.run_backup(db_path=db, backup_dir=backups, retention_count=1)
    backup_module.run_backup(db_path=db, backup_dir=backups, retention_count=1)

    assert keepme.exists()
