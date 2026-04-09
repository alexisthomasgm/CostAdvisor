import uuid
from datetime import datetime, timezone
from sqlalchemy import Integer, SmallInteger, Numeric, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ActualPrice(Base):
    __tablename__ = "actual_prices"
    __table_args__ = (
        UniqueConstraint("cost_model_id", "year", "quarter"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cost_model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_models.id", ondelete="CASCADE")
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    quarter: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    source_file: Mapped[str | None] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    cost_model = relationship("CostModel", back_populates="actual_prices")
