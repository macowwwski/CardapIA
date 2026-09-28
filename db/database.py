"""
Configuração de conexão com o banco de dados PostgreSQL via SQLAlchemy.

Carrega as variáveis de ambiente a partir do .env raiz do projeto e disponibiliza:
- engine: Instância de conexão do SQLAlchemy.
- SessionLocal: Fábrica para criação de sessões de banco.
- Base: Classe base declarativa para os modelos ORM (db/models.py).
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Carrega o .env a partir da raiz do CardapIA
caminho_env = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(caminho_env)

# Porta e URL de conexão com o PostgreSQL
PORT = os.getenv("DB_PORT", "5433")
DATABASE_URL = os.getenv("DATABASE_URL", f"postgresql://cardapia:cardapia@localhost:{PORT}/cardapia")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    """Classe base declarativa do SQLAlchemy para os modelos do CardapIA."""
    pass