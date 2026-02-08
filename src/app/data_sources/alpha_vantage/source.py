# src/app/data_sources/alpha_vantage/source.py
"""Alpha Vantage data source implementation."""

import logging
from typing import Any

from ..base import BaseDataSource
from .. import register_source
from .handlers import vix, economic_calendar, sector_performance

logger = logging.getLogger("data_aggregator")


@register_source
class AlphaVantageSource(BaseDataSource):
    """Alpha Vantage data source for market data (free tier)."""

    name = "alpha_vantage"
    supported_data_types = ["vix", "economic_calendar", "sector_performance"]

    def __init__(self):
        self._handlers = {
            "vix": vix.fetch_vix,
            "economic_calendar": economic_calendar.fetch_economic_calendar,
            "sector_performance": sector_performance.fetch_sector_performance,
        }

    async def fetch(
        self,
        data_type: str,
        ticker: str | list[str],
        params: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
        """
        Fetch data from Alpha Vantage.

        Args:
            data_type: One of 'vix', 'economic_calendar', 'sector_performance'
            ticker: Not used for these endpoints (market-wide data)
            params: Additional parameters

        Returns:
            Dict with 'success', 'data', and optionally 'errors'
        """
        if not self.supports(data_type):
            return {
                "success": False,
                "data": None,
                "errors": [f"Unsupported data type: {data_type}"],
            }

        handler = self._handlers[data_type]
        params = params or {}

        ticker_str = ticker if isinstance(ticker, str) else ticker[0] if ticker else ""

        try:
            logger.info(f"Fetching Alpha Vantage {data_type}")
            data = await handler(ticker_str, params, request=request)
            return {
                "success": True,
                "data": data,
                "errors": None,
            }
        except Exception as e:
            logger.error(f"Alpha Vantage {data_type} fetch error: {e}")
            return {
                "success": False,
                "data": None,
                "errors": [str(e)],
            }
