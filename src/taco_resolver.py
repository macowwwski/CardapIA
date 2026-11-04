"""
Ponto central de acesso para busca de alimentos na TACO e porções por aluno.

Mantém os nomes e funções disponíveis para partes do sistema que ainda usam
este arquivo, direcionando os pedidos para a pasta `src.taco`.
"""
from src.taco import (
    MatchTaco,
    resolver_taco,
    resolver_per_capita,
    SINONIMOS_TACO,
    _norm,
    _tokens,
)

__all__ = [
    "MatchTaco",
    "resolver_taco",
    "resolver_per_capita",
    "SINONIMOS_TACO",
    "_norm",
    "_tokens",
]
