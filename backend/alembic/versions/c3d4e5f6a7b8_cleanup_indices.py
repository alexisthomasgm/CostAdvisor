"""cleanup indices: remove fake, add real sources

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-19 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fake indices to remove entirely (all values were 1 with no real source)
REMOVE_INDICES = ['Alcohol', 'Manufacturing Overhead', 'Packaging', 'Logistics']

# Fake regional data to remove (keep only regions with real data)
REMOVE_REGIONAL = {
    'Aluminum': ['NA', 'Asia', 'Latam'],
    'Iron': ['NA', 'Asia', 'Latam'],
    'Chlorine': ['NA', 'Asia', 'Latam'],
    'Ammonia': ['NA', 'Asia', 'Latam'],
    'Oil Price': ['NA', 'Asia', 'Latam'],
    'Natural Gas': ['NA', 'Asia', 'Latam'],
    'Energy & Utilities': ['NA', 'Asia', 'Latam'],
    'Direct Labor Costs': ['NA', 'Asia', 'Latam'],
}

# Source URLs for existing commodities
UPDATE_SOURCE_URLS = {
    'Aluminum': 'https://www.insee.fr/fr/statistiques/serie/010002041',
    'Iron': 'https://www.investing.com/commodities/iron-ore-62-cfr-futures-historical-data',
    'Copper': 'https://www.insee.fr/fr/statistiques/serie/010002052',
    'Nickel': 'https://www.insee.fr/fr/statistiques/serie/010002060',
    'Zinc': 'https://www.insee.fr/fr/statistiques/serie/010002072',
    'Lead': 'https://www.insee.fr/fr/statistiques/serie/010002064',
    'Naphtha': 'https://www.insee.fr/fr/statistiques/serie/010002081',
    'Oil Price': 'https://prixdubaril.com/',
    'Natural Gas': 'https://www.insee.fr/fr/statistiques/serie/010767333',
    'Energy & Utilities': 'https://ec.europa.eu/eurostat/databrowser/view/nrg_pc_203__custom_19036657/default/table',
    'Chlorine': 'https://www.imarcgroup.com/chlorine-pricing-report',
    'Ammonia': 'https://businessanalytiq.com/procurementanalytics/index/ammonia-price-index/',
    'Direct Labor Costs': 'https://ec.europa.eu/eurostat/databrowser/view/tps00173/default/table',
}

# New commodities to add
NEW_COMMODITIES = [
    # (name, unit, source_url, scrape_enabled)
    # Metals
    ('Tin', '$/mt', 'https://www.insee.fr/fr/statistiques/serie/010002071', True),
    # Chemical feedstocks & products
    ('Caustic Soda', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/caustic-soda-price-index/', False),
    ('Sulfuric Acid', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/sulphuric-acid-price-index/', False),
    ('Hydrochloric Acid', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/hydrochloric-acid-price-index/', False),
    ('Phosphoric Acid', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/phosphoric-acid-price-index/', False),
    ('Ethylene', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/ethylene-price-index/', False),
    ('Propylene', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/propylene-price-index/', False),
    ('Benzene', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/benzene-price-index/', False),
    ('Toluene', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/toluene-price-index/', False),
    ('Methanol', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/methanol-price-index/', False),
    ('Ethanol', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/ethanol-price-index/', False),
    ('Urea', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/urea-price-index/', False),
    ('Acetic Acid', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/acetic-acid-price-index/', False),
    ('Hydrogen Peroxide', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/hydrogen-peroxide-price-index/', False),
    ('Sodium Carbonate', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/soda-ash-price-index/', False),
    # Polymers
    ('Polyethylene HDPE', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/hdpe-high-density-polyethylene-price-index/', False),
    ('PVC', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/pvc-price-index/', False),
    ('Polypropylene', '$/mt', 'https://businessanalytiq.com/procurementanalytics/index/polypropylene-price-index/', False),
    # Labor
    ('Labor China', 'index', 'https://tradingeconomics.com/china/labour-costs', False),
    ('ECI USA', 'index', 'https://www.bls.gov/news.release/eci.toc.htm', False),
    # PPI & Manufacturing
    ('PPI Manufacturing Europe', 'index', 'https://ec.europa.eu/eurostat/databrowser/view/sts_inpp_m/default/table?lang=en', False),
    ('PPI Chemicals USA', 'index', 'https://www.bls.gov/ppi/databases/', False),
    ('Industrial Production USA', 'index', 'https://www.federalreserve.gov/releases/G17/20250815/ipdisk/alltables.htm', False),
    # Logistics
    ('Container Freight WCI', '$/40ft', 'https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry', False),
]


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Remove fake regional index values
    for commodity_name, regions in REMOVE_REGIONAL.items():
        row = conn.execute(
            sa.text("SELECT id FROM commodity_indexes WHERE name = :name"),
            {"name": commodity_name},
        ).fetchone()
        if row:
            cid = row[0]
            for region in regions:
                conn.execute(
                    sa.text("DELETE FROM index_values WHERE commodity_id = :cid AND region = :region"),
                    {"cid": cid, "region": region},
                )
                # Also clean up any overrides for these fake regions
                conn.execute(
                    sa.text("DELETE FROM index_overrides WHERE commodity_id = :cid AND region = :region"),
                    {"cid": cid, "region": region},
                )

    # 2. Remove entirely fake indices (cascade: values, overrides, formula components, team sources)
    for name in REMOVE_INDICES:
        row = conn.execute(
            sa.text("SELECT id FROM commodity_indexes WHERE name = :name"),
            {"name": name},
        ).fetchone()
        if not row:
            continue
        cid = row[0]
        # Remove dependent rows
        conn.execute(sa.text("DELETE FROM index_values WHERE commodity_id = :cid"), {"cid": cid})
        conn.execute(sa.text("DELETE FROM index_overrides WHERE commodity_id = :cid"), {"cid": cid})
        conn.execute(sa.text(
            "UPDATE formula_components SET commodity_id = NULL WHERE commodity_id = :cid"
        ), {"cid": cid})
        conn.execute(sa.text("DELETE FROM team_index_sources WHERE commodity_id = :cid"), {"cid": cid})
        conn.execute(sa.text("DELETE FROM commodity_indexes WHERE id = :cid"), {"cid": cid})

    # 3. Set source_url on existing commodities
    for name, url in UPDATE_SOURCE_URLS.items():
        conn.execute(
            sa.text("UPDATE commodity_indexes SET source_url = :url WHERE name = :name"),
            {"url": url, "name": name},
        )

    # 4. Add new commodities (skip if already exists, e.g. from jacobi seed)
    for name, unit, source_url, scrape_enabled in NEW_COMMODITIES:
        exists = conn.execute(
            sa.text("SELECT id FROM commodity_indexes WHERE name = :name"),
            {"name": name},
        ).fetchone()
        if not exists:
            conn.execute(
                sa.text(
                    "INSERT INTO commodity_indexes (name, unit, source_url, scrape_enabled) "
                    "VALUES (:name, :unit, :url, :scrape)"
                ),
                {"name": name, "unit": unit, "url": source_url, "scrape": scrape_enabled},
            )


def downgrade() -> None:
    conn = op.get_bind()

    # Remove added commodities
    for name, _, _, _ in NEW_COMMODITIES:
        row = conn.execute(
            sa.text("SELECT id FROM commodity_indexes WHERE name = :name"),
            {"name": name},
        ).fetchone()
        if row:
            cid = row[0]
            conn.execute(sa.text("DELETE FROM index_values WHERE commodity_id = :cid"), {"cid": cid})
            conn.execute(sa.text("DELETE FROM index_overrides WHERE commodity_id = :cid"), {"cid": cid})
            conn.execute(sa.text("DELETE FROM team_index_sources WHERE commodity_id = :cid"), {"cid": cid})
            conn.execute(sa.text("DELETE FROM commodity_indexes WHERE id = :cid"), {"cid": cid})

    # Clear source_urls
    for name in UPDATE_SOURCE_URLS:
        conn.execute(
            sa.text("UPDATE commodity_indexes SET source_url = NULL WHERE name = :name"),
            {"name": name},
        )

    # Note: removed indices (Alcohol, Manufacturing Overhead, Packaging, Logistics)
    # and removed regional data cannot be fully restored by downgrade — re-seed if needed.
