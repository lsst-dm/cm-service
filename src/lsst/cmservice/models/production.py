"""Pydantic model for the Production tables
"""
from pydantic import BaseModel


class ProductionBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # Unique name for this production
    name: str


class ProductionCreate(ProductionBase):
    """Parameters that are used to create new rows but not in DB tables"""

    pass


class Production(ProductionBase):
    """Parameters that are in DB tables and not used to create new rows"""

    # PrimaryKey
    id: int

    class Config:
        orm_mode = True
