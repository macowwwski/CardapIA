# Equivalente ao schema

from sqlalchemy import Column, String, Float, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from db.database import Base

class Taco(Base):
    __tablename__ = "taco"

    id             = Column(UUID(as_uuid=True), primary_key=True)
    created_at     = Column(DateTime)
    updated_at     = Column(DateTime)
    deleted_at     = Column(DateTime, nullable=True)
    created_by     = Column(String)
    updated_by     = Column(String)
    deleted_by     = Column(String, nullable=True)
    alternative_id = Column(Integer)
    description    = Column(String) # nome do alimento
    category       = Column(String)
    humidity       = Column(Float, nullable=True)
    energy_kcal    = Column(Float, nullable=True)
    energy_kj      = Column(Float, nullable=True)
    proteins       = Column(Float, nullable=True)
    lipids         = Column(Float, nullable=True)
    cholesterol    = Column(Float, nullable=True)
    carbohydrates  = Column(Float, nullable=True)
    dietary_fiber  = Column(Float, nullable=True)
    ashe           = Column(Float, nullable=True)
    calcium        = Column(Float, nullable=True)
    magnesium      = Column(Float, nullable=True)
    manganese      = Column(Float, nullable=True)
    phosphoru      = Column(Float, nullable=True)
    iron           = Column(Float, nullable=True)
    sodium         = Column(Float, nullable=True)
    potassium      = Column(Float, nullable=True)
    copper         = Column(Float, nullable=True)
    zinc           = Column(Float, nullable=True)
    retinol        = Column(Float, nullable=True)
    re             = Column(Float, nullable=True)
    rae            = Column(Float, nullable=True)
    thiamine       = Column(Float, nullable=True)
    riboflavin     = Column(Float, nullable=True)
    pyridoxine     = Column(Float, nullable=True)
    niacin         = Column(Float, nullable=True)
    c_vitamin      = Column(Float, nullable=True)