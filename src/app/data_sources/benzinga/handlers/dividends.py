"""Handler for Benzinga dividends data."""

import logging
import os
from datetime import datetime, timedelta
from typing import Any

from ....services.http_client import HttpClient

logger = logging.getLogger("data_aggregator")

BENZINGA_DIVIDENDS_URL = "https://api.benzinga.com/api/v2.1/calendar/dividends"


async def fetch_dividends(ticker: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch dividend announcements from Benzinga.

    Args:
        ticker: Stock symbol (e.g., 'AAPL') or 'all' for all dividends
        params: Optional parameters:
            - limit: Number of dividends (default: 20, max: 100)
            - page: Page number (default: 0)
            - date_from: Start date (YYYY-MM-DD)
            - date_to: End date (YYYY-MM-DD)
            - importance: Filter by importance (0-5)

    Returns:
        Dict with dividend data
    """
    api_key = os.getenv("BENZINGA_API_KEY")
    if not api_key:
        raise ValueError("BENZINGA_API_KEY not configured")

    client = HttpClient(use_proxy=False)

    headers = {
        "Accept": "application/json",
    }

    # Default date range: today to 30 days from now
    today = datetime.now().strftime("%Y-%m-%d")
    month_later = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    query_params = {
        "token": api_key,
        "pageSize": params.get("limit", 20),
        "page": params.get("page", 0),
        "parameters[date_from]": params.get("date_from", today),
        "parameters[date_to]": params.get("date_to", month_later),
    }

    # Add ticker filter if not 'all'
    if ticker.lower() != "all":
        query_params["parameters[tickers]"] = ticker.upper()

    # Add importance filter if provided
    if "importance" in params:
        query_params["parameters[importance]"] = params["importance"]

    try:
        response = await client.get(BENZINGA_DIVIDENDS_URL, headers=headers, params=query_params)
        data = response.json()

        # API returns list directly or dict with "dividends" key
        items = data if isinstance(data, list) else data.get("dividends", [])

        # Transform response to normalized format
        dividends = []
        for item in items:
            dividends.append({
                "id": item.get("id"),
                "date": item.get("date"),
                "ticker": item.get("ticker"),
                "exchange": item.get("exchange"),
                "company": item.get("name"),
                "dividend": item.get("dividend"),
                "dividend_prior": item.get("dividend_prior"),
                "dividend_type": item.get("dividend_type"),
                "dividend_yield": item.get("dividend_yield"),
                "ex_dividend_date": item.get("ex_dividend_date"),
                "payable_date": item.get("payable_date"),
                "record_date": item.get("record_date"),
                "frequency": item.get("frequency"),
                "importance": item.get("importance"),
                "updated": item.get("updated"),
            })

        # Sort by date (most recent first)
        dividends.sort(key=lambda x: x["date"], reverse=True)

        return {
            "ticker": ticker if ticker.lower() != "all" else "market",
            "count": len(dividends),
            "date_range": {
                "from": query_params["parameters[date_from]"],
                "to": query_params["parameters[date_to]"],
            },
            "dividends": dividends,
        }

    except Exception as e:
        logger.error(f"Benzinga dividends API error for {ticker}: {e}")
        raise ValueError(f"Failed to fetch dividends: {str(e)}")
