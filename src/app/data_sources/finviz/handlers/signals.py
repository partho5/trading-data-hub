# src/app/data_sources/finviz/handlers/signals.py
"""Handler for Finviz technical signals (new highs, oversold, breakouts, etc.)."""

import logging
from typing import Any

from bs4 import BeautifulSoup

from src.app.services import HttpClient

logger = logging.getLogger("data_aggregator")

FINVIZ_SCREENER_URL = "https://finviz.com/screener.ashx"

# Available signal types mapped to Finviz screener signal codes
SIGNAL_MAP = {
    "new_high": "ta_newhigh",
    "new_low": "ta_newlow",
    "overbought": "ta_overbought",
    "oversold": "ta_oversold",
    "most_volatile": "ta_mostvolatile",
    "most_active": "ta_mostactive",
    "channel_up": "ta_channelup",
    "channel_down": "ta_channeldown",
    "wedge_up": "ta_wedgeup",
    "wedge_down": "ta_wedgedown",
    "double_bottom": "ta_doublebottom",
    "double_top": "ta_doubletop",
}


async def fetch_signals(ticker: str, params: dict[str, Any], request=None) -> dict[str, Any]:
    """
    Fetch stocks matching a technical signal from Finviz screener.

    Args:
        ticker: Not used (market-wide data)
        params: Required params:
            - signal: One of 'new_high', 'new_low', 'overbought', 'oversold',
                      'most_volatile', 'most_active', 'channel_up', 'channel_down',
                      'wedge_up', 'wedge_down', 'double_bottom', 'double_top'
            - limit: Number of results (default 20)

    Returns:
        Dict with stocks matching the signal
    """
    signal = params.get("signal", "new_high")
    limit = params.get("limit", 20)

    signal_code = SIGNAL_MAP.get(signal)
    if not signal_code:
        return {
            "type": "signals",
            "signal": signal,
            "error": f"Unknown signal. Available: {list(SIGNAL_MAP.keys())}",
            "count": 0,
            "data": [],
        }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    query_params = {
        "v": "111",
        "s": signal_code,
        "f": "sh_avgvol_o200",  # Min avg volume 200K for liquidity
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
        "type": "signals",
        "signal": signal,
        "signal_description": signal.replace("_", " ").title(),
        "count": len(stocks),
        "data": stocks,
    }
