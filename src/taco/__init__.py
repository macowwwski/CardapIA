"""
Módulo de integração com a Tabela TACO e resolução de per capita via Qdrant.
"""
from src.taco.synonyms import SINONIMOS_TACO
from src.taco.client import (
    get_qdrant_client,
    get_dense_embedder,
    get_sparse_embedder,
)
from src.taco.resolver import (
    MatchTaco,
    resolver_taco,
    resolver_per_capita,
    _norm,
    _tokens,
)

__all__ = [
    "SINONIMOS_TACO",
    "MatchTaco",
    "resolver_taco",
    "resolver_per_capita",
    "get_qdrant_client",
    "get_dense_embedder",
    "get_sparse_embedder",
    "_norm",
    "_tokens",
]
