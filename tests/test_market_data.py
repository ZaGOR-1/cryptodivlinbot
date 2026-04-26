"""Market-data parsing tests using ``httpx.MockTransport``."""
from __future__ import annotations

import json

import httpx
import pytest

from cryptodivlinbot.market_data import MarketDataClient


def _fake_coingecko_payload():
    return [
        {
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "current_price": 50000.5,
            "market_cap_rank": 1,
            "price_change_percentage_24h_in_currency": 1.23,
        },
        {
            "id": "ethereum",
            "symbol": "eth",
            "name": "Ethereum",
            "current_price": 2000.0,
            "market_cap_rank": 2,
            "price_change_percentage_24h_in_currency": -0.5,
        },
    ]


@pytest.mark.asyncio
async def test_coingecko_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/coins/markets"
        assert request.url.params["vs_currency"] == "usd"
        return httpx.Response(200, json=_fake_coingecko_payload())

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        md = MarketDataClient(
            coingecko_base_url="https://api.coingecko.com/api/v3",
            binance_base_url="https://api.binance.com",
            client=client,
        )
        snapshots = await md.fetch_top_markets(2)

    assert [s.coin_id for s in snapshots] == ["bitcoin", "ethereum"]
    assert snapshots[0].symbol == "BTC"
    assert snapshots[0].price_usd == 50000.5
    assert snapshots[0].pct_change_24h == 1.23
    assert snapshots[1].pct_change_24h == -0.5


@pytest.mark.asyncio
async def test_falls_back_to_binance_on_coingecko_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        if "coingecko" in str(request.url.host):
            return httpx.Response(500, text="boom")
        if request.url.path == "/api/v3/ticker/price":
            symbol = request.url.params["symbol"]
            return httpx.Response(200, json={"symbol": symbol, "price": "1234.5"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        # ``retry_delays=()`` skips the exponential-backoff sleeps so the test
        # doesn't add 6s of wall-clock waiting per run.
        md = MarketDataClient(
            coingecko_base_url="https://api.coingecko.com/api/v3",
            binance_base_url="https://api.binance.com",
            client=client,
            retry_delays=(),
        )
        snapshots = await md.fetch_top_markets(3)

    assert snapshots, "fallback should produce at least one snapshot"
    # Stablecoins are pinned to $1 in the fallback path.
    by_id = {s.coin_id: s for s in snapshots}
    if "tether" in by_id:
        assert by_id["tether"].price_usd == 1.0
    # Non-stablecoins should pick up the mocked $1234.5 quote.
    assert any(s.price_usd == 1234.5 for s in snapshots)


@pytest.mark.asyncio
async def test_coingecko_empty_response_falls_back():
    def handler(request: httpx.Request) -> httpx.Response:
        if "coingecko" in str(request.url.host):
            return httpx.Response(200, content=json.dumps([]))
        return httpx.Response(200, json={"price": "10.0"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        md = MarketDataClient(
            coingecko_base_url="https://api.coingecko.com/api/v3",
            binance_base_url="https://api.binance.com",
            client=client,
            retry_delays=(),
        )
        snapshots = await md.fetch_top_markets(2)

    assert snapshots


@pytest.mark.asyncio
async def test_coingecko_retries_on_5xx_then_succeeds():
    """A transient 503 must trigger a retry before the fallback kicks in."""
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "coingecko" in str(request.url.host):
            calls["count"] += 1
            if calls["count"] < 3:
                return httpx.Response(503, text="overloaded")
            return httpx.Response(200, json=_fake_coingecko_payload())
        return httpx.Response(500)  # binance shouldn't be hit

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        md = MarketDataClient(
            coingecko_base_url="https://api.coingecko.com/api/v3",
            binance_base_url="https://api.binance.com",
            client=client,
            retry_delays=(0, 0, 0),
        )
        snapshots = await md.fetch_top_markets(2)

    assert calls["count"] == 3
    assert [s.coin_id for s in snapshots] == ["bitcoin", "ethereum"]


@pytest.mark.asyncio
async def test_coingecko_retries_on_429_rate_limit():
    """CoinGecko's free tier returns 429s that should be retried, not failed."""
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "coingecko" in str(request.url.host):
            calls["count"] += 1
            if calls["count"] < 2:
                return httpx.Response(429, text="rate limited")
            return httpx.Response(200, json=_fake_coingecko_payload())
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        md = MarketDataClient(
            coingecko_base_url="https://api.coingecko.com/api/v3",
            binance_base_url="https://api.binance.com",
            client=client,
            retry_delays=(0, 0, 0),
        )
        snapshots = await md.fetch_top_markets(2)

    assert calls["count"] == 2
    assert snapshots


@pytest.mark.asyncio
async def test_coingecko_retries_exhaust_then_falls_back_to_binance():
    """All retries 5xx → fall back to the static Binance list."""
    coingecko_calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "coingecko" in str(request.url.host):
            coingecko_calls["count"] += 1
            return httpx.Response(503, text="still overloaded")
        if request.url.path == "/api/v3/ticker/price":
            return httpx.Response(200, json={"price": "100.0"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        md = MarketDataClient(
            coingecko_base_url="https://api.coingecko.com/api/v3",
            binance_base_url="https://api.binance.com",
            client=client,
            retry_delays=(0, 0, 0),  # 1 initial + 3 retries = 4 total attempts
        )
        snapshots = await md.fetch_top_markets(3)

    assert coingecko_calls["count"] == 4  # initial + 3 retries
    assert snapshots, "must fall back to Binance after retries exhausted"
