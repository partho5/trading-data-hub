"""Handler for Benzinga analyst ratings data."""

import logging
import os
from typing import Any

from ....services.http_client import HttpClient

logger = logging.getLogger("data_aggregator")

BENZINGA_RATINGS_URL = "https://api.benzinga.com/api/v2.1/calendar/ratings"


async def fetch_ratings(ticker: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch analyst ratings for a ticker from Benzinga.

    Args:
        ticker: Stock symbol (e.g., 'AAPL') or 'all' for all ratings
        params: Optional parameters:
            - limit: Number of ratings (default: 20, max: 100)
            - page: Page number (default: 0)
            - date_from: Start date (YYYY-MM-DD)
            - date_to: End date (YYYY-MM-DD)
            - action: Filter by action (Upgrades, Downgrades, Initiates, Reiterates, Maintains)

    Returns:
        Dict with analyst ratings
    """
    api_key = os.getenv("BENZINGA_API_KEY")
    if not api_key:
        raise ValueError("BENZINGA_API_KEY not configured")

    client = HttpClient(use_proxy=False)

    query_params = {
        "token": api_key,
        "pageSize": params.get("limit", 20),
        "page": params.get("page", 0),
    }

    # Add ticker filter if not 'all'
    if ticker.lower() != "all":
        query_params["parameters[tickers]"] = ticker.upper()

    # Add date filters if provided
    if "date_from" in params:
        query_params["parameters[date_from]"] = params["date_from"]
    if "date_to" in params:
        query_params["parameters[date_to]"] = params["date_to"]

    # Add action filter if provided
    if "action" in params:
        query_params["parameters[action]"] = params["action"]

    try:
        response = await client.get(BENZINGA_RATINGS_URL, params=query_params)
        data = response.json()

        # Transform response to normalized format
        ratings = []
        for item in data.get("ratings", []):
            ratings.append({
                "id": item.get("id"),
                "date": item.get("date"),
                "time": item.get("time"),
                "ticker": item.get("ticker"),
                "exchange": item.get("exchange"),
                "company": item.get("name"),
                "analyst": item.get("analyst"),
                "analyst_firm": item.get("analyst_name"),
                "action": item.get("action"),  # Upgrades, Downgrades, etc.
                "rating_current": item.get("rating_current"),
                "rating_prior": item.get("rating_prior"),
                "price_target_current": item.get("pt_current"),
                "price_target_prior": item.get("pt_prior"),
                "url": item.get("url"),
                "importance": item.get("importance"),  # 0-5 scale
            })

        # Sort by date/time (most recent first)
        ratings.sort(key=lambda x: (x["date"], x["time"]), reverse=True)

        return {
            "ticker": ticker if ticker.lower() != "all" else "market",
            "count": len(ratings),
            "ratings": ratings,
        }

    except Exception as e:
        logger.error(f"Benzinga ratings API error for {ticker}: {e}")
        raise ValueError(f"Failed to fetch ratings: {str(e)}")
