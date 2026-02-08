# src/app/services/proxy_manager.py
"""Rotating proxy manager."""

import logging
import os
import random
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env file from src directory
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

logger = logging.getLogger("data_aggregator")


class ProxyManager:
    """
    Manages rotating proxies for HTTP requests.

    Proxies are loaded from PROXY_LIST env var (comma-separated).
    Format: http://user:pass@host:port or http://host:port
    """

    def __init__(self):
        self._proxies: list[str] = []
        self._failed_proxies: set[str] = set()
        self._load_proxies()

    def _load_proxies(self) -> None:
        """Load proxies from environment variable."""
        proxy_list = os.getenv("PROXY_LIST", "")
        if proxy_list:
            self._proxies = [p.strip() for p in proxy_list.split(",") if p.strip()]
            logger.info(f"Loaded {len(self._proxies)} proxies")
        else:
            logger.warning("No proxies configured (PROXY_LIST env var empty)")

    def get_proxy(self) -> Optional[str]:
        """Get a random working proxy."""
        available = [p for p in self._proxies if p not in self._failed_proxies]

        if not available:
            # Reset failed proxies if all have failed
            if self._failed_proxies:
                logger.info("All proxies failed, resetting failed list")
                self._failed_proxies.clear()
                available = self._proxies

        if available:
            return random.choice(available)

        return None

    def mark_failed(self, proxy: Optional[str]) -> None:
        """Mark a proxy as failed."""
        if proxy:
            self._failed_proxies.add(proxy)
            logger.debug(f"Marked proxy as failed: {proxy[:20]}...")

    def get_proxy_count(self) -> int:
        """Get total number of proxies."""
        return len(self._proxies)

    def get_available_count(self) -> int:
        """Get number of currently available proxies."""
        return len([p for p in self._proxies if p not in self._failed_proxies])
