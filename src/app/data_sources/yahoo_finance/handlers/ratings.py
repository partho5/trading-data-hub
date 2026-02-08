# src/app/data_sources/yahoo_finance/handlers/ratings.py
"""Handler for Yahoo Finance analyst ratings."""

import logging
from typing import Any

import httpx

from .auth import get_yahoo_crumb, clear_crumb_cache

logger = logging.getLogger("data_aggregator")

YAHOO_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"


async def fetch_ratings(ticker: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch analyst ratings and price targets.

    Args:
        ticker: Stock symbol (e.g., 'AAPL')
        params: Not used

    Returns:
        Dict with analyst recommendations, price targets, upgrades/downgrades
    """
    # Get crumb and cookies for authentication
    crumb, cookies = await get_yahoo_crumb()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    url = YAHOO_SUMMARY_URL.format(ticker=ticker.upper())

    query_params = {
        "modules": "recommendationTrend,upgradeDowngradeHistory,financialData",
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
        raise ValueError(error.get("description", f"No ratings data for {ticker}"))

    result = results[0]

    # Current recommendation trend
    rec_trend = result.get("recommendationTrend", {}).get("trend", [])
    current_ratings = None
    if rec_trend:
        current = rec_trend[0]
        current_ratings = {
            "period": current.get("period"),
            "strong_buy": current.get("strongBuy"),
            "buy": current.get("buy"),
            "hold": current.get("hold"),
            "sell": current.get("sell"),
            "strong_sell": current.get("strongSell"),
        }

    # Financial data (price targets)
    financial = result.get("financialData", {})
    target_high = financial.get("targetHighPrice", {}).get("raw")
    target_low = financial.get("targetLowPrice", {}).get("raw")
    target_mean = financial.get("targetMeanPrice", {}).get("raw")
    target_median = financial.get("targetMedianPrice", {}).get("raw")
    current_price = financial.get("currentPrice", {}).get("raw")
    num_analysts = financial.get("numberOfAnalystOpinions", {}).get("raw")
    recommendation = financial.get("recommendationKey")
    recommendation_mean = financial.get("recommendationMean", {}).get("raw")

    # Calculate upside/downside
    upside_pct = None
    if current_price and target_mean:
        upside_pct = round(((target_mean - current_price) / current_price) * 100, 2)

    # Recent upgrades/downgrades
    history = result.get("upgradeDowngradeHistory", {}).get("history", [])
    recent_changes = []
    for h in history[:10]:  # Last 10 changes
        recent_changes.append({
            "firm": h.get("firm"),
            "to_grade": h.get("toGrade"),
            "from_grade": h.get("fromGrade"),
            "action": h.get("action"),
            "date": h.get("epochGradeDate"),
        })

    return {
        "ticker": ticker.upper(),
        "recommendation": {
            "key": recommendation,
            "mean_score": recommendation_mean,  # 1=Strong Buy, 5=Strong Sell
            "num_analysts": num_analysts,
        },
        "current_ratings": current_ratings,
        "price_targets": {
            "current_price": current_price,
            "target_high": target_high,
            "target_low": target_low,
            "target_mean": target_mean,
            "target_median": target_median,
            "upside_percent": upside_pct,
        },
        "recent_changes": recent_changes,
    }
