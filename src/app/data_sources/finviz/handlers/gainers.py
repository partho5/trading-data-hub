# src/app/data_sources/finviz/handlers/gainers.py
"""Handler for Finviz top gainers."""

import logging
from typing import Any

from bs4 import BeautifulSoup

from src.app.services import HttpClient, chart_service

logger = logging.getLogger("data_aggregator")

FINVIZ_SCREENER_URL = "https://finviz.com/screener.ashx"


async def fetch_gainers(ticker: str, params: dict[str, Any], request=None) -> dict[str, Any]:
    """
    Fetch top gaining stocks from Finviz.

    Args:
        ticker: Not used (market-wide data)
        params: Optional params:
            - limit: Number of results (default 20)
            - chart: Generate chart if True
        request: FastAPI Request object (for URL generation)

    Returns:
        Dict with list of top gainers
    """
    limit = params.get("limit", 20)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # Finviz screener sorted by change descending
    query_params = {
        "v": "111",  # Overview view
        "s": "ta_topgainers",  # Top gainers signal
        "f": "sh_avgvol_o500",  # Avg volume > 500K for liquidity
        "o": "-change",  # Sort by change descending
    }

    client = HttpClient(use_proxy=True)
    response = await client.get(
        FINVIZ_SCREENER_URL, headers=headers, params=query_params
    )

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the screener results table
    table = soup.find("table", {"class": "styled-table-new"})
    if not table:
        # Try alternate table class
        table = soup.find("table", {"id": "screener-table"})

    gainers = []

    if table:
        rows = table.find_all("tr")[1:]  # Skip header

        for row in rows[:limit]:
            cells = row.find_all("td")
            if len(cells) >= 10:
                ticker_cell = cells[1].find("a")
                ticker_symbol = ticker_cell.text.strip() if ticker_cell else ""

                company = cells[2].text.strip() if len(cells) > 2 else ""
                sector = cells[3].text.strip() if len(cells) > 3 else ""
                price = cells[8].text.strip() if len(cells) > 8 else ""
                change = cells[9].text.strip() if len(cells) > 9 else ""
                volume = cells[10].text.strip() if len(cells) > 10 else ""

                if ticker_symbol:
                    gainers.append({
                        "ticker": ticker_symbol,
                        "company": company,
                        "sector": sector,
                        "price": price,
                        "change": change,
                        "volume": volume,
                    })

    result = {
        "type": "gainers",
        "count": len(gainers),
        "data": gainers,
    }

    # Chart generation if requested
    if params and params.get("chart") is True and gainers and request:
        try:
            # Transform to chart data format (top 10)
            chart_data = []
            for g in gainers[:10]:
                # Parse change string (e.g., "+12.5%")
                change_str = g["change"].replace("%", "").replace("+", "")
                try:
                    change_val = float(change_str)
                except ValueError:
                    continue

                chart_data.append({
                    "label": f"{g['ticker']} ({g['company'][:15]}...)" if len(g['company']) > 15 else f"{g['ticker']} ({g['company']})",
                    "value": change_val,
                })

            if chart_data:
                # Generate chart
                filename = await chart_service.generate_bar_chart(
                    data=chart_data,
                    chart_type="gainers",
                    title="Top Stock Gainers",
                    subtitle="Today's Biggest % Movers",
                )

                # Build public URL
                base_url = str(request.base_url).rstrip("/")
                chart_url = f"{base_url}/static/charts/{filename}"

                result["graphics"] = chart_url
                logger.info(f"Generated gainers chart: {chart_url}")
        except Exception as e:
            logger.error(f"Gainers chart generation failed: {e}")
            result["graphics"] = None

    return result
