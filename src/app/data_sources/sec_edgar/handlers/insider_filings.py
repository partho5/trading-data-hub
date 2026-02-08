# src/app/data_sources/sec_edgar/handlers/insider_filings.py
"""Handler for SEC EDGAR Form 4 insider trading filings.

Uses the EDGAR Full-Text Search System (EFTS) — free, no API key needed.
Requires User-Agent with contact email per SEC policy.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from src.app.services import HttpClient

logger = logging.getLogger("data_aggregator")

EDGAR_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
SEC_USER_AGENT = "TradingDataHub/1.0 (admin@example.com)"


async def fetch_insider_filings(ticker: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch recent Form 4 insider trading filings from SEC EDGAR.

    Uses the EFTS full-text search API which is free and requires no key.
    SEC requires a User-Agent with contact email.

    Args:
        ticker: Optional - company name to filter
        params: Optional params:
            - days: Look back N days (default 1)
            - limit: Max results (default 20)

    Returns:
        Dict with recent insider filings
    """
    days = params.get("days", 1)
    limit = min(params.get("limit", 20), 50)

    today = datetime.now()
    start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")

    query_params = {
        "q": '"4"',
        "forms": "4",
        "dateRange": "custom",
        "startdt": start_date,
        "enddt": end_date,
    }

    headers = {"User-Agent": SEC_USER_AGENT}

    # SEC EDGAR is a public gov API — no proxy needed, and proxy IPs get blocked
    client = HttpClient(use_proxy=False, timeout=30)
    response = await client.get(EDGAR_EFTS_URL, headers=headers, params=query_params)
    data = response.json()

    hits = data.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    results = hits.get("hits", [])

    filings = []
    for hit in results[:limit]:
        source = hit.get("_source", {})
        display_names = source.get("display_names", [])

        # First name is typically the insider, second is the company
        insider_name = display_names[0] if display_names else ""
        company_name = display_names[1] if len(display_names) > 1 else ""

        # Clean up CIK from display name
        insider_name = insider_name.split("(CIK")[0].strip() if insider_name else ""
        company_name = company_name.split("(CIK")[0].strip() if company_name else ""

        # Filter by ticker/company if provided
        if ticker and ticker.lower() not in ("all", "any", ""):
            if ticker.upper() not in company_name.upper():
                continue

        filing_date = source.get("file_date", "")
        sics = source.get("sics", [])
        states = source.get("biz_states", [])
        accession = source.get("adsh", "")

        filings.append({
            "insider": insider_name,
            "company": company_name,
            "filing_date": filing_date,
            "form": source.get("form", "4"),
            "industry_sic": sics[0] if sics else "",
            "state": states[0] if states else "",
            "accession_number": accession,
            "filing_url": f"https://www.sec.gov/Archives/edgar/data/{accession.replace('-', '')[:10]}/{accession}.txt" if accession else "",
        })

    # Extract top companies with most filings
    company_counts: dict[str, int] = {}
    for f in filings:
        co = f["company"]
        if co:
            company_counts[co] = company_counts.get(co, 0) + 1
    top_companies = sorted(company_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "date_range": {"from": start_date, "to": end_date},
        "total_filings": total,
        "returned": len(filings),
        "filings": filings,
        "top_companies": [{"company": c, "filing_count": n} for c, n in top_companies],
    }
