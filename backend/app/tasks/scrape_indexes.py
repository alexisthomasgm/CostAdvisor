import asyncio
from datetime import datetime, timezone

from app.tasks import celery_app
from app.database import SessionLocal, bypass_rls_var
from app.models.index_data import CommodityIndex, IndexOverride, TeamIndexSource
from app.services.scraper import SCRAPER_REGISTRY, GenericWebScraper
from app.services.fx_sync import sync_fx_rates


@celery_app.task(name="app.tasks.scrape_indexes.scrape_all")
def scrape_all():
    """Run all registered scrapers."""
    bypass_rls_var.set(True)  # System task — no user context
    db = SessionLocal()
    try:
        commodities = db.query(CommodityIndex).filter(
            CommodityIndex.scrape_enabled == True  # noqa: E712
        ).all()

        results = {}
        for commodity in commodities:
            scraper_cls = SCRAPER_REGISTRY.get(commodity.name)
            if not scraper_cls:
                results[commodity.name] = "no_scraper"
                continue

            scraper = scraper_cls()
            count = asyncio.run(scraper.run(db))
            results[commodity.name] = f"updated_{count}"

        # After scraping, sync FX rates into the fx_rates table
        fx_count = sync_fx_rates(db)
        results["_fx_synced"] = fx_count

        return results
    finally:
        db.close()


@celery_app.task(name="app.tasks.scrape_indexes.scrape_one")
def scrape_one(commodity_name: str):
    """Scrape a single commodity."""
    scraper_cls = SCRAPER_REGISTRY.get(commodity_name)
    if not scraper_cls:
        return {"error": f"No scraper for {commodity_name}"}

    bypass_rls_var.set(True)
    db = SessionLocal()
    try:
        scraper = scraper_cls()
        count = asyncio.run(scraper.run(db))
        return {"commodity": commodity_name, "updated": count}
    finally:
        db.close()


@celery_app.task(name="app.tasks.scrape_indexes.scrape_team_sources")
def scrape_team_sources():
    """Scrape all team-configured URL sources and upsert into IndexOverride."""
    bypass_rls_var.set(True)
    db = SessionLocal()
    try:
        sources = db.query(TeamIndexSource).filter(
            TeamIndexSource.source_type == "scrape_url"
        ).all()

        results = {}
        for source in sources:
            key = f"{source.team_id}:{source.commodity_id}:{source.region}"
            if not source.scrape_url:
                results[key] = "no_url"
                continue

            try:
                scraper = GenericWebScraper(source.scrape_url, source.scrape_config)
                value = asyncio.run(scraper.scrape())
                _upsert_override(db, source, value)
                results[key] = f"ok:{value}"
            except Exception as exc:
                results[key] = f"error:{exc}"

        return results
    finally:
        db.close()


def _upsert_override(db, source: TeamIndexSource, value: float):
    """Write a scraped value into IndexOverride for the current quarter."""
    now = datetime.now(timezone.utc)
    year = now.year
    quarter = (now.month - 1) // 3 + 1

    existing = db.query(IndexOverride).filter(
        IndexOverride.team_id == source.team_id,
        IndexOverride.commodity_id == source.commodity_id,
        IndexOverride.region == source.region,
        IndexOverride.year == year,
        IndexOverride.quarter == quarter,
    ).first()

    if existing:
        existing.value = value
        existing.uploaded_by = source.created_by
        existing.source_file = f"scrape:{source.scrape_url}"
        existing.uploaded_at = now
    else:
        override = IndexOverride(
            team_id=source.team_id,
            commodity_id=source.commodity_id,
            region=source.region,
            year=year,
            quarter=quarter,
            value=value,
            uploaded_by=source.created_by,
            source_file=f"scrape:{source.scrape_url}",
        )
        db.add(override)

    db.commit()
