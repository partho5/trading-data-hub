# src/app/data_sources/alpha_vantage/handlers/economic_calendar.py
"""Handler for market calendar data using Alpha Vantage free endpoints.

Uses EARNINGS_CALENDAR and IPO_CALENDAR (both free, return CSV).
"""

import csv
import io
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.app.services import HttpClient

# Load .env file
env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"
load_dotenv(env_path)

logger = logging.getLogger("data_aggregator")

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"


def _parse_csv(text: str) -> list[dict[str, str]]:
    """Parse CSV text into list of dicts."""
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


async def fetch_economic_calendar(ticker: str, params: dict[str, Any], request=None) -> dict[str, Any]:
    """
    Fetch upcoming market events (earnings + IPOs) from Alpha Vantage free tier.

    Both EARNINGS_CALENDAR and IPO_CALENDAR are free endpoints
    that return CSV data.

    Args:
        ticker: Not used (market-wide data)
        params: Optional params:
            - horizon: '1month' or '3month' (default '1month') for earnings

    Returns:
        Dict with upcoming earnings and IPO events
    """
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
    horizon = params.get("horizon", "1month")

    earnings = []
    ipos = []
    errors = []

    client = HttpClient(use_proxy=True)

    # Fetch earnings calendar (CSV)
    try:
        resp = await client.get(
            ALPHA_VANTAGE_URL,
            params={
                "function": "EARNINGS_CALENDAR",
                "horizon": horizon,
                "apikey": api_key,
            },
        )
        text = resp.text.strip()
        if text and not text.startswith("{"):
            rows = _parse_csv(text)
            today = datetime.now().strftime("%Y-%m-%d")
            for row in rows:
                report_date = row.get("reportDate", "")
                if report_date >= today:
                    earnings.append({
                        "date": report_date,
                        "symbol": row.get("symbol", ""),
                        "name": row.get("name", ""),
                        "estimate": row.get("estimate", ""),
                        "currency": row.get("currency", ""),
                    })
        elif text.startswith("{"):
            errors.append("Earnings calendar: rate limited or error")
    except Exception as e:
        logger.warning(f"Earnings calendar fetch failed: {e}")
        errors.append(f"Earnings calendar: {e}")

    # Fetch IPO calendar (CSV)
    try:
        resp = await client.get(
            ALPHA_VANTAGE_URL,
            params={
                "function": "IPO_CALENDAR",
                "apikey": api_key,
            },
        )
        text = resp.text.strip()
        if text and not text.startswith("{"):
            rows = _parse_csv(text)
            today = datetime.now().strftime("%Y-%m-%d")
            for row in rows:
                ipo_date = row.get("ipoDate", "")
                if ipo_date >= today:
                    ipos.append({
                        "date": ipo_date,
                        "symbol": row.get("symbol", ""),
                        "name": row.get("name", ""),
                        "exchange": row.get("exchange", ""),
                        "price_range_low": row.get("priceRangeLow", ""),
                        "price_range_high": row.get("priceRangeHigh", ""),
                        "currency": row.get("currency", ""),
                    })
        elif text.startswith("{"):
            errors.append("IPO calendar: rate limited or error")
    except Exception as e:
        logger.warning(f"IPO calendar fetch failed: {e}")
        errors.append(f"IPO calendar: {e}")

    # Limit results
    earnings = earnings[:50]
    ipos = ipos[:30]

    # Group earnings by date
    earnings_by_date: dict[str, list] = {}
    for e in earnings:
        date = e.get("date", "unknown")
        if date not in earnings_by_date:
            earnings_by_date[date] = []
        earnings_by_date[date].append(e)

    return {
        "horizon": horizon,
        "earnings_count": len(earnings),
        "ipo_count": len(ipos),
        "upcoming_earnings": earnings[:20],
        "earnings_by_date": earnings_by_date,
        "upcoming_ipos": ipos[:15],
        "errors": errors if errors else None,
    }
