# src/app/api/v1/data.py
"""Data aggregator endpoints."""

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, HTTPException, Request

from ...api.dependencies import get_current_user
from ...data_sources import get_source, list_sources, get_source_info
from ...services.cache_service import cache_service

logger = logging.getLogger("data_aggregator")

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/sources")
async def get_available_sources() -> dict[str, Any]:
    """List all available data sources and their supported data types."""
    sources = []
    for name in list_sources():
        info = get_source_info(name)
        if info:
            sources.append(info)

    return {"sources": sources}


@router.get("/{source}/{data_type}")
async def fetch_data(
    request: Request,
    source: str,
    data_type: str,
    ticker: Annotated[str, Query(description="Ticker symbol(s), comma-separated for batch")],
    params: Annotated[str | None, Query(description="JSON-encoded parameters")] = None,
    chart: Annotated[bool, Query(description="Generate chart if supported")] = False,
    current_user: Annotated[dict, Depends(get_current_user)] = None,
) -> dict[str, Any]:
    """
    Fetch data from a source.

    - **source**: Data source (e.g., yahoo_finance)
    - **data_type**: Type of data (e.g., quote, chart)
    - **ticker**: Stock symbol(s), comma-separated for batch
    - **params**: JSON-encoded parameters (e.g., {"interval": "1d", "range": "1mo"})
    - **chart**: Generate chart if supported (default: false)
    """
    # Get source
    data_source = get_source(source)
    if not data_source:
        available = list_sources()
        raise HTTPException(
            status_code=404,
            detail=f"Source '{source}' not found. Available: {available}",
        )

    # Check data type
    if not data_source.supports(data_type):
        raise HTTPException(
            status_code=400,
            detail=f"Source '{source}' does not support '{data_type}'. Supported: {data_source.supported_data_types}",
        )

    # Parse params
    parsed_params = None
    if params:
        try:
            parsed_params = json.loads(params)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in params")

    # Ensure parsed_params is dict
    if parsed_params is None:
        parsed_params = {}

    # Merge chart param into parsed_params
    if chart:
        parsed_params["chart"] = True

    # Parse tickers
    tickers = [t.strip().upper() for t in ticker.split(",") if t.strip()]
    if not tickers:
        raise HTTPException(status_code=400, detail="No valid tickers provided")

    # Check cache for single ticker
    if len(tickers) == 1:
        cached = await cache_service.get(source, data_type, tickers[0], parsed_params)
        if cached:
            logger.info(f"Cache hit: {source}/{data_type}/{tickers[0]}")
            return {
                "success": True,
                "cached": True,
                "data": cached,
            }

    # Fetch from source
    logger.info(f"Fetching: {source}/{data_type} for {tickers}")

    ticker_input = tickers[0] if len(tickers) == 1 else tickers
    result = await data_source.fetch(data_type, ticker_input, parsed_params, request=request)

    # Cache single ticker results
    if len(tickers) == 1 and result.get("success") and result.get("data"):
        await cache_service.set(source, data_type, tickers[0], result["data"], parsed_params)

    return {
        "success": result.get("success", False),
        "cached": False,
        "data": result.get("data"),
        "errors": result.get("errors"),
    }
