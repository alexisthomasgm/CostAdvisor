"""
Scraper subpackage — one module per external data source.
All scraper classes subclass BaseScraper from app.services.scraper.
"""
from app.services.scrapers.eurostat import (
    EurostatDirectLaborScraper,
    EurostatPPIManufacturingScraper,
    EurostatEnergyUtilitiesScraper,
    EurostatLaborEuropeScraper,
    EurostatEnergieEuropeScraper,
    EurostatManufacturingGoodsFranceScraper,
)
from app.services.scrapers.fred import (
    FREDECIScraper,
    FREDPPIChemicalsScraper,
    FREDIndustrialProductionScraper,
)
from app.services.scrapers.ecb import (
    ECBEURUSDScraper,
    ECBGBPEURScraper,
    ECBCNYEURScraper,
    ECBJPYEURScraper,
    ECBIDREURScraper,
    ECBPHPEURScraper,
)
from app.services.scrapers.worldbank import (
    WorldBankUreaScraper,
)

__all__ = [
    "EurostatDirectLaborScraper",
    "EurostatPPIManufacturingScraper",
    "EurostatEnergyUtilitiesScraper",
    "EurostatLaborEuropeScraper",
    "EurostatEnergieEuropeScraper",
    "EurostatManufacturingGoodsFranceScraper",
    "FREDECIScraper",
    "FREDPPIChemicalsScraper",
    "FREDIndustrialProductionScraper",
    "ECBEURUSDScraper",
    "ECBGBPEURScraper",
    "ECBCNYEURScraper",
    "ECBJPYEURScraper",
    "ECBIDREURScraper",
    "ECBPHPEURScraper",
    "WorldBankUreaScraper",
]
