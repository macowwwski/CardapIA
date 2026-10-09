"""
Script de Ingestão e Indexação Vetorial no Qdrant.
Gera embeddings e popula as coleções:
1. 'taco_foods' (alimentos e nutrientes da TACO)
2. 'per_capita_items' (porções oficiais por etapa escolar)
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding

# Adiciona a raiz do projeto ao path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import engine
from db.models import Taco, PerCapita

load_dotenv()

# Configurações de conexão com o nó Qdrant e modelo de embedding local
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

# Modelo multilíngue leve otimizado para inferência rápida em CPU via FastEmbed (384 dimensões)
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

def main():
    print(f" Conectando ao Qdrant em {QDRANT_HOST}:{QDRANT_PORT}...")
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    print(f" Carregando modelo de embeddings ({MODEL_NAME})...")
    embedding_model = TextEmbedding(model_name=MODEL_NAME)
    vector_size = 384  # Dimensão dos vetores densos gerados pelo MiniLM-L12

    with Session(engine) as session:
        # =====================================================
        # 1. INDEXAÇÃO DA TABELA TACO
        # =====================================================
        collection_taco = "taco_foods"
        print(f"\n Recriando coleção '{collection_taco}' no Qdrant...")
        client.recreate_collection(
            collection_name=collection_taco,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
        )

        tacos = session.query(Taco).filter(Taco.deleted_at == None).all()
        print(f" Extraindo {len(tacos)} alimentos da TACO...")

        textos_taco = [
            f"{t.description}, categoria: {t.category or 'geral'}"
            for t in tacos
        ]
        vetores_taco = list(embedding_model.embed(textos_taco))

        pontos_taco = []
        for i, t in enumerate(tacos):
            pontos_taco.append(PointStruct(
                id=str(t.id),
                vector=vetores_taco[i].tolist(),
                payload={
                    "taco_id": str(t.id),
                    "description": t.description,
                    "category": t.category,
                    "energy_kcal": float(t.energy_kcal or 0),
                    "carbohydrates": float(t.carbohydrates or 0),
                    "proteins": float(t.proteins or 0),
                    "lipids": float(t.lipids or 0),
                    "sodium": float(t.sodium or 0),
                    "iron": float(t.iron or 0),
                    "calcium": float(t.calcium or 0),
                    "retinol": float(t.retinol or 0),
                    "c_vitamin": float(t.c_vitamin or 0)
                }
            ))

        # Upload em lote (batch)
        client.upsert(collection_name=collection_taco, points=pontos_taco)
        print(f" Sucesso: {len(pontos_taco)} alimentos indexados em '{collection_taco}'.")

        # =====================================================
        # 2. INDEXAÇÃO DA BASE DE PER CAPITA
        # =====================================================
        collection_per_capita = "per_capita_items"
        print(f"\n Recriando coleção '{collection_per_capita}' no Qdrant...")
        client.recreate_collection(
            collection_name=collection_per_capita,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
        )

        per_capitas = session.query(PerCapita).all()
        print(f" Extraindo {len(per_capitas)} itens de per capita...")

        textos_pc = [pc.nome_alimento for pc in per_capitas]
        vetores_pc = list(embedding_model.embed(textos_pc))

        pontos_pc = []
        for i, pc in enumerate(per_capitas):
            pontos_pc.append(PointStruct(
                id=str(pc.id),
                vector=vetores_pc[i].tolist(),
                payload={
                    "per_capita_id": str(pc.id),
                    "taco_id": str(pc.taco_id) if pc.taco_id else None,
                    "nome_alimento": pc.nome_alimento,
                    "per_capita_creche": float(pc.per_capita_creche) if pc.per_capita_creche is not None else None,
                    "per_capita_pre_escola": float(pc.per_capita_pre_escola) if pc.per_capita_pre_escola is not None else None,
                    "per_capita_fund": float(pc.per_capita_fund) if pc.per_capita_fund is not None else None,
                    "per_capita_medio_eja": float(pc.per_capita_medio_eja) if pc.per_capita_medio_eja is not None else None,
                }
            ))

        client.upsert(collection_name=collection_per_capita, points=pontos_pc)
        print(f" Sucesso: {len(pontos_pc)} itens indexados em '{collection_per_capita}'.")

    print("\n Ingestão no Qdrant finalizada com sucesso!")

if __name__ == "__main__":
    main()
