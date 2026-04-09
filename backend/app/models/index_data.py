import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String, Integer, SmallInteger, Numeric, Boolean, DateTime,
    ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CommodityIndex(Base):
    __tablename__ = "commodity_indexes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32))
    currency: Mapped[str | None] = mapped_column(String(3))
    category: Mapped[str | None] = mapped_column(String(32))
    source_url: Mapped[str | None] = mapped_column(String(512))
    scrape_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    values = relationship("IndexValue", back_populates="commodity", lazy="dynamic")


class IndexValue(Base):
    __tablename__ = "index_values"
    __table_args__ = (
        UniqueConstraint("commodity_id", "region", "year", "quarter"),
        Index("idx_index_values_lookup", "commodity_id", "region", "year", "quarter"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    commodity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commodity_indexes.id"), nullable=False
    )
    region: Mapped[str] = mapped_column(String(20), nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    quarter: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="scraped")
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    commodity = relationship("CommodityIndex", back_populates="values")


class IndexOverride(Base):
    __tablename__ = "index_overrides"
    __table_args__ = (
        UniqueConstraint("team_id", "commodity_id", "region", "year", "quarter"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE")
    )
    commodity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commodity_indexes.id")
    )
    region: Mapped[str] = mapped_column(String(20), nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    quarter: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    source_file: Mapped[str | None] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class TeamIndexSource(Base):
    """Configuration for how a team obtains override values for a commodity+region."""

    __tablename__ = "team_index_sources"
    __table_args__ = (
        UniqueConstraint("team_id", "commodity_id", "region"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    commodity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commodity_indexes.id"), nullable=False
    )
    region: Mapped[str] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "manual" | "scrape_url" | "upload"
    scrape_url: Mapped[str | None] = mapped_column(String(512))
    scrape_config: Mapped[dict | None] = mapped_column(JSONB)
    source_file: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    commodity = relationship("CommodityIndex")