# src/app/data_sources/yahoo_finance/handlers/auth.py
"""Yahoo Finance authentication helper for quoteSummary API."""

import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger("data_aggregator")

# Cache for crumb and cookies
_crumb_cache: dict = {"crumb": None, "cookies": None}


async def get_yahoo_crumb(proxy: Optional[str] = None) -> tuple[str, dict]:
    """
    Get Yahoo Finance crumb and cookies required for quoteSummary API.

    Returns:
        Tuple of (crumb, cookies_dict)
    """
    global _crumb_cache

    # Return cached if available
    if _crumb_cache["crumb"] and _crumb_cache["cookies"]:
        return _crumb_cache["crumb"], _crumb_cache["cookies"]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        async with httpx.AsyncClient(timeout=30, proxy=proxy) as client:
            # First, get cookies from Yahoo Finance
            resp = await client.get("https://fc.yahoo.com", headers=headers)
            cookies = dict(resp.cookies)

            # Then get the crumb
            resp = await client.get(
                "https://query1.finance.yahoo.com/v1/test/getcrumb",
                headers=headers,
                cookies=cookies,
            )

            if resp.status_code == 200:
                crumb = resp.text
                _crumb_cache["crumb"] = crumb
                _crumb_cache["cookies"] = cookies
                logger.debug(f"Got Yahoo crumb: {crumb[:10]}...")
                return crumb, cookies

    except Exception as e:
        logger.warning(f"Failed to get Yahoo crumb: {e}")

    raise ValueError("Could not obtain Yahoo Finance authentication")


def clear_crumb_cache():
    """Clear the crumb cache to force refresh."""
    global _crumb_cache
    _crumb_cache = {"crumb": None, "cookies": None}
