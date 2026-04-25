"""Async market-data clients: CoinGecko (primary) with a Binance fallback.

The bot only needs lightweight, free, public data: a list of the top-N coins by
market cap and their current USD price plus 24h change. We deliberately keep this
module small and side-effect-free — callers are responsible for caching results
in the database.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

# Mapping from a few common CoinGecko ids to the equivalent Binance USDT trading pair.
# Binance is only used when CoinGecko fails; symbols are what the bot displays anyway.
_BINANCE_SYMBOL_MAP: dict[str, str] = {
    "bitcoin": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "tether": "USDTUSDT",  # placeholder — stablecoin, treated as $1
    "binancecoin": "BNBUSDT",
    "solana": "SOLUSDT",
    "ripple": "XRPUSDT",
    "usd-coin": "USDCUSDT",  # placeholder — stablecoin, treated as $1
    "staked-ether": "ETHUSDT",
    "cardano": "ADAUSDT",
    "dogecoin": "DOGEUSDT",
    "tron": "TRXUSDT",
    "avalanche-2": "AVAXUSDT",
    "polkadot": "DOTUSDT",
    "chainlink": "LINKUSDT",
    "polygon": "MATICUSDT",
    "litecoin": "LTCUSDT",
    "shiba-inu": "SHIBUSDT",
    "bitcoin-cash": "BCHUSDT",
    "near": "NEARUSDT",
    "uniswap": "UNIUSDT",
}

# Static fallback list of well-known top coins, used if CoinGecko is completely
# unreachable on the very first run (and we have nothing cached).
_STATIC_FALLBACK: list[tuple[str, str, str]] = [
    ("bitcoin", "BTC", "Bitcoin"),
    ("ethereum", "ETH", "Ethereum"),
    ("tether", "USDT", "Tether"),
    ("binancecoin", "BNB", "BNB"),
    ("solana", "SOL", "Solana"),
    ("ripple", "XRP", "XRP"),
    ("usd-coin", "USDC", "USD Coin"),
    ("cardano", "ADA", "Cardano"),
    ("dogecoin", "DOGE", "Dogecoin"),
    ("tron", "TRX", "TRON"),
]


@dataclass(slots=True)
class CoinSnapshot:
    """Single point-in-time snapshot of a coin used by the alerts engine."""

    coin_id: str
    symbol: str
    name: str
    price_usd: float
    market_cap_rank: int | None = None
    pct_change_24h: float | None = None
    extras: dict[str, float] = field(default_factory=dict)


class MarketDataError(RuntimeError):
    """Raised when no data source could satisfy a request."""


class MarketDataClient:
    """Thin wrapper around CoinGecko + Binance shared by the polling job."""

    def __init__(
        self,
        *,
        coingecko_base_url: str,
        binance_base_url: str,
        coingecko_api_key: str | None = None,
        timeout_sec: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._coingecko_base_url = coingecko_base_url.rstrip("/")
        self._binance_base_url = binance_base_url.rstrip("/")
        self._coingecko_api_key = coingecko_api_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_sec)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> MarketDataClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    # CoinGecko
    # ------------------------------------------------------------------
    async def fetch_top_markets(self, top_n: int) -> list[CoinSnapshot]:
        """Return the top-N coins by market cap, with current USD price & 24h change.

        Falls back to Binance prices for a static list if CoinGecko fails entirely.
        """
        try:
            return await self._coingecko_top_markets(top_n)
        except (httpx.HTTPError, MarketDataError) as exc:
            logger.warning("CoinGecko fetch failed (%s); falling back to Binance", exc)
            return await self._binance_fallback(top_n)

    async def _coingecko_top_markets(self, top_n: int) -> list[CoinSnapshot]:
        params: dict[str, str | int] = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": top_n,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h",
        }
        headers: dict[str, str] = {}
        if self._coingecko_api_key:
            headers["x-cg-pro-api-key"] = self._coingecko_api_key
        url = f"{self._coingecko_base_url}/coins/markets"

        resp = await self._client.get(url, params=params, headers=headers or None)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list) or not data:
            raise MarketDataError("CoinGecko returned no markets")

        out: list[CoinSnapshot] = []
        for item in data:
            try:
                price = float(item["current_price"])
            except (TypeError, ValueError, KeyError):
                continue
            symbol = str(item.get("symbol", "")).upper() or str(item.get("id", "")).upper()
            change_24h_raw = item.get("price_change_percentage_24h_in_currency")
            if change_24h_raw is None:
                change_24h_raw = item.get("price_change_percentage_24h")
            try:
                change_24h = float(change_24h_raw) if change_24h_raw is not None else None
            except (TypeError, ValueError):
                change_24h = None
            rank_raw = item.get("market_cap_rank")
            try:
                rank = int(rank_raw) if rank_raw is not None else None
            except (TypeError, ValueError):
                rank = None
            out.append(
                CoinSnapshot(
                    coin_id=str(item["id"]),
                    symbol=symbol,
                    name=str(item.get("name", symbol)),
                    price_usd=price,
                    market_cap_rank=rank,
                    pct_change_24h=change_24h,
                )
            )
        if not out:
            raise MarketDataError("CoinGecko returned no parseable markets")
        return out

    # ------------------------------------------------------------------
    # Binance fallback
    # ------------------------------------------------------------------
    async def _binance_fallback(self, top_n: int) -> list[CoinSnapshot]:
        """Best-effort fallback when CoinGecko is unreachable.

        We can't compute true market-cap ranks without CoinGecko, so we use the
        static well-known list and trim/extend to top_n.
        """
        coins = _STATIC_FALLBACK[:top_n]
        results: list[CoinSnapshot] = []
        # Deduplicate trading symbols to avoid hammering Binance with duplicates.
        symbols = {c[0]: _BINANCE_SYMBOL_MAP.get(c[0]) for c in coins}

        async def _one(coin_id: str, sym: str | None) -> tuple[str, float | None]:
            if sym is None:
                return coin_id, None
            if sym in {"USDTUSDT", "USDCUSDT"}:
                # Stablecoins on Binance don't trade against themselves; pin to $1.
                return coin_id, 1.0
            url = f"{self._binance_base_url}/api/v3/ticker/price"
            try:
                resp = await self._client.get(url, params={"symbol": sym})
                resp.raise_for_status()
                payload = resp.json()
                price = float(payload["price"])
                return coin_id, price
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                logger.debug("Binance fallback for %s failed: %s", sym, exc)
                return coin_id, None

        prices = await asyncio.gather(*(_one(cid, sym) for cid, sym in symbols.items()))
        price_by_id = dict(prices)

        for rank, (coin_id, symbol, name) in enumerate(coins, start=1):
            price = price_by_id.get(coin_id)
            if price is None:
                continue
            results.append(
                CoinSnapshot(
                    coin_id=coin_id,
                    symbol=symbol,
                    name=name,
                    price_usd=price,
                    market_cap_rank=rank,
                    pct_change_24h=None,
                )
            )
        if not results:
            raise MarketDataError("All market data sources are unavailable")
        return results
