# src/app/data_sources/yahoo_finance/handlers/quote.py
"""Handler for Yahoo Finance quote data."""

import logging
from typing import Any

from ....services.http_client import HttpClient

logger = logging.getLogger("data_aggregator")

# Use v8 chart endpoint - works without auth, contains quote data in meta
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


async def fetch_quote(ticker: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch current quote data for a ticker.

    Uses the chart endpoint which includes quote data in metadata.

    Args:
        ticker: Stock symbol (e.g., 'AAPL')
        params: Not used for quote

    Returns:
        Dict with quote data
    """
    client = HttpClient(use_proxy=True)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    url = YAHOO_CHART_URL.format(ticker=ticker.upper())

    # Get 1 day data - we just need the meta info
    query_params = {
        "interval": "1d",
        "range": "1d",
    }

    response = await client.get(url, headers=headers, params=query_params)
    data = response.json()

    # Extract from chart response
    chart_response = data.get("chart", {})
    results = chart_response.get("result", [])

    if not results:
        error = chart_response.get("error", {})
        raise ValueError(error.get("description", f"No data found for {ticker}"))

    result = results[0]
    meta = result.get("meta", {})

    # Get latest OHLCV if available
    indicators = result.get("indicators", {})
    quote_data = indicators.get("quote", [{}])[0]

    latest_close = None
    latest_open = None
    latest_high = None
    latest_low = None
    latest_volume = None

    if quote_data.get("close"):
        latest_close = quote_data["close"][-1]
    if quote_data.get("open"):
        latest_open = quote_data["open"][-1]
    if quote_data.get("high"):
        latest_high = quote_data["high"][-1]
    if quote_data.get("low"):
        latest_low = quote_data["low"][-1]
    if quote_data.get("volume"):
        latest_volume = quote_data["volume"][-1]

    # Calculate change
    previous_close = meta.get("chartPreviousClose") or meta.get("previousClose")
    current_price = meta.get("regularMarketPrice", latest_close)

    change = None
    change_percent = None
    if current_price and previous_close:
        change = current_price - previous_close
        change_percent = (change / previous_close) * 100

    return {
        "ticker": meta.get("symbol"),
        "name": meta.get("shortName"),
        "price": current_price,
        "change": round(change, 4) if change else None,
        "change_percent": round(change_percent, 2) if change_percent else None,
        "volume": meta.get("regularMarketVolume", latest_volume),
        "day_high": meta.get("regularMarketDayHigh", latest_high),
        "day_low": meta.get("regularMarketDayLow", latest_low),
        "open": latest_open,
        "previous_close": previous_close,
        "market_cap": meta.get("marketCap"),
        "week_52_high": meta.get("fiftyTwoWeekHigh"),
        "week_52_low": meta.get("fiftyTwoWeekLow"),
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName"),
    }
