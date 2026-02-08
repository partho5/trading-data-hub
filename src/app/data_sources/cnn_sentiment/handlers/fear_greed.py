# src/app/data_sources/cnn_sentiment/handlers/fear_greed.py
"""Handler for CNN Fear & Greed Index via their dataviz API."""

import logging
from typing import Any

from src.app.services import HttpClient, chart_service

logger = logging.getLogger("data_aggregator")

CNN_FEAR_GREED_API = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

# These headers are required — without Referer/Origin, CNN returns 418 "I'm a teapot"
CNN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://edition.cnn.com/markets/fear-and-greed",
    "Origin": "https://edition.cnn.com",
    "Accept-Language": "en-US,en;q=0.9",
}

# Mapping of CNN's internal indicator keys to human-readable names
INDICATOR_NAMES = {
    "market_momentum_sp500": "Market Momentum (S&P 500)",
    "market_momentum_sp125": "Market Momentum (S&P 125-day)",
    "stock_price_strength": "Stock Price Strength",
    "stock_price_breadth": "Stock Price Breadth",
    "put_call_options": "Put/Call Options",
    "market_volatility_vix": "Market Volatility (VIX)",
    "market_volatility_vix_50": "Market Volatility (VIX 50-day)",
    "safe_haven_demand": "Safe Haven Demand",
    "junk_bond_demand": "Junk Bond Demand",
}


async def fetch_fear_greed(
    ticker: str, params: dict[str, Any], request=None
) -> dict[str, Any]:
    """
    Fetch CNN Fear & Greed Index from their dataviz JSON API.

    Args:
        ticker: Not used (market-wide data)
        params: Optional parameters including 'chart': bool
        request: FastAPI Request object (for URL generation)

    Returns:
        Dict with fear & greed score, rating, sub-indicators, history, and optional graphics URL
    """
    client = HttpClient(use_proxy=True, timeout=30)
    response = await client.get(CNN_FEAR_GREED_API, headers=CNN_HEADERS)
    data = response.json()

    # Main score
    fg = data.get("fear_and_greed", {})
    score = fg.get("score")
    rating = fg.get("rating")
    timestamp = fg.get("timestamp")

    # Score comparisons
    comparisons = {}
    if fg.get("previous_close") is not None:
        comparisons["previous_close"] = round(fg["previous_close"], 1)
    if fg.get("previous_1_week") is not None:
        comparisons["1_week_ago"] = round(fg["previous_1_week"], 1)
    if fg.get("previous_1_month") is not None:
        comparisons["1_month_ago"] = round(fg["previous_1_month"], 1)
    if fg.get("previous_1_year") is not None:
        comparisons["1_year_ago"] = round(fg["previous_1_year"], 1)

    # Sub-indicators
    indicators = []
    for key, display_name in INDICATOR_NAMES.items():
        indicator_data = data.get(key)
        if indicator_data and isinstance(indicator_data, dict):
            indicators.append({
                "name": display_name,
                "score": round(indicator_data.get("score", 0), 1),
                "rating": indicator_data.get("rating", ""),
            })

    # Build base response
    result = {
        "score": round(score, 1) if score is not None else None,
        "rating": rating.title() if rating else None,
        "timestamp": timestamp,
        "comparisons": comparisons,
        "indicators": indicators if indicators else None,
        "source": "CNN Fear & Greed Index",
        "note": "0=Extreme Fear, 100=Extreme Greed",
    }

    # Chart generation if requested
    if params and params.get("chart") is True:
        historical = data.get("fear_and_greed_historical", {})
        historical_data = historical.get("data", [])

        if historical_data and request:
            try:
                # Generate chart
                filename = await chart_service.generate_fear_greed_chart(historical_data)

                # Build public URL
                base_url = str(request.base_url).rstrip("/")
                chart_url = f"{base_url}/static/charts/{filename}"

                result["graphics"] = chart_url
                logger.info(f"Generated chart: {chart_url}")
            except Exception as e:
                logger.error(f"Chart generation failed: {e}")
                result["graphics"] = None
        else:
            if not historical_data:
                logger.warning("Chart requested but no historical data available")
            if not request:
                logger.warning("Chart requested but no request context provided")

    return result
