# Equivalente ao schema

import uuid
from datetime import datetime, time
from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime,
    Float, ForeignKey, Integer, String, Text, Time, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
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

    # Relacionamento reverso
    ingredientes    = relationship("Ingrediente", back_populates="taco")
 
 
class EtapaEscolar(Base):
    __tablename__ = "etapa_escolar"
    __table_args__ = (
        UniqueConstraint("etapa", "faixa_etaria"),
    )
 
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    etapa        = Column(String, nullable=False)    # "creche", "pré-escola", etc.
    faixa_etaria = Column(String, nullable=False)    
 
    # Relacionamento reverso
    cardapios    = relationship("Cardapio", back_populates="etapa_escolar")
 
 
class Cardapio(Base):
    __tablename__ = "cardapio"
 
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    etapa_escolar_id = Column(UUID(as_uuid=True), ForeignKey("etapa_escolar.id"), nullable=False)
    periodo          = Column(String, nullable=False)        # "parcial", "integral"
    mes_aplicacao    = Column(String, nullable=False)
    num_refeicoes    = Column(Integer, nullable=False)
    num_semanas      = Column(Integer, nullable=False, default=4)
    data_geracao     = Column(DateTime, nullable=False, default=datetime.now)
    aprovado         = Column(Boolean, nullable=False, default=False)
    observacoes      = Column(Text, nullable=True)
 
    # Relacionamentos
    etapa_escolar    = relationship("EtapaEscolar", back_populates="cardapios")
    semanas          = relationship("Semana", back_populates="cardapio", cascade="all, delete-orphan")
 
 
class Semana(Base):
    __tablename__ = "semana"
    __table_args__ = (
        CheckConstraint("numero BETWEEN 1 AND 4"),
    )
 
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cardapio_id = Column(UUID(as_uuid=True), ForeignKey("cardapio.id"), nullable=False)
    numero      = Column(Integer, nullable=False)    # 1, 2, 3, 4
 
    # Relacionamentos
    cardapio    = relationship("Cardapio", back_populates="semanas")
    dias        = relationship("Dia", back_populates="semana", cascade="all, delete-orphan")
 
 
class Dia(Base):
    __tablename__ = "dia"
 
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    semana_id   = Column(UUID(as_uuid=True), ForeignKey("semana.id"), nullable=False)
    dia_semana  = Column(String, nullable=False)    # "segunda", "terça", etc.
 
    # Relacionamentos
    semana      = relationship("Semana", back_populates="dias")
    refeicoes   = relationship("Refeicao", back_populates="dia", cascade="all, delete-orphan")
 
 
class Refeicao(Base):
    __tablename__ = "refeicao"
 
    id      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dia_id  = Column(UUID(as_uuid=True), ForeignKey("dia.id"), nullable=False)
    tipo    = Column(String, nullable=False)     # "almoço", "lanche da manhã", etc.
    horario = Column(Time, nullable=True)
 
    # Relacionamentos
    dia     = relationship("Dia", back_populates="refeicoes")
    pratos  = relationship("Prato", back_populates="refeicao", cascade="all, delete-orphan")
 
 
class Prato(Base):
    __tablename__ = "prato"
 
    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    refeicao_id       = Column(UUID(as_uuid=True), ForeignKey("refeicao.id"), nullable=False)
    nome              = Column(String, nullable=False)
    estado_preparacao = Column(String, nullable=True)   # "cozido", "grelhado", "cru", "assado"
 
    # Relacionamentos
    refeicao          = relationship("Refeicao", back_populates="pratos")
    ingredientes      = relationship("Ingrediente", back_populates="prato", cascade="all, delete-orphan")
 
 
class Ingrediente(Base):
    __tablename__ = "ingrediente"
 
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prato_id     = Column(UUID(as_uuid=True), ForeignKey("prato.id"), nullable=False)
    taco_id      = Column(UUID(as_uuid=True), ForeignKey("taco.id"), nullable=False)
    quantidade_g = Column(Float, nullable=False)
 
    # Relacionamentos
    prato        = relationship("Prato", back_populates="ingredientes")
    taco         = relationship("Taco", back_populates="ingredientes")


class PerCapita(Base):
    __tablename__ = "per_capita"

    id                       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    taco_id                  = Column(UUID(as_uuid=True), ForeignKey("taco.id"), nullable=True)
    nome_alimento            = Column(String, nullable=False, unique=True)
    fator_correcao           = Column(Float, nullable=False, default=1.0)
    fator_coccao             = Column(Float, nullable=False, default=1.0)
    per_capita_creche        = Column(Float, nullable=True)  # NULL = restrito
    per_capita_pre_escola    = Column(Float, nullable=True)
    per_capita_fund          = Column(Float, nullable=True)
    per_capita_medio_eja     = Column(Float, nullable=True)

    # Relacionamento
    taco = relationship("Taco")