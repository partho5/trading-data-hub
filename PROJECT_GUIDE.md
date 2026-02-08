# Trading Data Hub - Project Guide

Your FastAPI application with Neon database and JWT authentication.

## Getting Started

### Prerequisites

- Python 3.12+
- Docker (for Redis)
- Neon database account

### Setup

```bash
# 1. Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env

# 2. Install ALL dependencies (from pyproject.toml)
uv sync

# Or install without dev dependencies:
# uv sync --no-dev

# 3. Start Redis
docker run -d --name redis -p 6379:6379 redis:alpine

# 4. Configure environment
# Edit src/.env with your Neon credentials

# 5. Run migrations
cd src && uv run alembic upgrade head && cd ..

# 6. Create admin user
# First, edit ADMIN_* values in src/.env with YOUR credentials (not demo ones!)
uv run python -m src.scripts.create_first_superuser

# 7. Start server
uv run uvicorn src.app.main:app --reload --port 8000
```

**Swagger UI:** http://localhost:8000/docs

---

## Authentication Flow

```
Register → Login → Get Token (60 min) → Call APIs → Refresh/Re-login
```

### 1. Register
```bash
curl -X POST "http://localhost:8000/api/v1/user" \
  -H "Content-Type: application/json" \
  -d '{"name": "John", "username": "john", "email": "john@example.com", "password": "Pass123!"}'
```

### 2. Login
```bash
curl -X POST "http://localhost:8000/api/v1/login" \
  -d "username=john&password=Pass123!"

# Response: {"access_token": "eyJ...", "token_type": "bearer"}
```

### 3. Use Token
```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/user/me/
```

---

## Project Structure

```
src/
├── app/
│   ├── main.py                 # App entry point
│   ├── api/
│   │   ├── v1/                 # API endpoints
│   │   │   ├── login.py        # Auth (login/logout/refresh)
│   │   │   ├── users.py        # User CRUD
│   │   │   ├── posts.py        # Example resource
│   │   │   └── __init__.py     # Router registration
│   │   └── dependencies.py     # Auth dependencies
│   ├── core/
│   │   ├── config.py           # Settings (from .env)
│   │   ├── security.py         # JWT & password hashing
│   │   └── db/
│   │       └── database.py     # SQLAlchemy async setup
│   ├── models/                 # Database models (SQLAlchemy)
│   ├── schemas/                # Request/Response schemas (Pydantic)
│   └── crud/                   # Database operations (FastCRUD)
├── migrations/                 # Alembic migrations
└── .env                        # Environment config
```

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/user` | No | Register new user |
| POST | `/api/v1/login` | No | Login, get JWT token |
| POST | `/api/v1/refresh` | Cookie | Refresh access token |
| POST | `/api/v1/logout` | Yes | Invalidate token |
| GET | `/api/v1/user/me/` | Yes | Get current user |
| GET | `/api/v1/users` | No | List all users |
| GET | `/api/v1/user/{username}` | No | Get user by username |
| GET | `/api/v1/health` | No | Health check |

---

## Adding New Features

### Step 1: Create Model

`src/app/models/product.py`:
```python
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db.database import Base
from ..core.db.models import UUIDMixin, TimestampMixin, SoftDeleteMixin

class Product(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True, init=False)
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
```

Register in `src/app/models/__init__.py`:
```python
from .product import Product
```

### Step 2: Create Schema

`src/app/schemas/product.py`:
```python
from pydantic import BaseModel, Field

class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price: int = Field(gt=0)

class ProductRead(BaseModel):
    id: int
    name: str
    price: int
    user_id: int

class ProductCreateInternal(ProductCreate):
    user_id: int
```

### Step 3: Create CRUD

`src/app/crud/crud_product.py`:
```python
from fastcrud import FastCRUD
from ..models.product import Product
from ..schemas.product import ProductCreateInternal, ProductRead

CRUDProduct = FastCRUD[Product, ProductCreateInternal, ProductRead]
crud_product = CRUDProduct(Product)
```

### Step 4: Create Endpoints

`src/app/api/v1/products.py`:
```python
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.dependencies import get_current_user
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...crud.crud_product import crud_product
from ...schemas.product import ProductCreate, ProductCreateInternal, ProductRead

router = APIRouter(tags=["products"])

@router.post("/product", response_model=ProductRead, status_code=201)
async def create_product(
    product: ProductCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
):
    """Create a new product (requires authentication)."""
    product_internal = ProductCreateInternal(
        **product.model_dump(),
        user_id=current_user["id"]
    )
    return await crud_product.create(db=db, object=product_internal)

@router.get("/products", response_model=list[ProductRead])
async def get_my_products(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
):
    """Get all products for current user."""
    result = await crud_product.get_multi(db=db, user_id=current_user["id"])
    return result["data"]

@router.get("/product/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
):
    """Get a specific product."""
    product = await crud_product.get(db=db, id=product_id, user_id=current_user["id"])
    if not product:
        raise NotFoundException("Product not found")
    return product

@router.delete("/product/{product_id}", status_code=204)
async def delete_product(
    product_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
):
    """Delete a product."""
    await crud_product.delete(db=db, id=product_id, user_id=current_user["id"])
```

### Step 5: Register Router

In `src/app/api/v1/__init__.py`, add:
```python
from .products import router as products_router

router.include_router(products_router)
```

### Step 6: Create Migration

```bash
cd src
uv run alembic revision --autogenerate -m "Add product table"
uv run alembic upgrade head
```

---

## Auth Dependencies

```python
from ...api.dependencies import get_current_user, get_current_superuser

# Requires login
@router.get("/protected")
async def protected(current_user: Annotated[dict, Depends(get_current_user)]):
    return {"user": current_user["username"]}

# Requires admin
@router.get("/admin-only")
async def admin_only(current_user: Annotated[dict, Depends(get_current_superuser)]):
    return {"admin": current_user["username"]}
```

---

## Environment Variables

Key settings in `src/.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_SERVER` | Database host | localhost |
| `POSTGRES_USER` | Database user | postgres |
| `POSTGRES_PASSWORD` | Database password | - |
| `POSTGRES_DB` | Database name | postgres |
| `SECRET_KEY` | JWT signing key | - |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token validity | 60 |
| `ADMIN_USERNAME` | Initial admin | admin |
| `ADMIN_PASSWORD` | Initial admin password | - |

---

## Common Commands

```bash
# Start server
uv run uvicorn src.app.main:app --reload --port 8000

# Start Redis
docker start redis

# Stop Redis
docker stop redis

# Create migration after model changes
cd src && uv run alembic revision --autogenerate -m "Description"

# Apply migrations
cd src && uv run alembic upgrade head

# Rollback one migration
cd src && uv run alembic downgrade -1

# View migration history
cd src && uv run alembic history
```

---

## Useful Patterns

### Public vs Protected Endpoints

```python
# Public - no auth needed
@router.get("/public")
async def public_endpoint():
    return {"message": "Anyone can see this"}

# Protected - requires valid token
@router.get("/private")
async def private_endpoint(
    current_user: Annotated[dict, Depends(get_current_user)]
):
    return {"message": f"Hello {current_user['username']}"}
```

### Pagination

```python
from fastcrud import PaginatedListResponse, compute_offset, paginated_response

@router.get("/items", response_model=PaginatedListResponse[ItemRead])
async def list_items(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    page: int = 1,
    items_per_page: int = 10
):
    data = await crud_items.get_multi(
        db=db,
        offset=compute_offset(page, items_per_page),
        limit=items_per_page
    )
    return paginated_response(crud_data=data, page=page, items_per_page=items_per_page)
```

### Soft Delete

Models with `SoftDeleteMixin` use soft delete by default:
```python
# Soft delete (sets is_deleted=True)
await crud_product.delete(db=db, id=product_id)

# Hard delete (removes from database)
await crud_product.db_delete(db=db, id=product_id)

# Query only non-deleted
await crud_product.get_multi(db=db, is_deleted=False)
```

---

## Data Aggregator

A plugin-based system for fetching financial data from multiple sources.

### API Endpoint

```
GET /api/v1/data/{source}/{data_type}?ticker={ticker}&params={json_params}
```

### Available Sources

| Source | Data Types | Description |
|--------|------------|-------------|
| `yahoo_finance` | `quote`, `chart`, `extended`, `earnings`, `stats`, `ratings` | Stock data from Yahoo Finance |
| `finviz` | `gainers`, `losers`, `unusual_volume`, `insider` | Market screener data from Finviz |
| `alpha_vantage` | `vix`, `economic_calendar`, `sector_performance` | Market indicators and economic data |

### Yahoo Finance Data Types

| Data Type | Description | Key Fields |
|-----------|-------------|------------|
| `quote` | Current price and basic info | price, change, volume, 52w high/low |
| `chart` | Historical OHLCV data | timestamps, open, high, low, close, volume |
| `extended` | Pre-market & after-hours | pre_market price/change, post_market price/change |
| `earnings` | Earnings calendar & history | next_earnings_date, EPS estimates, surprise history |
| `stats` | Key statistics | float, short interest, avg volume, PE ratio, beta |
| `ratings` | Analyst ratings & targets | recommendations, price targets, recent upgrades/downgrades |

### Finviz Data Types

| Data Type | Description | Key Fields |
|-----------|-------------|------------|
| `gainers` | Top gaining stocks | ticker, company, sector, price, change, volume |
| `losers` | Top losing stocks | ticker, company, sector, price, change, volume |
| `unusual_volume` | Stocks with unusual volume | ticker, company, sector, price, change, volume |
| `insider` | Recent insider trades | ticker, owner, relationship, transaction, value |

### Alpha Vantage Data Types

| Data Type | Description | Key Fields |
|-----------|-------------|------------|
| `vix` | VIX Fear Index | current, change, sentiment (Extreme Fear to Complacency) |
| `economic_calendar` | Upcoming economic events | date, event, country, impact, estimate |
| `sector_performance` | Sector ETF performance | sectors with change %, leaders, laggards |

### Usage Examples

```bash
# Get current quote
curl "http://localhost:8000/api/v1/data/yahoo_finance/quote?ticker=AAPL" \
  -H "Authorization: Bearer <token>"

# Get historical chart (1 month, daily)
curl "http://localhost:8000/api/v1/data/yahoo_finance/chart?ticker=AAPL" \
  -H "Authorization: Bearer <token>"

# Chart with custom interval/range
curl "http://localhost:8000/api/v1/data/yahoo_finance/chart?ticker=AAPL&params={\"interval\":\"1h\",\"range\":\"5d\"}" \
  -H "Authorization: Bearer <token>"

# Pre-market/after-hours data
curl "http://localhost:8000/api/v1/data/yahoo_finance/extended?ticker=AAPL" \
  -H "Authorization: Bearer <token>"

# Earnings data (next date, estimates, history)
curl "http://localhost:8000/api/v1/data/yahoo_finance/earnings?ticker=AAPL" \
  -H "Authorization: Bearer <token>"

# Key stats (float, short interest, volume ratios)
curl "http://localhost:8000/api/v1/data/yahoo_finance/stats?ticker=AAPL" \
  -H "Authorization: Bearer <token>"

# Analyst ratings and price targets
curl "http://localhost:8000/api/v1/data/yahoo_finance/ratings?ticker=AAPL" \
  -H "Authorization: Bearer <token>"

# Batch request (multiple tickers)
curl "http://localhost:8000/api/v1/data/yahoo_finance/quote?ticker=AAPL,MSFT,GOOG" \
  -H "Authorization: Bearer <token>"

# List available sources
curl "http://localhost:8000/api/v1/data/sources"

# --- Finviz ---

# Top gainers (market-wide, no ticker needed)
curl "http://localhost:8000/api/v1/data/finviz/gainers?ticker=all" \
  -H "Authorization: Bearer <token>"

# Top losers
curl "http://localhost:8000/api/v1/data/finviz/losers?ticker=all" \
  -H "Authorization: Bearer <token>"

# Unusual volume stocks
curl "http://localhost:8000/api/v1/data/finviz/unusual_volume?ticker=all" \
  -H "Authorization: Bearer <token>"

# Recent insider trades (all)
curl "http://localhost:8000/api/v1/data/finviz/insider?ticker=all" \
  -H "Authorization: Bearer <token>"

# Insider trades for specific ticker
curl "http://localhost:8000/api/v1/data/finviz/insider?ticker=AAPL" \
  -H "Authorization: Bearer <token>"

# Filter insider trades by type (buy/sell)
curl "http://localhost:8000/api/v1/data/finviz/insider?ticker=all&params={\"type\":\"buy\"}" \
  -H "Authorization: Bearer <token>"

# --- Alpha Vantage ---

# VIX Fear Index
curl "http://localhost:8000/api/v1/data/alpha_vantage/vix?ticker=all" \
  -H "Authorization: Bearer <token>"

# Economic calendar (next 7 days)
curl "http://localhost:8000/api/v1/data/alpha_vantage/economic_calendar?ticker=all" \
  -H "Authorization: Bearer <token>"

# Economic calendar (custom range)
curl "http://localhost:8000/api/v1/data/alpha_vantage/economic_calendar?ticker=all&params={\"days\":14}" \
  -H "Authorization: Bearer <token>"

# Sector ETF performance
curl "http://localhost:8000/api/v1/data/alpha_vantage/sector_performance?ticker=all" \
  -H "Authorization: Bearer <token>"
```

### Response Format

```json
{
  "success": true,
  "cached": false,
  "data": { ... },
  "errors": null
}
```

### Adding a New Data Source

See [docs/ADDING_DATA_SOURCES.md](docs/ADDING_DATA_SOURCES.md) for detailed instructions.

**Quick overview:**

1. Create folder: `src/app/data_sources/{source_name}/`
2. Create handlers in `handlers/` for each data type
3. Create `source.py` with `@register_source` decorator
4. Import in `src/app/data_sources/__init__.py`

### Project Structure (Data Aggregator)

```
src/app/
├── data_sources/
│   ├── __init__.py          # Source registry
│   ├── base.py              # Base class
│   ├── yahoo_finance/       # Yahoo Finance source
│   │   ├── source.py
│   │   └── handlers/
│   │       ├── auth.py      # Yahoo crumb authentication
│   │       ├── quote.py     # Current price data
│   │       ├── chart.py     # Historical OHLCV
│   │       ├── extended.py  # Pre/post market
│   │       ├── earnings.py  # Earnings calendar
│   │       ├── stats.py     # Key statistics
│   │       └── ratings.py   # Analyst ratings
│   ├── finviz/              # Finviz market screener
│   │   ├── source.py
│   │   └── handlers/
│   │       ├── gainers.py   # Top gainers
│   │       ├── losers.py    # Top losers
│   │       ├── unusual_volume.py  # Unusual volume
│   │       └── insider.py   # Insider trading
│   └── alpha_vantage/       # Alpha Vantage / FMP
│       ├── source.py
│       └── handlers/
│           ├── vix.py       # VIX Fear Index
│           ├── economic_calendar.py  # Economic events
│           └── sector_performance.py # Sector ETFs
├── services/
│   ├── http_client.py       # HTTP with retry logic
│   ├── proxy_manager.py     # Rotating proxy support
│   └── cache_service.py     # Redis cache wrapper
└── logs/
    └── data_aggregator.log  # Data operations log
```

### Configuration

Add to `src/.env`:

```env
# Proxies (optional, comma-separated)
PROXY_LIST=http://user:pass@host1:port,http://user:pass@host2:port

# Alpha Vantage API key (free tier: 25 calls/day)
ALPHA_VANTAGE_API_KEY=your_api_key_here

# Financial Modeling Prep API key (free tier: 250 calls/day)
FMP_API_KEY=your_api_key_here
```

**Get free API keys:**
- Alpha Vantage: https://www.alphavantage.co/support/#api-key
- FMP: https://financialmodelingprep.com/developer/docs/

### Caching

- Results cached in Redis for 5 minutes (configurable in `cache_service.py`)
- Single ticker requests are cached
- Batch requests are not cached (each ticker fetched fresh)

### Logging

Data operations logged to `src/app/logs/data_aggregator.log`

---

## Production Deployment

### Overview

Your FastAPI app can be deployed using:
- **Systemd service** (bare metal/VPS)
- **Docker Compose** (containerized)
- **PM2** (process manager)
- **Supervisord** (Python process manager)

**Recommended:** Systemd (simple, reliable) or Docker Compose (portable)

---

### Option 1: Systemd Service (Recommended)

**Use when:** Deploying to VPS/bare metal server (Ubuntu, Debian, CentOS)

#### 1. Clone Repository

```bash
# On your server
cd /home/your-username
git clone https://github.com/your-username/FastAPI-boilerplate.git
cd FastAPI-boilerplate
```

#### 2. Install Dependencies

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # or ~/.zshrc

# Install dependencies
uv sync --no-dev

# Setup environment
cp src/.env.example src/.env
# Edit src/.env with production values
nano src/.env
```

#### 3. Run Migrations

```bash
cd src
uv run alembic upgrade head
cd ..
```

#### 4. Create Systemd Service

Create `/etc/systemd/system/trading-api.service`:

```ini
[Unit]
Description=Trading Data Hub API
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=your-username
Group=your-username
WorkingDirectory=/home/your-username/FastAPI-boilerplate/src
Environment="PATH=/home/your-username/.local/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/your-username/.local/bin/uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10
StandardOutput=append:/var/log/trading-api/access.log
StandardError=append:/var/log/trading-api/error.log

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/your-username/FastAPI-boilerplate/src/static/charts
ReadWritePaths=/var/log/trading-api

[Install]
WantedBy=multi-user.target
```

#### 5. Create Log Directory

```bash
sudo mkdir -p /var/log/trading-api
sudo chown your-username:your-username /var/log/trading-api
```

#### 6. Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable trading-api

# Start service
sudo systemctl start trading-api

# Check status
sudo systemctl status trading-api

# View logs
sudo journalctl -u trading-api -f
```

#### 7. Service Management

```bash
# Start
sudo systemctl start trading-api

# Stop
sudo systemctl stop trading-api

# Restart
sudo systemctl restart trading-api

# View logs (live)
sudo journalctl -u trading-api -f

# View last 100 lines
sudo journalctl -u trading-api -n 100

# Disable auto-start
sudo systemctl disable trading-api
```

---

### Option 2: Docker Compose (Containerized)

**Use when:** You want isolated, portable deployment

#### 1. Install Docker

```bash
# Install Docker Engine (Ubuntu)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt-get install docker-compose-plugin

# Add user to docker group (no sudo needed)
sudo usermod -aG docker $USER
newgrp docker
```

#### 2. Clone and Configure

```bash
git clone https://github.com/your-username/FastAPI-boilerplate.git
cd FastAPI-boilerplate

# Setup environment
cp src/.env.example src/.env
nano src/.env
```

#### 3. Update docker-compose.yml

Ensure `docker-compose.yml` has production settings:

```yaml
version: '3.8'

services:
  api:
    build: .
    container_name: trading-api
    ports:
      - "8000:8000"
    environment:
      - POSTGRES_SERVER=${POSTGRES_SERVER}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./src/static/charts:/app/src/static/charts
    depends_on:
      - redis
    restart: always
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

  redis:
    image: redis:7-alpine
    container_name: trading-redis
    restart: always
    volumes:
      - redis-data:/data

volumes:
  redis-data:
```

#### 4. Deploy

```bash
# Build and start (detached mode)
docker compose up -d --build

# View logs
docker compose logs -f api

# Stop
docker compose down

# Restart
docker compose restart api

# View running containers
docker compose ps
```

#### 5. Run Migrations (Docker)

```bash
# One-time migration
docker compose exec api uv run alembic upgrade head

# Create admin user
docker compose exec api uv run python -m scripts.create_first_superuser
```

---

### Option 3: PM2 Process Manager

**Use when:** You prefer Node.js-style process management

#### 1. Install PM2

```bash
npm install -g pm2
```

#### 2. Create ecosystem.config.js

```javascript
module.exports = {
  apps: [{
    name: 'trading-api',
    script: '/home/your-username/.local/bin/uv',
    args: 'run uvicorn app.main:app --host 0.0.0.0 --port 8000',
    cwd: '/home/your-username/FastAPI-boilerplate/src',
    instances: 4,
    exec_mode: 'cluster',
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      NODE_ENV: 'production'
    }
  }]
};
```

#### 3. Start with PM2

```bash
# Start
pm2 start ecosystem.config.js

# Auto-start on reboot
pm2 startup
pm2 save

# Management commands
pm2 status
pm2 logs trading-api
pm2 restart trading-api
pm2 stop trading-api
pm2 delete trading-api
```

---

### Nginx Reverse Proxy (Recommended)

Use Nginx to:
- Serve as reverse proxy
- Handle SSL/TLS (HTTPS)
- Serve static files directly
- Load balancing
- Rate limiting

#### 1. Install Nginx

```bash
sudo apt update
sudo apt install nginx
```

#### 2. Create Nginx Config

Create `/etc/nginx/sites-available/trading-api`:

```nginx
upstream trading_api {
    server 127.0.0.1:8000;
    # Add more workers for load balancing:
    # server 127.0.0.1:8001;
    # server 127.0.0.1:8002;
}

# Rate limiting
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    # SSL certificates (use certbot for Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Logs
    access_log /var/log/nginx/trading-api-access.log;
    error_log /var/log/nginx/trading-api-error.log;

    # Max upload size
    client_max_body_size 10M;

    # Proxy to FastAPI
    location / {
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://trading_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Serve static files directly (faster than FastAPI)
    location /static/ {
        alias /home/your-username/FastAPI-boilerplate/src/static/;
        expires 1h;
        add_header Cache-Control "public, immutable";
    }

    # Health check (no rate limit)
    location /api/v1/health {
        proxy_pass http://trading_api;
        access_log off;
    }
}
```

#### 3. Enable Site

```bash
# Create symlink
sudo ln -s /etc/nginx/sites-available/trading-api /etc/nginx/sites-enabled/

# Test config
sudo nginx -t

# Reload
sudo systemctl reload nginx
```

#### 4. Setup SSL with Let's Encrypt

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Auto-renewal (certbot sets this up automatically)
sudo certbot renew --dry-run
```

---

### Environment Variables (Production)

Update `src/.env` for production:

```env
# Database (use Neon, AWS RDS, or DigitalOcean managed DB)
POSTGRES_SERVER=your-db-host.neon.tech
POSTGRES_USER=your-db-user
POSTGRES_PASSWORD=strong-random-password-here
POSTGRES_DB=trading_hub_prod
POSTGRES_PORT=5432

# Security
SECRET_KEY=generate-64-char-random-string-here
REFRESH_SECRET_KEY=generate-another-64-char-random-string
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# Admin (change default credentials!)
ADMIN_USERNAME=your-admin-username
ADMIN_PASSWORD=very-strong-password-here
ADMIN_EMAIL=admin@your-domain.com

# Redis
REDIS_URL=redis://localhost:6379

# API Keys (external services)
ALPHA_VANTAGE_API_KEY=your-api-key
FMP_API_KEY=your-api-key

# Proxies (optional, for production scraping)
PROXY_LIST=http://user:pass@proxy1:port,http://user:pass@proxy2:port

# Environment
ENVIRONMENT=production
DEBUG=False

# CORS (your frontend domain)
CORS_ORIGINS=["https://your-frontend.com"]

# Logging
LOG_LEVEL=INFO
```

**Generate secure keys:**
```bash
# SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# REFRESH_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

### Security Checklist

- [ ] Change default admin credentials
- [ ] Use strong, unique SECRET_KEY and REFRESH_SECRET_KEY
- [ ] Enable HTTPS (SSL/TLS)
- [ ] Set up firewall (UFW):
  ```bash
  sudo ufw allow 22    # SSH
  sudo ufw allow 80    # HTTP
  sudo ufw allow 443   # HTTPS
  sudo ufw enable
  ```
- [ ] Restrict database access (allow only your server IP)
- [ ] Use environment variables (never hardcode secrets)
- [ ] Set `DEBUG=False` in production
- [ ] Enable rate limiting (Nginx or FastAPI)
- [ ] Regular security updates:
  ```bash
  sudo apt update && sudo apt upgrade
  ```
- [ ] Backup database regularly (see below)
- [ ] Monitor logs for suspicious activity
- [ ] Use non-root user for running services

---

### Monitoring & Logs

#### Application Logs

**Systemd:**
```bash
# Live logs
sudo journalctl -u trading-api -f

# Last 100 lines
sudo journalctl -u trading-api -n 100

# Logs from today
sudo journalctl -u trading-api --since today

# Errors only
sudo journalctl -u trading-api -p err
```

**Docker:**
```bash
# Live logs
docker compose logs -f api

# Last 100 lines
docker compose logs --tail 100 api
```

#### Nginx Logs

```bash
# Access logs
sudo tail -f /var/log/nginx/trading-api-access.log

# Error logs
sudo tail -f /var/log/nginx/trading-api-error.log

# Rotate logs (prevent disk full)
sudo logrotate -f /etc/logrotate.d/nginx
```

#### Health Monitoring

Create a simple health check script:

```bash
#!/bin/bash
# /home/your-username/health-check.sh

ENDPOINT="http://localhost:8000/api/v1/health"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" $ENDPOINT)

if [ "$STATUS" -eq 200 ]; then
    echo "$(date): API is healthy (HTTP $STATUS)"
else
    echo "$(date): API is DOWN (HTTP $STATUS)" | tee -a /var/log/health-check.log
    # Restart service
    sudo systemctl restart trading-api
    # Send alert (optional)
    # curl -X POST https://hooks.slack.com/... -d '{"text":"API is down!"}'
fi
```

Add to crontab (check every 5 minutes):
```bash
crontab -e
# Add:
*/5 * * * * /home/your-username/health-check.sh >> /var/log/health-check.log 2>&1
```

---

### Backup & Recovery

#### Database Backup

**Automated daily backup:**

Create `/home/your-username/backup-db.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/home/your-username/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="trading_hub_prod"

mkdir -p $BACKUP_DIR

# Neon/Postgres dump
PGPASSWORD="your-password" pg_dump \
  -h your-db-host.neon.tech \
  -U your-db-user \
  -d $DB_NAME \
  -Fc > $BACKUP_DIR/db_backup_$DATE.dump

# Keep only last 7 days
find $BACKUP_DIR -name "db_backup_*.dump" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/db_backup_$DATE.dump"
```

Make executable and add to crontab:
```bash
chmod +x /home/your-username/backup-db.sh
crontab -e
# Add (daily at 2 AM):
0 2 * * * /home/your-username/backup-db.sh >> /var/log/db-backup.log 2>&1
```

#### Restore from Backup

```bash
# Restore
PGPASSWORD="your-password" pg_restore \
  -h your-db-host.neon.tech \
  -U your-db-user \
  -d $DB_NAME \
  --clean \
  /path/to/backup.dump
```

---

### Performance Tuning

#### FastAPI Workers

Adjust workers based on CPU cores:

```bash
# Formula: (2 x CPU cores) + 1
# For 4 cores: 9 workers

# Systemd: Edit /etc/systemd/system/trading-api.service
ExecStart=... --workers 9

# Docker: Edit docker-compose.yml
command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 9
```

#### Redis Memory Limit

Edit `/etc/redis/redis.conf`:
```
maxmemory 256mb
maxmemory-policy allkeys-lru
```

#### Database Connection Pool

In `src/app/core/db/database.py`, tune pool size:
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,        # Increase for high traffic
    max_overflow=40,     # Total max connections: 20 + 40 = 60
    pool_pre_ping=True,  # Verify connections before use
)
```

---

### Troubleshooting

**Service won't start:**
```bash
# Check logs
sudo journalctl -u trading-api -n 50

# Check if port is in use
sudo lsof -i :8000

# Check file permissions
ls -la /home/your-username/FastAPI-boilerplate/
```

**Database connection errors:**
```bash
# Test connection
PGPASSWORD="your-password" psql \
  -h your-db-host.neon.tech \
  -U your-db-user \
  -d trading_hub_prod
```

**Redis not connecting:**
```bash
# Check Redis
redis-cli ping  # Should return PONG

# Restart Redis
sudo systemctl restart redis
```

**502 Bad Gateway (Nginx):**
```bash
# Check if FastAPI is running
curl http://localhost:8000/api/v1/health

# Check Nginx logs
sudo tail -f /var/log/nginx/trading-api-error.log
```

---

### Updates & Maintenance

**Deploying new version:**

```bash
# Pull latest code
cd /home/your-username/FastAPI-boilerplate
git pull origin main

# Install new dependencies (if any)
uv sync --no-dev

# Run migrations (if any)
cd src && uv run alembic upgrade head && cd ..

# Restart service
sudo systemctl restart trading-api

# Check status
sudo systemctl status trading-api
```

**Zero-downtime deployment (advanced):**

1. Run multiple workers on different ports (8000, 8001, 8002)
2. Use Nginx upstream load balancing
3. Stop one worker, update, restart
4. Repeat for other workers

---

### Quick Reference

**Systemd commands:**
```bash
sudo systemctl start trading-api      # Start
sudo systemctl stop trading-api       # Stop
sudo systemctl restart trading-api    # Restart
sudo systemctl status trading-api     # Status
sudo journalctl -u trading-api -f    # Logs
```

**Docker commands:**
```bash
docker compose up -d                  # Start
docker compose down                   # Stop
docker compose restart api            # Restart
docker compose logs -f api            # Logs
```

**Nginx commands:**
```bash
sudo nginx -t                         # Test config
sudo systemctl reload nginx           # Reload
sudo systemctl restart nginx          # Restart
```
