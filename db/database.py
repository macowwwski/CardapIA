"""
Configuração de conexão com o banco de dados PostgreSQL.

Lê as configurações do arquivo .env e organiza o acesso ao banco:
- engine: canal de comunicação direto com o banco de dados.
- SessionLocal: gerador de sessões para consultar ou salvar informações.
- Base: modelo padrão que todas as tabelas do sistema utilizam.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

try:
    from src.config import DATABASE_URL
except ImportError:
    caminho_env = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(caminho_env)
    PORT = os.getenv("DB_PORT", "5433")
    DATABASE_URL = os.getenv("DATABASE_URL", f"postgresql://cardapia:cardapia@localhost:{PORT}/cardapia")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """Classe base declarativa do SQLAlchemy para os modelos do CardapIA."""
    pass