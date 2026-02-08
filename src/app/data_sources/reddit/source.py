# src/app/data_sources/reddit/source.py
"""Reddit data source for retail trader sentiment."""

import logging
from typing import Any

from ..base import BaseDataSource
from .. import register_source
from .handlers import trending

logger = logging.getLogger("data_aggregator")


@register_source
class RedditSource(BaseDataSource):
    """Reddit for retail trader sentiment (WSB, stocks, options)."""

    name = "reddit"
    supported_data_types = ["trending"]

    def __init__(self):
        self._handlers = {
            "trending": trending.fetch_trending,
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
            logger.info(f"Fetching Reddit {data_type}")
            data = await handler(ticker_str, params, request=request)
            return {"success": True, "data": data, "errors": None}
        except Exception as e:
            logger.error(f"Reddit {data_type} fetch error: {e}")
            return {"success": False, "data": None, "errors": [str(e)]}
