"""
Centralização de configurações e variáveis de ambiente do CardapIA.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Carrega o arquivo .env a partir da raiz do projeto
caminho_env = PROJECT_ROOT / ".env"
load_dotenv(caminho_env)

# Banco de Dados PostgreSQL
DB_PORT = os.getenv("DB_PORT", "5433")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://cardapia:cardapia@localhost:{DB_PORT}/cardapia",
)

# Qdrant Vector Database
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# Modelos de Embedding e Recuperação
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
SPARSE_MODEL_NAME = os.getenv("SPARSE_MODEL_NAME", "Qdrant/bm25")

# Limiares de pontuação semântica
TACO_MATCH_MIN_SCORE = float(os.getenv("TACO_MATCH_MIN_SCORE", "0.005"))
PER_CAPITA_MATCH_MIN_SCORE = float(os.getenv("PER_CAPITA_MATCH_MIN_SCORE", "0.005"))

# LLM (Ollama)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud")
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.3"))

# Caminho para os dados normativos do PNAE
CAMINHO_PNAE_JSON = PROJECT_ROOT / "data" / "pnae.json"

# Servidor HTTP
SERVER_PORT = int(os.getenv("PORT", "8005"))
