# src/app/data_sources/reddit/handlers/trending.py
"""Handler for Reddit trending tickers from trading subreddits.

Scrapes hot posts from r/wallstreetbets, r/stocks, r/options
and extracts mentioned ticker symbols to gauge retail sentiment.
"""

import logging
import re
from collections import Counter
from typing import Any

from src.app.services import HttpClient, chart_service

logger = logging.getLogger("data_aggregator")

# Common words that look like tickers but aren't
TICKER_BLACKLIST = {
    "A", "I", "AM", "PM", "CEO", "CFO", "CTO", "IPO", "ETF", "SEC",
    "THE", "FOR", "AND", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN",
    "HER", "WAS", "ONE", "OUR", "OUT", "HAS", "HIS", "HOW", "ITS",
    "MAY", "NEW", "NOW", "OLD", "SEE", "WAY", "WHO", "BOY", "DID",
    "GET", "HIM", "LET", "SAY", "SHE", "TOO", "USE", "DD", "YOLO",
    "TL", "DR", "IMO", "IMHO", "FYI", "LOL", "OMG", "WTF", "USA",
    "GDP", "CPI", "FED", "NYSE", "HODL", "FOMO", "ATH", "ATL",
    "PE", "EPS", "RSI", "MACD", "SMA", "EMA", "IV", "OTM", "ITM",
    "PUMP", "DUMP", "CALL", "PUT", "BEAR", "BULL", "LONG", "SHORT",
    "BUY", "SELL", "HOLD", "GAIN", "LOSS", "RED", "GREEN", "MOON",
    "APE", "APES", "BAGS", "DIP", "RIP", "UP", "IT", "AI", "US",
    "UK", "EU", "GO", "SO", "MY", "OR", "IF", "IS", "ON", "IN",
    "TO", "DO", "NO", "BE", "BY", "AT", "OF", "OP", "TD", "POS",
}

SUBREDDITS = ["wallstreetbets", "stocks", "options"]


async def _fetch_subreddit_posts(
    client: HttpClient, subreddit: str, limit: int
) -> list[dict[str, Any]]:
    """Fetch hot posts from a subreddit via JSON API."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json"
    headers = {
        "User-Agent": "TradingDataHub/1.0 (market research bot)",
    }
    params = {"limit": str(limit)}

    try:
        response = await client.get(url, headers=headers, params=params)
        data = response.json()
        children = data.get("data", {}).get("children", [])
        posts = []
        for child in children:
            post = child.get("data", {})
            if post.get("stickied"):
                continue
            posts.append({
                "title": post.get("title", ""),
                "selftext": post.get("selftext", "")[:500],
                "score": post.get("ups", 0),
                "num_comments": post.get("num_comments", 0),
                "subreddit": subreddit,
                "created_utc": post.get("created_utc", 0),
                "url": f"https://reddit.com{post.get('permalink', '')}",
            })
        return posts
    except Exception as e:
        logger.warning(f"Failed to fetch r/{subreddit}: {e}")
        return []


def _extract_tickers(text: str) -> list[str]:
    """Extract potential ticker symbols from text.

    Looks for $TICKER patterns and standalone ALL-CAPS words (1-5 chars).
    """
    tickers = []

    # $TICKER pattern (most reliable)
    dollar_tickers = re.findall(r'\$([A-Z]{1,5})\b', text)
    tickers.extend(dollar_tickers)

    # ALL CAPS words that look like tickers (2-5 chars, not in blacklist)
    caps_words = re.findall(r'\b([A-Z]{2,5})\b', text)
    for word in caps_words:
        if word not in TICKER_BLACKLIST:
            tickers.append(word)

    return tickers


async def fetch_trending(ticker: str, params: dict[str, Any], request=None) -> dict[str, Any]:
    """
    Fetch trending tickers from Reddit trading subreddits.

    Scrapes hot posts from r/wallstreetbets, r/stocks, r/options,
    extracts mentioned ticker symbols, and ranks by mention frequency.

    Args:
        ticker: Not used (market-wide data)
        params: Optional params:
            - limit: Posts per subreddit (default 25)
            - subreddits: Comma-separated list (default: wsb,stocks,options)
            - chart: Generate chart if True
        request: FastAPI Request object (for URL generation)

    Returns:
        Dict with trending tickers and top posts
    """
    limit = params.get("limit", 25)
    subreddit_param = params.get("subreddits", "")
    subreddits = [s.strip() for s in subreddit_param.split(",") if s.strip()] if subreddit_param else SUBREDDITS

    client = HttpClient(use_proxy=True, timeout=30)

    all_posts = []
    for sub in subreddits:
        posts = await _fetch_subreddit_posts(client, sub, limit)
        all_posts.extend(posts)

    # Extract and count ticker mentions
    ticker_counter: Counter = Counter()
    ticker_posts: dict[str, list] = {}

    for post in all_posts:
        text = f"{post['title']} {post['selftext']}"
        tickers_found = _extract_tickers(text)
        unique_tickers = set(tickers_found)

        for t in unique_tickers:
            ticker_counter[t] += 1
            if t not in ticker_posts:
                ticker_posts[t] = []
            ticker_posts[t].append({
                "title": post["title"][:100],
                "score": post["score"],
                "subreddit": post["subreddit"],
            })

    # Top trending tickers
    trending_tickers = []
    for symbol, count in ticker_counter.most_common(20):
        trending_tickers.append({
            "ticker": symbol,
            "mentions": count,
            "top_posts": ticker_posts.get(symbol, [])[:3],
        })

    # Top posts by engagement
    top_posts = sorted(all_posts, key=lambda x: x["score"], reverse=True)[:10]

    result = {
        "subreddits": subreddits,
        "total_posts_scanned": len(all_posts),
        "trending_tickers": trending_tickers,
        "top_posts": [
            {
                "title": p["title"],
                "score": p["score"],
                "comments": p["num_comments"],
                "subreddit": p["subreddit"],
                "url": p["url"],
            }
            for p in top_posts
        ],
    }

    # Chart generation if requested
    if params and params.get("chart") is True and trending_tickers and request:
        try:
            # Transform to chart data format (top 10 tickers)
            chart_data = [
                {
                    "label": t["ticker"],
                    "value": t["mentions"],
                }
                for t in trending_tickers[:10]
            ]

            # Generate chart
            filename = await chart_service.generate_bar_chart(
                data=chart_data,
                chart_type="trending",
                title="Reddit Trending Tickers",
                subtitle=f"Most Mentioned on {', '.join([f'r/{s}' for s in subreddits])}",
            )

            # Build public URL
            base_url = str(request.base_url).rstrip("/")
            chart_url = f"{base_url}/static/charts/{filename}"

            result["graphics"] = chart_url
            logger.info(f"Generated trending chart: {chart_url}")
        except Exception as e:
            logger.error(f"Trending chart generation failed: {e}")
            result["graphics"] = None

    return result
