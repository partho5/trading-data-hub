# src/app/services/http_client.py
"""HTTP client with retry logic."""

import asyncio
import logging
from typing import Any

import httpx

from .proxy_manager import ProxyManager

logger = logging.getLogger("data_aggregator")

DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 1


class HttpClient:
    """HTTP client with retry and proxy rotation."""

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS,
        use_proxy: bool = False,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.use_proxy = use_proxy
        self.proxy_manager = ProxyManager() if use_proxy else None

    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """
        Make GET request with retry logic.

        Raises:
            httpx.HTTPError: If all retries fail
        """
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            proxy = None
            if self.proxy_manager:
                proxy = self.proxy_manager.get_proxy()
                logger.debug(f"Using proxy: {proxy}")

            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    proxy=proxy,
                ) as client:
                    response = await client.get(url, headers=headers, params=params)
                    response.raise_for_status()
                    return response

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"HTTP {e.response.status_code} on attempt {attempt}/{self.max_retries}: {url}"
                )
                # Don't retry on client errors (4xx) except 429
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise

            except httpx.RequestError as e:
                last_error = e
                logger.warning(
                    f"Request error on attempt {attempt}/{self.max_retries}: {e}"
                )

            # Rotate proxy on failure
            if self.proxy_manager:
                self.proxy_manager.mark_failed(proxy)

            # Wait before retry
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay * attempt)

        logger.error(f"All {self.max_retries} attempts failed for: {url}")
        raise last_error or httpx.RequestError(f"Failed after {self.max_retries} retries")
