# src/app/data_sources/finviz/handlers/losers.py
"""Handler for Finviz top losers."""

import logging
from typing import Any

from bs4 import BeautifulSoup

from src.app.services import HttpClient

logger = logging.getLogger("data_aggregator")

FINVIZ_SCREENER_URL = "https://finviz.com/screener.ashx"


async def fetch_losers(ticker: str, params: dict[str, Any], request=None) -> dict[str, Any]:
    """
    Fetch top losing stocks from Finviz.

    Args:
        ticker: Not used (market-wide data)
        params: Optional params:
            - limit: Number of results (default 20)

    Returns:
        Dict with list of top losers
    """
    limit = params.get("limit", 20)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # Finviz screener sorted by change ascending (biggest losers first)
    query_params = {
        "v": "111",  # Overview view
        "s": "ta_toplosers",  # Top losers signal
        "f": "sh_avgvol_o500",  # Avg volume > 500K for liquidity
        "o": "change",  # Sort by change ascending
    }

    client = HttpClient(use_proxy=True)
    response = await client.get(
        FINVIZ_SCREENER_URL, headers=headers, params=query_params
    )

    soup = BeautifulSoup(response.text, "html.parser")

    table = soup.find("table", {"class": "styled-table-new"})
    if not table:
        table = soup.find("table", {"id": "screener-table"})

    losers = []

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
                    losers.append({
                        "ticker": ticker_symbol,
                        "company": company,
                        "sector": sector,
                        "price": price,
                        "change": change,
                        "volume": volume,
                    })

    return {
        "type": "losers",
        "count": len(losers),
        "data": losers,
    }
