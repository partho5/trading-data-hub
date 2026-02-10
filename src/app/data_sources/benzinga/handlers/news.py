"""Handler for Benzinga news data."""

import logging
import os
from typing import Any

from ....services.http_client import HttpClient

logger = logging.getLogger("data_aggregator")

BENZINGA_NEWS_URL = "https://api.benzinga.com/api/v2/news"


async def fetch_news(ticker: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch news for a ticker from Benzinga.

    Args:
        ticker: Stock symbol (e.g., 'AAPL') or 'all' for general market news
        params: Optional parameters:
            - limit: Number of articles (default: 20, max: 100)
            - page: Page number (default: 0)
            - date_from: Start date (YYYY-MM-DD)
            - date_to: End date (YYYY-MM-DD)

    Returns:
        Dict with news articles
    """
    api_key = os.getenv("BENZINGA_API_KEY")
    if not api_key:
        raise ValueError("BENZINGA_API_KEY not configured")

    client = HttpClient(use_proxy=False)

    query_params = {
        "token": api_key,
        "displayOutput": "full",
        "pageSize": params.get("limit", 20),
        "page": params.get("page", 0),
    }

    # Add ticker filter if not 'all'
    if ticker.lower() != "all":
        query_params["tickers"] = ticker.upper()

    # Add date filters if provided
    if "date_from" in params:
        query_params["dateFrom"] = params["date_from"]
    if "date_to" in params:
        query_params["dateTo"] = params["date_to"]

    try:
        response = await client.get(BENZINGA_NEWS_URL, params=query_params)
        data = response.json()

        # Transform response to normalized format
        articles = []
        for item in data:
            articles.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "teaser": item.get("teaser"),
                "body": item.get("body"),
                "url": item.get("url"),
                "image": item.get("image", [{}])[0].get("url") if item.get("image") else None,
                "published": item.get("created"),
                "updated": item.get("updated"),
                "author": item.get("author"),
                "channels": item.get("channels", []),
                "stocks": item.get("stocks", []),
                "tags": item.get("tags", []),
            })

        return {
            "ticker": ticker if ticker.lower() != "all" else "market",
            "count": len(articles),
            "articles": articles,
        }

    except Exception as e:
        logger.error(f"Benzinga news API error for {ticker}: {e}")
        raise ValueError(f"Failed to fetch news: {str(e)}")
