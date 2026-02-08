# src/app/data_sources/sec_edgar/source.py
"""SEC EDGAR data source for insider trading filings."""

import logging
from typing import Any

from ..base import BaseDataSource
from .. import register_source
from .handlers import insider_filings

logger = logging.getLogger("data_aggregator")


@register_source
class SecEdgarSource(BaseDataSource):
    """SEC EDGAR for insider trading data (Form 4 filings)."""

    name = "sec_edgar"
    supported_data_types = ["insider_filings"]

    def __init__(self):
        self._handlers = {
            "insider_filings": insider_filings.fetch_insider_filings,
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
            logger.info(f"Fetching SEC EDGAR {data_type}")
            data = await handler(ticker_str, params)
            return {"success": True, "data": data, "errors": None}
        except Exception as e:
            logger.error(f"SEC EDGAR {data_type} fetch error: {e}")
            return {"success": False, "data": None, "errors": [str(e)]}
