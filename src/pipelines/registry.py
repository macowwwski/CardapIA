"""
Catálogo central e registro determinístico dos perfis nutricionais do PNAE.

Implementa a resolução determinística de perfis com base na Resolução CD/FNDE nº 06/2020
e nas especificações normativas, mapeando as 22 combinações válidas de etapa de ensino,
faixa etária e quantidade de refeições.
"""
from typing import Dict, Optional, List
from src.pipelines.models import (
    PerfilNutricional,
    ParametrosNutricionais,
    IntervaloNutricional,
    LimitesComposicao,
    MetasSemanais,
    FrequenciasMensais,
    DistribuicaoRefeicao,
    PerfilIncompletoError,
)


class PerfilNaoSuportadoError(ValueError):
    """Lançada quando a combinação de etapa, faixa etária e refeições não é suportada pelo PNAE."""
    pass


# ---------------------------------------------------------------------------
# Catálogo de Metas Semanais por Período / Refeições
# ---------------------------------------------------------------------------
METAS_SEMANAIS_PARCIAL_1_REF = MetasSemanais(
    min_diversidade=10,
    min_flv_g=280.0,
    min_frutas_dias=2,
    min_legumes_verduras_dias=3,
    max_biscoito_semana=2,
    max_doce_semana=None,
    max_margarina_semana=None,
)

METAS_SEMANAIS_PARCIAL_2_REF = MetasSemanais(
    min_diversidade=14,
    min_flv_g=280.0,
    min_frutas_dias=2,
    min_legumes_verduras_dias=3,
    max_biscoito_semana=3,
    max_doce_semana=None,
    max_margarina_semana=None,
)

METAS_SEMANAIS_INTEGRAL = MetasSemanais(
    min_diversidade=23,
    min_flv_g=520.0,
    min_frutas_dias=4,
    min_legumes_verduras_dias=5,
    max_biscoito_semana=7,
    max_doce_semana=1,
    max_margarina_semana=1,
)

# ---------------------------------------------------------------------------
# Templates Validados de Distribuição por Refeição
# ---------------------------------------------------------------------------
def _dist_1ref_almoco(energia_kcal: float) -> List[DistribuicaoRefeicao]:
    """Distribuição para 1 refeição parcial (20% VET - almoço/refeição principal)."""
    return [
        DistribuicaoRefeicao(
            tipo_refeicao="almoço",
            ordem=1,
            percentual_energia=0.20,
            energia_kcal_alvo=energia_kcal,
            composicao_esperada=["Cereal / Tubérculo", "Leguminosa", "Carne / Proteína", "Legumes / Salada", "Fruta"],
            regras_especificas={"tipo": "refeicao_principal", "prato_base": True, "base_per_capita": "porcao_refeicao"},
        )
    ]


def _dist_2ref_creche(energia_kcal: float) -> List[DistribuicaoRefeicao]:
    """Distribuição para Creche parcial (30% VET - 12% desjejum + 18% almoço)."""
    return [
        DistribuicaoRefeicao(
            tipo_refeicao="desjejum",
            ordem=1,
            percentual_energia=0.12,
            energia_kcal_alvo=round(energia_kcal * (0.12 / 0.30), 1),
            composicao_esperada=["Fruta fresca picada/amassada", "Papa de cereal / Leite"],
            regras_especificas={"consistencia_adequada": True, "base_per_capita": "porcao_refeicao"},
        ),
        DistribuicaoRefeicao(
            tipo_refeicao="almoço",
            ordem=2,
            percentual_energia=0.18,
            energia_kcal_alvo=round(energia_kcal * (0.18 / 0.30), 1),
            composicao_esperada=["Arroz / Papa salgada", "Feijão batido/amaciado", "Proteína moída/desfiada", "Legumes cozidos macios"],
            regras_especificas={"prato_principal": True, "base_per_capita": "porcao_refeicao"},
        ),
    ]


def _dist_2ref_padrao(energia_kcal: float) -> List[DistribuicaoRefeicao]:
    """Distribuição para Ensino Básico parcial (30% VET - 10% lanche/desjejum + 20% almoço)."""
    return [
        DistribuicaoRefeicao(
            tipo_refeicao="desjejum",
            ordem=1,
            percentual_energia=0.10,
            energia_kcal_alvo=round(energia_kcal * (0.10 / 0.30), 1),
            composicao_esperada=["Bebida láctea / Fruta", "Cereal / Pão integral"],
            regras_especificas={"refeicao": "lanche_matutino", "base_per_capita": "porcao_refeicao"},
        ),
        DistribuicaoRefeicao(
            tipo_refeicao="almoço",
            ordem=2,
            percentual_energia=0.20,
            energia_kcal_alvo=round(energia_kcal * (0.20 / 0.30), 1),
            composicao_esperada=["Arroz", "Feijão", "Proteína", "Legumes / Salada", "Fruta"],
            regras_especificas={"prato_principal": True, "base_per_capita": "porcao_refeicao"},
        ),
    ]


def _dist_3ref_integral(energia_kcal: float) -> List[DistribuicaoRefeicao]:
    """Distribuição para Ensino Integral (70% VET - 20% desjejum + 35% almoço + 15% lanche da tarde)."""
    return [
        DistribuicaoRefeicao(
            tipo_refeicao="desjejum",
            ordem=1,
            percentual_energia=0.20,
            energia_kcal_alvo=round(energia_kcal * (0.20 / 0.70), 1),
            composicao_esperada=["Leite / Bebida láctea", "Pão / Torrada / Cereal", "Fruta fresca"],
            regras_especificas={"refeicao": "desjejum", "base_per_capita": "porcao_refeicao"},
        ),
        DistribuicaoRefeicao(
            tipo_refeicao="almoço",
            ordem=2,
            percentual_energia=0.35,
            energia_kcal_alvo=round(energia_kcal * (0.35 / 0.70), 1),
            composicao_esperada=["Arroz / Raiz", "Feijão / Leguminosa", "Carne / Ovos / Peixe", "Verduras e Legumes", "Fruta"],
            regras_especificas={"prato_principal": True, "base_per_capita": "porcao_refeicao"},
        ),
        DistribuicaoRefeicao(
            tipo_refeicao="lanche da tarde",
            ordem=3,
            percentual_energia=0.15,
            energia_kcal_alvo=round(energia_kcal * (0.15 / 0.70), 1),
            composicao_esperada=["Fruta fresca", "Pão / Biscoito simples / Iogurte"],
            regras_especificas={"refeicao": "lanche_tarde", "base_per_capita": "porcao_refeicao"},
        ),
    ]


# ---------------------------------------------------------------------------
# Catálogo dos 22 Perfis Nutricionais Oficiais
# ---------------------------------------------------------------------------
CATALOGO_PERFIS: Dict[str, PerfilNutricional] = {
    # -----------------------------------------------------------------------
    # CRECHE (0 a 3 anos) - Parcial (30% VET - mín 2 refeições) e Integral (70% VET - mín 3 refeições)
    # -----------------------------------------------------------------------
    "creche_7_11_meses_parcial_2ref": PerfilNutricional(
        id_perfil="creche_7_11_meses_parcial_2ref",
        etapa="creche",
        faixa_etaria="7_11_meses",
        periodo="parcial",
        num_refeicoes=2,
        percentual_atendimento=30,
        percentual_label="30% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=203.0,
            carboidratos_g=IntervaloNutricional(28.0, 33.0),
            proteinas_g=IntervaloNutricional(5.0, 8.0),
            lipidios_g=IntervaloNutricional(6.0, 8.0),
            vitamina_a_mcg=150.0,
            vitamina_c_mg=15.0,
            calcio_mg=78.0,
            ferro_mg=2.0,
        ),
        limites=LimitesComposicao(
            max_sodio_mg=400.0,
            max_acucar_adicionado_pct=0.0,
            max_gordura_saturada_pct=7.0,
            gorduras_totais_pct=IntervaloNutricional(25.0, 35.0),
        ),
        metas_semanais=METAS_SEMANAIS_PARCIAL_2_REF,
        distribuicao_refeicoes=_dist_2ref_creche(203.0),
        frequencias_mensais=FrequenciasMensais(max_produtos_carneos=0, max_conservas=0, max_doces=0, max_liquidos_lacteos=0),
        alimentos_proibidos=["alimentos ultraprocessados", "alimentos com adição de açúcar", "alimentos com adição de mel", "alimentos com adição de adoçante", "alimentos ricos em gorduras trans industrializadas"],
        orientacoes_especificas=["Consistência pastosa/amassada em transição para sólida", "Sem adição de sal refinado ou açúcar", "Comida de verdade in natura"]
    ),

    "creche_7_11_meses_integral": PerfilNutricional(
        id_perfil="creche_7_11_meses_integral",
        etapa="creche",
        faixa_etaria="7_11_meses",
        periodo="integral",
        num_refeicoes=3,
        percentual_atendimento=70,
        percentual_label="70% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=475.0,
            carboidratos_g=IntervaloNutricional(65.0, 77.0),
            proteinas_g=IntervaloNutricional(12.0, 18.0),
            lipidios_g=IntervaloNutricional(13.0, 18.0),
            vitamina_a_mcg=350.0,
            vitamina_c_mg=35.0,
            calcio_mg=182.0,
            ferro_mg=5.0,
        ),
        limites=LimitesComposicao(
            max_sodio_mg=600.0,
            max_acucar_adicionado_pct=0.0,
            max_gordura_saturada_pct=7.0,
            gorduras_totais_pct=IntervaloNutricional(25.0, 35.0),
        ),
        metas_semanais=METAS_SEMANAIS_INTEGRAL,
        distribuicao_refeicoes=_dist_3ref_integral(475.0),
        frequencias_mensais=FrequenciasMensais(max_produtos_carneos=0, max_conservas=0, max_doces=0, max_liquidos_lacteos=0),
        alimentos_proibidos=["alimentos ultraprocessados", "alimentos com adição de açúcar", "alimentos com adição de mel", "alimentos com adição de adoçante", "alimentos ricos em gorduras trans industrializadas"],
        orientacoes_especificas=["Mínimo 3 refeições diárias para período integral", "Zero adição de açúcares ou adoçantes"]
    ),

    "creche_1_3_anos_parcial_2ref": PerfilNutricional(
        id_perfil="creche_1_3_anos_parcial_2ref",
        etapa="creche",
        faixa_etaria="1_3_anos",
        periodo="parcial",
        num_refeicoes=2,
        percentual_atendimento=30,
        percentual_label="30% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=304.0,
            carboidratos_g=IntervaloNutricional(42.0, 49.0),
            proteinas_g=IntervaloNutricional(8.0, 11.0),
            lipidios_g=IntervaloNutricional(8.0, 12.0),
            vitamina_a_mcg=63.0,
            vitamina_c_mg=4.0,
            calcio_mg=150.0,
            ferro_mg=1.0,
        ),
        limites=LimitesComposicao(
            max_sodio_mg=500.0,
            max_acucar_adicionado_pct=0.0,
            max_gordura_saturada_pct=7.0,
            gorduras_totais_pct=IntervaloNutricional(25.0, 35.0),
        ),
        metas_semanais=METAS_SEMANAIS_PARCIAL_2_REF,
        distribuicao_refeicoes=_dist_2ref_creche(304.0),
        frequencias_mensais=FrequenciasMensais(max_produtos_carneos=0, max_conservas=0, max_doces=0, max_liquidos_lacteos=0),
        alimentos_proibidos=["alimentos ultraprocessados", "alimentos com adição de açúcar", "alimentos com adição de mel", "alimentos com adição de adoçante", "alimentos ricos em gorduras trans industrializadas"],
        orientacoes_especificas=["Alimentação complementar saudável", "Proibido qualquer ultraprocessado e açúcar até 2 anos de idade completos"]
    ),

    "creche_1_3_anos_integral": PerfilNutricional(
        id_perfil="creche_1_3_anos_integral",
        etapa="creche",
        faixa_etaria="1_3_anos",
        periodo="integral",
        num_refeicoes=3,
        percentual_atendimento=70,
        percentual_label="70% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=708.0,
            carboidratos_g=IntervaloNutricional(97.0, 115.0),
            proteinas_g=IntervaloNutricional(18.0, 27.0),
            lipidios_g=IntervaloNutricional(20.0, 28.0),
            vitamina_a_mcg=147.0,
            vitamina_c_mg=9.0,
            calcio_mg=350.0,
            ferro_mg=2.0,
        ),
        limites=LimitesComposicao(
            max_sodio_mg=800.0,
            max_acucar_adicionado_pct=0.0,
            max_gordura_saturada_pct=7.0,
            gorduras_totais_pct=IntervaloNutricional(25.0, 35.0),
        ),
        metas_semanais=METAS_SEMANAIS_INTEGRAL,
        distribuicao_refeicoes=_dist_3ref_integral(708.0),
        frequencias_mensais=FrequenciasMensais(max_produtos_carneos=0, max_conservas=0, max_doces=0, max_liquidos_lacteos=0),
        alimentos_proibidos=["alimentos ultraprocessados", "alimentos com adição de açúcar", "alimentos com adição de mel", "alimentos com adição de adoçante", "alimentos ricos em gorduras trans industrializadas"],
        orientacoes_especificas=["Mínimo 3 refeições diárias", "Proibido adição de açúcar, mel e ultraprocessados"]
    ),

    # -----------------------------------------------------------------------
    # PRÉ-ESCOLA (4 a 5 anos) - 20%, 30% e 70% VET
    # -----------------------------------------------------------------------
    "pre_escola_4_5_anos_parcial_1ref": PerfilNutricional(
        id_perfil="pre_escola_4_5_anos_parcial_1ref",
        etapa="pre_escola",
        faixa_etaria="4_5_anos",
        periodo="parcial",
        num_refeicoes=1,
        percentual_atendimento=20,
        percentual_label="20% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=270.0,
            carboidratos_g=IntervaloNutricional(37.0, 44.0),
            proteinas_g=IntervaloNutricional(7.0, 10.0),
            lipidios_g=IntervaloNutricional(8.0, 11.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=600.0),
        metas_semanais=METAS_SEMANAIS_PARCIAL_1_REF,
        distribuicao_refeicoes=_dist_1ref_almoco(270.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),
    "pre_escola_4_5_anos_parcial_2ref": PerfilNutricional(
        id_perfil="pre_escola_4_5_anos_parcial_2ref",
        etapa="pre_escola",
        faixa_etaria="4_5_anos",
        periodo="parcial",
        num_refeicoes=2,
        percentual_atendimento=30,
        percentual_label="30% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=405.0,
            carboidratos_g=IntervaloNutricional(56.0, 66.0),
            proteinas_g=IntervaloNutricional(10.0, 15.0),
            lipidios_g=IntervaloNutricional(11.0, 16.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=800.0),
        metas_semanais=METAS_SEMANAIS_PARCIAL_2_REF,
        distribuicao_refeicoes=_dist_2ref_padrao(405.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),
    "pre_escola_4_5_anos_integral": PerfilNutricional(
        id_perfil="pre_escola_4_5_anos_integral",
        etapa="pre_escola",
        faixa_etaria="4_5_anos",
        periodo="integral",
        num_refeicoes=3,
        percentual_atendimento=70,
        percentual_label="70% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=945.0,
            carboidratos_g=IntervaloNutricional(130.0, 154.0),
            proteinas_g=IntervaloNutricional(24.0, 35.0),
            lipidios_g=IntervaloNutricional(26.0, 37.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=1400.0),
        metas_semanais=METAS_SEMANAIS_INTEGRAL,
        distribuicao_refeicoes=_dist_3ref_integral(945.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),

    # -----------------------------------------------------------------------
    # ENSINO FUNDAMENTAL (6 a 10 anos) - 20%, 30% e 70% VET
    # -----------------------------------------------------------------------
    "ensino_fundamental_6_10_anos_parcial_1ref": PerfilNutricional(
        id_perfil="ensino_fundamental_6_10_anos_parcial_1ref",
        etapa="ensino_fundamental",
        faixa_etaria="6_10_anos",
        periodo="parcial",
        num_refeicoes=1,
        percentual_atendimento=20,
        percentual_label="20% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=329.0,
            carboidratos_g=IntervaloNutricional(45.0, 53.0),
            proteinas_g=IntervaloNutricional(8.0, 12.0),
            lipidios_g=IntervaloNutricional(9.0, 13.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=600.0),
        metas_semanais=METAS_SEMANAIS_PARCIAL_1_REF,
        distribuicao_refeicoes=_dist_1ref_almoco(329.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),
    "ensino_fundamental_6_10_anos_parcial_2ref": PerfilNutricional(
        id_perfil="ensino_fundamental_6_10_anos_parcial_2ref",
        etapa="ensino_fundamental",
        faixa_etaria="6_10_anos",
        periodo="parcial",
        num_refeicoes=2,
        percentual_atendimento=30,
        percentual_label="30% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=493.0,
            carboidratos_g=IntervaloNutricional(68.0, 80.0),
            proteinas_g=IntervaloNutricional(12.0, 18.0),
            lipidios_g=IntervaloNutricional(14.0, 19.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=800.0),
        metas_semanais=METAS_SEMANAIS_PARCIAL_2_REF,
        distribuicao_refeicoes=_dist_2ref_padrao(493.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),
    "ensino_fundamental_6_10_anos_integral": PerfilNutricional(
        id_perfil="ensino_fundamental_6_10_anos_integral",
        etapa="ensino_fundamental",
        faixa_etaria="6_10_anos",
        periodo="integral",
        num_refeicoes=3,
        percentual_atendimento=70,
        percentual_label="70% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=1150.0,
            carboidratos_g=IntervaloNutricional(158.0, 187.0),
            proteinas_g=IntervaloNutricional(29.0, 43.0),
            lipidios_g=IntervaloNutricional(32.0, 45.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=1400.0),
        metas_semanais=METAS_SEMANAIS_INTEGRAL,
        distribuicao_refeicoes=_dist_3ref_integral(1150.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),

    # -----------------------------------------------------------------------
    # ENSINO FUNDAMENTAL (11 a 15 anos) - 20%, 30% e 70% VET
    # -----------------------------------------------------------------------
    "ensino_fundamental_11_15_anos_parcial_1ref": PerfilNutricional(
        id_perfil="ensino_fundamental_11_15_anos_parcial_1ref",
        etapa="ensino_fundamental",
        faixa_etaria="11_15_anos",
        periodo="parcial",
        num_refeicoes=1,
        percentual_atendimento=20,
        percentual_label="20% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=473.0,
            carboidratos_g=IntervaloNutricional(65.0, 77.0),
            proteinas_g=IntervaloNutricional(12.0, 18.0),
            lipidios_g=IntervaloNutricional(13.0, 18.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=600.0),
        metas_semanais=METAS_SEMANAIS_PARCIAL_1_REF,
        distribuicao_refeicoes=_dist_1ref_almoco(473.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),
    "ensino_fundamental_11_15_anos_parcial_2ref": PerfilNutricional(
        id_perfil="ensino_fundamental_11_15_anos_parcial_2ref",
        etapa="ensino_fundamental",
        faixa_etaria="11_15_anos",
        periodo="parcial",
        num_refeicoes=2,
        percentual_atendimento=30,
        percentual_label="30% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=710.0,
            carboidratos_g=IntervaloNutricional(98.0, 115.0),
            proteinas_g=IntervaloNutricional(18.0, 27.0),
            lipidios_g=IntervaloNutricional(20.0, 28.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=800.0),
        metas_semanais=METAS_SEMANAIS_PARCIAL_2_REF,
        distribuicao_refeicoes=_dist_2ref_padrao(710.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),
    "ensino_fundamental_11_15_anos_integral": PerfilNutricional(
        id_perfil="ensino_fundamental_11_15_anos_integral",
        etapa="ensino_fundamental",
        faixa_etaria="11_15_anos",
        periodo="integral",
        num_refeicoes=3,
        percentual_atendimento=70,
        percentual_label="70% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=1656.0,
            carboidratos_g=IntervaloNutricional(228.0, 269.0),
            proteinas_g=IntervaloNutricional(41.0, 62.0),
            lipidios_g=IntervaloNutricional(46.0, 64.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=1400.0),
        metas_semanais=METAS_SEMANAIS_INTEGRAL,
        distribuicao_refeicoes=_dist_3ref_integral(1656.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),

    # -----------------------------------------------------------------------
    # ENSINO MÉDIO (16 a 18 anos) - 20%, 30% e 70% VET
    # -----------------------------------------------------------------------
    "ensino_medio_16_18_anos_parcial_1ref": PerfilNutricional(
        id_perfil="ensino_medio_16_18_anos_parcial_1ref",
        etapa="ensino_medio",
        faixa_etaria="16_18_anos",
        periodo="parcial",
        num_refeicoes=1,
        percentual_atendimento=20,
        percentual_label="20% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=543.0,
            carboidratos_g=IntervaloNutricional(75.0, 88.0),
            proteinas_g=IntervaloNutricional(14.0, 20.0),
            lipidios_g=IntervaloNutricional(15.0, 21.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=600.0),
        metas_semanais=METAS_SEMANAIS_PARCIAL_1_REF,
        distribuicao_refeicoes=_dist_1ref_almoco(543.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
        orientacoes_especificas=["Garantir base sólida de carboidratos complexos (arroz, feijão, tubérculos)", "Proteína calibrada entre 14 e 20g"]
    ),
    "ensino_medio_16_18_anos_parcial_2ref": PerfilNutricional(
        id_perfil="ensino_medio_16_18_anos_parcial_2ref",
        etapa="ensino_medio",
        faixa_etaria="16_18_anos",
        periodo="parcial",
        num_refeicoes=2,
        percentual_atendimento=30,
        percentual_label="30% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=815.0,
            carboidratos_g=IntervaloNutricional(112.0, 132.0),
            proteinas_g=IntervaloNutricional(20.0, 31.0),
            lipidios_g=IntervaloNutricional(23.0, 32.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=800.0),
        metas_semanais=METAS_SEMANAIS_PARCIAL_2_REF,
        distribuicao_refeicoes=_dist_2ref_padrao(815.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),
    "ensino_medio_16_18_anos_integral": PerfilNutricional(
        id_perfil="ensino_medio_16_18_anos_integral",
        etapa="ensino_medio",
        faixa_etaria="16_18_anos",
        periodo="integral",
        num_refeicoes=3,
        percentual_atendimento=70,
        percentual_label="70% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=1902.0,
            carboidratos_g=IntervaloNutricional(262.0, 309.0),
            proteinas_g=IntervaloNutricional(48.0, 71.0),
            lipidios_g=IntervaloNutricional(53.0, 74.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=1400.0),
        metas_semanais=METAS_SEMANAIS_INTEGRAL,
        distribuicao_refeicoes=_dist_3ref_integral(1902.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),

    # -----------------------------------------------------------------------
    # EJA (19 a 30 anos) - 20%, 30% e 70% VET
    # -----------------------------------------------------------------------
    "eja_19_30_anos_parcial_1ref": PerfilNutricional(
        id_perfil="eja_19_30_anos_parcial_1ref",
        etapa="eja",
        faixa_etaria="19_30_anos",
        periodo="parcial",
        num_refeicoes=1,
        percentual_atendimento=20,
        percentual_label="20% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=477.0,
            carboidratos_g=IntervaloNutricional(66.0, 77.0),
            proteinas_g=IntervaloNutricional(12.0, 18.0),
            lipidios_g=IntervaloNutricional(8.0, 16.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=600.0),
        metas_semanais=METAS_SEMANAIS_PARCIAL_1_REF,
        distribuicao_refeicoes=_dist_1ref_almoco(477.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),
    "eja_19_30_anos_parcial_2ref": PerfilNutricional(
        id_perfil="eja_19_30_anos_parcial_2ref",
        etapa="eja",
        faixa_etaria="19_30_anos",
        periodo="parcial",
        num_refeicoes=2,
        percentual_atendimento=30,
        percentual_label="30% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=715.0,
            carboidratos_g=IntervaloNutricional(98.0, 116.0),
            proteinas_g=IntervaloNutricional(18.0, 27.0),
            lipidios_g=IntervaloNutricional(12.0, 24.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=800.0),
        metas_semanais=METAS_SEMANAIS_PARCIAL_2_REF,
        distribuicao_refeicoes=_dist_2ref_padrao(715.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),
    "eja_19_30_anos_integral": PerfilNutricional(
        id_perfil="eja_19_30_anos_integral",
        etapa="eja",
        faixa_etaria="19_30_anos",
        periodo="integral",
        num_refeicoes=3,
        percentual_atendimento=70,
        percentual_label="70% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=1668.0,
            carboidratos_g=IntervaloNutricional(229.0, 271.0),
            proteinas_g=IntervaloNutricional(42.0, 63.0),
            lipidios_g=IntervaloNutricional(28.0, 56.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=1400.0),
        metas_semanais=METAS_SEMANAIS_INTEGRAL,
        distribuicao_refeicoes=_dist_3ref_integral(1668.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),

    # -----------------------------------------------------------------------
    # EJA (31 a 60 anos) - 20%, 30% e 70% VET
    # -----------------------------------------------------------------------
    "eja_31_60_anos_parcial_1ref": PerfilNutricional(
        id_perfil="eja_31_60_anos_parcial_1ref",
        etapa="eja",
        faixa_etaria="31_60_anos",
        periodo="parcial",
        num_refeicoes=1,
        percentual_atendimento=20,
        percentual_label="20% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=459.0,
            carboidratos_g=IntervaloNutricional(63.0, 75.0),
            proteinas_g=IntervaloNutricional(11.0, 17.0),
            lipidios_g=IntervaloNutricional(8.0, 15.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=600.0),
        metas_semanais=METAS_SEMANAIS_PARCIAL_1_REF,
        distribuicao_refeicoes=_dist_1ref_almoco(459.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),
    "eja_31_60_anos_parcial_2ref": PerfilNutricional(
        id_perfil="eja_31_60_anos_parcial_2ref",
        etapa="eja",
        faixa_etaria="31_60_anos",
        periodo="parcial",
        num_refeicoes=2,
        percentual_atendimento=30,
        percentual_label="30% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=689.0,
            carboidratos_g=IntervaloNutricional(95.0, 112.0),
            proteinas_g=IntervaloNutricional(17.0, 26.0),
            lipidios_g=IntervaloNutricional(11.0, 23.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=800.0),
        metas_semanais=METAS_SEMANAIS_PARCIAL_2_REF,
        distribuicao_refeicoes=_dist_2ref_padrao(689.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),
    "eja_31_60_anos_integral": PerfilNutricional(
        id_perfil="eja_31_60_anos_integral",
        etapa="eja",
        faixa_etaria="31_60_anos",
        periodo="integral",
        num_refeicoes=3,
        percentual_atendimento=70,
        percentual_label="70% das necessidades diárias",
        nutricao=ParametrosNutricionais(
            energia_kcal=1607.0,
            carboidratos_g=IntervaloNutricional(221.0, 261.0),
            proteinas_g=IntervaloNutricional(40.0, 60.0),
            lipidios_g=IntervaloNutricional(27.0, 54.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=1400.0),
        metas_semanais=METAS_SEMANAIS_INTEGRAL,
        distribuicao_refeicoes=_dist_3ref_integral(1607.0),
        alimentos_proibidos=["alimentos ricos em gorduras trans industrializadas"],
    ),
}

# Aliases de compatibilidade para identificadores conceituais explícitos
ALIASES_PERFIS: Dict[str, PerfilNutricional] = {
    "creche_7_11_meses_integral_3ref": CATALOGO_PERFIS["creche_7_11_meses_integral"],
    "creche_1_3_anos_integral_3ref": CATALOGO_PERFIS["creche_1_3_anos_integral"],
    "pre_escola_4_5_anos_integral_3ref": CATALOGO_PERFIS["pre_escola_4_5_anos_integral"],
    "ensino_fundamental_6_10_anos_integral_3ref": CATALOGO_PERFIS["ensino_fundamental_6_10_anos_integral"],
    "ensino_fundamental_11_15_anos_integral_3ref": CATALOGO_PERFIS["ensino_fundamental_11_15_anos_integral"],
    "ensino_medio_16_18_anos_integral_3ref": CATALOGO_PERFIS["ensino_medio_16_18_anos_integral"],
    "eja_19_30_anos_integral_3ref": CATALOGO_PERFIS["eja_19_30_anos_integral"],
    "eja_31_60_anos_integral_3ref": CATALOGO_PERFIS["eja_31_60_anos_integral"],
}


# ---------------------------------------------------------------------------
# Mapeamento e Normalização de Aliases
# ---------------------------------------------------------------------------
ETAPAS_NORMALIZADAS = {
    "creche": "creche",
    "bercario": "creche",
    "pre": "pre_escola",
    "pre_escola": "pre_escola",
    "pré-escola": "pre_escola",
    "pre-escola": "pre_escola",
    "infantil": "pre_escola",
    "fundamental": "ensino_fundamental",
    "ensino_fundamental": "ensino_fundamental",
    "fundamental_1": "ensino_fundamental",
    "fundamental_2": "ensino_fundamental",
    "medio": "ensino_medio",
    "médio": "ensino_medio",
    "ensino_medio": "ensino_medio",
    "ensino_médio": "ensino_medio",
    "ensino medio": "ensino_medio",
    "ensino médio": "ensino_medio",
    "eja": "eja",
}

FAIXAS_ETARIAS_NORMALIZADAS = {
    # Creche (0 a 3 anos - geral ou subfaixas)
    "0_3": "1_3_anos",
    "0_3a": "1_3_anos",
    "0_3_anos": "1_3_anos",
    "0 a 3": "1_3_anos",
    "0 a 3 anos": "1_3_anos",
    "0_a_3_anos": "1_3_anos",
    "0_a_3": "1_3_anos",
    "7_11": "7_11_meses",
    "7_11m": "7_11_meses",
    "7_11_meses": "7_11_meses",
    "7 a 11 meses": "7_11_meses",
    "7_a_11_meses": "7_11_meses",
    "1_3": "1_3_anos",
    "1_3a": "1_3_anos",
    "1_3_anos": "1_3_anos",
    "1 a 3 anos": "1_3_anos",
    "1_a_3_anos": "1_3_anos",

    # Pré-escola
    "4_5": "4_5_anos",
    "4_5a": "4_5_anos",
    "4_5_anos": "4_5_anos",
    "4 a 5": "4_5_anos",
    "4 a 5 anos": "4_5_anos",

    # Fundamental
    "6_10": "6_10_anos",
    "6_10a": "6_10_anos",
    "6_10_anos": "6_10_anos",
    "6 a 10": "6_10_anos",
    "6 a 10 anos": "6_10_anos",
    "6_a_10_anos": "6_10_anos",

    "11_15": "11_15_anos",
    "11_15a": "11_15_anos",
    "11_15_anos": "11_15_anos",
    "11 a 15": "11_15_anos",
    "11 a 15 anos": "11_15_anos",
    "11_a_15_anos": "11_15_anos",

    # Médio
    "16_18": "16_18_anos",
    "16_18a": "16_18_anos",
    "16_18_anos": "16_18_anos",
    "16 a 18": "16_18_anos",
    "16 a 18 anos": "16_18_anos",
    "16_a_18_anos": "16_18_anos",

    # EJA
    "19_30": "19_30_anos",
    "19_30a": "19_30_anos",
    "19_30_anos": "19_30_anos",
    "19 a 30": "19_30_anos",
    "19 a 30 anos": "19_30_anos",
    "19_a_30_anos": "19_30_anos",

    "31_60": "31_60_anos",
    "31_60a": "31_60_anos",
    "31_60_anos": "31_60_anos",
    "31 a 60": "31_60_anos",
    "31 a 60 anos": "31_60_anos",
    "31_a_60_anos": "31_60_anos",
}

# Compatibilidade válida entre etapa e faixa etária
ETAPAS_FAIXAS_VALIDAS = {
    "creche": {"7_11_meses", "1_3_anos"},
    "pre_escola": {"4_5_anos"},
    "ensino_fundamental": {"6_10_anos", "11_15_anos"},
    "ensino_medio": {"16_18_anos"},
    "eja": {"19_30_anos", "31_60_anos"},
}


def resolver_perfil(
    etapa: str,
    faixa_etaria: str,
    periodo: Optional[str] = None,
    num_refeicoes: Optional[int] = None,
) -> PerfilNutricional:
    """
    Resolve determinísticamente o perfil nutricional oficial do PNAE a partir dos parâmetros de entrada.

    Levanta PerfilNaoSuportadoError se os parâmetros formarem uma combinação inválida
    ou não suportada pelas normas do FNDE.
    """
    if not etapa or not str(etapa).strip():
        raise PerfilNaoSuportadoError("Etapa de ensino é obrigatória para a resolução do pipeline.")
    if not faixa_etaria or not str(faixa_etaria).strip():
        raise PerfilNaoSuportadoError("Faixa etária é obrigatória para a resolução do pipeline.")

    # 1. Normalizar etapa
    etapa_limpa = str(etapa).strip().lower()
    etapa_norm = ETAPAS_NORMALIZADAS.get(etapa_limpa)
    if not etapa_norm:
        raise PerfilNaoSuportadoError(f"Etapa de ensino não reconhecida ou não suportada: '{etapa}'.")

    # 2. Normalizar faixa etária
    faixa_limpa = str(faixa_etaria).strip().lower()
    faixa_norm = FAIXAS_ETARIAS_NORMALIZADAS.get(faixa_limpa)
    if not faixa_norm:
        raise PerfilNaoSuportadoError(f"Faixa etária não reconhecida ou não suportada: '{faixa_etaria}'.")

    # 3. Validar se a faixa etária pertence à etapa
    faixas_permitidas = ETAPAS_FAIXAS_VALIDAS.get(etapa_norm, set())
    if faixa_norm not in faixas_permitidas:
        raise PerfilNaoSuportadoError(
            f"Combinação inválida de etapa '{etapa}' ({etapa_norm}) e faixa etária '{faixa_etaria}' ({faixa_norm}). "
            f"Faixas permitidas para {etapa_norm}: {sorted(list(faixas_permitidas))}."
        )

    # 4. Determinar e validar período e número de refeições
    refeicoes = int(num_refeicoes or 1)
    if refeicoes < 1:
        raise PerfilNaoSuportadoError(f"Número de refeições por dia deve ser no mínimo 1. Informado: {num_refeicoes}.")

    periodo_limpo = str(periodo or "").strip().lower()
    if periodo_limpo and periodo_limpo not in ("parcial", "integral"):
        raise PerfilNaoSuportadoError(f"Período de atendimento inválido: '{periodo}'. Valores permitidos: 'parcial', 'integral'.")

    # Resolução do período quando não informado explicitamente
    if not periodo_limpo:
        if refeicoes == 3:
            periodo_resolvido = "integral"
        elif refeicoes in (1, 2):
            periodo_resolvido = "parcial"
        else:
            raise PerfilNaoSuportadoError(
                f"Quantidade de refeições '{refeicoes}' não possui período correspondente suportado pelas normas do PNAE."
            )
    else:
        periodo_resolvido = periodo_limpo

    # Validação rigorosa: não presumir equivalências e rejeitar combinações inválidas
    if periodo_resolvido == "integral":
        if refeicoes != 3:
            raise PerfilNaoSuportadoError(
                f"O período integral regulamentar do PNAE neste sistema exige exatamente 3 refeições diárias (70% VET). "
                f"Combinação não suportada: período='integral' com {refeicoes} refeição(ões)."
            )
    elif periodo_resolvido == "parcial":
        if etapa_norm == "creche":
            if refeicoes != 2:
                raise PerfilNaoSuportadoError(
                    f"A etapa Creche exige no mínimo 2 refeições diárias (parcial 30%) ou 3 refeições diárias (integral 70%) "
                    f"conforme a Resolução CD/FNDE nº 06/2020. Informado: {refeicoes} refeição(ões)."
                )
        else:
            if refeicoes not in (1, 2):
                raise PerfilNaoSuportadoError(
                    f"O período parcial para {etapa_norm} suporta apenas 1 refeição (20% VET) ou 2 refeições (30% VET). "
                    f"Informado: {refeicoes} refeição(ões). Para 3 refeições, selecione período integral."
                )

    # 5. Resolução determinística da chave do perfil
    if periodo_resolvido == "integral":
        id_chave = f"{etapa_norm}_{faixa_norm}_integral"
    else:
        id_chave = f"{etapa_norm}_{faixa_norm}_parcial_{refeicoes}ref"

    perfil = CATALOGO_PERFIS.get(id_chave) or ALIASES_PERFIS.get(id_chave)
    if not perfil:
        raise PerfilNaoSuportadoError(
            f"Nenhum perfil oficial encontrado para {etapa_norm} / {faixa_norm} com {refeicoes} ref (período: {periodo_resolvido})."
        )

    # 6. Validar completude das metas diárias e configuração da distribuição por refeição
    if not perfil.nutricao or perfil.nutricao.energia_kcal <= 0:
        raise PerfilIncompletoError(
            f"Perfil '{id_chave}' encontrado, mas suas metas nutricionais diárias estão incompletas."
        )

    perfil.validar_distribuicao()

    return perfil
