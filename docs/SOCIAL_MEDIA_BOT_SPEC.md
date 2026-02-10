# Social Media Bot Specification

## Purpose

Create an automated bot that fetches market data from the Trading Data Hub API and posts formatted updates to X (Twitter) and Discord servers. Charts must be included when available to maximize engagement.

# Development Rules

## Core Principles
1. **Simplicity First**: No over-engineering, straightforward step-by-step workflow. **Modular design, obey SRP rules**.
2. **Production Ready**: One-command restart using `uv` or Docker
3. **Developer Friendly**: Clear README with workflow, features, and modification guide
4. **Rate Limit Safe**: Track X posting count, enforce strict limits
5. **Configurable**: All adjustable values in config/env variables, zero hardcoding

## Tech Stack
- Python with `uv` for dependency management
- Environment variables for all configs (API keys, intervals, limits)
- Simple JSON/SQLite for tracking post history
- Systemd service or Docker container for deployment

## Key Requirements
- X rate limit tracker with hard stops
- Chart inclusion when available
- Simple restart: `systemctl restart bot` or `docker compose restart`
- README sections: Setup, Architecture, Adding Features, Removing Features


## Available API Endpoints

Base URL: `http://localhost:8000/api/v1/data`
Base URL in Production: `https://trading-data-hub.nanybot.com/api/v1/data`

### Authentication
```
POST /api/v1/login
Body: username=admin&password=Str1ngst!
Response: {"access_token": "...", "token_type": "bearer"}
```

All data endpoints require: `Authorization: Bearer {access_token}`

### Endpoints with Chart Support

#### 1. CNN Fear & Greed Index
```
GET /cnn_sentiment/fear_greed?ticker=any&chart=true
```
**Data returned:**
- Current sentiment score (0-100)
- Rating (Extreme Fear, Fear, Neutral, Greed, Extreme Greed)
- Historical comparisons (yesterday, 1 week, 1 month, 1 year ago)
- 9 sub-indicators with scores
- `graphics`: Line chart URL showing 254-day trend

**Post frequency:** Every 4 hours (6x/day)
**Engagement hooks:** "Market Sentiment: FEAR (44.9)" with dynamic color-coded messaging

---

#### 2. Reddit Trending Tickers
```
GET /reddit/trending?ticker=any&chart=true
```
**Data returned:**
- Top 20 most-mentioned tickers from r/wallstreetbets, r/stocks, r/options
- Mention counts per ticker
- Top 3 posts mentioning each ticker
- `graphics`: Horizontal bar chart of top 10 tickers by mentions

**Post frequency:** Every 2 hours (12x/day)
**Engagement hooks:** "🔥 Reddit is talking about..." with actual mention counts

---

#### 3. Top Stock Gainers
```
GET /finviz/gainers?ticker=any&chart=true&limit=10
```
**Data returned:**
- Top 10 gaining stocks from Finviz screener
- Ticker, company name, sector, price, % change, volume
- `graphics`: Bar chart of top 10 with % change

**Post frequency:** Market open + every 1 hour during trading (9:30 AM - 4 PM ET)
**Engagement hooks:** "📈 Biggest movers today" with actual % gains

---

#### 4. Sector Performance
```
GET /alpha_vantage/sector_performance?ticker=any&chart=true
```
**Data returned:**
- All 11 sector ETFs ranked by % change
- Symbol, sector name, price, change %, high/low, volume
- Top 3 leaders and bottom 3 laggards
- `graphics`: Bar chart showing all sectors sorted by performance

**Post frequency:** Market close (4 PM ET) daily
**Engagement hooks:** "📊 How sectors performed today"
**Note:** Takes ~13 seconds due to rate limits (11 sectors × 1.2s delay)

---

### Endpoints WITHOUT Chart Support

#### 5. VIX Proxy (Market Volatility)
```
GET /alpha_vantage/vix?ticker=any
```
**Data returned:**
- VIXY ETF price (VIX proxy)
- Price change %, sentiment interpretation
- Open, high, low, volume

**Post frequency:** Every 6 hours
**Engagement hooks:** "Market volatility: [Extreme Fear/Low Fear/etc]"

---

#### 6. Economic Calendar
```
GET /alpha_vantage/economic_calendar?ticker=any
```
**Data returned:**
- Upcoming earnings (next 30 days)
- Upcoming IPOs
- Earnings grouped by date

**Post frequency:** Daily at 7 AM ET
**Engagement hooks:** "📅 This week's earnings"

---

#### 7. SEC Insider Trading
```
GET /sec_edgar/insider_filings?ticker=any
```
**Data returned:**
- Last 30 days of Form 4 filings
- Insider name, company, transaction type, shares, value
- Top 10 companies by filing activity

**Post frequency:** Daily at 6 PM ET
**Engagement hooks:** "👀 What insiders are buying/selling"

---

#### 8. Yahoo Finance Quote
```
GET /yahoo_finance/quote?ticker=AAPL,TSLA,NVDA
```
**Data returned:**
- Real-time price, change %, market cap
- Day high/low, 52-week range, volume
- P/E ratio, dividend yield

**Post frequency:** On-demand or watchlist tickers every 30 minutes during market hours

---

## Bot Requirements

### Core Behavior

**WHAT the bot must achieve:**

1. **Token Management**
   - Obtain JWT token on startup via `/api/v1/login`
   - Detect 401 errors and refresh token automatically
   - Handle token expiration gracefully (tokens expire after ~30 days)

2. **Scheduling**
   - Execute each endpoint at its specified frequency
   - Avoid posting duplicate content (track last posted data hash)
   - Handle overlapping schedules without conflicts
   - Respect rate limits: Max 1 post per minute to X, unlimited to Discord

3. **Content Formatting**

   **For X (Twitter):**
   - Character limit: 280 characters for text
   - Image required when `graphics` field is present
   - Format: `[Hook] [Key metric] [Chart]`
   - Example: "📊 Market Sentiment: EXTREME FEAR (24.5) ⬇️ Down from 44.9 yesterday [chart image]"
   - Use emojis for visual appeal: 📈📉🔥👀📊📅⚡
   - Include relevant hashtags: #Stocks #Trading #MarketSentiment (max 3)

   **For Discord:**
   - Rich embed format with title, description, fields, footer
   - Embed chart image inline when available
   - Use color coding: Green for positive, Red for negative, Blue for neutral
   - Include timestamp and source attribution
   - Use Discord markdown for formatting (bold, italics, code blocks)

4. **Chart Handling**

   **WHAT must happen when `graphics` field is present:**
   - Download the chart image from the URL
   - Verify it's a valid PNG image
   - For X: Attach as media (Twitter supports up to 4 images, use 1)
   - For Discord: Set as embed thumbnail or image
   - If chart download fails, post text-only version
   - Cache downloaded charts to avoid re-downloading duplicates

5. **Error Handling**

   **WHAT errors to handle:**
   - API endpoint returns 500/503: Retry 3x with exponential backoff (2s, 4s, 8s)
   - API returns 401: Re-authenticate immediately
   - X/Discord API rate limit: Queue and retry after cooldown
   - Chart download timeout: Skip chart, post text only
   - Network connectivity loss: Pause and retry every 5 minutes
   - All errors must be logged with context (endpoint, timestamp, error message)

6. **Engagement Optimization**

   **WHAT makes content engaging:**
   - Dynamic messaging based on data (e.g., "🚀 NVDA up 12.3%" vs "📉 NVDA down 5.2%")
   - Trend indicators: ⬆️ up, ⬇️ down, ➡️ flat
   - Comparative context: "Highest since [date]" or "First time below [level] in [period]"
   - Call-to-action for extreme values: "⚠️ VIX at extreme levels"
   - Charts must be visible, not cut off or text-overlapping

---

## Expected Output Examples

### CNN Fear & Greed to X
```
📊 Market Sentiment: FEAR (44.9) ⬇️

Down from 51.2 yesterday
7 of 9 indicators show fear

Chart: [254-day trend line chart]

#Stocks #MarketSentiment #Trading
```

### Reddit Trending to Discord
```
🔥 Reddit Trending Tickers

1. NVDA - 847 mentions
2. TSLA - 612 mentions
3. AAPL - 501 mentions
[...8 more]

Chart: [Bar chart showing top 10]

Scanned 225 posts from r/wallstreetbets, r/stocks, r/options
```

### Sector Performance to X
```
📈 Sector Winners Today:
🥇 Technology +2.8%
🥈 Communication +1.9%
🥉 Consumer Discretionary +1.4%

Chart: [All 11 sectors ranked]

#Stocks #Sectors
```

---

## Success Criteria

**The bot has achieved its purpose when:**

1. Posts appear on X and Discord at the correct frequencies without manual intervention
2. All charts are properly attached and visible in posts
3. Zero duplicate posts (same data posted twice)
4. 99% uptime over 7-day period (excluding API downtime)
5. Average engagement rate on X: >2% (likes + retweets / followers)
6. Discord messages receive reactions within 1 hour of posting
7. No manual token refreshes required for 30 days
8. Error logs contain <5% of total operations
9. Charts are readable on mobile devices (text not cut off)
10. Content is timely (posted within 2 minutes of scheduled time)

---

## Implementation Constraints

**WHAT the bot must NOT do:**

- Never post the same exact content twice
- Never exceed X rate limits (1 post/minute)
- Never expose API credentials in logs or error messages
- Never spam Discord channels (respect 1 post per update frequency)
- Never fetch data more frequently than needed (wastes rate limits)
- Never ignore authentication errors (must re-auth immediately)

**WHAT resources are available:**

- FastAPI server running at `http://localhost:8000`
- Redis available for caching (optional)
- Static chart files served at `/static/charts/*.png`
- All endpoints return JSON with consistent `{"success": bool, "data": {}, "errors": []}` structure
- Charts auto-delete after 24 hours (don't cache URLs, cache images)

---

## Deployment Expectations

**The bot must run as:**

- Background service/daemon (systemd, PM2, or Docker container)
- Automatic restart on crash
- Logs persisted to file and rotated daily
- Configuration via environment variables:
  - `API_BASE_URL`
  - `API_USERNAME`
  - `API_PASSWORD`
  - `TWITTER_API_KEY`, `TWITTER_API_SECRET`, etc.
  - `DISCORD_WEBHOOK_URL` or `DISCORD_BOT_TOKEN`
- Graceful shutdown (finish in-flight posts before exiting)

**Health monitoring:**

- Expose `/health` endpoint showing:
  - Last successful post time per platform
  - Token expiration time
  - Error count in last 24 hours
  - Uptime
- Alert if no posts in 4 hours
- Alert if error rate >10% in 1 hour

---

## Platform-Specific Requirements

### X (Twitter)

**OAuth 1.0a or OAuth 2.0 that applies, with write permissions**

- Post tweets with text + 1 image (optional)
- Handle 280 character limit (truncate gracefully)
- Use Twitter Cards for better chart previews
- Rate limit: max 15/24 hours, use proxy for api request to avoid 429 error which is not only per account, but also per ip.

### Discord

**Webhook or Bot Token**

- Post to specific channel via webhook URL
- Use rich embeds (title, description, fields, image, footer)
- Support multiple servers (1 bot, N webhooks)
- No rate limit issues for <50 posts/day

---

## Future Extensibility

**The bot architecture should allow:**

- Adding new endpoints without code changes (config-driven)
- Posting to additional platforms (Telegram, Slack, etc.)
- Customizing post templates per endpoint
- A/B testing different message formats
