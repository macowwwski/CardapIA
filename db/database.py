# arquivo de conexão com o BD

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

load_dotenv()

PORT = os.getenv("DB_PORT", "5433")
DATABASE_URL = os.getenv("DATABASE_URL", f"postgresql://cardapia:cardapia@localhost:{PORT}/cardapia")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass