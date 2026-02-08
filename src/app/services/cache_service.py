# src/app/services/cache_service.py
"""Cache service using Redis."""

import json
import logging
from typing import Any, Optional

from ..core.utils.cache import client as redis_client

logger = logging.getLogger("data_aggregator")

DEFAULT_TTL_SECONDS = 300  # 5 minutes


class CacheService:
    """Simple cache wrapper for data source results."""

    def __init__(self, ttl: int = DEFAULT_TTL_SECONDS):
        self.ttl = ttl

    def _make_key(self, source: str, data_type: str, ticker: str, params: dict | None) -> str:
        """Generate cache key from request parameters."""
        params_str = json.dumps(params, sort_keys=True) if params else ""
        return f"data:{source}:{data_type}:{ticker}:{params_str}"

    async def get(
        self,
        source: str,
        data_type: str,
        ticker: str,
        params: dict | None = None,
    ) -> Optional[dict[str, Any]]:
        """Get cached data if available."""
        if redis_client is None:
            return None

        key = self._make_key(source, data_type, ticker, params)

        try:
            cached = await redis_client.get(key)
            if cached:
                logger.debug(f"Cache hit: {key}")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache get error: {e}")

        return None

    async def set(
        self,
        source: str,
        data_type: str,
        ticker: str,
        data: dict[str, Any],
        params: dict | None = None,
    ) -> None:
        """Store data in cache."""
        if redis_client is None:
            return

        key = self._make_key(source, data_type, ticker, params)

        try:
            await redis_client.set(key, json.dumps(data), ex=self.ttl)
            logger.debug(f"Cache set: {key}")
        except Exception as e:
            logger.warning(f"Cache set error: {e}")


# Singleton instance
cache_service = CacheService()
