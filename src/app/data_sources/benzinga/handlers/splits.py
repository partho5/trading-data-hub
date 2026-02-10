"""Handler for Benzinga stock splits data."""

import logging
import os
from datetime import datetime, timedelta
from typing import Any

from ....services.http_client import HttpClient

logger = logging.getLogger("data_aggregator")

BENZINGA_SPLITS_URL = "https://api.benzinga.com/api/v2.1/calendar/splits"


async def fetch_splits(ticker: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch stock split announcements from Benzinga.

    Args:
        ticker: Stock symbol (e.g., 'AAPL') or 'all' for all splits
        params: Optional parameters:
            - limit: Number of splits (default: 20, max: 100)
            - page: Page number (default: 0)
            - date_from: Start date (YYYY-MM-DD)
            - date_to: End date (YYYY-MM-DD)
            - importance: Filter by importance (0-5)

    Returns:
        Dict with stock split data
    """
    api_key = os.getenv("BENZINGA_API_KEY")
    if not api_key:
        raise ValueError("BENZINGA_API_KEY not configured")

    client = HttpClient(use_proxy=False)

    headers = {
        "Accept": "application/json",
    }

    # Default date range: today to 60 days from now
    today = datetime.now().strftime("%Y-%m-%d")
    two_months_later = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")

    query_params = {
        "token": api_key,
        "pageSize": params.get("limit", 20),
        "page": params.get("page", 0),
        "parameters[date_from]": params.get("date_from", today),
        "parameters[date_to]": params.get("date_to", two_months_later),
    }

    # Add ticker filter if not 'all'
    if ticker.lower() != "all":
        query_params["parameters[tickers]"] = ticker.upper()

    # Add importance filter if provided
    if "importance" in params:
        query_params["parameters[importance]"] = params["importance"]

    try:
        response = await client.get(BENZINGA_SPLITS_URL, headers=headers, params=query_params)
        data = response.json()

        # API returns list directly or dict with "splits" key
        items = data if isinstance(data, list) else data.get("splits", [])

        # Transform response to normalized format
        splits = []
        for item in items:
            splits.append({
                "id": item.get("id"),
                "date": item.get("date"),
                "ticker": item.get("ticker"),
                "exchange": item.get("exchange"),
                "company": item.get("name"),
                "ratio": item.get("ratio"),
                "optionable": item.get("optionable"),
                "type": item.get("type"),  # Forward, Reverse
                "importance": item.get("importance"),
                "updated": item.get("updated"),
            })

        # Sort by date (most recent first)
        splits.sort(key=lambda x: x["date"], reverse=True)

        return {
            "ticker": ticker if ticker.lower() != "all" else "market",
            "count": len(splits),
            "date_range": {
                "from": query_params["parameters[date_from]"],
                "to": query_params["parameters[date_to]"],
            },
            "splits": splits,
        }

    except Exception as e:
        logger.error(f"Benzinga splits API error for {ticker}: {e}")
        raise ValueError(f"Failed to fetch splits: {str(e)}")
