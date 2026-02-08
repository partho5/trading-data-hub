# src/app/data_sources/cnn_sentiment/source.py
"""CNN Fear & Greed Index data source."""

import logging
from typing import Any

from ..base import BaseDataSource
from .. import register_source
from .handlers import fear_greed

logger = logging.getLogger("data_aggregator")


@register_source
class CnnSentimentSource(BaseDataSource):
    """CNN Fear & Greed Index for market sentiment."""

    name = "cnn_sentiment"
    supported_data_types = ["fear_greed"]

    def __init__(self):
        self._handlers = {
            "fear_greed": fear_greed.fetch_fear_greed,
        }

    async def fetch(
        self,
        data_type: str,
        ticker: str | list[str],
        params: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
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
            logger.info(f"Fetching CNN {data_type}")
            data = await handler(ticker_str, params, request=request)
            return {"success": True, "data": data, "errors": None}
        except Exception as e:
            logger.error(f"CNN {data_type} fetch error: {e}")
            return {"success": False, "data": None, "errors": [str(e)]}
