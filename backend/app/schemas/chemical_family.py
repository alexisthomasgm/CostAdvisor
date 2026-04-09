from pydantic import BaseModel


class ChemicalFamilyCreate(BaseModel):
    name: str
    custom_attribute_schema: list[dict] | None = None


class ChemicalFamilyOut(BaseModel):
    id: int
    name: str
    custom_attribute_schema: list[dict] | None = None

    model_config = {"from_attributes": True}
