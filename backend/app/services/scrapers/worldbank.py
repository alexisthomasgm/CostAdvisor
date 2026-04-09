"""
World Bank Commodity Price scrapers.

Uses the World Bank API v2 for commodity price data (free, no auth).

Docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/898581
"""
import httpx

from app.services.scraper import BaseScraper, ScrapedDataPoint
from app.config import get_settings


class WorldBankScraper(BaseScraper):
    """
    Base scraper for World Bank commodity price indicators.

    Subclasses set:
      - commodity_name: maps to CommodityIndex.name
      - INDICATOR: World Bank indicator ID
    """

    INDICATOR: str = ""

    def __init__(self):
        super().__init__(self.commodity_name)

    async def fetch(self) -> list[ScrapedDataPoint]:
        settings = get_settings()
        base = settings.worldbank_api_base
        # Fetch last 5 years of monthly data
        url = f"{base}/country/all/indicator/{self.INDICATOR}"
        params = {
            "format": "json",
            "date": "2021:2026",
            "per_page": "500",
            "source": "6",  # International Financial Statistics
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()

        data = resp.json()
        return self._parse_response(data)

    @staticmethod
    def _parse_response(data: list | dict) -> list[ScrapedDataPoint]:
        """Parse World Bank API v2 JSON response into quarterly data points."""
        # WB API v2 returns [metadata, data_list]
        if isinstance(data, list) and len(data) >= 2:
            records = data[1]
        elif isinstance(data, dict):
            records = data.get("data", [])
        else:
            return []

        if not records:
            return []

        quarterly: dict[tuple[int, int], list[float]] = {}
        for record in records:
            if record is None:
                continue
            val = record.get("value")
            date_str = record.get("date", "")
            if val is None or not date_str:
                continue
            try:
                val = float(val)
            except (ValueError, TypeError):
                continue

            try:
                if "M" in date_str:
                    # Monthly: "2024M03"
                    parts = date_str.split("M")
                    year = int(parts[0])
                    month = int(parts[1])
                    quarter = (month - 1) // 3 + 1
                elif "Q" in date_str:
                    parts = date_str.split("Q")
                    year = int(parts[0])
                    quarter = int(parts[1])
                elif len(date_str) == 4:
                    year = int(date_str)
                    quarter = 4  # Annual → Q4
                else:
                    continue
            except (ValueError, IndexError):
                continue

            quarterly.setdefault((year, quarter), []).append(val)

        results = []
        for (year, quarter), vals in sorted(quarterly.items()):
            avg = sum(vals) / len(vals)
            results.append(ScrapedDataPoint(
                region="GLOBAL", year=year, quarter=quarter,
                value=round(avg, 4),
            ))
        return results


# ── Concrete World Bank scrapers ───────────────────────────────────────

class WorldBankUreaScraper(WorldBankScraper):
    """Urea, granular, Black Sea, USD/mt (World Bank Commodity Prices)."""
    commodity_name = "Urea"
    INDICATOR = "CMDT.UREA.USD"
