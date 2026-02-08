# src/app/data_sources/alpha_vantage/handlers/vix.py
"""Handler for VIX proxy data using VIXY ETF (free Alpha Vantage endpoint)."""

import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.app.services import HttpClient

# Load .env file
env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"
load_dotenv(env_path)

logger = logging.getLogger("data_aggregator")

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"


async def fetch_vix(ticker: str, params: dict[str, Any], request=None) -> dict[str, Any]:
    """
    Fetch VIX proxy data via VIXY ETF using GLOBAL_QUOTE (free tier).

    VIXY (ProShares VIX Short-Term Futures ETF) tracks VIX futures
    and is available on Alpha Vantage free tier unlike the VIX index itself.

    Args:
        ticker: Not used (VIXY is fixed)
        params: Not used

    Returns:
        Dict with VIX proxy data and sentiment interpretation
    """
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")

    query_params = {
        "function": "GLOBAL_QUOTE",
        "symbol": "VIXY",
        "apikey": api_key,
    }

    client = HttpClient(use_proxy=True)
    response = await client.get(ALPHA_VANTAGE_URL, params=query_params)
    data = response.json()

    # Check for error / rate limit
    if "Error Message" in data:
        raise ValueError(data["Error Message"])
    if "Note" in data or "Information" in data:
        raise ValueError(data.get("Note") or data.get("Information", "API limit reached"))

    quote = data.get("Global Quote", {})
    if not quote:
        raise ValueError("No quote data returned")

    price = float(quote.get("05. price", 0))
    change = float(quote.get("09. change", 0))
    change_pct_str = quote.get("10. change percent", "0%").rstrip("%")
    change_pct = float(change_pct_str) if change_pct_str else 0
    prev_close = float(quote.get("08. previous close", 0))
    high = float(quote.get("03. high", 0))
    low = float(quote.get("04. low", 0))
    open_price = float(quote.get("02. open", 0))
    volume = int(quote.get("06. volume", 0))
    trading_day = quote.get("07. latest trading day", "")

    # VIXY sentiment interpretation (VIXY price roughly tracks VIX level)
    if price < 15:
        sentiment = "Extreme Complacency"
    elif price < 25:
        sentiment = "Low Fear"
    elif price < 35:
        sentiment = "Moderate Fear"
    elif price < 50:
        sentiment = "High Fear"
    else:
        sentiment = "Extreme Fear"

    return {
        "symbol": "VIXY",
        "name": "ProShares VIX Short-Term Futures ETF (VIX Proxy)",
        "date": trading_day,
        "current": price,
        "open": open_price,
        "high": high,
        "low": low,
        "previous_close": prev_close,
        "change": round(change, 2),
        "change_percent": round(change_pct, 2),
        "volume": volume,
        "sentiment": sentiment,
    }
