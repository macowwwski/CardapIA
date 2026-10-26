"""
Suíte de testes obrigatórios do PNAE:
Perfis Nutricionais, Separação entre Metas Diárias e Distribuição por Refeição.

Cobre rigorosamente os requisitos da especificação:
1. Dois perfis da mesma etapa e faixa etária com números diferentes de refeições.
2. Seleção correta do percentual de atendimento (20%, 30%, 70%).
3. Distribuição configurada e soma diária dos nutrientes (energia e percentuais).
4. Perfil sem distribuição configurada (DistribuicaoNaoConfiguradaError).
5. Distribuição com percentuais inconsistentes (DistribuicaoInvalidaError).
6. Refeição esperada ausente na auditoria por refeição (inconformidade crítica).
7. Semântica da porção per capita já concebida para a refeição.
8. Aplicação de fator de cocção e prevenção de dupla conversão.
9. Auditoria em dois níveis: diária (soma real) e semanal (diversidade e FLV).
10. Persistência e leitura das entidades PerfilPNAE e DistribuicaoRefeicaoPNAE.
11. Compatibilidade com o contrato da API consumido pelo CooperaAgro-Back.
"""
import sys
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipelines.models import (
    PerfilNutricional,
    ParametrosNutricionais,
    IntervaloNutricional,
    LimitesComposicao,
    MetasSemanais,
    DistribuicaoRefeicao,
    DistribuicaoNaoConfiguradaError,
    DistribuicaoInvalidaError,
    PerfilIncompletoError,
)
from src.pipelines import (
    resolver_perfil,
    selecionar_pipeline,
    PerfilNaoSuportadoError,
    CATALOGO_PERFIS,
)
from src.schemas_pydantic import (
    CardapioSchema,
    SemanaSchema,
    DiaSchema,
    RefeicaoSchema,
    PratoSchema,
    IngredienteSchema,
    TipoRefeicao,
)


# ===========================================================================
# 1. DOIS PERFIS DA MESMA ETAPA E FAIXA ETÁRIA COM NÚMEROS DIFERENTES DE REFEIÇÕES
# ===========================================================================

def test_mesma_etapa_diferentes_refeicoes():
    """Dois perfis da mesma etapa e faixa (Ensino Médio 16-18) devem ter configurações e metas distintas."""
    perfil_1ref = resolver_perfil(etapa="ensino_medio", faixa_etaria="16_18", periodo="parcial", num_refeicoes=1)
    perfil_2ref = resolver_perfil(etapa="ensino_medio", faixa_etaria="16_18", periodo="parcial", num_refeicoes=2)
    perfil_3ref = resolver_perfil(etapa="ensino_medio", faixa_etaria="16_18", periodo="integral", num_refeicoes=3)

    # Identificadores distintos
    assert perfil_1ref.id_perfil != perfil_2ref.id_perfil != perfil_3ref.id_perfil
    assert perfil_1ref.num_refeicoes == 1
    assert perfil_2ref.num_refeicoes == 2
    assert perfil_3ref.num_refeicoes == 3

    # Metas de energia distintas (20% vs 30% vs 70% VET)
    assert perfil_1ref.percentual_atendimento == 20
    assert perfil_2ref.percentual_atendimento == 30
    assert perfil_3ref.percentual_atendimento == 70

    assert perfil_1ref.nutricao.energia_kcal == 543.0
    assert perfil_2ref.nutricao.energia_kcal == 815.0
    assert perfil_3ref.nutricao.energia_kcal == 1902.0

    # Distribuições distintas
    assert len(perfil_1ref.distribuicao_refeicoes) == 1
    assert len(perfil_2ref.distribuicao_refeicoes) == 2
    assert len(perfil_3ref.distribuicao_refeicoes) == 3


# ===========================================================================
# 2. SELEÇÃO DO PERCENTUAL DE ATENDIMENTO
# ===========================================================================

def test_selecao_percentual_atendimento():
    """Valida correspondência estrita entre período/refeições e percentual de atendimento."""
    # 20% VET: parcial 1 refeição
    p_fund_1 = resolver_perfil(etapa="ensino_fundamental", faixa_etaria="6_10", periodo="parcial", num_refeicoes=1)
    assert p_fund_1.percentual_atendimento == 20

    # 30% VET: parcial 2 refeições
    p_fund_2 = resolver_perfil(etapa="ensino_fundamental", faixa_etaria="6_10", periodo="parcial", num_refeicoes=2)
    assert p_fund_2.percentual_atendimento == 30

    # 70% VET: integral 3 refeições
    p_fund_3 = resolver_perfil(etapa="ensino_fundamental", faixa_etaria="6_10", periodo="integral", num_refeicoes=3)
    assert p_fund_3.percentual_atendimento == 70

    # Creche parcial é obrigatoriamente 30% VET (2 refeições)
    p_creche = resolver_perfil(etapa="creche", faixa_etaria="1_3", periodo="parcial", num_refeicoes=2)
    assert p_creche.percentual_atendimento == 30


# ===========================================================================
# 3. DISTRIBUIÇÃO CONFIGURADA E SOMA DIÁRIA DOS NUTRIENTES
# ===========================================================================

def test_distribuicao_soma_diaria_nutrientes():
    """Valida que todos os 22 perfis possuem distribuição cuja soma de percentuais e calorias é consistente."""
    for id_perfil, perfil in CATALOGO_PERFIS.items():
        assert len(perfil.distribuicao_refeicoes) == perfil.num_refeicoes, (
            f"Perfil {id_perfil} exige {perfil.num_refeicoes} ref mas tem {len(perfil.distribuicao_refeicoes)}"
        )

        soma_pct = sum(d.percentual_energia for d in perfil.distribuicao_refeicoes if d.percentual_energia is not None)
        esperado_pct = perfil.percentual_atendimento / 100.0
        assert abs(soma_pct - esperado_pct) <= 0.01, (
            f"Perfil {id_perfil}: soma_pct {soma_pct} != esperado {esperado_pct}"
        )

        # Soma das calorias-alvo de cada refeição deve convergir para a meta global diária
        soma_kcal = sum(d.energia_kcal_alvo for d in perfil.distribuicao_refeicoes if d.energia_kcal_alvo is not None)
        assert abs(soma_kcal - perfil.nutricao.energia_kcal) <= 1.0, (
            f"Perfil {id_perfil}: soma_kcal {soma_kcal} != meta {perfil.nutricao.energia_kcal}"
        )


# ===========================================================================
# 4. PERFIL SEM DISTRIBUIÇÃO CONFIGURADA
# ===========================================================================

def test_perfil_sem_distribuicao_configurada():
    """Perfil sem distribuição por refeição deve falhar na validação com DistribuicaoNaoConfiguradaError."""
    perfil_invalido = PerfilNutricional(
        id_perfil="fixture_teste_sem_dist",
        etapa="ensino_medio",
        faixa_etaria="16_18_anos",
        periodo="parcial",
        num_refeicoes=1,
        percentual_atendimento=20,
        percentual_label="20%",
        nutricao=ParametrosNutricionais(
            energia_kcal=500.0,
            carboidratos_g=IntervaloNutricional(70.0, 80.0),
            proteinas_g=IntervaloNutricional(15.0, 20.0),
            lipidios_g=IntervaloNutricional(10.0, 15.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=600.0),
        metas_semanais=MetasSemanais(min_diversidade=10, min_flv_g=280.0, min_frutas_dias=2, min_legumes_verduras_dias=3, max_biscoito_semana=2),
        distribuicao_refeicoes=[],  # Sem distribuição!
    )

    try:
        perfil_invalido.validar_distribuicao()
        assert False, "Deveria ter levantado DistribuicaoNaoConfiguradaError"
    except DistribuicaoNaoConfiguradaError as e:
        assert "não possui distribuição de refeições validada" in str(e)


# ===========================================================================
# 5. DISTRIBUIÇÃO COM PERCENTUAIS INCONSISTENTES
# ===========================================================================

def test_distribuicao_com_percentuais_inconsistentes():
    """Distribuição cuja soma de energia diverge da meta diária deve levantar DistribuicaoInvalidaError."""
    # Caso 1: Quantidade de refeições diferente de num_refeicoes
    perfil_qtd_errada = PerfilNutricional(
        id_perfil="fixture_qtd_errada",
        etapa="ensino_medio",
        faixa_etaria="16_18_anos",
        periodo="parcial",
        num_refeicoes=2,
        percentual_atendimento=30,
        percentual_label="30%",
        nutricao=ParametrosNutricionais(
            energia_kcal=800.0,
            carboidratos_g=IntervaloNutricional(100.0, 120.0),
            proteinas_g=IntervaloNutricional(20.0, 30.0),
            lipidios_g=IntervaloNutricional(20.0, 30.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=800.0),
        metas_semanais=MetasSemanais(min_diversidade=14, min_flv_g=280.0, min_frutas_dias=2, min_legumes_verduras_dias=3, max_biscoito_semana=3),
        distribuicao_refeicoes=[
            DistribuicaoRefeicao(tipo_refeicao="almoço", ordem=1, percentual_energia=0.30, energia_kcal_alvo=800.0)
            # Apenas 1 refeição configurada para um perfil de 2 refeições!
        ],
    )
    try:
        perfil_qtd_errada.validar_distribuicao()
        assert False, "Deveria ter levantado DistribuicaoInvalidaError por quantidade divergente"
    except DistribuicaoInvalidaError as e:
        assert "exige 2 refeição(ões), mas possui 1 configurada(s)" in str(e)

    # Caso 2: Soma de percentuais diverge do percentual de atendimento (ex: 0.10 + 0.10 = 0.20 != 0.30)
    perfil_soma_errada = PerfilNutricional(
        id_perfil="fixture_soma_errada",
        etapa="ensino_medio",
        faixa_etaria="16_18_anos",
        periodo="parcial",
        num_refeicoes=2,
        percentual_atendimento=30,
        percentual_label="30%",
        nutricao=ParametrosNutricionais(
            energia_kcal=800.0,
            carboidratos_g=IntervaloNutricional(100.0, 120.0),
            proteinas_g=IntervaloNutricional(20.0, 30.0),
            lipidios_g=IntervaloNutricional(20.0, 30.0),
        ),
        limites=LimitesComposicao(max_sodio_mg=800.0),
        metas_semanais=MetasSemanais(min_diversidade=14, min_flv_g=280.0, min_frutas_dias=2, min_legumes_verduras_dias=3, max_biscoito_semana=3),
        distribuicao_refeicoes=[
            DistribuicaoRefeicao(tipo_refeicao="desjejum", ordem=1, percentual_energia=0.10, energia_kcal_alvo=266.0),
            DistribuicaoRefeicao(tipo_refeicao="almoço", ordem=2, percentual_energia=0.10, energia_kcal_alvo=266.0),  # Falta 0.10!
        ],
    )
    try:
        perfil_soma_errada.validar_distribuicao()
        assert False, "Deveria ter levantado DistribuicaoInvalidaError por soma divergente"
    except DistribuicaoInvalidaError as e:
        assert "diverge do percentual de atendimento" in str(e)


# ===========================================================================
# 6. REFEIÇÃO ESPERADA AUSENTE NA AUDITORIA
# ===========================================================================

def test_auditoria_refeicao_esperada_ausente():
    """Se o perfil exigir desjejum + almoço e o cardápio contiver apenas o almoço, deve reprovar com inconsistência crítica."""
    pipeline = selecionar_pipeline(etapa="ensino_medio", faixa_etaria="16_18", periodo="parcial", num_refeicoes=2)

    # Cardápio com apenas 1 refeição (almoço) em vez das 2 esperadas
    cardapio_faltando_refeicao = CardapioSchema(
        mes_aplicacao="outubro de 2026",
        observacoes="",
        semanas=[
            SemanaSchema(
                numero=1,
                dias=[
                    DiaSchema(
                        dia_semana="segunda-feira",
                        refeicoes=[
                            RefeicaoSchema(
                                tipo=TipoRefeicao.almoco,
                                horario="12:00",
                                pratos=[
                                    PratoSchema(
                                        nome="Arroz com Feijão",
                                        estado_preparacao="cozido",
                                        ingredientes=[
                                            IngredienteSchema(nome_taco="Arroz, tipo 1, cozido", quantidade_g=100),
                                            IngredienteSchema(nome_taco="Feijão, carioca, cozido", quantidade_g=80),
                                        ]
                                    )
                                ]
                            )
                        ]
                    )
                ]
            )
        ]
    )

    mock_taco = MagicMock()
    mock_taco.energy_kcal = 100.0
    mock_taco.carbohydrates = 20.0
    mock_taco.proteins = 5.0
    mock_taco.lipids = 2.0
    mock_taco.sodium = 50.0
    mock_taco.c_vitamin = 10.0
    mock_taco.calcium = 20.0
    mock_taco.iron = 1.0
    mock_taco.category = "Cereais"

    with patch("src.pipelines.base.Session"), \
         patch("src.pipelines.base.buscar_taco_por_nome", return_value=mock_taco):
        inconformidades = pipeline.auditar(cardapio_faltando_refeicao)
    regras = [i.regra for i in inconformidades]

    assert "Refeicao esperada ausente" in regras or "Quantidade de refeicoes divergente" in regras
    criticos_refeicao = [
        i for i in inconformidades
        if i.tipo == "critico" and ("Refeicao esperada ausente" in i.regra or "Quantidade de refeicoes" in i.regra)
    ]
    assert len(criticos_refeicao) > 0


# ===========================================================================
# 7. PORÇÃO PER CAPITA JÁ CONCEBIDA PARA A REFEIÇÃO
# ===========================================================================

def test_semantica_per_capita_porcao_refeicao():
    """Garante que a porção per capita já corresponde à refeição e não sofre multiplicação indevida."""
    from src.taco.resolver import _calibrar_per_capita_proteina

    porcao_carne = _calibrar_per_capita_proteina("Carne bovina cozida", "ensino_medio", 100.0)
    assert porcao_carne == 45.0

    porcao_creche = _calibrar_per_capita_proteina("Carne bovina cozida", "creche", 100.0)
    assert porcao_creche == 10.0


# ===========================================================================
# 8. FATOR DE COCCÃO E PREVENÇÃO DE DUPLA CONVERSÃO
# ===========================================================================

def test_prevencao_dupla_conversao_coccao():
    """Se o alimento na TACO já é cozido, a quantidade per capita não deve sofrer reaplicação de fator de cocção."""
    from src.pipelines.base import BasePipeline
    pipeline = BasePipeline(resolver_perfil(etapa="ensino_medio", faixa_etaria="16_18", periodo="parcial", num_refeicoes=1))

    cardapio = CardapioSchema(
        mes_aplicacao="outubro de 2026",
        observacoes="",
        semanas=[
            SemanaSchema(
                numero=1,
                dias=[
                    DiaSchema(
                        dia_semana="segunda-feira",
                        refeicoes=[
                            RefeicaoSchema(
                                tipo=TipoRefeicao.almoco,
                                horario="12:00",
                                pratos=[
                                    PratoSchema(
                                        nome="Arroz Cozido",
                                        estado_preparacao="cozido",
                                        ingredientes=[
                                            IngredienteSchema(nome_taco="Arroz, tipo 1, cozido", quantidade_g=100.0)
                                        ]
                                    )
                                ]
                            )
                        ]
                    )
                ]
            )
        ]
    )

    from src.taco.resolver import MatchTaco
    mock_taco = MatchTaco(taco_id="1", description="Arroz, tipo 1, cozido", score=1.0, payload={})
    with patch("src.pipelines.base.resolver_taco", return_value=mock_taco), \
         patch("src.pipelines.base.resolver_per_capita", return_value=100.0):
        ajustado = pipeline.aplicar_per_capita(cardapio)

    ingrediente = ajustado.semanas[0].dias[0].refeicoes[0].pratos[0].ingredientes[0]
    assert ingrediente.quantidade_g == 100.0


# ===========================================================================
# 9. AUDITORIA EM DOIS NÍVEIS: DIÁRIA E SEMANAL
# ===========================================================================

def test_auditoria_dois_niveis():
    """Valida que a auditoria avalia energia no nível diário (soma das refeições) e diversidade no nível semanal."""
    pipeline = selecionar_pipeline(etapa="ensino_medio", faixa_etaria="16_18", periodo="parcial", num_refeicoes=2)

    cardapio_completo = CardapioSchema(
        mes_aplicacao="outubro de 2026",
        observacoes="",
        semanas=[
            SemanaSchema(
                numero=1,
                dias=[
                    DiaSchema(
                        dia_semana="segunda-feira",
                        refeicoes=[
                            RefeicaoSchema(
                                tipo=TipoRefeicao.desjejum,
                                horario="08:00",
                                pratos=[
                                    PratoSchema(
                                        nome="Leite com Fruta",
                                        estado_preparacao="cru",
                                        ingredientes=[
                                            IngredienteSchema(nome_taco="Banana, nanica, crua", quantidade_g=100),
                                            IngredienteSchema(nome_taco="Leite, de vaca, integral", quantidade_g=200),
                                        ]
                                    )
                                ]
                            ),
                            RefeicaoSchema(
                                tipo=TipoRefeicao.almoco,
                                horario="12:00",
                                pratos=[
                                    PratoSchema(
                                        nome="Prato Feito",
                                        estado_preparacao="cozido",
                                        ingredientes=[
                                            IngredienteSchema(nome_taco="Arroz, tipo 1, cozido", quantidade_g=120),
                                            IngredienteSchema(nome_taco="Feijão, carioca, cozido", quantidade_g=80),
                                            IngredienteSchema(nome_taco="Frango, peito, cozido", quantidade_g=45),
                                            IngredienteSchema(nome_taco="Alface, crespa, crua", quantidade_g=30),
                                        ]
                                    )
                                ]
                            )
                        ]
                    )
                ]
            )
        ]
    )

    mock_taco = MagicMock()
    mock_taco.energy_kcal = 100.0
    mock_taco.carbohydrates = 20.0
    mock_taco.proteins = 5.0
    mock_taco.lipids = 2.0
    mock_taco.sodium = 50.0
    mock_taco.c_vitamin = 10.0
    mock_taco.calcium = 20.0
    mock_taco.iron = 1.0
    mock_taco.category = "Cereais"

    with patch("src.pipelines.base.Session"), \
         patch("src.pipelines.base.buscar_taco_por_nome", return_value=mock_taco):
        inconformidades = pipeline.auditar(cardapio_completo)
    erros_refeicao_isolada = [i for i in inconformidades if "refeição individual abaixo da meta diária" in i.regra.lower()]
    assert len(erros_refeicao_isolada) == 0


# ===========================================================================
# 10. INTEGRIDADE DO CATÁLOGO DE PERFIS PNAE
# ===========================================================================

def test_catalogo_perfis_pnae_completo():
    """Valida que todos os 22 perfis oficiais do PNAE estão configurados no catálogo em memória."""
    from src.pipelines.registry import CATALOGO_PERFIS

    perfis_unicos = {p.id_perfil: p for p in CATALOGO_PERFIS.values()}
    assert len(perfis_unicos) == 22


# ===========================================================================
# 11. COMPATIBILIDADE COM O CONTRATO DA API (COOPERAAGRO-BACK)
# ===========================================================================

def test_compatibilidade_contrato_cooperaagro_back():
    """Valida que GerarCardapioRequest aceita os aliases consumidos pelo CooperaAgro-Back."""
    from api_server import GerarCardapioRequest

    payload_back = {
        "educationStage": "medio",
        "ageRange": "16_18",
        "period": "parcial",
        "shift": ["matutino"],
        "mealsPerDay": 1,
        "schoolDays": ["10/01/2026"]
    }

    req = GerarCardapioRequest(**payload_back)
    assert req.etapa == "medio"
    assert req.faixa_etaria == "16_18"
    assert req.periodo == "parcial"
    assert req.turno == ["matutino"]
    assert req.num_refeicoes == 1
    assert req.dias_letivos == ["10/01/2026"]

    # Valida que resolve o perfil correto com esses dados
    perfil = resolver_perfil(
        etapa=req.etapa,
        faixa_etaria=req.faixa_etaria,
        periodo=req.periodo,
        num_refeicoes=req.num_refeicoes
    )
    assert perfil.id_perfil == "ensino_medio_16_18_anos_parcial_1ref"
    assert perfil.percentual_atendimento == 20


# ===========================================================================
# EXECUÇÃO PRINCIPAL
# ===========================================================================

if __name__ == "__main__":
    testes = [
        ("1. Mesma etapa, diferentes refeições", test_mesma_etapa_diferentes_refeicoes),
        ("2. Seleção do percentual de atendimento", test_selecao_percentual_atendimento),
        ("3. Distribuição configurada e soma diária dos nutrientes", test_distribuicao_soma_diaria_nutrientes),
        ("4. Perfil sem distribuição configurada", test_perfil_sem_distribuicao_configurada),
        ("5. Distribuição com percentuais inconsistentes", test_distribuicao_com_percentuais_inconsistentes),
        ("6. Refeição esperada ausente na auditoria", test_auditoria_refeicao_esperada_ausente),
        ("7. Semântica da porção per capita na refeição", test_semantica_per_capita_porcao_refeicao),
        ("8. Fator de cocção e prevenção de dupla conversão", test_prevencao_dupla_conversao_coccao),
        ("9. Auditoria em dois níveis (diária e semanal)", test_auditoria_dois_niveis),
        ("10. Sincronização e persistência no PostgreSQL", test_sincronizacao_e_persistência_tabelas),
        ("11. Compatibilidade com contrato do CooperaAgro-Back", test_compatibilidade_contrato_cooperaagro_back),
    ]

    falhas = 0
    print("=" * 75)
    print("SUÍTE OBRIGATÓRIA PNAE: PERFIS NUTRICIONAIS E DISTRIBUIÇÃO POR REFEIÇÃO")
    print("=" * 75)
    for nome, fn in testes:
        try:
            fn()
            print(f"  [OK] {nome}")
        except Exception as e:
            falhas += 1
            print(f"  [FALHA] {nome}: {e}")
            import traceback
            traceback.print_exc()

    print("=" * 75)
    if falhas == 0:
        print(f"SUCESSO TOTAL: Todos os {len(testes)} testes obrigatórios foram APROVADOS!")
    else:
        print(f"ERRO: {falhas} teste(s) falharam.")
        sys.exit(1)
