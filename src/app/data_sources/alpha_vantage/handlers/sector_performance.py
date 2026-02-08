# src/app/data_sources/alpha_vantage/handlers/sector_performance.py
"""Handler for sector ETF performance using Alpha Vantage GLOBAL_QUOTE (free tier)."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.app.services import HttpClient, chart_service

# Load .env file
env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"
load_dotenv(env_path)

logger = logging.getLogger("data_aggregator")

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"

# Major sector ETFs
SECTOR_ETFS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLV": "Healthcare",
    "XLE": "Energy",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
}


async def _fetch_etf_quote(
    client: HttpClient, symbol: str, sector_name: str, api_key: str
) -> dict[str, Any] | None:
    """Fetch a single ETF quote from Alpha Vantage GLOBAL_QUOTE (free tier)."""
    try:
        response = await client.get(
            ALPHA_VANTAGE_URL,
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": api_key,
            },
        )
        data = response.json()

        # Rate limit or error
        if "Note" in data or "Information" in data:
            msg = data.get("Note") or data.get("Information", "")
            logger.warning(f"AV rate limit for {symbol}: {msg[:80]}")
            return None

        quote = data.get("Global Quote", {})
        if not quote:
            return None

        price = float(quote.get("05. price", 0))
        change = float(quote.get("09. change", 0))
        change_pct = float(quote.get("10. change percent", "0%").rstrip("%") or 0)

        return {
            "symbol": symbol,
            "sector": sector_name,
            "price": price,
            "change": change,
            "change_percent": change_pct,
            "day_high": float(quote.get("03. high", 0)),
            "day_low": float(quote.get("04. low", 0)),
            "volume": int(quote.get("06. volume", 0)),
        }

    except Exception as e:
        logger.warning(f"Failed to fetch {symbol}: {e}")
    return None


async def fetch_sector_performance(ticker: str, params: dict[str, Any], request=None) -> dict[str, Any]:
    """
    Fetch sector ETF performance via Alpha Vantage GLOBAL_QUOTE (free tier).

    Each sector ETF is queried with a 1.2s delay to respect rate limits
    (free tier: 5 calls/min, 25/day).

    Args:
        ticker: Not used (all sectors)
        params: Optional parameters including 'chart': bool
        request: FastAPI Request object (for URL generation)

    Returns:
        Dict with sector performance data
    """
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")

    sectors = []
    client = HttpClient(use_proxy=True)

    for symbol, sector_name in SECTOR_ETFS.items():
        result = await _fetch_etf_quote(client, symbol, sector_name, api_key)
        if result:
            sectors.append(result)
        # 1.2s between calls to stay under 5 req/min on free tier
        await asyncio.sleep(1.2)

    # Sort by performance
    sectors.sort(key=lambda x: x.get("change_percent", 0), reverse=True)

    leaders = sectors[:3] if len(sectors) >= 3 else sectors
    laggards = sectors[-3:] if len(sectors) >= 3 else []

    result = {
        "count": len(sectors),
        "sectors": sectors,
        "leaders": leaders,
        "laggards": laggards,
    }

    # Chart generation if requested
    if params and params.get("chart") is True and sectors and request:
        try:
            # Transform to chart data format
            chart_data = [
                {
                    "label": s["sector"],
                    "value": s["change_percent"],
                }
                for s in sectors
            ]

            # Generate chart
            filename = await chart_service.generate_bar_chart(
                data=chart_data,
                chart_type="sector",
                title="Sector Performance",
                subtitle="Today's % Change by Sector ETF",
            )

            # Build public URL
            base_url = str(request.base_url).rstrip("/")
            chart_url = f"{base_url}/static/charts/{filename}"

            result["graphics"] = chart_url
            logger.info(f"Generated sector chart: {chart_url}")
        except Exception as e:
            logger.error(f"Sector chart generation failed: {e}")
            result["graphics"] = None

    return result
