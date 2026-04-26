"""Persistence layer tests."""
from __future__ import annotations

import sqlite3

from cryptodivlinbot.state import SCHEMA_VERSION, State


def test_chat_lifecycle(tmp_path):
    state = State(tmp_path / "test.sqlite")
    chat = state.upsert_chat(123, default_language="uk")
    assert chat.language == "uk"
    assert chat.subscribed is False
    # Idempotent
    again = state.upsert_chat(123, default_language="en")
    assert again.language == "uk"

    state.set_language(123, "ru")
    state.set_subscribed(123, True)
    state.set_threshold(123, 2.5)

    refreshed = state.get_chat(123)
    assert refreshed is not None
    assert refreshed.language == "ru"
    assert refreshed.subscribed is True
    assert refreshed.threshold_pct == 2.5

    subs = state.list_subscribed_chats()
    assert [c.chat_id for c in subs] == [123]


def test_price_history_ordering_and_pruning(tmp_path):
    state = State(tmp_path / "test.sqlite")
    state.record_prices([("bitcoin", 100.0)], ts=10.0)
    state.record_prices([("bitcoin", 101.0)], ts=20.0)
    state.record_prices([("bitcoin", 102.0)], ts=30.0)
    state.record_prices([("ethereum", 50.0)], ts=15.0)

    btc = state.get_recent_history("bitcoin", since_ts=15.0)
    assert btc == [(20.0, 101.0), (30.0, 102.0)]

    eth = state.get_recent_history("ethereum", since_ts=0.0)
    assert eth == [(15.0, 50.0)]

    deleted = state.prune_history(older_than_ts=20.0)
    assert deleted == 2  # ts=10 (btc) and ts=15 (eth)
    assert state.get_recent_history("bitcoin", since_ts=0.0) == [
        (20.0, 101.0),
        (30.0, 102.0),
    ]


def test_cooldowns(tmp_path):
    state = State(tmp_path / "test.sqlite")
    assert state.get_last_alert_ts(1, "bitcoin") is None
    state.set_last_alert_ts(1, "bitcoin", 1234.5)
    assert state.get_last_alert_ts(1, "bitcoin") == 1234.5
    state.set_last_alert_ts(1, "bitcoin", 9999.0)
    assert state.get_last_alert_ts(1, "bitcoin") == 9999.0


def test_coin_meta_upsert(tmp_path):
    state = State(tmp_path / "test.sqlite")
    state.upsert_coin_meta(
        "bitcoin",
        symbol="BTC",
        name="Bitcoin",
        rank=1,
        pct_change_24h=1.5,
        last_price=50000.0,
    )
    state.upsert_coin_meta(
        "ethereum",
        symbol="ETH",
        name="Ethereum",
        rank=2,
        pct_change_24h=-0.5,
        last_price=2000.0,
    )
    state.upsert_coin_meta(
        "bitcoin",
        symbol="BTC",
        name="Bitcoin",
        rank=1,
        pct_change_24h=2.0,
        last_price=51000.0,
    )

    rows = state.list_coin_meta()
    by_id = {r["coin_id"]: r for r in rows}
    assert by_id["bitcoin"]["last_price"] == 51000.0
    assert by_id["bitcoin"]["pct_change_24h"] == 2.0
    assert by_id["ethereum"]["rank"] == 2
    # Ordered by rank ascending
    assert [r["coin_id"] for r in rows] == ["bitcoin", "ethereum"]


def test_schema_version_is_set_on_fresh_db(tmp_path):
    state = State(tmp_path / "fresh.sqlite")
    assert state.schema_version() == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 1


def test_migrations_are_idempotent(tmp_path):
    """Re-opening an already-migrated DB must not bump the version again."""
    db_path = tmp_path / "stable.sqlite"
    State(db_path).close()
    second = State(db_path)
    assert second.schema_version() == SCHEMA_VERSION


def test_migrations_apply_to_legacy_unversioned_db(tmp_path):
    """A pre-existing DB without ``user_version`` must be brought to current."""
    db_path = tmp_path / "legacy.sqlite"
    raw = sqlite3.connect(db_path)
    try:
        # Fresh empty DB has user_version=0 by default. No tables exist yet.
        assert raw.execute("PRAGMA user_version").fetchone()[0] == 0
    finally:
        raw.close()
    state = State(db_path)
    assert state.schema_version() == SCHEMA_VERSION
    # The migration should have created the chats table.
    state.upsert_chat(42, default_language="en")
    assert state.get_chat(42) is not None


def test_delete_chat_wipes_chat_and_cooldowns(tmp_path):
    """``delete_chat`` removes the chat row and all its cooldown rows."""
    state = State(tmp_path / "del.sqlite")
    state.upsert_chat(42, default_language="en")
    state.set_subscribed(42, True)
    state.set_last_alert_ts(42, "bitcoin", 100.0)
    state.set_last_alert_ts(42, "ethereum", 200.0)
    # Sibling chat that must survive the delete.
    state.upsert_chat(99, default_language="ru")
    state.set_last_alert_ts(99, "bitcoin", 300.0)

    existed = state.delete_chat(42)
    assert existed is True
    assert state.get_chat(42) is None
    assert state.get_last_alert_ts(42, "bitcoin") is None
    assert state.get_last_alert_ts(42, "ethereum") is None
    # Untouched neighbour
    assert state.get_chat(99) is not None
    assert state.get_last_alert_ts(99, "bitcoin") == 300.0


def test_delete_chat_returns_false_when_chat_missing(tmp_path):
    state = State(tmp_path / "del.sqlite")
    assert state.delete_chat(404) is False


def test_last_alerts_unique_per_chat_and_coin(tmp_path):
    """The cooldown table must allow exactly one row per (chat, coin)."""
    state = State(tmp_path / "uniq.sqlite")
    state.set_last_alert_ts(1, "bitcoin", 100.0)
    state.set_last_alert_ts(1, "bitcoin", 200.0)  # overwrite, not duplicate
    state.set_last_alert_ts(1, "ethereum", 150.0)
    state.set_last_alert_ts(2, "bitcoin", 175.0)

    assert state.get_last_alert_ts(1, "bitcoin") == 200.0
    assert state.get_last_alert_ts(1, "ethereum") == 150.0
    assert state.get_last_alert_ts(2, "bitcoin") == 175.0

    # Also assert at the schema level: PRIMARY KEY on (chat_id, coin_id)
    # means SQLite rejects a literal duplicate insert without ON CONFLICT.
    raw = sqlite3.connect(tmp_path / "uniq.sqlite")
    try:
        raw.execute(
            "INSERT INTO last_alerts (chat_id, coin_id, ts) VALUES (1, 'bitcoin', 1.0)"
        )
    except sqlite3.IntegrityError:
        pass
    else:  # pragma: no cover - regression
        raise AssertionError("Duplicate (chat_id, coin_id) was accepted")
    finally:
        raw.close()
