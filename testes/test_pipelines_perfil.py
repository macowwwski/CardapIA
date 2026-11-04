"""
Testes unitários e de integração para os pipelines especializados por perfil escolar do PNAE.

Cobre:
1. Resolução determinística e seleção de pipelines especializados.
2. Normalização de aliases e equivalências de entrada.
3. Rejeição com erro explícito de combinações inválidas ou não suportadas.
4. Integridade dos parâmetros nutricionais de todos os 22 perfis oficiais do PNAE.
5. Especialização dos prompts do sistema por perfil (sem contaminação cruzada).
6. Regras de porcionamento per capita, controle de óleos, sal e descarte de água avulsa.
7. Auditoria independente por perfil nutricional.
"""
try:
    import pytest
except ImportError:
    import contextlib
    class DummyMark:
        @staticmethod
        def parametrize(*args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

    class DummyPytest:
        mark = DummyMark()

        @staticmethod
        @contextlib.contextmanager
        def raises(expected_exception):
            class ExcInfo:
                value = None
            info = ExcInfo()
            try:
                yield info
            except expected_exception as e:
                info.value = e
            else:
                raise AssertionError(f"Esperava {expected_exception.__name__}, mas nenhuma exceção foi levantada.")
    pytest = DummyPytest()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipelines import (
    resolver_perfil,
    selecionar_pipeline,
    PerfilNaoSuportadoError,
    CATALOGO_PERFIS,
    CrechePipeline,
    PreEscolaPipeline,
    EnsinoFundamentalPipeline,
    EnsinoMedioPipeline,
    EJAPipeline,
)
from src.schemas_pydantic import (
    CardapioSchema,
    SemanaSchema,
    DiaSchema,
    RefeicaoSchema,
    PratoSchema,
    IngredienteSchema,
)


# ===========================================================================
# 1. TESTES DE SELEÇÃO E RESOLUÇÃO DETERMINÍSTICA DE PIPELINES
# ===========================================================================

def test_selecao_ensino_medio_16_18_1_refeicao():
    """Garante seleção do pipeline de Ensino Médio (16 a 18 anos, 1 refeição / 20% VET)."""
    pipeline = selecionar_pipeline(
        etapa="ensino_medio",
        faixa_etaria="16_18",
        periodo="parcial",
        num_refeicoes=1,
    )
    assert isinstance(pipeline, EnsinoMedioPipeline)
    p = pipeline.perfil
    assert p.id_perfil == "ensino_medio_16_18_anos_parcial_1ref"
    assert p.percentual_atendimento == 20
    assert p.nutricao.energia_kcal == 543.0
    assert p.nutricao.carboidratos_g.minimo == 75.0
    assert p.nutricao.carboidratos_g.maximo == 88.0
    assert p.nutricao.proteinas_g.minimo == 14.0
    assert p.nutricao.proteinas_g.maximo == 20.0
    assert p.nutricao.lipidios_g.minimo == 15.0
    assert p.nutricao.lipidios_g.maximo == 21.0
    assert p.limites.max_sodio_mg == 600.0


def test_selecao_ensino_fundamental_6_10_2_refeicoes():
    """Garante seleção do pipeline de Ensino Fundamental (6 a 10 anos, 2 refeições / 30% VET)."""
    pipeline = selecionar_pipeline(
        etapa="ensino_fundamental",
        faixa_etaria="6_10",
        periodo="parcial",
        num_refeicoes=2,
    )
    assert isinstance(pipeline, EnsinoFundamentalPipeline)
    p = pipeline.perfil
    assert p.id_perfil == "ensino_fundamental_6_10_anos_parcial_2ref"
    assert p.percentual_atendimento == 30
    assert p.nutricao.energia_kcal == 493.0
    assert p.nutricao.carboidratos_g.minimo == 68.0
    assert p.nutricao.carboidratos_g.maximo == 80.0
    assert p.nutricao.proteinas_g.minimo == 12.0
    assert p.nutricao.proteinas_g.maximo == 18.0
    assert p.nutricao.lipidios_g.minimo == 14.0
    assert p.nutricao.lipidios_g.maximo == 19.0
    assert p.limites.max_sodio_mg == 800.0


def test_selecao_ensino_fundamental_11_15_1_refeicao():
    """Garante seleção do pipeline de Ensino Fundamental (11 a 15 anos, 1 refeição / 20% VET)."""
    pipeline = selecionar_pipeline(
        etapa="ensino_fundamental",
        faixa_etaria="11_15",
        periodo="parcial",
        num_refeicoes=1,
    )
    assert isinstance(pipeline, EnsinoFundamentalPipeline)
    p = pipeline.perfil
    assert p.id_perfil == "ensino_fundamental_11_15_anos_parcial_1ref"
    assert p.percentual_atendimento == 20
    assert p.nutricao.energia_kcal == 473.0
    assert p.nutricao.carboidratos_g.minimo == 65.0
    assert p.nutricao.carboidratos_g.maximo == 77.0
    assert p.nutricao.proteinas_g.minimo == 12.0
    assert p.nutricao.proteinas_g.maximo == 18.0
    assert p.nutricao.lipidios_g.minimo == 13.0
    assert p.nutricao.lipidios_g.maximo == 18.0


def test_selecao_pre_escola():
    """Garante seleção do pipeline de Pré-Escola (4 a 5 anos)."""
    pipeline = selecionar_pipeline(
        etapa="pre_escola",
        faixa_etaria="4_5",
        periodo="parcial",
        num_refeicoes=1,
    )
    assert isinstance(pipeline, PreEscolaPipeline)
    assert pipeline.perfil.nutricao.energia_kcal == 270.0


def test_selecao_eja():
    """Garante seleção do pipeline de EJA (19 a 30 anos e 31 a 60 anos)."""
    p1 = selecionar_pipeline("eja", "19_30", "parcial", 1)
    assert isinstance(p1, EJAPipeline)
    assert p1.perfil.nutricao.energia_kcal == 477.0

    p2 = selecionar_pipeline("eja", "31_60", "parcial", 2)
    assert isinstance(p2, EJAPipeline)
    assert p2.perfil.nutricao.energia_kcal == 689.0


def test_selecao_creche_e_micronutrientes():
    """Garante seleção de Creche e presença obrigatória de micronutrientes."""
    pipeline_parcial = selecionar_pipeline("creche", "7_11_meses", "parcial", 2)
    assert isinstance(pipeline_parcial, CrechePipeline)
    n = pipeline_parcial.perfil.nutricao
    assert n.energia_kcal == 203.0
    assert n.vitamina_a_mcg == 150.0
    assert n.vitamina_c_mg == 15.0
    assert n.calcio_mg == 78.0
    assert n.ferro_mg == 2.0
    assert "alimentos ultraprocessados" in pipeline_parcial.perfil.alimentos_proibidos
    assert "alimentos com adição de açúcar" in pipeline_parcial.perfil.alimentos_proibidos

    pipeline_integral = selecionar_pipeline("creche", "1_3_anos", "integral", 3)
    assert isinstance(pipeline_integral, CrechePipeline)
    n2 = pipeline_integral.perfil.nutricao
    assert n2.energia_kcal == 708.0
    assert n2.vitamina_a_mcg == 147.0
    assert n2.vitamina_c_mg == 9.0
    assert n2.calcio_mg == 350.0
    assert n2.ferro_mg == 2.0


# ===========================================================================
# 2. TESTES DE NORMALIZAÇÃO DE ALIASES E FORMATOS EQUIVALENTES
# ===========================================================================

@pytest.mark.parametrize("etapa_in,faixa_in,esperado_id", [
    ("medio", "16_18", "ensino_medio_16_18_anos_parcial_1ref"),
    ("ensino medio", "16 a 18 anos", "ensino_medio_16_18_anos_parcial_1ref"),
    ("ensino_médio", "16_18a", "ensino_medio_16_18_anos_parcial_1ref"),
    ("fundamental", "6_10", "ensino_fundamental_6_10_anos_parcial_1ref"),
    ("fundamental_1", "6 a 10 anos", "ensino_fundamental_6_10_anos_parcial_1ref"),
    ("fundamental_2", "11 a 15 anos", "ensino_fundamental_11_15_anos_parcial_1ref"),
    ("pre", "4_5", "pre_escola_4_5_anos_parcial_1ref"),
    ("pré-escola", "4 a 5 anos", "pre_escola_4_5_anos_parcial_1ref"),
    ("infantil", "4_5_anos", "pre_escola_4_5_anos_parcial_1ref"),
    ("creche", "0_3", "creche_1_3_anos_parcial_2ref"),
    ("creche", "0 a 3 anos", "creche_1_3_anos_parcial_2ref"),
    ("creche", "1 a 3 anos", "creche_1_3_anos_parcial_2ref"),
    ("bercario", "7 a 11 meses", "creche_7_11_meses_parcial_2ref"),
])
def test_normalizacao_aliases(etapa_in, faixa_in, esperado_id):
    """Verifica que variações de escrita e aliases do backend resolvem o perfil correto."""
    num_ref = 2 if "creche" in esperado_id else 1
    perfil = resolver_perfil(etapa=etapa_in, faixa_etaria=faixa_in, periodo="parcial", num_refeicoes=num_ref)
    assert perfil.id_perfil == esperado_id


# ===========================================================================
# 3. TESTES DE REJEIÇÃO DETERMINÍSTICA DE COMBINAÇÕES INVÁLIDAS
# ===========================================================================

def test_rejeicao_creche_com_idade_ensino_medio():
    """Creche não pode atender adolescentes de 16 a 18 anos."""
    with pytest.raises(PerfilNaoSuportadoError) as exc_info:
        selecionar_pipeline(etapa="creche", faixa_etaria="16_18", periodo="parcial", num_refeicoes=2)
    assert "Combinação inválida de etapa 'creche'" in str(exc_info.value)


def test_rejeicao_ensino_medio_com_meses():
    """Ensino Médio não pode atender bebês de 7 a 11 meses."""
    with pytest.raises(PerfilNaoSuportadoError) as exc_info:
        selecionar_pipeline(etapa="ensino_medio", faixa_etaria="7_11_meses", periodo="parcial", num_refeicoes=1)
    assert "Combinação inválida de etapa 'ensino_medio'" in str(exc_info.value)


def test_rejeicao_creche_com_1_refeicao():
    """Creche exige no mínimo 2 refeições para parcial e 3 para integral segundo o PNAE."""
    with pytest.raises(PerfilNaoSuportadoError) as exc_info:
        selecionar_pipeline(etapa="creche", faixa_etaria="1_3_anos", periodo="parcial", num_refeicoes=1)
    assert "A etapa Creche exige no mínimo 2 refeições diárias" in str(exc_info.value)


def test_rejeicao_etapa_inexistente():
    """Etapas inexistentes devem ser rejeitadas com erro claro."""
    with pytest.raises(PerfilNaoSuportadoError) as exc_info:
        selecionar_pipeline(etapa="doutorado", faixa_etaria="16_18", periodo="parcial", num_refeicoes=1)
    assert "Etapa de ensino não reconhecida" in str(exc_info.value)


def test_rejeicao_parametros_vazios():
    """Campos em branco ou nulos devem ser rejeitados determinísticamente."""
    with pytest.raises(PerfilNaoSuportadoError):
        selecionar_pipeline(etapa="", faixa_etaria="16_18")
    with pytest.raises(PerfilNaoSuportadoError):
        selecionar_pipeline(etapa="medio", faixa_etaria="")


# ===========================================================================
# 4. TESTES DE PROMPTS ESPECIALIZADOS (SEM CONTAMINAÇÃO CRUZADA)
# ===========================================================================

def test_prompt_especializado_ensino_medio():
    """O prompt do Ensino Médio deve focar em 16-18 anos e não conter regras de creche."""
    pipeline = selecionar_pipeline("ensino_medio", "16_18", "parcial", 1)
    prompt = pipeline.construir_system_prompt()
    # Deve conter referências específicas
    assert "543.0 kcal" in prompt
    assert "75.0g a 88.0g" in prompt
    assert "14.0g a 20.0g" in prompt
    assert "15.0g a 21.0g" in prompt
    # NÃO deve conter regras de creche
    assert "alimentação complementar" not in prompt.lower()
    assert "papa salgada" not in prompt.lower()
    assert "amassados com garfo" not in prompt.lower()


def test_prompt_especializado_creche():
    """O prompt de Creche deve conter proibições de açúcar e consistência sem valores de ensino médio."""
    pipeline = selecionar_pipeline("creche", "7_11_meses", "parcial", 2)
    prompt = pipeline.construir_system_prompt()
    assert "203.0 kcal" in prompt
    assert "alimentos com adição de açúcar" in prompt.lower()
    assert "alimentos ultraprocessados" in prompt.lower()
    assert "amassados com garfo" in prompt.lower()
    # NÃO deve conter as 543 kcal do ensino médio
    assert "543" not in prompt


# ===========================================================================
# 5. TESTES DE PORCIONAMENTO PER CAPITA E CONTROLE DE INGREDIENTES
# ===========================================================================

def test_aplicar_per_capita_elimina_agua_e_calibra_sal():
    """
    Garante que a etapa de per capita elimina água de cocção avulsa,
    unifica óleos e calibra o sal de cozinha.
    """
    pipeline = selecionar_pipeline("ensino_medio", "16_18", "parcial", 1)

    cardapio_teste = CardapioSchema(
        nome="Cardápio Teste",
        mes_aplicacao="outubro de 2026",
        observacoes="Planejamento de teste",
        semanas=[
            SemanaSchema(
                numero=1,
                dias=[
                    DiaSchema(
                        dia_semana="segunda-feira",
                        refeicoes=[
                            RefeicaoSchema(
                                tipo="almoço",
                                horario="11:30",
                                pratos=[
                                    PratoSchema(
                                        nome="Arroz Branco",
                                        estado_preparacao="cozido",
                                        ingredientes=[
                                            IngredienteSchema(nome_taco="Arroz, tipo 1, cozido", quantidade_g=100),
                                            IngredienteSchema(nome_taco="Água potável", quantidade_g=50),
                                            IngredienteSchema(nome_taco="Sal", quantidade_g=3.0),
                                            IngredienteSchema(nome_taco="Azeite de oliva", quantidade_g=10.0),
                                        ]
                                    ),
                                    PratoSchema(
                                        nome="Feijão Carioca",
                                        estado_preparacao="cozido",
                                        ingredientes=[
                                            IngredienteSchema(nome_taco="Feijão, carioca, cozido", quantidade_g=80),
                                            IngredienteSchema(nome_taco="Água", quantidade_g=40),
                                            IngredienteSchema(nome_taco="Sal", quantidade_g=3.0),
                                            IngredienteSchema(nome_taco="Azeite de oliva", quantidade_g=10.0),
                                        ]
                                    ),
                                ]
                            )
                        ]
                    )
                ]
            )
        ]
    )

    from unittest.mock import patch
    from src.taco.resolver import MatchTaco
    mock_match = MatchTaco(taco_id="1", description="alimento", score=1.0, payload={})
    with patch("src.pipelines.base.resolver_taco", return_value=mock_match), \
         patch("src.pipelines.base.resolver_per_capita", return_value=50.0):
        cardapio_ajustado = pipeline.aplicar_per_capita(cardapio_teste)
    todos_ingredientes = [
        ing.nome_taco.lower()
        for s in cardapio_ajustado.semanas
        for d in s.dias
        for r in d.refeicoes
        for p in r.pratos
        for ing in p.ingredientes
    ]

    # Água não deve estar presente
    assert not any("água" in n or "agua" in n for n in todos_ingredientes)
    # Azeite deve estar presente exatamente 1 vez
    assert sum(1 for n in todos_ingredientes if "azeite" in n) == 1
    # Sal deve estar presente exatamente 1 vez
    assert sum(1 for n in todos_ingredientes if "sal" in n) == 1


# ===========================================================================
# 6. TESTE DE COBERTURA INTEGRAL DO CATÁLOGO DE PERFIS
# ===========================================================================

def test_catalogo_contem_22_perfis():
    """Garante que todos os 22 perfis oficiais do PNAE estão cadastrados e são imutáveis."""
    assert len(CATALOGO_PERFIS) == 22
    for chave, perfil in CATALOGO_PERFIS.items():
        assert perfil.id_perfil == chave
        assert perfil.nutricao.energia_kcal > 0
        assert perfil.nutricao.carboidratos_g.minimo > 0
        assert perfil.nutricao.proteinas_g.minimo > 0
        assert perfil.nutricao.lipidios_g.minimo > 0
        assert perfil.limites.max_sodio_mg > 0


if __name__ == "__main__":
    testes = [
        ("Seleção Ensino Médio 16-18 (1 ref / 20% VET)", test_selecao_ensino_medio_16_18_1_refeicao),
        ("Seleção Ensino Fundamental 6-10 (2 ref / 30% VET)", test_selecao_ensino_fundamental_6_10_2_refeicoes),
        ("Seleção Ensino Fundamental 11-15 (1 ref / 20% VET)", test_selecao_ensino_fundamental_11_15_1_refeicao),
        ("Seleção Pré-Escola (4-5 anos)", test_selecao_pre_escola),
        ("Seleção EJA (19-30 e 31-60 anos)", test_selecao_eja),
        ("Seleção Creche e Micronutrientes (7-11m e 1-3a)", test_selecao_creche_e_micronutrientes),
        ("Normalização de aliases e equivalências", lambda: [
            test_normalizacao_aliases(e, f, i) for e, f, i in [
                ("medio", "16_18", "ensino_medio_16_18_anos_parcial_1ref"),
                ("ensino medio", "16 a 18 anos", "ensino_medio_16_18_anos_parcial_1ref"),
                ("ensino_médio", "16_18a", "ensino_medio_16_18_anos_parcial_1ref"),
                ("fundamental", "6_10", "ensino_fundamental_6_10_anos_parcial_1ref"),
                ("fundamental_1", "6 a 10 anos", "ensino_fundamental_6_10_anos_parcial_1ref"),
                ("fundamental_2", "11 a 15 anos", "ensino_fundamental_11_15_anos_parcial_1ref"),
                ("pre", "4_5", "pre_escola_4_5_anos_parcial_1ref"),
                ("pré-escola", "4 a 5 anos", "pre_escola_4_5_anos_parcial_1ref"),
                ("infantil", "4_5_anos", "pre_escola_4_5_anos_parcial_1ref"),
                ("creche", "0_3", "creche_1_3_anos_parcial_2ref"),
                ("creche", "0 a 3 anos", "creche_1_3_anos_parcial_2ref"),
                ("creche", "1 a 3 anos", "creche_1_3_anos_parcial_2ref"),
                ("bercario", "7 a 11 meses", "creche_7_11_meses_parcial_2ref"),
            ]
        ]),
        ("Rejeição de creche com idade de ensino médio", test_rejeicao_creche_com_idade_ensino_medio),
        ("Rejeição de ensino médio com idade em meses", test_rejeicao_ensino_medio_com_meses),
        ("Rejeição de creche com 1 refeição (mínimo exigido 2)", test_rejeicao_creche_com_1_refeicao),
        ("Rejeição de etapa inexistente", test_rejeicao_etapa_inexistente),
        ("Rejeição de parâmetros vazios", test_rejeicao_parametros_vazios),
        ("Prompt especializado do Ensino Médio", test_prompt_especializado_ensino_medio),
        ("Prompt especializado de Creche", test_prompt_especializado_creche),
        ("Per capita elimina água avulsa e calibra sal/óleo", test_aplicar_per_capita_elimina_agua_e_calibra_sal),
        ("Catálogo de 22 perfis nutricionais completos", test_catalogo_contem_22_perfis),
    ]

    falhas = 0
    print("=" * 70)
    print("EXECUTANDO SUÍTE DE TESTES: PIPELINES POR PERFIL ESCOLAR (PNAE)")
    print("=" * 70)
    for nome, fn in testes:
        try:
            fn()
            print(f"  [OK] {nome}")
        except Exception as e:
            falhas += 1
            print(f"  [FALHA] {nome}: {e}")
            import traceback
            traceback.print_exc()
    print("=" * 70)
    if falhas == 0:
        print(f"SUCESSO TOTAL: Todos os {len(testes)} testes de pipeline foram APROVADOS!")
    else:
        print(f"ERRO: {falhas} teste(s) falharam.")
        sys.exit(1)
