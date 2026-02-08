# src/app/data_sources/finviz/handlers/unusual_volume.py
"""Handler for Finviz unusual volume stocks."""

import logging
from typing import Any

from bs4 import BeautifulSoup

from src.app.services import HttpClient

logger = logging.getLogger("data_aggregator")

FINVIZ_SCREENER_URL = "https://finviz.com/screener.ashx"


async def fetch_unusual_volume(ticker: str, params: dict[str, Any], request=None) -> dict[str, Any]:
    """
    Fetch stocks with unusual volume from Finviz.

    Args:
        ticker: Not used (market-wide data)
        params: Optional params:
            - limit: Number of results (default 20)

    Returns:
        Dict with list of unusual volume stocks
    """
    limit = params.get("limit", 20)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # Finviz screener for unusual volume
    query_params = {
        "v": "111",  # Overview view
        "s": "ta_unusualvolume",  # Unusual volume signal
        "o": "-relativevolume",  # Sort by relative volume descending
    }

    client = HttpClient(use_proxy=True)
    response = await client.get(
        FINVIZ_SCREENER_URL, headers=headers, params=query_params
    )

    soup = BeautifulSoup(response.text, "html.parser")

    table = soup.find("table", {"class": "styled-table-new"})
    if not table:
        table = soup.find("table", {"id": "screener-table"})

    stocks = []

    if table:
        rows = table.find_all("tr")[1:]

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
                    stocks.append({
                        "ticker": ticker_symbol,
                        "company": company,
                        "sector": sector,
                        "price": price,
                        "change": change,
                        "volume": volume,
                    })

    return {
        "type": "unusual_volume",
        "count": len(stocks),
        "data": stocks,
    }
