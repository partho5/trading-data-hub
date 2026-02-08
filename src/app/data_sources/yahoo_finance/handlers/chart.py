# src/app/data_sources/yahoo_finance/handlers/chart.py
"""Handler for Yahoo Finance chart (historical) data."""

import logging
from typing import Any

from ....services.http_client import HttpClient

logger = logging.getLogger("data_aggregator")

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"

# Valid intervals: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
# Valid ranges: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
DEFAULT_INTERVAL = "1d"
DEFAULT_RANGE = "1mo"


async def fetch_chart(ticker: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch historical OHLCV chart data for a ticker.

    Args:
        ticker: Stock symbol (e.g., 'AAPL')
        params: Optional 'interval' and 'range'

    Returns:
        Dict with chart data (timestamps and OHLCV arrays)
    """
    interval = params.get("interval", DEFAULT_INTERVAL)
    range_period = params.get("range", DEFAULT_RANGE)

    client = HttpClient(use_proxy=True)  # Set to True when proxies configured

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    url = YAHOO_CHART_URL.format(ticker=ticker.upper())

    query_params = {
        "interval": interval,
        "range": range_period,
        "includePrePost": "false",
    }

    response = await client.get(url, headers=headers, params=query_params)
    data = response.json()

    # Extract chart data
    chart_response = data.get("chart", {})
    results = chart_response.get("result", [])

    if not results:
        error = chart_response.get("error", {})
        raise ValueError(error.get("description", f"No chart data found for {ticker}"))

    result = results[0]
    meta = result.get("meta", {})
    timestamps = result.get("timestamp", [])
    indicators = result.get("indicators", {})
    quote_data = indicators.get("quote", [{}])[0]

    # Build OHLCV data points
    ohlcv = []
    for i, ts in enumerate(timestamps):
        ohlcv.append({
            "timestamp": ts,
            "open": quote_data.get("open", [])[i] if i < len(quote_data.get("open", [])) else None,
            "high": quote_data.get("high", [])[i] if i < len(quote_data.get("high", [])) else None,
            "low": quote_data.get("low", [])[i] if i < len(quote_data.get("low", [])) else None,
            "close": quote_data.get("close", [])[i] if i < len(quote_data.get("close", [])) else None,
            "volume": quote_data.get("volume", [])[i] if i < len(quote_data.get("volume", [])) else None,
        })

    return {
        "ticker": meta.get("symbol"),
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName"),
        "interval": interval,
        "range": range_period,
        "data_points": len(ohlcv),
        "ohlcv": ohlcv,
    }
