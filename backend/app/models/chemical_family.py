from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChemicalFamily(Base):
    __tablename__ = "chemical_families"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    custom_attribute_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Schema example: [{"name": "concentration", "type": "number"}, {"name": "charge", "type": "string"}]

    products = relationship("Product", back_populates="chemical_family")
