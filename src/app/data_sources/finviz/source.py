# src/app/data_sources/finviz/source.py
"""Finviz data source implementation."""

import logging
from typing import Any

from ..base import BaseDataSource
from .. import register_source
from .handlers import gainers, losers, unusual_volume, insider, signals

logger = logging.getLogger("data_aggregator")


@register_source
class FinvizSource(BaseDataSource):
    """Finviz data source for market screener data."""

    name = "finviz"
    supported_data_types = ["gainers", "losers", "unusual_volume", "insider", "signals"]

    def __init__(self):
        self._handlers = {
            "gainers": gainers.fetch_gainers,
            "losers": losers.fetch_losers,
            "unusual_volume": unusual_volume.fetch_unusual_volume,
            "insider": insider.fetch_insider,
            "signals": signals.fetch_signals,
        }

    async def fetch(
        self,
        data_type: str,
        ticker: str | list[str],
        params: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
        """
        Fetch data from Finviz.

        Args:
            data_type: One of 'gainers', 'losers', 'unusual_volume', 'insider'
            ticker: For 'insider' can filter by ticker, others ignore this
            params: Additional parameters (limit, type for insider)

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

        # For market-wide data, ticker is ignored except for insider
        ticker_str = ticker if isinstance(ticker, str) else ticker[0] if ticker else ""

        try:
            logger.info(f"Fetching Finviz {data_type}")
            data = await handler(ticker_str, params, request=request)
            return {
                "success": True,
                "data": data,
                "errors": None,
            }
        except Exception as e:
            logger.error(f"Finviz {data_type} fetch error: {e}")
            return {
                "success": False,
                "data": None,
                "errors": [str(e)],
            }
