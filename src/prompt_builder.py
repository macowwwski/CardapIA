"""
Fachada retrocompatível para construção de contexto e regras do PNAE.

Redireciona para o pacote modular `src.prompts.builder`.
"""
from src.prompts.builder import (
    construir_contexto,
    resolver_tipos_refeicao,
    normalizar_etapa,
    normalizar_faixa_etaria,
    REGRAS_PNAE,
    MAPA_ETAPAS,
    MAPA_FAIXAS,
    _obter_etapa,
    _mapear_percentual,
    _mapear_refeicoes_periodo,
    _obter_referencias_nutricionais,
    _mapear_e_obter_faixa_etaria,
    _obter_recomendacoes_quantidade,
    _formatar_lista,
    _formatar_frequencias,
)

__all__ = [
    "construir_contexto",
    "resolver_tipos_refeicao",
    "normalizar_etapa",
    "normalizar_faixa_etaria",
    "REGRAS_PNAE",
    "MAPA_ETAPAS",
    "MAPA_FAIXAS",
    "_obter_etapa",
    "_mapear_percentual",
    "_mapear_refeicoes_periodo",
    "_obter_referencias_nutricionais",
    "_mapear_e_obter_faixa_etaria",
    "_obter_recomendacoes_quantidade",
    "_formatar_lista",
    "_formatar_frequencias",
]
