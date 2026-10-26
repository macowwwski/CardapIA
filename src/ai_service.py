"""
Fachada retrocompatível para os serviços de IA, regras do PNAE e validação do CardapIA.

Reexporta as implementações modulares organizadas em:
- `src.services`: Orquestração de IA e normalização de estruturas de dados.
- `src.nutrition`: Classificação de alimentos, cálculo de nutrientes e auditoria do PNAE.
- `src.taco`: Resolução semântica de alimentos e porções per capita oficiais.
- `src.prompts`: Construção de contexto e templates de prompts.
- `src.schemas_pydantic`: Contratos de validação de dados.
"""
from src.schemas_pydantic import (
    CardapioSchema,
    SemanaSchema,
    DiaSchema,
    RefeicaoSchema,
    PratoSchema,
    IngredienteSchema,
    InconformidadePNAESchema,
    RelatorioValidacaoSchema,
    TipoRefeicao,
    StatusValidacao,
    ORDEM_TIPOS_REFEICAO,
    TIPOS_REFEICAO_PERMITIDOS,
)
from src.nutrition import (
    validar_coerencia_culinaria,
    validar_cardapio_pnae,
    avaliar_status_cardapio,
    calcular_nutrientes_alimento,
    buscar_taco_por_nome,
    ajustar_macronutrientes_cardapio,
    auditar_vet_e_macros,
    _classificar_alimento,
    _identificar_frutas,
    _somar_nutriente,
    _dentro_intervalo,
    _resolver_regras_pnae,
    _violacoes_proibicoes,
    _texto_normalizado,
    _tokens_normalizados,
)
from src.taco import (
    MatchTaco,
    resolver_taco,
    resolver_per_capita,
    SINONIMOS_TACO,
)
from src.prompts import (
    construir_contexto,
    montar_prompt_geracao_cardapio,
    montar_prompt_correcao_cardapio,
    montar_prompt_conversao_json,
    montar_mensagem_conversao_json,
)
from src.services import (
    gerar_cardapio,
    aplicar_per_capita,
    obter_per_capita,
    corrigir_estrutura,
    validar_cardapio,
)

__all__ = [
    # Schemas e Enums
    "CardapioSchema",
    "SemanaSchema",
    "DiaSchema",
    "RefeicaoSchema",
    "PratoSchema",
    "IngredienteSchema",
    "InconformidadePNAESchema",
    "RelatorioValidacaoSchema",
    "TipoRefeicao",
    "StatusValidacao",
    "ORDEM_TIPOS_REFEICAO",
    "TIPOS_REFEICAO_PERMITIDOS",
    # Serviços Principais
    "gerar_cardapio",
    "aplicar_per_capita",
    "obter_per_capita",
    "corrigir_estrutura",
    "validar_cardapio",
    # Nutrição e PNAE
    "validar_coerencia_culinaria",
    "validar_cardapio_pnae",
    "avaliar_status_cardapio",
    "calcular_nutrientes_alimento",
    "buscar_taco_por_nome",
    "ajustar_macronutrientes_cardapio",
    "auditar_vet_e_macros",
    "_classificar_alimento",
    "_identificar_frutas",
    "_somar_nutriente",
    "_dentro_intervalo",
    "_resolver_regras_pnae",
    "_violacoes_proibicoes",
    "_texto_normalizado",
    "_tokens_normalizados",
    # TACO
    "MatchTaco",
    "resolver_taco",
    "resolver_per_capita",
    "SINONIMOS_TACO",
    # Prompts
    "construir_contexto",
    "montar_prompt_geracao_cardapio",
    "montar_prompt_correcao_cardapio",
    "montar_prompt_conversao_json",
    "montar_mensagem_conversao_json",
]
