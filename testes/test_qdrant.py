"""
Teste prático para verificar se o banco de busca inteligente (Qdrant) está funcionando
e encontrando os alimentos corretamente pelo significado do nome.
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
        hits = None
        for using_name in ["dense", None]:
            try:
                res = client.query_points(
                    collection_name="taco_foods",
                    query=query_vector,
                    using=using_name,
                    limit=2
                )
                if res and res.points:
                    hits = res.points
                    break
            except Exception:
                pass

        if hits is None:
            import requests
            for v_payload in [{"name": "dense", "vector": query_vector}, query_vector]:
                try:
                    r = requests.post(
                        f"http://{QDRANT_HOST}:{QDRANT_PORT}/collections/taco_foods/points/search",
                        json={"vector": v_payload, "limit": 2, "with_payload": True}
                    ).json()
                    data = r.get("result")
                    if data:
                        class _Hit:
                            def __init__(self, item):
                                self.score = item.get("score", 0.0)
                                self.payload = item.get("payload", {})
                        hits = [_Hit(it) for it in data]
                        break
                except Exception:
                    pass
        hits = hits or []
        print(f"\nBusca por: '{q}'")
        for hit in hits:
            print(f"  -> Score: {hit.score:.4f} | {hit.payload['description']} ({hit.payload['energy_kcal']} kcal)")

if __name__ == "__main__":
    testar()
