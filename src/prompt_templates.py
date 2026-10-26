"""
Fachada retrocompatível para templates de prompts da LLM.

Redireciona para o pacote modular `src.prompts.templates`.
"""
from src.prompts.templates import (
    montar_prompt_geracao_cardapio,
    montar_prompt_correcao_cardapio,
    montar_prompt_conversao_json,
    montar_mensagem_conversao_json,
)

__all__ = [
    "montar_prompt_geracao_cardapio",
    "montar_prompt_correcao_cardapio",
    "montar_prompt_conversao_json",
    "montar_mensagem_conversao_json",
]
