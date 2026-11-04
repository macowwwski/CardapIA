"""
Módulo de prompts, formatação de contexto regulatório do PNAE e geração LLM.
"""
from src.prompts.builder import (
    construir_contexto,
    resolver_tipos_refeicao,
    REGRAS_PNAE,
    _obter_etapa,
    _mapear_percentual,
    _mapear_refeicoes_periodo,
    _obter_referencias_nutricionais,
    _mapear_e_obter_faixa_etaria,
)
from src.prompts.templates import (
    montar_prompt_geracao_cardapio,
    montar_prompt_correcao_cardapio,
    montar_prompt_conversao_json,
    montar_mensagem_conversao_json,
)

__all__ = [
    "construir_contexto",
    "resolver_tipos_refeicao",
    "REGRAS_PNAE",
    "montar_prompt_geracao_cardapio",
    "montar_prompt_correcao_cardapio",
    "montar_prompt_conversao_json",
    "montar_mensagem_conversao_json",
    "_obter_etapa",
    "_mapear_percentual",
    "_mapear_refeicoes_periodo",
    "_obter_referencias_nutricionais",
    "_mapear_e_obter_faixa_etaria",
]
