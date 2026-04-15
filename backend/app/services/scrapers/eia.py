"""
EIA (U.S. Energy Information Administration) scrapers.

EIA provides free access with an API key. Get one at:
https://www.eia.gov/opendata/register.php

Uses the v2 API. Docs: https://www.eia.gov/opendata/documentation.php

Data is public domain (U.S. government work).
"""
import httpx

from app.services.scraper import BaseScraper, ScrapedDataPoint
from app.config import get_settings


class EIAScraper(BaseScraper):
    """
    Base scraper for EIA petroleum spot-price series.

    Subclasses set:
      - commodity_name: maps to CommodityIndex.name
      - SERIES_ID: EIA series facet (e.g. "RBRTE" for Brent)
      - FREQUENCY: "monthly" (default), "weekly", or "daily"
    """

    SERIES_ID: str = ""
    FREQUENCY: str = "monthly"
    EIA_BASE_URL = "https://api.eia.gov/v2/petroleum/pri/spt/data/"

    def __init__(self):
        super().__init__(self.commodity_name)

    async def fetch(self) -> list[ScrapedDataPoint]:
        settings = get_settings()
        api_key = settings.eia_api_key
        if not api_key:
            return []  # Gracefully skip if no API key configured

        params = {
            "api_key": api_key,
            "frequency": self.FREQUENCY,
            "data[0]": "value",
            "facets[series][]": self.SERIES_ID,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": "120",  # ~10 years of monthly data
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(self.EIA_BASE_URL, params=params)
            resp.raise_for_status()

        return self._parse_response(resp.json())

    @staticmethod
    def _parse_response(data: dict) -> list[ScrapedDataPoint]:
        """Parse EIA v2 JSON response into quarterly data points."""
        rows = data.get("response", {}).get("data", [])
        if not rows:
            return []

        quarterly: dict[tuple[int, int], list[float]] = {}
        for row in rows:
            period = row.get("period", "")
            value = row.get("value")
            if not period or value is None:
                continue
            try:
                year = int(period[:4])
                month = int(period[5:7])
                val = float(value)
            except (ValueError, IndexError, TypeError):
                continue

            quarter = (month - 1) // 3 + 1
            quarterly.setdefault((year, quarter), []).append(val)

        results = []
        for (year, quarter), vals in sorted(quarterly.items()):
            avg = sum(vals) / len(vals)
            results.append(ScrapedDataPoint(
                region="GLOBAL", year=year, quarter=quarter,
                value=round(avg, 4),
            ))
        return results


# ── Concrete EIA scrapers ─────────────────────────────────────────────

class EIABrentOilScraper(EIAScraper):
    """Europe Brent Spot Price FOB, USD/bbl (EIA public domain data)."""
    commodity_name = "Brent Crude Oil (EIA)"
    SERIES_ID = "RBRTE"
