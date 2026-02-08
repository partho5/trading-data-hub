# src/app/data_sources/yahoo_finance/handlers/earnings.py
"""Handler for Yahoo Finance earnings data."""

import logging
from typing import Any

import httpx

from .auth import get_yahoo_crumb, clear_crumb_cache

logger = logging.getLogger("data_aggregator")

YAHOO_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"


async def fetch_earnings(ticker: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch earnings calendar and history data.

    Args:
        ticker: Stock symbol (e.g., 'AAPL')
        params: Not used

    Returns:
        Dict with earnings data including next date, estimates, history
    """
    # Get crumb and cookies for authentication
    crumb, cookies = await get_yahoo_crumb()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    url = YAHOO_SUMMARY_URL.format(ticker=ticker.upper())

    query_params = {
        "modules": "calendarEvents,earningsHistory,earningsTrend",
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
        raise ValueError(error.get("description", f"No earnings data for {ticker}"))

    result = results[0]

    # Calendar events (next earnings date)
    calendar = result.get("calendarEvents", {})
    earnings_info = calendar.get("earnings", {})

    next_earnings_date = None
    earnings_dates = earnings_info.get("earningsDate", [])
    if earnings_dates:
        next_earnings_date = earnings_dates[0].get("raw")

    # Earnings estimates
    eps_estimate = earnings_info.get("earningsAverage", {}).get("raw")
    eps_low = earnings_info.get("earningsLow", {}).get("raw")
    eps_high = earnings_info.get("earningsHigh", {}).get("raw")
    revenue_estimate = earnings_info.get("revenueAverage", {}).get("raw")

    # Earnings history (last 4 quarters)
    history = result.get("earningsHistory", {}).get("history", [])
    earnings_history = []
    for h in history[-4:]:
        earnings_history.append({
            "quarter": h.get("quarter", {}).get("fmt"),
            "date": h.get("quarterDate", {}).get("fmt"),
            "eps_estimate": h.get("epsEstimate", {}).get("raw"),
            "eps_actual": h.get("epsActual", {}).get("raw"),
            "surprise": h.get("epsDifference", {}).get("raw"),
            "surprise_percent": h.get("surprisePercent", {}).get("raw"),
        })

    # Earnings trend (current/next quarter estimates)
    trend = result.get("earningsTrend", {}).get("trend", [])
    current_estimate = None
    next_estimate = None
    for t in trend:
        period = t.get("period")
        if period == "0q":
            current_estimate = {
                "period": t.get("endDate"),
                "eps_estimate": t.get("earningsEstimate", {}).get("avg", {}).get("raw"),
                "revenue_estimate": t.get("revenueEstimate", {}).get("avg", {}).get("raw"),
                "num_analysts": t.get("earningsEstimate", {}).get("numberOfAnalysts", {}).get("raw"),
            }
        elif period == "+1q":
            next_estimate = {
                "period": t.get("endDate"),
                "eps_estimate": t.get("earningsEstimate", {}).get("avg", {}).get("raw"),
                "revenue_estimate": t.get("revenueEstimate", {}).get("avg", {}).get("raw"),
                "num_analysts": t.get("earningsEstimate", {}).get("numberOfAnalysts", {}).get("raw"),
            }

    return {
        "ticker": ticker.upper(),
        "next_earnings_date": next_earnings_date,
        "estimates": {
            "eps_average": eps_estimate,
            "eps_low": eps_low,
            "eps_high": eps_high,
            "revenue_average": revenue_estimate,
        },
        "current_quarter": current_estimate,
        "next_quarter": next_estimate,
        "history": earnings_history,
    }
