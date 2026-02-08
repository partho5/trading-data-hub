# src/app/data_sources/yahoo_finance/handlers/extended.py
"""Handler for Yahoo Finance pre-market and after-hours data."""

import logging
from typing import Any

from ....services.http_client import HttpClient

logger = logging.getLogger("data_aggregator")

YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


async def fetch_extended(ticker: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch pre-market and after-hours price data.

    Args:
        ticker: Stock symbol (e.g., 'AAPL')
        params: Not used

    Returns:
        Dict with extended hours data
    """
    client = HttpClient(use_proxy=True)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    url = YAHOO_QUOTE_URL.format(ticker=ticker.upper())

    query_params = {
        "interval": "1d",
        "range": "1d",
        "includePrePost": "true",
    }

    response = await client.get(url, headers=headers, params=query_params)
    data = response.json()

    chart_response = data.get("chart", {})
    results = chart_response.get("result", [])

    if not results:
        error = chart_response.get("error", {})
        raise ValueError(error.get("description", f"No data found for {ticker}"))

    result = results[0]
    meta = result.get("meta", {})

    # Extract extended hours data
    pre_market_price = meta.get("preMarketPrice")
    pre_market_change = meta.get("preMarketChange")
    pre_market_change_percent = meta.get("preMarketChangePercent")
    pre_market_time = meta.get("preMarketTime")

    post_market_price = meta.get("postMarketPrice")
    post_market_change = meta.get("postMarketChange")
    post_market_change_percent = meta.get("postMarketChangePercent")
    post_market_time = meta.get("postMarketTime")

    regular_price = meta.get("regularMarketPrice")
    regular_time = meta.get("regularMarketTime")

    return {
        "ticker": meta.get("symbol"),
        "regular_market": {
            "price": regular_price,
            "time": regular_time,
        },
        "pre_market": {
            "price": pre_market_price,
            "change": round(pre_market_change, 4) if pre_market_change else None,
            "change_percent": round(pre_market_change_percent, 2) if pre_market_change_percent else None,
            "time": pre_market_time,
            "active": pre_market_price is not None,
        },
        "post_market": {
            "price": post_market_price,
            "change": round(post_market_change, 4) if post_market_change else None,
            "change_percent": round(post_market_change_percent, 2) if post_market_change_percent else None,
            "time": post_market_time,
            "active": post_market_price is not None,
        },
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName"),
    }
