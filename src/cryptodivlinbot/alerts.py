"""Spike-detection logic.

Pure helpers that take a price history and decide whether a coin's move over the
configured window crosses a chat-specific threshold. Side effects (sending Telegram
messages, persisting cooldowns) live in the bot module — this file is easy to
unit-test in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpikeEvent:
    coin_id: str
    pct_change: float  # signed: positive = up, negative = down
    price_then: float
    price_now: float
    ts_then: float
    ts_now: float


def percent_change(price_then: float, price_now: float) -> float:
    """Return the signed percent change from ``price_then`` to ``price_now``.

    Returns ``0.0`` when ``price_then`` is non-positive — the input is invalid and
    we don't want a divide-by-zero to bring down the polling job.
    """
    if price_then <= 0:
        return 0.0
    return (price_now - price_then) / price_then * 100.0


def detect_spike(
    history: list[tuple[float, float]],
    *,
    window_sec: float,
    threshold_pct: float,
    now_ts: float,
) -> SpikeEvent | None:
    """Detect whether ``history`` shows a spike >= ``threshold_pct`` over ``window_sec``.

    ``history`` is ``[(ts, price), ...]`` sorted ascending by timestamp. We compare
    the most recent price to the *oldest* sample within ``[now_ts - window_sec, now_ts]``.

    Returns ``None`` when there isn't enough data or the move is below threshold.
    """
    if not history or threshold_pct <= 0:
        return None
    cutoff = now_ts - window_sec
    # Drop anything older than the window, then check we have ≥2 samples.
    in_window = [(ts, p) for ts, p in history if ts >= cutoff]
    if len(in_window) < 2:
        return None

    ts_then, price_then = in_window[0]
    ts_now, price_now = in_window[-1]
    if price_then <= 0 or price_now <= 0:
        return None

    pct = percent_change(price_then, price_now)
    if abs(pct) < threshold_pct:
        return None
    return SpikeEvent(
        coin_id="",  # filled in by caller — they know which coin this is
        pct_change=pct,
        price_then=price_then,
        price_now=price_now,
        ts_then=ts_then,
        ts_now=ts_now,
    )


def is_within_cooldown(
    last_alert_ts: float | None,
    *,
    now_ts: float,
    cooldown_sec: float,
) -> bool:
    """Return True if ``last_alert_ts`` is recent enough to suppress a new alert."""
    if last_alert_ts is None or cooldown_sec <= 0:
        return False
    return (now_ts - last_alert_ts) < cooldown_sec


def format_price(price: float) -> str:
    """Format a USD price with sensible precision for both BTC and SHIB-style coins."""
    if price >= 1000:
        return f"{price:,.2f}"
    if price >= 1:
        return f"{price:,.4f}"
    if price >= 0.01:
        return f"{price:.4f}"
    return f"{price:.8f}"


def format_signed_pct(pct: float | None) -> str:
    """Format a signed percent value (or 'n/a') for digest lines."""
    if pct is None:
        return "n/a"
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


# Characters that are special in Telegram's *legacy* Markdown parse mode.
# We escape them in dynamic values (coin symbols and names) before
# interpolating into a `parse_mode=Markdown` message — otherwise a coin
# whose name contains an underscore (e.g. "wormhole_eth") or asterisk
# silently breaks the whole message:
#     "Can't parse entities: can't find end of the entity ..."
_MD_SPECIAL_CHARS = ("_", "*", "`", "[")


def escape_md(value: str) -> str:
    """Backslash-escape Telegram legacy-Markdown special characters in ``value``.

    Apply to user-facing dynamic content (coin symbol, coin name) before
    passing it into a template that will be sent with
    ``ParseMode.MARKDOWN``. Idempotency is *not* guaranteed: do not call
    this twice on the same string.
    """
    out = value
    for ch in _MD_SPECIAL_CHARS:
        out = out.replace(ch, "\\" + ch)
    return out
