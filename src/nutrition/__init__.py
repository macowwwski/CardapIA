"""
Módulo de regras nutricionais, conformidade com o PNAE e coerência culinária.
"""
from src.nutrition.classifier import (
    _texto_normalizado,
    _tokens_normalizados,
    _classificar_alimento,
    _identificar_frutas,
)
from src.nutrition.calculator import (
    _somar_nutriente,
    _dentro_intervalo,
    buscar_taco_por_nome,
    calcular_nutrientes_alimento,
)
from src.nutrition.culinary_validator import validar_coerencia_culinaria
from src.nutrition.pnae_auditor import (
    validar_cardapio_pnae,
    avaliar_status_cardapio,
    _resolver_regras_pnae,
    _violacoes_proibicoes,
)
from src.nutrition.macro_adjuster import (
    ajustar_macronutrientes_cardapio,
    auditar_vet_e_macros,
    StatusMacronutrientesDia,
    RelatorioAjusteNutricional,
)

__all__ = [
    "validar_coerencia_culinaria",
    "validar_cardapio_pnae",
    "avaliar_status_cardapio",
    "calcular_nutrientes_alimento",
    "buscar_taco_por_nome",
    "ajustar_macronutrientes_cardapio",
    "auditar_vet_e_macros",
    "StatusMacronutrientesDia",
    "RelatorioAjusteNutricional",
    "_classificar_alimento",
    "_identificar_frutas",
    "_somar_nutriente",
    "_dentro_intervalo",
    "_resolver_regras_pnae",
    "_violacoes_proibicoes",
    "_texto_normalizado",
    "_tokens_normalizados",
]
