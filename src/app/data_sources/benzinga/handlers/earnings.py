"""Handler for Benzinga earnings calendar data."""

import logging
import os
from typing import Any
from datetime import datetime, timedelta

from ....services.http_client import HttpClient

logger = logging.getLogger("data_aggregator")

BENZINGA_EARNINGS_URL = "https://api.benzinga.com/api/v2.1/calendar/earnings"


async def fetch_earnings(ticker: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch earnings calendar for a ticker from Benzinga.

    Args:
        ticker: Stock symbol (e.g., 'AAPL') or 'all' for all earnings
        params: Optional parameters:
            - limit: Number of earnings (default: 20, max: 100)
            - page: Page number (default: 0)
            - date_from: Start date (YYYY-MM-DD, default: today)
            - date_to: End date (YYYY-MM-DD, default: 7 days from now)
            - importance: Filter by importance (0-5)

    Returns:
        Dict with earnings calendar events
    """
    api_key = os.getenv("BENZINGA_API_KEY")
    if not api_key:
        raise ValueError("BENZINGA_API_KEY not configured")

    client = HttpClient(use_proxy=False)

    headers = {
        "Accept": "application/json",
    }

    # Default date range: today to 7 days from now
    today = datetime.now().strftime("%Y-%m-%d")
    week_later = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    query_params = {
        "token": api_key,
        "pageSize": params.get("limit", 20),
        "page": params.get("page", 0),
        "parameters[date_from]": params.get("date_from", today),
        "parameters[date_to]": params.get("date_to", week_later),
    }

    # Add ticker filter if not 'all'
    if ticker.lower() != "all":
        query_params["parameters[tickers]"] = ticker.upper()

    # Add importance filter if provided
    if "importance" in params:
        query_params["parameters[importance]"] = params["importance"]

    try:
        response = await client.get(BENZINGA_EARNINGS_URL, headers=headers, params=query_params)
        data = response.json()

        # API returns list directly or dict with "earnings" key
        items = data if isinstance(data, list) else data.get("earnings", [])

        # Transform response to normalized format
        earnings = []
        for item in items:
            earnings.append({
                "id": item.get("id"),
                "date": item.get("date"),
                "time": item.get("time"),
                "ticker": item.get("ticker"),
                "exchange": item.get("exchange"),
                "company": item.get("name"),
                "period": item.get("period"),
                "period_year": item.get("period_year"),
                "eps_estimate": item.get("eps_est"),
                "eps_actual": item.get("eps"),
                "eps_prior": item.get("eps_prior"),
                "eps_surprise": item.get("eps_surprise"),
                "eps_surprise_percent": item.get("eps_surprise_percent"),
                "revenue_estimate": item.get("revenue_est"),
                "revenue_actual": item.get("revenue"),
                "revenue_prior": item.get("revenue_prior"),
                "revenue_surprise": item.get("revenue_surprise"),
                "revenue_surprise_percent": item.get("revenue_surprise_percent"),
                "importance": item.get("importance"),  # 0-5 scale
                "updated": item.get("updated"),
            })

        # Sort by date/time (chronological)
        earnings.sort(key=lambda x: (x["date"], x["time"] or ""))

        return {
            "ticker": ticker if ticker.lower() != "all" else "market",
            "count": len(earnings),
            "date_range": {
                "from": query_params["parameters[date_from]"],
                "to": query_params["parameters[date_to]"],
            },
            "earnings": earnings,
        }

    except Exception as e:
        logger.error(f"Benzinga earnings API error for {ticker}: {e}")
        raise ValueError(f"Failed to fetch earnings: {str(e)}")
