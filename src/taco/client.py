"""
Conexão com a base de busca e modelos de linguagem para encontrar alimentos.

Reúne em um só lugar o acesso ao banco de busca de alimentos e aos modelos
que entendem tanto o significado das palavras quanto a escrita exata dos pratos.
"""
from src.config import (
    QDRANT_HOST,
    QDRANT_PORT,
    EMBEDDING_MODEL_NAME,
    SPARSE_MODEL_NAME,
)

_client = None
_embedder_dense = None
_embedder_sparse = None


def get_qdrant_client():
    """Entrega a conexão com a base de busca de alimentos, reaproveitando a mesma conexão."""
    global _client
    if _client is None:
        from qdrant_client import QdrantClient
        _client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return _client


def get_dense_embedder():
    """Entrega o modelo que compreende o significado dos alimentos pelo contexto e sinônimos."""
    global _embedder_dense
    if _embedder_dense is None:
        from fastembed import TextEmbedding
        _embedder_dense = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
    return _embedder_dense


def get_sparse_embedder():
    """Entrega o modelo focado na escrita e correspondência exata dos termos."""
    global _embedder_sparse
    if _embedder_sparse is None:
        from fastembed import SparseTextEmbedding
        _embedder_sparse = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
    return _embedder_sparse
