"""
Teste de verificação da conexão e busca semântica no Qdrant.
"""
import os
from qdrant_client import QdrantClient
from fastembed import TextEmbedding

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

def testar():
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    embedder = TextEmbedding(model_name=MODEL_NAME)

    print("--- 1. COLEÇÕES DISPONÍVEIS ---")
    cols = client.get_collections().collections
    for c in cols:
        info = client.get_collection(c.name)
        print(f"• Coleção: {c.name} | Total de vetores: {info.points_count}")

    print("\n--- 2. TESTE DE BUSCA SEMÂNTICA (TACO) ---")
    queries = ["frango desfiado cozido", "arroz soltinho", "suco de caju natural"]
    for q in queries:
        query_vector = list(embedder.embed([q]))[0].tolist()
        hits = client.query_points(
            collection_name="taco_foods",
            query=query_vector,
            limit=2
        ).points
        print(f"\nBusca por: '{q}'")
        for hit in hits:
            print(f"  -> Score: {hit.score:.4f} | {hit.payload['description']} ({hit.payload['energy_kcal']} kcal)")

if __name__ == "__main__":
    testar()
