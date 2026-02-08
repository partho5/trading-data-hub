# Adding New Data Sources

This guide explains how to add a new data source to the Data Aggregator.

## Overview

The system uses a plugin architecture:
- Each source is a folder in `src/app/data_sources/`
- Sources register themselves using the `@register_source` decorator
- Each source can have multiple data type handlers

## Step-by-Step: Adding a New Source

### Example: Adding Benzinga

We'll add a `benzinga` source with a `news` data type.

---

### Step 1: Create Folder Structure

```
src/app/data_sources/benzinga/
├── __init__.py
├── source.py
└── handlers/
    ├── __init__.py
    └── news.py
```

```bash
mkdir -p src/app/data_sources/benzinga/handlers
touch src/app/data_sources/benzinga/__init__.py
touch src/app/data_sources/benzinga/source.py
touch src/app/data_sources/benzinga/handlers/__init__.py
touch src/app/data_sources/benzinga/handlers/news.py
```

---

### Step 2: Create the Handler

`src/app/data_sources/benzinga/handlers/news.py`:

```python
"""Handler for Benzinga news data."""

import logging
from typing import Any

from ....services.http_client import HttpClient

logger = logging.getLogger("data_aggregator")

BENZINGA_NEWS_URL = "https://api.benzinga.com/api/v2/news"


async def fetch_news(ticker: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch news for a ticker.

    Args:
        ticker: Stock symbol (e.g., 'AAPL')
        params: Optional parameters like 'limit', 'page'

    Returns:
        Dict with news data
    """
    client = HttpClient(use_proxy=False)

    headers = {
        "User-Agent": "Mozilla/5.0",
        # Add API key if required:
        # "Authorization": f"Bearer {os.getenv('BENZINGA_API_KEY')}"
    }

    query_params = {
        "tickers": ticker.upper(),
        "limit": params.get("limit", 10),
    }

    response = await client.get(BENZINGA_NEWS_URL, headers=headers, params=query_params)
    data = response.json()

    # Transform response to normalized format
    articles = []
    for item in data.get("articles", []):
        articles.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "published": item.get("created"),
            "source": "benzinga",
        })

    return {
        "ticker": ticker,
        "count": len(articles),
        "articles": articles,
    }
```

---

### Step 3: Create Handler Init

`src/app/data_sources/benzinga/handlers/__init__.py`:

```python
"""Benzinga data handlers."""

from . import news

__all__ = ["news"]
```

---

### Step 4: Create the Source Class

`src/app/data_sources/benzinga/source.py`:

```python
"""Benzinga data source implementation."""

import logging
from typing import Any

from ..base import BaseDataSource
from .. import register_source
from .handlers import news

logger = logging.getLogger("data_aggregator")


@register_source
class BenzingaSource(BaseDataSource):
    """Benzinga data source."""

    name = "benzinga"
    supported_data_types = ["news"]

    def __init__(self):
        self._handlers = {
            "news": news.fetch_news,
        }

    async def fetch(
        self,
        data_type: str,
        ticker: str | list[str],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fetch data from Benzinga."""

        if not self.supports(data_type):
            return {
                "success": False,
                "data": None,
                "errors": [f"Unsupported data type: {data_type}"],
            }

        handler = self._handlers[data_type]
        tickers = [ticker] if isinstance(ticker, str) else ticker

        results = []
        errors = []

        for t in tickers:
            try:
                result = await handler(t, params or {})
                results.append(result)
            except Exception as e:
                logger.error(f"Error fetching {data_type} for {t}: {e}")
                errors.append({"ticker": t, "error": str(e)})

        if len(tickers) == 1:
            data = results[0] if results else None
        else:
            data = results

        return {
            "success": len(errors) == 0,
            "data": data,
            "errors": errors if errors else None,
        }
```

---

### Step 5: Create Source Init

`src/app/data_sources/benzinga/__init__.py`:

```python
"""Benzinga data source."""

from .source import BenzingaSource

__all__ = ["BenzingaSource"]
```

---

### Step 6: Register the Source

Edit `src/app/data_sources/__init__.py`:

```python
# Import sources to trigger registration
from . import yahoo_finance  # noqa: E402, F401
from . import benzinga       # noqa: E402, F401  <- ADD THIS
```

---

### Step 7: Test

```bash
# Restart server
uv run uvicorn src.app.main:app --reload --port 8000

# Test the new source
curl "http://localhost:8000/api/v1/data/sources"
# Should show benzinga in the list

curl "http://localhost:8000/api/v1/data/benzinga/news?ticker=AAPL" \
  -H "Authorization: Bearer <token>"
```

---

## Adding a New Data Type to Existing Source

To add a new data type to an existing source (e.g., `financials` to `yahoo_finance`):

### Step 1: Create Handler

`src/app/data_sources/yahoo_finance/handlers/financials.py`:

```python
"""Handler for Yahoo Finance financials data."""

import logging
from typing import Any

from ....services.http_client import HttpClient

logger = logging.getLogger("data_aggregator")

YAHOO_FINANCIALS_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"


async def fetch_financials(ticker: str, params: dict[str, Any]) -> dict[str, Any]:
    """Fetch financial data for a ticker."""
    client = HttpClient(use_proxy=False)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    url = YAHOO_FINANCIALS_URL.format(ticker=ticker.upper())
    query_params = {
        "modules": "financialData,defaultKeyStatistics",
    }

    response = await client.get(url, headers=headers, params=query_params)
    data = response.json()

    result = data.get("quoteSummary", {}).get("result", [])
    if not result:
        raise ValueError(f"No financial data for {ticker}")

    financial_data = result[0].get("financialData", {})
    key_stats = result[0].get("defaultKeyStatistics", {})

    return {
        "ticker": ticker,
        "revenue": financial_data.get("totalRevenue", {}).get("raw"),
        "profit_margin": financial_data.get("profitMargins", {}).get("raw"),
        "pe_ratio": key_stats.get("trailingPE", {}).get("raw"),
        "eps": key_stats.get("trailingEps", {}).get("raw"),
    }
```

### Step 2: Register Handler

Edit `src/app/data_sources/yahoo_finance/handlers/__init__.py`:

```python
from . import quote, chart, financials  # <- ADD financials

__all__ = ["quote", "chart", "financials"]
```

### Step 3: Add to Source

Edit `src/app/data_sources/yahoo_finance/source.py`:

```python
from .handlers import quote, chart, financials  # <- ADD

class YahooFinanceSource(BaseDataSource):
    name = "yahoo_finance"
    supported_data_types = ["quote", "chart", "financials"]  # <- ADD

    def __init__(self):
        self._handlers = {
            "quote": quote.fetch_quote,
            "chart": chart.fetch_chart,
            "financials": financials.fetch_financials,  # <- ADD
        }
```

---

## Using Proxies

To enable proxy rotation for a handler:

```python
# In your handler
client = HttpClient(use_proxy=True)  # Enable proxy rotation
```

Configure proxies in `src/.env`:

```env
PROXY_LIST=http://user:pass@proxy1:port,http://user:pass@proxy2:port
```

---

## Best Practices

1. **Normalize responses** - Transform source-specific formats to consistent structure
2. **Handle errors gracefully** - Catch exceptions, log them, return structured errors
3. **Use logging** - Log to `data_aggregator` logger for debugging
4. **Keep handlers simple** - One handler = one data type = one responsibility
5. **Document parameters** - Describe what `params` each handler accepts
6. **Test thoroughly** - Test with valid/invalid tickers, edge cases

---

## Checklist for New Source

- [ ] Create folder structure
- [ ] Implement handler(s)
- [ ] Create source class with `@register_source`
- [ ] Add to `__init__.py` imports
- [ ] Test via API
- [ ] Document supported data types and parameters