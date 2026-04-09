"""
Eurostat SDMX-JSON scrapers for European statistics.

Eurostat provides free, unauthenticated access to its data via a REST SDMX API.
Response format is SDMX-JSON — different from INSEE's SDMX-ML XML.

Docs: https://wikis.ec.europa.eu/display/EUROSTATHELP/API+SDMX+2.1+-+data+query
"""
import httpx

from app.services.scraper import BaseScraper, ScrapedDataPoint
from app.config import get_settings


class EurostatScraper(BaseScraper):
    """
    Base scraper for Eurostat SDMX-JSON datasets.

    Subclasses set:
      - commodity_name: maps to CommodityIndex.name
      - DATAFLOW: Eurostat dataset ID (e.g. "lc_lci_r2_a")
      - FILTER_KEY: dot-separated dimension filter (e.g. "A.LCI_R2.I20.EU27_2020.EUR")
      - PARAMS: extra query params dict
    """

    DATAFLOW: str = ""
    FILTER_KEY: str = ""
    PARAMS: dict = {}

    def __init__(self):
        super().__init__(self.commodity_name)

    async def fetch(self) -> list[ScrapedDataPoint]:
        settings = get_settings()
        base = settings.eurostat_api_base
        url = f"{base}/data/{self.DATAFLOW}/{self.FILTER_KEY}"
        params = {
            "format": "JSON",
            "lang": "en",
            "lastNObservations": "24",
            **self.PARAMS,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()

        return self._parse_sdmx_json(resp.json())

    @staticmethod
    def _parse_sdmx_json(data: dict) -> list[ScrapedDataPoint]:
        """Parse Eurostat SDMX-JSON response into quarterly data points."""
        try:
            # Navigate the SDMX-JSON structure
            dimension = data["dimension"]
            time_dim = dimension.get("time") or dimension.get("TIME_PERIOD", {})
            time_categories = time_dim.get("category", {}).get("index", {})

            # Get the first (and usually only) series
            values = data.get("value", {})

            if not time_categories or not values:
                return []

            # Build time index → label mapping
            time_labels = {v: k for k, v in time_categories.items()}

            quarterly: dict[tuple[int, int], list[float]] = {}
            for idx_str, val in values.items():
                idx = int(idx_str)
                label = time_labels.get(idx, "")
                if not label or val is None:
                    continue

                try:
                    # Labels can be "2024-Q1", "2024Q1", "2024-03", "2024"
                    if "Q" in label:
                        parts = label.replace("-", "").replace("Q", " ").split()
                        year, quarter = int(parts[0]), int(parts[1])
                    elif len(label) == 7 and label[4] == "-":
                        # Monthly: "2024-03"
                        year = int(label[:4])
                        month = int(label[5:7])
                        quarter = (month - 1) // 3 + 1
                    elif len(label) == 4:
                        # Annual: "2024" → assign to Q4
                        year = int(label)
                        quarter = 4
                    else:
                        continue

                    quarterly.setdefault((year, quarter), []).append(float(val))
                except (ValueError, IndexError):
                    continue

            results = []
            for (year, quarter), vals in sorted(quarterly.items()):
                avg = sum(vals) / len(vals)
                results.append(ScrapedDataPoint(
                    region="GLOBAL", year=year, quarter=quarter,
                    value=round(avg, 4),
                ))
            return results

        except (KeyError, TypeError):
            return []


# ── Concrete Eurostat scrapers ─────────────────────────────────────────

class EurostatDirectLaborScraper(EurostatScraper):
    """EU27 labour cost index, total economy, EUR per hour."""
    commodity_name = "Direct Labor Costs"
    DATAFLOW = "lc_lci_r2_a"
    FILTER_KEY = "A.LCI_R2.TOTAL.EU27_2020.EUR"


class EurostatPPIManufacturingScraper(EurostatScraper):
    """PPI manufacturing, domestic market, EU27, index 2015=100."""
    commodity_name = "PPI Manufacturing Europe"
    DATAFLOW = "sts_inpp_m"
    FILTER_KEY = "M.I15.MIG_ING.EU27_2020.PRIX"


class EurostatEnergyUtilitiesScraper(EurostatScraper):
    """Electricity prices for non-household consumers, EU27, EUR/kWh."""
    commodity_name = "Energy & Utilities"
    DATAFLOW = "nrg_pc_203"
    FILTER_KEY = "S.N.MWH_LT20.EU27_2020"


class EurostatLaborEuropeScraper(EurostatScraper):
    """EU27 hourly labour costs, all NACE activities."""
    commodity_name = "Labor Europe"
    DATAFLOW = "lc_lci_r2_a"
    FILTER_KEY = "A.LCI_R2.TOTAL.EU27_2020.EUR"


class EurostatEnergieEuropeScraper(EurostatScraper):
    """Electricity prices for medium-size industrial consumers, EU27."""
    commodity_name = "Energie Europe"
    DATAFLOW = "nrg_pc_205"
    FILTER_KEY = "S.N.MWH_GE500.EU27_2020"


class EurostatManufacturingGoodsFranceScraper(EurostatScraper):
    """Industrial production index for manufacturing, France."""
    commodity_name = "Manufacturing Goods France"
    DATAFLOW = "sts_inpr_m"
    FILTER_KEY = "M.I15.MIG_ING.FR.PROD"
