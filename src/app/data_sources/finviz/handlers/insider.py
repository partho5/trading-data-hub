# src/app/data_sources/finviz/handlers/insider.py
"""Handler for Finviz insider trading data."""

import logging
from typing import Any

from bs4 import BeautifulSoup

from src.app.services import HttpClient

logger = logging.getLogger("data_aggregator")

FINVIZ_INSIDER_URL = "https://finviz.com/insidertrading.ashx"


async def fetch_insider(ticker: str, params: dict[str, Any], request=None) -> dict[str, Any]:
    """
    Fetch recent insider trading activity from Finviz.

    Args:
        ticker: Optional - filter by specific ticker
        params: Optional params:
            - limit: Number of results (default 20)
            - type: 'buy', 'sell', or 'all' (default 'all')

    Returns:
        Dict with list of insider trades
    """
    limit = params.get("limit", 20)
    trade_type = params.get("type", "all")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    query_params = {}

    # Filter by trade type
    if trade_type == "buy":
        query_params["tc"] = "1"  # Buys only
    elif trade_type == "sell":
        query_params["tc"] = "2"  # Sells only

    # Filter by specific ticker if provided
    if ticker and ticker.lower() != "all":
        query_params["ticker"] = ticker.upper()

    client = HttpClient(use_proxy=True)
    response = await client.get(
        FINVIZ_INSIDER_URL, headers=headers, params=query_params
    )

    soup = BeautifulSoup(response.text, "html.parser")

    # Find insider trading table
    table = soup.find("table", {"class": "styled-table-new"})
    if not table:
        table = soup.find("table", {"class": "table-insider"})

    trades = []

    if table:
        rows = table.find_all("tr")[1:]  # Skip header

        for row in rows[:limit]:
            cells = row.find_all("td")
            if len(cells) >= 9:
                ticker_cell = cells[0].find("a")
                ticker_symbol = ticker_cell.text.strip() if ticker_cell else ""

                owner = cells[1].text.strip() if len(cells) > 1 else ""
                relationship = cells[2].text.strip() if len(cells) > 2 else ""
                date = cells[3].text.strip() if len(cells) > 3 else ""
                transaction = cells[4].text.strip() if len(cells) > 4 else ""
                cost = cells[5].text.strip() if len(cells) > 5 else ""
                shares = cells[6].text.strip() if len(cells) > 6 else ""
                value = cells[7].text.strip() if len(cells) > 7 else ""
                total_shares = cells[8].text.strip() if len(cells) > 8 else ""

                if ticker_symbol:
                    trades.append({
                        "ticker": ticker_symbol,
                        "owner": owner,
                        "relationship": relationship,
                        "date": date,
                        "transaction": transaction,
                        "cost": cost,
                        "shares": shares,
                        "value": value,
                        "total_shares": total_shares,
                    })

    return {
        "type": "insider",
        "filter": {"ticker": ticker if ticker else "all", "trade_type": trade_type},
        "count": len(trades),
        "data": trades,
    }
