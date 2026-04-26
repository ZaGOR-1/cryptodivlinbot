"""SQLite persistence layer for cryptodivlinbot.

Holds:
  * ``chats``        — per-chat preferences (language, subscription, threshold).
  * ``price_history`` — short rolling window of (coin_id, timestamp, price) tuples
                       used by :mod:`alerts` to compute percent moves over a window.
  * ``last_alerts``  — per-chat / per-coin spike-alert cooldown timestamps.

The schema is intentionally tiny so the module stays easy to reason about. All
writes go through a single shared connection guarded by a re-entrant lock to keep
SQLite happy when called from both the polling job and command handlers running
on different async tasks.

Schema versions are tracked via SQLite's ``PRAGMA user_version``. Adding a new
migration is a matter of appending a tuple to :data:`_MIGRATIONS`; on next
startup it is applied exactly once.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ChatPrefs:
    chat_id: int
    language: str
    subscribed: bool
    threshold_pct: float | None
    created_at: float


# Retain at most this many history rows per coin to keep the DB compact.
_MAX_HISTORY_PER_COIN = 240


# Ordered list of (target_version, sql) migrations. Each entry is applied
# exactly once: when the DB's current ``PRAGMA user_version`` is below
# ``target_version``, the SQL is executed and the version is bumped.
#
# IMPORTANT: never edit a migration that has already shipped — append a new
# one. Migrations are applied in order inside a single transaction.
_MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS chats (
            chat_id      INTEGER PRIMARY KEY,
            language     TEXT    NOT NULL DEFAULT 'en',
            subscribed   INTEGER NOT NULL DEFAULT 0,
            threshold_pct REAL   DEFAULT NULL,
            created_at   REAL    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS price_history (
            coin_id   TEXT    NOT NULL,
            ts        REAL    NOT NULL,
            price_usd REAL    NOT NULL,
            PRIMARY KEY (coin_id, ts)
        );
        CREATE INDEX IF NOT EXISTS price_history_coin_ts
            ON price_history(coin_id, ts DESC);

        CREATE TABLE IF NOT EXISTS last_alerts (
            chat_id INTEGER NOT NULL,
            coin_id TEXT    NOT NULL,
            ts      REAL    NOT NULL,
            PRIMARY KEY (chat_id, coin_id)
        );

        CREATE TABLE IF NOT EXISTS coins_meta (
            coin_id TEXT PRIMARY KEY,
            symbol  TEXT NOT NULL,
            name    TEXT NOT NULL,
            rank    INTEGER,
            pct_change_24h REAL,
            last_price REAL,
            updated_at REAL NOT NULL
        );
        """,
    ),
]


# Highest version known to this build. Used by tests to assert that migrations
# are wired up correctly.
SCHEMA_VERSION: int = max(version for version, _ in _MIGRATIONS) if _MIGRATIONS else 0


class State:
    """Thread-safe SQLite wrapper used by jobs and handlers."""

    def __init__(self, db_path: str | Path):
        self._db_path = str(db_path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            isolation_level=None,  # autocommit
            timeout=30.0,
        )
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._migrate()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def _migrate(self) -> None:
        """Apply pending schema migrations exactly once each.

        Uses SQLite's ``PRAGMA user_version`` as the schema version cursor:
        each migration is applied only when the DB's current version is below
        the migration's target. Migrations should be written to be idempotent
        (e.g. ``CREATE TABLE IF NOT EXISTS``) so a crash mid-way leaves the
        DB safe to retry on next startup.
        """
        with self._lock:
            current = self._user_version()
            for target, sql in _MIGRATIONS:
                if target <= current:
                    continue
                logger.info("Applying DB migration v%d → v%d", current, target)
                self._conn.executescript(sql)
                # ``PRAGMA user_version = N`` does not accept bound parameters;
                # ``target`` is an int from a hard-coded module constant
                # (never user input) so direct interpolation is safe here.
                self._conn.execute(f"PRAGMA user_version = {int(target)}")
                current = target

    def _user_version(self) -> int:
        with self._lock:
            row = self._conn.execute("PRAGMA user_version").fetchone()
        if row is None:
            return 0
        return int(row[0])

    def schema_version(self) -> int:
        """Return the current applied schema version (after ``__init__``)."""
        return self._user_version()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------
    # Chats
    # ------------------------------------------------------------------
    def get_chat(self, chat_id: int) -> ChatPrefs | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT chat_id, language, subscribed, threshold_pct, created_at "
                "FROM chats WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        return _row_to_chat(row) if row is not None else None

    def upsert_chat(
        self,
        chat_id: int,
        *,
        default_language: str,
    ) -> ChatPrefs:
        """Ensure a chat row exists, returning the (possibly new) preferences."""
        existing = self.get_chat(chat_id)
        if existing is not None:
            return existing
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO chats (chat_id, language, subscribed, threshold_pct, "
                "created_at) VALUES (?, ?, 0, NULL, ?)",
                (chat_id, default_language, now),
            )
        return ChatPrefs(
            chat_id=chat_id,
            language=default_language,
            subscribed=False,
            threshold_pct=None,
            created_at=now,
        )

    def set_language(self, chat_id: int, language: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE chats SET language = ? WHERE chat_id = ?",
                (language, chat_id),
            )

    def set_subscribed(self, chat_id: int, subscribed: bool) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE chats SET subscribed = ? WHERE chat_id = ?",
                (1 if subscribed else 0, chat_id),
            )

    def set_threshold(self, chat_id: int, threshold_pct: float | None) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE chats SET threshold_pct = ? WHERE chat_id = ?",
                (threshold_pct, chat_id),
            )

    def list_subscribed_chats(self) -> list[ChatPrefs]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT chat_id, language, subscribed, threshold_pct, created_at "
                "FROM chats WHERE subscribed = 1"
            ).fetchall()
        return [_row_to_chat(r) for r in rows]

    def delete_chat(self, chat_id: int) -> bool:
        """Erase every row tied to ``chat_id``. Returns ``True`` if a chat row existed.

        Removes from the ``chats`` and ``last_alerts`` tables. The shared
        ``price_history`` and ``coins_meta`` tables are not chat-scoped so
        they are intentionally left intact.
        """
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM chats WHERE chat_id = ?", (chat_id,)
            )
            existed = cur.rowcount > 0
            self._conn.execute(
                "DELETE FROM last_alerts WHERE chat_id = ?", (chat_id,)
            )
        return existed

    # ------------------------------------------------------------------
    # Price history
    # ------------------------------------------------------------------
    def record_price(self, coin_id: str, price_usd: float, ts: float | None = None) -> None:
        ts = ts if ts is not None else time.time()
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO price_history (coin_id, ts, price_usd) "
                "VALUES (?, ?, ?)",
                (coin_id, ts, price_usd),
            )

    def record_prices(self, items: Iterable[tuple[str, float]], ts: float | None = None) -> None:
        ts = ts if ts is not None else time.time()
        with self._lock:
            self._conn.executemany(
                "INSERT OR REPLACE INTO price_history (coin_id, ts, price_usd) "
                "VALUES (?, ?, ?)",
                [(coin_id, ts, price) for coin_id, price in items],
            )

    def get_recent_history(
        self, coin_id: str, *, since_ts: float
    ) -> list[tuple[float, float]]:
        """Return ``[(ts, price), ...]`` for ``coin_id`` newer than ``since_ts``.

        Sorted ascending by timestamp. Both ends inclusive.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, price_usd FROM price_history "
                "WHERE coin_id = ? AND ts >= ? ORDER BY ts ASC",
                (coin_id, since_ts),
            ).fetchall()
        return [(float(r["ts"]), float(r["price_usd"])) for r in rows]

    def prune_history(self, *, older_than_ts: float) -> int:
        """Drop rows older than the cut-off and trim per-coin retention."""
        with self._lock:
            deleted = self._conn.execute(
                "DELETE FROM price_history WHERE ts < ?", (older_than_ts,)
            ).rowcount
            # Per-coin cap: keep only the newest N rows per coin_id.
            self._conn.execute(
                """
                DELETE FROM price_history
                WHERE rowid IN (
                    SELECT rowid FROM (
                        SELECT rowid,
                               ROW_NUMBER() OVER (
                                   PARTITION BY coin_id ORDER BY ts DESC
                               ) AS rn
                        FROM price_history
                    )
                    WHERE rn > ?
                )
                """,
                (_MAX_HISTORY_PER_COIN,),
            )
        return int(deleted or 0)

    # ------------------------------------------------------------------
    # Coin metadata cache
    # ------------------------------------------------------------------
    def upsert_coin_meta(
        self,
        coin_id: str,
        *,
        symbol: str,
        name: str,
        rank: int | None,
        pct_change_24h: float | None,
        last_price: float,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO coins_meta (coin_id, symbol, name, rank,
                                        pct_change_24h, last_price, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(coin_id) DO UPDATE SET
                    symbol = excluded.symbol,
                    name = excluded.name,
                    rank = excluded.rank,
                    pct_change_24h = excluded.pct_change_24h,
                    last_price = excluded.last_price,
                    updated_at = excluded.updated_at
                """,
                (coin_id, symbol, name, rank, pct_change_24h, last_price, time.time()),
            )

    def list_coin_meta(self) -> list[sqlite3.Row]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT coin_id, symbol, name, rank, pct_change_24h, last_price, "
                "updated_at FROM coins_meta ORDER BY rank IS NULL, rank ASC"
            ).fetchall()
        return list(rows)

    # ------------------------------------------------------------------
    # Alert cooldowns
    # ------------------------------------------------------------------
    def get_last_alert_ts(self, chat_id: int, coin_id: str) -> float | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT ts FROM last_alerts WHERE chat_id = ? AND coin_id = ?",
                (chat_id, coin_id),
            ).fetchone()
        return float(row["ts"]) if row is not None else None

    def set_last_alert_ts(self, chat_id: int, coin_id: str, ts: float | None = None) -> None:
        ts = ts if ts is not None else time.time()
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO last_alerts (chat_id, coin_id, ts) "
                "VALUES (?, ?, ?)",
                (chat_id, coin_id, ts),
            )


def _row_to_chat(row: sqlite3.Row) -> ChatPrefs:
    threshold = row["threshold_pct"]
    return ChatPrefs(
        chat_id=int(row["chat_id"]),
        language=str(row["language"]),
        subscribed=bool(row["subscribed"]),
        threshold_pct=float(threshold) if threshold is not None else None,
        created_at=float(row["created_at"]),
    )
