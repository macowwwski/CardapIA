"""
Módulo de serviços de negócio e orquestração do CardapIA.
"""
from src.services.normalizer import (
    corrigir_estrutura,
    validar_cardapio,
    _extrair_numero,
    _tipo_refeicao_por_posicao,
    _normalizar_tipo_refeicao,
)
from src.services.ai_generator import (
    gerar_cardapio,
    aplicar_per_capita,
    obter_per_capita,
)

__all__ = [
    "gerar_cardapio",
    "aplicar_per_capita",
    "obter_per_capita",
    "corrigir_estrutura",
    "validar_cardapio",
    "_extrair_numero",
    "_tipo_refeicao_por_posicao",
    "_normalizar_tipo_refeicao",
]
