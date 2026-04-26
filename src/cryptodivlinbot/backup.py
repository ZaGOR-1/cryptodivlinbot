"""SQLite online-backup helper.

Uses :py:meth:`sqlite3.Connection.backup` to copy ``bot.sqlite`` into a
sibling ``backups/`` directory while the bot is still running. Unlike
``shutil.copy`` this is safe under WAL mode — the source connection sees
a consistent snapshot even if writers are mid-transaction.

Backups are named ``<stem>-YYYYMMDDTHHMMSSZ.sqlite`` so directory listing
is naturally chronological. After each new backup the oldest files beyond
``retention_count`` are deleted (rotation).

The module is import-time side-effect free; ``run_backup`` is the only
entrypoint and is meant to be scheduled by the bot's :class:`JobQueue`.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# UTC timestamp suffix using basic-ISO 8601 (no separators) so filenames
# stay portable on Windows / macOS / Linux. Z suffix marks UTC.
_TIMESTAMP_FORMAT: str = "%Y%m%dT%H%M%SZ"


def _utc_now() -> datetime:
    """Indirection so tests can monkey-patch the clock if they want to."""
    return datetime.now(UTC)


def run_backup(
    *,
    db_path: Path,
    backup_dir: Path,
    retention_count: int,
) -> Path | None:
    """Take an online backup of ``db_path`` and rotate old copies.

    Parameters
    ----------
    db_path:
        Path to the live SQLite file. If it does not exist yet (e.g. the
        bot hasn't completed its first migration), the call logs a warning
        and returns ``None`` instead of raising — that's the right thing
        to do for a *scheduled* job.
    backup_dir:
        Directory where snapshots are written. Created with parents if
        missing.
    retention_count:
        Maximum number of snapshot files to keep. Anything older (by
        modification time) is removed after the new snapshot is in place.
        Must be ``>= 1``.

    Returns
    -------
    Path | None
        Path to the newly created snapshot, or ``None`` if the source DB
        was missing.
    """
    if retention_count < 1:
        raise ValueError(f"retention_count must be >= 1, got {retention_count}")

    if not db_path.exists():
        logger.warning(
            "Backup skipped: source DB %s does not exist yet", db_path
        )
        return None

    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = _utc_now().strftime(_TIMESTAMP_FORMAT)
    target = backup_dir / f"{db_path.stem}-{timestamp}.sqlite"

    # SQLite refuses to overwrite an existing file via ``backup()``; if a
    # second backup happens within the same second (tests, manual triggers)
    # disambiguate with a numeric suffix instead of crashing.
    if target.exists():
        i = 1
        while True:
            candidate = backup_dir / f"{db_path.stem}-{timestamp}-{i}.sqlite"
            if not candidate.exists():
                target = candidate
                break
            i += 1

    src = sqlite3.connect(str(db_path))
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    logger.info("Backup written: %s", target)
    _rotate(backup_dir=backup_dir, db_stem=db_path.stem, retention_count=retention_count)
    return target


def _rotate(*, backup_dir: Path, db_stem: str, retention_count: int) -> None:
    """Keep at most ``retention_count`` snapshots; delete the rest (oldest first).

    Only files matching ``<db_stem>-*.sqlite`` are considered, so unrelated
    files in the same directory are left alone.
    """
    pattern = f"{db_stem}-*.sqlite"
    snapshots = sorted(
        backup_dir.glob(pattern),
        # Sort by mtime so the order is stable even if filesystem clock
        # disagrees with the embedded timestamp suffix.
        key=lambda p: p.stat().st_mtime,
    )
    excess = len(snapshots) - retention_count
    if excess <= 0:
        return
    for old in snapshots[:excess]:
        try:
            old.unlink()
            logger.info("Pruned old backup: %s", old)
        except OSError as exc:
            logger.warning("Failed to prune %s: %s", old, exc)
