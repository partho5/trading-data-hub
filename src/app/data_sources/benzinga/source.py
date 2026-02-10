"""Benzinga data source implementation."""

import logging
from typing import Any

from ..base import BaseDataSource
from .. import register_source
from .handlers import news, ratings, earnings, dividends, splits, ipos

logger = logging.getLogger("data_aggregator")


@register_source
class BenzingaSource(BaseDataSource):
    """Benzinga data source - news, ratings, earnings, dividends, splits, and IPOs."""

    name = "benzinga"
    supported_data_types = ["news", "ratings", "earnings", "dividends", "splits", "ipos"]

    def __init__(self):
        self._handlers = {
            "news": news.fetch_news,
            "ratings": ratings.fetch_ratings,
            "earnings": earnings.fetch_earnings,
            "dividends": dividends.fetch_dividends,
            "splits": splits.fetch_splits,
            "ipos": ipos.fetch_ipos,
        }

    async def fetch(
        self,
        data_type: str,
        ticker: str | list[str],
        params: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
        """Fetch data from Benzinga."""

        if not self.supports(data_type):
            return {
                "success": False,
                "data": None,
                "errors": [f"Unsupported data type: {data_type}. Supported: {', '.join(self.supported_data_types)}"],
            }

        handler = self._handlers[data_type]
        tickers = [ticker] if isinstance(ticker, str) else ticker

        results = []
        errors = []

        for t in tickers:
            try:
                logger.info(f"Fetching Benzinga {data_type} for {t}")
                result = await handler(t, params or {})
                results.append(result)
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error fetching Benzinga {data_type} for {t}: {error_msg}")
                errors.append({"ticker": t, "error": error_msg})

        # Return single result for single ticker, list for multiple
        if len(tickers) == 1:
            data = results[0] if results else None
        else:
            data = results

        return {
            "success": len(errors) == 0,
            "data": data,
            "errors": errors if errors else None,
        }
