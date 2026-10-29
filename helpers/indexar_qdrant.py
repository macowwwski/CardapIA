"""
Carrega os alimentos da Tabela TACO e as porções recomendadas para dentro da busca inteligente (Qdrant).

Prepara duas listas de busca:
1. 'taco_foods': alimentos com suas informações nutricionais (calorias, proteínas, ferro, etc.).
2. 'per_capita_items': peso oficial de cada alimento por aluno e etapa escolar.
"""
import os
import sys
import unicodedata
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, SparseVectorParams, SparseIndexParams,
    PointStruct, SparseVector
)
from fastembed import TextEmbedding, SparseTextEmbedding

# Adiciona a raiz do projeto ao path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import engine
from db.models import Taco, PerCapita

load_dotenv()

# Endereço e porta para conectar no banco de busca inteligente
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

# Modelo de inteligência para entender o significado dos nomes de alimentos em português
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Apelidos e nomes populares dos alimentos para ajudar a encontrar a opção certa
from src.taco.synonyms import SINONIMOS_TACO


def main():
    print(f" Conectando ao Qdrant em {QDRANT_HOST}:{QDRANT_PORT}...")
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    print(f" Carregando modelos de embeddings ({MODEL_NAME} e Qdrant/bm25)...")
    dense_model = TextEmbedding(model_name=MODEL_NAME)
    sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    vector_size = 384  # Dimensão dos vetores densos gerados pelo MiniLM-L12

    with Session(engine) as session:
        # =====================================================
        # 1. INDEXAÇÃO DA TABELA TACO
        # =====================================================
        collection_taco = "taco_foods"
        print(f"\n Recriando coleção '{collection_taco}' no Qdrant com vetores híbridos...")
        client.recreate_collection(
            collection_name=collection_taco,
            vectors_config={"dense": VectorParams(size=vector_size, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))}
        )

        tacos = session.query(Taco).filter(Taco.deleted_at == None).all()
        print(f" Extraindo {len(tacos)} alimentos da TACO...")

        def _desacentuar(s: str) -> str:
            t = unicodedata.normalize("NFD", str(s or ""))
            return "".join(c for c in t if unicodedata.category(c) != "Mn")

        textos_taco = [
            f"{t.description}. {_desacentuar(t.description)}. {SINONIMOS_TACO.get(t.description, '')}. Categoria: {t.category or 'geral'}"
            for t in tacos
        ]
        dense_taco = list(dense_model.embed(textos_taco))
        sparse_taco = list(sparse_model.embed(textos_taco))

        pontos_taco = []
        for i, t in enumerate(tacos):
            sp = sparse_taco[i]
            pontos_taco.append(PointStruct(
                id=str(t.id),
                vector={
                    "dense": dense_taco[i].tolist(),
                    "sparse": SparseVector(indices=sp.indices.tolist(), values=sp.values.tolist())
                },
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
        print(f"\n Recriando coleção '{collection_per_capita}' no Qdrant com vetores híbridos...")
        client.recreate_collection(
            collection_name=collection_per_capita,
            vectors_config={"dense": VectorParams(size=vector_size, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))}
        )

        per_capitas = session.query(PerCapita).all()
        print(f" Extraindo {len(per_capitas)} itens de per capita...")

        textos_pc = [
            f"{pc.nome_alimento}. {_desacentuar(pc.nome_alimento)}"
            for pc in per_capitas
        ]
        dense_pc = list(dense_model.embed(textos_pc))
        sparse_pc = list(sparse_model.embed(textos_pc))

        pontos_pc = []
        for i, pc in enumerate(per_capitas):
            sp = sparse_pc[i]
            pontos_pc.append(PointStruct(
                id=str(pc.id),
                vector={
                    "dense": dense_pc[i].tolist(),
                    "sparse": SparseVector(indices=sp.indices.tolist(), values=sp.values.tolist())
                },
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
