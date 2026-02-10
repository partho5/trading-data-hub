"""Handler for Benzinga IPO calendar data."""

import logging
import os
from datetime import datetime, timedelta
from typing import Any

from ....services.http_client import HttpClient

logger = logging.getLogger("data_aggregator")

BENZINGA_IPOS_URL = "https://api.benzinga.com/api/v2.1/calendar/ipos"


async def fetch_ipos(ticker: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch IPO calendar from Benzinga.

    Args:
        ticker: Stock symbol (e.g., 'ABNB') or 'all' for all IPOs
        params: Optional parameters:
            - limit: Number of IPOs (default: 20, max: 100)
            - page: Page number (default: 0)
            - date_from: Start date (YYYY-MM-DD)
            - date_to: End date (YYYY-MM-DD)
            - importance: Filter by importance (0-5)

    Returns:
        Dict with IPO data
    """
    api_key = os.getenv("BENZINGA_API_KEY")
    if not api_key:
        raise ValueError("BENZINGA_API_KEY not configured")

    client = HttpClient(use_proxy=False)

    headers = {
        "Accept": "application/json",
    }

    # Default date range: today to 90 days from now
    today = datetime.now().strftime("%Y-%m-%d")
    three_months_later = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

    query_params = {
        "token": api_key,
        "pageSize": params.get("limit", 20),
        "page": params.get("page", 0),
        "parameters[date_from]": params.get("date_from", today),
        "parameters[date_to]": params.get("date_to", three_months_later),
    }

    # Add ticker filter if not 'all'
    if ticker.lower() != "all":
        query_params["parameters[tickers]"] = ticker.upper()

    # Add importance filter if provided
    if "importance" in params:
        query_params["parameters[importance]"] = params["importance"]

    try:
        response = await client.get(BENZINGA_IPOS_URL, headers=headers, params=query_params)
        data = response.json()

        # API returns list directly or dict with "ipos" key
        items = data if isinstance(data, list) else data.get("ipos", [])

        # Transform response to normalized format
        ipos = []
        for item in items:
            ipos.append({
                "id": item.get("id"),
                "date": item.get("date"),
                "ticker": item.get("ticker"),
                "exchange": item.get("exchange"),
                "company": item.get("name"),
                "price": item.get("price"),
                "price_min": item.get("price_min"),
                "price_max": item.get("price_max"),
                "deal_status": item.get("deal_status"),
                "insider_lockup_days": item.get("insider_lockup_days"),
                "insider_lockup_date": item.get("insider_lockup_date"),
                "offering_value": item.get("offering_value"),
                "offering_shares": item.get("offering_shares"),
                "lead_underwriters": item.get("lead_underwriters"),
                "underwriter_quiet_expiration_days": item.get("underwriter_quiet_expiration_days"),
                "underwriter_quiet_expiration_date": item.get("underwriter_quiet_expiration_date"),
                "importance": item.get("importance"),
                "updated": item.get("updated"),
            })

        # Sort by date (most recent first)
        ipos.sort(key=lambda x: x["date"], reverse=True)

        return {
            "ticker": ticker if ticker.lower() != "all" else "market",
            "count": len(ipos),
            "date_range": {
                "from": query_params["parameters[date_from]"],
                "to": query_params["parameters[date_to]"],
            },
            "ipos": ipos,
        }

    except Exception as e:
        logger.error(f"Benzinga IPOs API error for {ticker}: {e}")
        raise ValueError(f"Failed to fetch IPOs: {str(e)}")
