# src/app/data_sources/yahoo_finance/handlers/stats.py
"""Handler for Yahoo Finance key statistics."""

import logging
from typing import Any

import httpx

from .auth import get_yahoo_crumb, clear_crumb_cache

logger = logging.getLogger("data_aggregator")

YAHOO_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"


async def fetch_stats(ticker: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch key statistics for squeeze potential and unusual activity detection.

    Args:
        ticker: Stock symbol (e.g., 'AAPL')
        params: Not used

    Returns:
        Dict with float, short interest, avg volume, etc.
    """
    # Get crumb and cookies for authentication
    crumb, cookies = await get_yahoo_crumb()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    url = YAHOO_SUMMARY_URL.format(ticker=ticker.upper())

    query_params = {
        "modules": "defaultKeyStatistics,summaryDetail,price",
        "crumb": crumb,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=headers, params=query_params, cookies=cookies)

        # If 401, clear cache and retry once
        if response.status_code == 401:
            clear_crumb_cache()
            crumb, cookies = await get_yahoo_crumb()
            query_params["crumb"] = crumb
            response = await client.get(url, headers=headers, params=query_params, cookies=cookies)

        response.raise_for_status()
        data = response.json()

    summary = data.get("quoteSummary", {})
    results = summary.get("result", [])

    if not results:
        error = summary.get("error", {})
        raise ValueError(error.get("description", f"No stats data for {ticker}"))

    result = results[0]

    key_stats = result.get("defaultKeyStatistics", {})
    summary_detail = result.get("summaryDetail", {})
    price_data = result.get("price", {})

    # Float and shares
    shares_outstanding = key_stats.get("sharesOutstanding", {}).get("raw")
    float_shares = key_stats.get("floatShares", {}).get("raw")
    shares_short = key_stats.get("sharesShort", {}).get("raw")
    short_ratio = key_stats.get("shortRatio", {}).get("raw")
    short_percent_of_float = key_stats.get("shortPercentOfFloat", {}).get("raw")
    shares_short_prior = key_stats.get("sharesShortPriorMonth", {}).get("raw")

    # Volume
    avg_volume = summary_detail.get("averageVolume", {}).get("raw")
    avg_volume_10d = summary_detail.get("averageDailyVolume10Day", {}).get("raw")
    current_volume = price_data.get("regularMarketVolume", {}).get("raw")

    # Calculate volume ratio
    volume_ratio = None
    if current_volume and avg_volume:
        volume_ratio = round(current_volume / avg_volume, 2)

    # Beta and other
    beta = key_stats.get("beta", {}).get("raw")
    pe_ratio = summary_detail.get("trailingPE", {}).get("raw")
    forward_pe = summary_detail.get("forwardPE", {}).get("raw")
    peg_ratio = key_stats.get("pegRatio", {}).get("raw")

    # 52-week range
    week_52_high = summary_detail.get("fiftyTwoWeekHigh", {}).get("raw")
    week_52_low = summary_detail.get("fiftyTwoWeekLow", {}).get("raw")
    current_price = price_data.get("regularMarketPrice", {}).get("raw")

    # Distance from 52-week high/low
    pct_from_52w_high = None
    pct_from_52w_low = None
    if current_price and week_52_high:
        pct_from_52w_high = round(((current_price - week_52_high) / week_52_high) * 100, 2)
    if current_price and week_52_low:
        pct_from_52w_low = round(((current_price - week_52_low) / week_52_low) * 100, 2)

    return {
        "ticker": ticker.upper(),
        "shares": {
            "outstanding": shares_outstanding,
            "float": float_shares,
            "short": shares_short,
            "short_prior_month": shares_short_prior,
        },
        "short_interest": {
            "ratio": short_ratio,
            "percent_of_float": round(short_percent_of_float * 100, 2) if short_percent_of_float else None,
        },
        "volume": {
            "current": current_volume,
            "avg_10d": avg_volume_10d,
            "avg_3m": avg_volume,
            "ratio_vs_avg": volume_ratio,
        },
        "valuation": {
            "pe_trailing": pe_ratio,
            "pe_forward": forward_pe,
            "peg_ratio": peg_ratio,
            "beta": beta,
        },
        "range_52w": {
            "high": week_52_high,
            "low": week_52_low,
            "pct_from_high": pct_from_52w_high,
            "pct_from_low": pct_from_52w_low,
        },
    }
