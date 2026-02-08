# src/app/data_sources/yahoo_finance/source.py
"""Yahoo Finance data source implementation."""

import logging
from typing import Any

from ..base import BaseDataSource
from .. import register_source
from .handlers import quote, chart, extended, earnings, stats, ratings

logger = logging.getLogger("data_aggregator")


@register_source
class YahooFinanceSource(BaseDataSource):
    """Yahoo Finance data source."""

    name = "yahoo_finance"
    supported_data_types = ["quote", "chart", "extended", "earnings", "stats", "ratings"]

    def __init__(self):
        # Map data_type to handler function
        self._handlers = {
            "quote": quote.fetch_quote,
            "chart": chart.fetch_chart,
            "extended": extended.fetch_extended,
            "earnings": earnings.fetch_earnings,
            "stats": stats.fetch_stats,
            "ratings": ratings.fetch_ratings,
        }

    async def fetch(
        self,
        data_type: str,
        ticker: str | list[str],
        params: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
        """
        Fetch data from Yahoo Finance.

        Args:
            data_type: 'quote' or 'chart'
            ticker: Single ticker or list of tickers
            params: For 'chart': interval, range

        Returns:
            {
                "success": bool,
                "data": {...} or [...],
                "errors": [...] (optional)
            }
        """
        if not self.supports(data_type):
            return {
                "success": False,
                "data": None,
                "errors": [f"Unsupported data type: {data_type}"],
            }

        handler = self._handlers[data_type]

        # Normalize to list
        tickers = [ticker] if isinstance(ticker, str) else ticker

        results = []
        errors = []

        for t in tickers:
            try:
                result = await handler(t, params or {})
                results.append(result)
            except Exception as e:
                logger.error(f"Error fetching {data_type} for {t}: {e}")
                errors.append({"ticker": t, "error": str(e)})

        # Format response
        if len(tickers) == 1:
            data = results[0] if results else None
        else:
            data = results

        return {
            "success": len(errors) == 0,
            "data": data,
            "errors": errors if errors else None,
        }
