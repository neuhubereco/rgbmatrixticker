"""Manage stock and cryptocurrency tickers and retrieve prices."""

from __future__ import annotations

import logging
from typing import Dict, Iterable, Set

import requests
import yfinance as yf

LOGGER = logging.getLogger(__name__)


class TickerManager:
    """Store and update tickers for stocks and cryptocurrencies."""

    def __init__(self) -> None:
        self.stocks: Set[str] = set()
        self.crypto: Set[str] = set()

    # ------------------------------------------------------------------
    def add_ticker(self, symbol: str, kind: str = "stock") -> None:
        symbol = symbol.upper()
        if kind == "crypto":
            self.crypto.add(symbol)
        else:
            self.stocks.add(symbol)
        LOGGER.debug("Added %s ticker: %s", kind, symbol)

    # ------------------------------------------------------------------
    def remove_ticker(self, symbol: str) -> None:
        symbol = symbol.upper()
        self.stocks.discard(symbol)
        self.crypto.discard(symbol)
        LOGGER.debug("Removed ticker: %s", symbol)

    # ------------------------------------------------------------------
    def _fetch_stock(self, symbol: str) -> str:
        try:
            ticker = yf.Ticker(symbol)
            price = ticker.fast_info.get("last_price") or ticker.info.get("regularMarketPrice")
            return f"{symbol}:{price:.2f}"
        except Exception as exc:  # pragma: no cover - network failures
            LOGGER.warning("Failed to fetch stock %s: %s", symbol, exc)
            return f"{symbol}:N/A"

    # ------------------------------------------------------------------
    def _fetch_crypto(self, symbol: str) -> str:
        try:
            url = (
                "https://api.coingecko.com/api/v3/simple/price?ids="
                f"{symbol.lower()}&vs_currencies=usd"
            )
            resp = requests.get(url, timeout=10)
            price = resp.json().get(symbol.lower(), {}).get("usd")
            return f"{symbol}:{price:.2f}"
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("Failed to fetch crypto %s: %s", symbol, exc)
            return f"{symbol}:N/A"

    # ------------------------------------------------------------------
    def build_ticker_string(self) -> str:
        parts = [self._fetch_stock(sym) for sym in sorted(self.stocks)]
        parts.extend(self._fetch_crypto(sym) for sym in sorted(self.crypto))
        return " | ".join(parts)

    # ------------------------------------------------------------------
    def as_dict(self) -> Dict[str, Iterable[str]]:
        return {"stocks": sorted(self.stocks), "crypto": sorted(self.crypto)}

