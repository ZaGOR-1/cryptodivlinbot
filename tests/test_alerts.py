"""Unit tests for the pure helpers in :mod:`cryptodivlinbot.alerts`."""
from __future__ import annotations

import pytest

from cryptodivlinbot.alerts import (
    detect_spike,
    escape_html,
    format_price,
    format_signed_pct,
    is_within_cooldown,
    percent_change,
)


class TestPercentChange:
    def test_positive_move(self):
        assert percent_change(100.0, 110.0) == pytest.approx(10.0)

    def test_negative_move(self):
        assert percent_change(100.0, 90.0) == pytest.approx(-10.0)

    def test_no_move(self):
        assert percent_change(100.0, 100.0) == 0.0

    def test_zero_then_returns_zero(self):
        assert percent_change(0.0, 100.0) == 0.0

    def test_negative_then_returns_zero(self):
        assert percent_change(-1.0, 1.0) == 0.0


class TestDetectSpike:
    def _hist(self, prices, *, now_ts=1000.0, step=60.0):
        return [(now_ts - step * (len(prices) - 1 - i), p) for i, p in enumerate(prices)]

    def test_returns_none_when_below_threshold(self):
        history = self._hist([100.0, 102.0])
        assert detect_spike(history, window_sec=300, threshold_pct=5.0, now_ts=1000.0) is None

    def test_detects_upside_spike(self):
        history = self._hist([100.0, 106.0])
        event = detect_spike(history, window_sec=300, threshold_pct=5.0, now_ts=1000.0)
        assert event is not None
        assert event.pct_change == pytest.approx(6.0)
        assert event.price_then == 100.0
        assert event.price_now == 106.0

    def test_detects_downside_spike(self):
        history = self._hist([100.0, 93.0])
        event = detect_spike(history, window_sec=300, threshold_pct=5.0, now_ts=1000.0)
        assert event is not None
        assert event.pct_change == pytest.approx(-7.0)

    def test_drops_samples_outside_window(self):
        # Old sample (300s away) is +10%, but it's outside the 60s window so
        # only the in-window samples should be compared and they're flat.
        history = [(700.0, 100.0), (970.0, 110.0), (1000.0, 110.0)]
        event = detect_spike(history, window_sec=60, threshold_pct=5.0, now_ts=1000.0)
        assert event is None

    def test_requires_at_least_two_samples(self):
        history = [(1000.0, 100.0)]
        assert detect_spike(history, window_sec=300, threshold_pct=5.0, now_ts=1000.0) is None

    def test_empty_history(self):
        assert detect_spike([], window_sec=300, threshold_pct=5.0, now_ts=1000.0) is None

    def test_zero_threshold_returns_none(self):
        history = self._hist([100.0, 200.0])
        assert detect_spike(history, window_sec=300, threshold_pct=0.0, now_ts=1000.0) is None


class TestCooldown:
    def test_none_means_no_cooldown(self):
        assert not is_within_cooldown(None, now_ts=1000.0, cooldown_sec=600)

    def test_recent_blocks(self):
        assert is_within_cooldown(900.0, now_ts=1000.0, cooldown_sec=600)

    def test_expired_does_not_block(self):
        assert not is_within_cooldown(0.0, now_ts=1000.0, cooldown_sec=600)

    def test_zero_cooldown_never_blocks(self):
        assert not is_within_cooldown(999.0, now_ts=1000.0, cooldown_sec=0)


class TestFormatters:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (1234.5, "1,234.50"),
            (12.345678, "12.3457"),
            (0.5, "0.5000"),
            (0.0001234, "0.00012340"),
        ],
    )
    def test_format_price(self, value, expected):
        assert format_price(value) == expected

    def test_format_signed_pct(self):
        assert format_signed_pct(None) == "n/a"
        assert format_signed_pct(0.0) == "+0.00%"
        assert format_signed_pct(2.345) == "+2.35%"
        assert format_signed_pct(-1.2) == "-1.20%"


class TestEscapeHtml:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("BTC", "BTC"),  # plain alphanum is untouched
            ("Wrapped <ETH>", "Wrapped &lt;ETH&gt;"),  # would otherwise be a tag
            ("AT&T", "AT&amp;T"),  # ampersand starts an HTML entity
            ("a < b", "a &lt; b"),  # standalone less-than
            ("Tom & Jerry > Mickey", "Tom &amp; Jerry &gt; Mickey"),
        ],
    )
    def test_escape_html(self, value, expected):
        assert escape_html(value) == expected

    def test_escape_html_leaves_md_specials_alone(self):
        # `_`, `*`, `` ` ``, `[`, `(`, `)` are NOT html-special; HTML mode
        # is precisely why we no longer have to escape them by hand.
        assert (
            escape_html("WETH_ETH FOO*BAR a`b [name](url)")
            == "WETH_ETH FOO*BAR a`b [name](url)"
        )

    def test_escape_html_does_not_touch_safe_chars(self):
        assert escape_html("BTC-USD 1,234.50 (+2.5%)") == "BTC-USD 1,234.50 (+2.5%)"

    def test_escape_html_quotes_are_left_alone(self):
        # quote=False keeps single/double quotes readable; we never use them
        # inside HTML attribute values, so escaping them is just visual noise.
        assert escape_html("She said \"hi\" — it's fine") == (
            "She said \"hi\" — it's fine"
        )
