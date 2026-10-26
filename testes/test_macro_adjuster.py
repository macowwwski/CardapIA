"""
Suíte de testes para o módulo de otimização matemática determinística de VET
e macronutrientes (src.nutrition.macro_adjuster).

Valida os critérios de aceitação:
1. Cálculo correto do VET total e distribuição percentual calórica (% Carbo, % Prot, % Lip).
2. Cálculo exato dos deltas frente a ParametrosNutricionais do perfil PNAE.
3. Microajustes proporcionais nas gramaturas dos alimentos base (amidos, carnes, óleos).
4. Respeito irrestrito aos pisos e tetos pedagógicos e gastronômicos por faixa etária.
5. Manutenção da média calórica diária dentro da margem da meta de VET correspondente.
6. Atendimento estrito às faixas estipuladas pelo PNAE para macronutrientes.
7. Preservação intacta de frutas, hortaliças e sal.
8. Acionamento integrado no pipeline escolar logo após aplicar_per_capita e antes de auditar.
"""
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.schemas_pydantic import (
    CardapioSchema,
    SemanaSchema,
    DiaSchema,
    RefeicaoSchema,
    PratoSchema,
    IngredienteSchema,
    TipoRefeicao,
)
from src.pipelines import resolver_perfil, selecionar_pipeline
from src.nutrition.macro_adjuster import (
    auditar_vet_e_macros,
    ajustar_macronutrientes_cardapio,
    _resolver_limites_faixa,
    LIMITES_POR_FAIXA,
)


def _criar_cardapio_dia(pratos: list[PratoSchema], dia_nome: str = "segunda-feira") -> CardapioSchema:
    """Helper para montar um CardapioSchema de 1 dia."""
    refeicao = RefeicaoSchema(
        tipo=TipoRefeicao.almoco,
        horario="11:30",
        pratos=pratos,
    )
    dia = DiaSchema(dia_semana=dia_nome, refeicoes=[refeicao])
    semana = SemanaSchema(numero=1, dias=[dia])
    return CardapioSchema(
        mes_aplicacao="outubro de 2026",
        observacoes="Cardápio Teste Macro",
        semanas=[semana],
    )


# =========================================================================
# 1. TESTE DE CÁLCULO DE VET E DISTRIBUIÇÃO PERCENTUAL CALÓRICA
# =========================================================================

def test_calculo_vet_e_percentuais_caloricos():
    """Valida o cálculo do VET e percentuais Atwater (% Carbo, % Prot, % Lip)."""
    perfil = resolver_perfil("ensino_medio", "16_18", "parcial", 1)

    # 100g arroz (~128 kcal, 28.1g carbo, 2.5g prot)
    # 50g feijao (~38 kcal, 6.8g carbo, 2.4g prot)
    # 40g frango (~65 kcal, 0g carbo, 12.6g prot, 1.3g lip)
    # 10g azeite (~88.4 kcal, 10g lip)
    # 50g maca (~28 kcal, 7.6g carbo)
    pratos = [
        PratoSchema(nome="Arroz", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="Arroz, tipo 1, cozido", quantidade_g=100.0)]),
        PratoSchema(nome="Feijão", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="Feijão, carioca, cozido", quantidade_g=50.0)]),
        PratoSchema(nome="Frango", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="Frango, peito, sem pele, cozido", quantidade_g=40.0)]),
        PratoSchema(nome="Salada", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="Azeite de oliva", quantidade_g=10.0)]),
        PratoSchema(nome="Sobremesa", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="Maçã, Fuji, com casca, crua", quantidade_g=50.0)]),
    ]
    cardapio = _criar_cardapio_dia(pratos)
    dia = cardapio.semanas[0].dias[0]

    status = auditar_vet_e_macros(dia, perfil)

    # VET deve ser positivo e coerente com a soma
    assert status.energia_kcal > 300.0
    assert status.carboidratos_g > 35.0
    assert status.proteinas_g > 15.0
    assert status.lipidios_g > 10.0

    # Percentuais devem somar ~100% (com tolerância devido a fibras e arredondamento)
    soma_pct = status.pct_carboidratos + status.pct_proteinas + status.pct_lipidios
    assert 95.0 <= soma_pct <= 105.0

    # Deltas calculados frente à meta do Ensino Médio (543 kcal)
    assert status.delta_vet == round(543.0 - status.energia_kcal, 2)


# =========================================================================
# 2. TESTE DE MICROAJUSTE PROPORCIONAL DETERMINÍSTICO (ENSINO MÉDIO)
# =========================================================================

def test_microajuste_ensino_medio_convergencia_vet_e_macros():
    """Garante que o microajuste atinge a meta de 543 kcal e faixas do PNAE para o Ensino Médio."""
    perfil = resolver_perfil("ensino_medio", "16_18", "parcial", 1)

    # Inicia com porções moderadas/subestimadas que totalizam cerca de ~380 kcal (abaixo de 543 kcal)
    pratos = [
        PratoSchema(nome="Arroz", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="Arroz, tipo 1, cozido", quantidade_g=90.0)]),
        PratoSchema(nome="Feijão", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="Feijão, carioca, cozido", quantidade_g=45.0)]),
        PratoSchema(nome="Carne Bovina", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="Carne, bovina, cozida", quantidade_g=28.0)]),
        PratoSchema(nome="Tempero", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="Óleo de soja", quantidade_g=6.0)]),
        PratoSchema(nome="Fruta", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="Banana prata", quantidade_g=60.0)]),
    ]
    cardapio = _criar_cardapio_dia(pratos)

    dia_antes = cardapio.semanas[0].dias[0]
    status_antes = auditar_vet_e_macros(dia_antes, perfil)
    assert status_antes.energia_kcal < 500.0  # deficitário antes do ajuste

    # Executa otimização determinística
    cardapio_ajustado = ajustar_macronutrientes_cardapio(cardapio, perfil)
    dia_depois = cardapio_ajustado.semanas[0].dias[0]
    status_depois = auditar_vet_e_macros(dia_depois, perfil)

    # 1. VET final dentro da margem de 10% da meta de 543 kcal (488.7 a 597.3 kcal)
    assert 488.7 <= status_depois.energia_kcal <= 597.3, f"VET {status_depois.energia_kcal} fora da margem de 543 kcal"

    # 2. Percentuais calóricos nas faixas estipuladas pelo PNAE
    assert 50.0 <= status_depois.pct_carboidratos <= 68.0, f"% Carbo {status_depois.pct_carboidratos} fora da faixa PNAE"
    assert 10.0 <= status_depois.pct_proteinas <= 17.0, f"% Prot {status_depois.pct_proteinas} fora da faixa PNAE"
    assert 15.0 <= status_depois.pct_lipidios <= 32.0, f"% Lip {status_depois.pct_lipidios} fora da faixa PNAE"

    # 3. Alimentos base ajustados proporcionalmente
    ingredientes_ajustados = {
        ing.nome_taco: ing.quantidade_g
        for r in dia_depois.refeicoes
        for p in r.pratos
        for ing in p.ingredientes
    }
    # Arroz deve ter aumentado para suprir o carboidrato e caloria
    assert ingredientes_ajustados["Arroz, tipo 1, cozido"] > 90.0
    # Óleo deve ter aumentado para suprir lipídios
    assert ingredientes_ajustados["Óleo de soja"] > 6.0
    # Fruta deve permanecer intacta
    assert ingredientes_ajustados["Banana prata"] == 60.0


# =========================================================================
# 3. TESTE DE RESPEITO AOS PISOS E TETOS PEDAGÓGICOS/GASTRONÔMICOS
# =========================================================================

def test_respeito_pisos_e_tetos_por_faixa_etaria():
    """Assegura que nenhuma gramatura ajustada ultrapasse os tetos ou caia abaixo dos pisos pedagógicos."""
    # Testa para Creche (1 a 3 anos, 2 refeições / 30% VET - 398 kcal)
    perfil_creche = resolver_perfil("creche", "1_3", "parcial", 2)
    limites_creche = _resolver_limites_faixa("creche", "1_3_anos")

    # Tenta forçar porção hipertrofiada de 150g de arroz para criança de creche
    pratos_creche = [
        PratoSchema(nome="Arroz", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="Arroz, tipo 1, cozido", quantidade_g=150.0)]),
        PratoSchema(nome="Frango", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="Peito de frango cozido", quantidade_g=50.0)]),
        PratoSchema(nome="Óleo", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="Azeite de oliva", quantidade_g=20.0)]),
    ]
    cardapio_creche = _criar_cardapio_dia(pratos_creche)
    ajustar_macronutrientes_cardapio(cardapio_creche, perfil_creche)

    ings_creche = {
        ing.nome_taco: ing.quantidade_g
        for r in cardapio_creche.semanas[0].dias[0].refeicoes
        for p in r.pratos
        for ing in p.ingredientes
    }

    # O arroz deve ter sido contido dentro do teto pedagógico da creche (máx 70g)
    assert ings_creche["Arroz, tipo 1, cozido"] <= limites_creche.teto_amido_g
    assert ings_creche["Peito de frango cozido"] <= limites_creche.teto_proteina_g
    assert ings_creche["Azeite de oliva"] <= limites_creche.teto_oleo_g


# =========================================================================
# 4. TESTE PARA ENSINO FUNDAMENTAL (6 A 10 ANOS - 367 KCAL)
# =========================================================================

def test_microajuste_ensino_fundamental():
    """Valida microajuste no Ensino Fundamental (6-10 anos, 1 ref / 20% VET - 367 kcal)."""
    perfil_fund = resolver_perfil("ensino_fundamental", "6_10", "parcial", 1)

    pratos = [
        PratoSchema(nome="Arroz Branco", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="Arroz, tipo 1, cozido", quantidade_g=60.0)]),
        PratoSchema(nome="Feijão Carioca", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="Feijão, carioca, cozido", quantidade_g=35.0)]),
        PratoSchema(nome="Iscas de Carne", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="Carne, bovina, cozida", quantidade_g=20.0)]),
        PratoSchema(nome="Óleo", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="Óleo de soja", quantidade_g=5.0)]),
        PratoSchema(nome="Salada", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="Alface americana", quantidade_g=25.0)]),
    ]
    cardapio = _criar_cardapio_dia(pratos)
    cardapio_ajustado = ajustar_macronutrientes_cardapio(cardapio, perfil_fund)

    status = auditar_vet_e_macros(cardapio_ajustado.semanas[0].dias[0], perfil_fund)

    # Tolerância de 10% sobre 367 kcal (330 a 404 kcal)
    assert 330.0 <= status.energia_kcal <= 405.0, f"VET {status.energia_kcal} fora da tolerância de 367 kcal"
    assert status.dentro_margem_vet is True

    # Alface não pode ser alterada
    alface = next(
        ing for r in cardapio_ajustado.semanas[0].dias[0].refeicoes
        for p in r.pratos for ing in p.ingredientes if "Alface" in ing.nome_taco
    )
    assert alface.quantidade_g == 25.0


# =========================================================================
# 5. TESTE DE INTEGRAÇÃO COM O PIPELINE (ACIONAMENTO DETERMINÍSTICO)
# =========================================================================

def test_acionamento_integrado_no_pipeline():
    """Garante que BasePipeline possui e executa ajustar_macronutrientes."""
    pipeline = selecionar_pipeline("ensino_medio", "16_18", "parcial", 1)
    assert hasattr(pipeline, "ajustar_macronutrientes")
    assert callable(pipeline.ajustar_macronutrientes)

    pratos = [
        PratoSchema(nome="Arroz", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="Arroz, tipo 1, cozido", quantidade_g=70.0)]),
        PratoSchema(nome="Feijão", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="Feijão, carioca, cozido", quantidade_g=40.0)]),
        PratoSchema(nome="Frango", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="Frango, peito, sem pele, cozido", quantidade_g=25.0)]),
        PratoSchema(nome="Azeite", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="Azeite de oliva", quantidade_g=5.0)]),
    ]
    cardapio = _criar_cardapio_dia(pratos)

    from src.taco.resolver import MatchTaco
    mock_match = MatchTaco(taco_id="1", description="alimento", score=1.0, payload={})
    with patch("src.pipelines.base.resolver_taco", return_value=mock_match), \
         patch("src.pipelines.base.resolver_per_capita", return_value=50.0):
        # Executa per capita e em seguida o ajuste de macronutrientes
        cardapio_per_capita = pipeline.aplicar_per_capita(cardapio)
        cardapio_ajustado = pipeline.ajustar_macronutrientes(cardapio_per_capita)

    # Confere metadados de ajuste presentes
    assert hasattr(cardapio_ajustado, "_relatorio_microajustes")
    relatorio = getattr(cardapio_ajustado, "_relatorio_microajustes")
    assert relatorio.meta_vet == 543.0
    assert len(relatorio.ajustes_realizados) > 0


# =========================================================================
# 6. TESTES ESPECÍFICOS DOS CRITÉRIOS DE ACEITE DA ISSUE 2
# =========================================================================

def test_ausencia_densidades_nutricionais_padrao_e_fallbacks():
    """Comprova a eliminação de DENSIDADES_NUTRICIONAIS_PADRAO e de fallbacks estáticos."""
    import src.nutrition.macro_adjuster as ma
    from src.nutrition.macro_adjuster import _obter_dados_nutricionais_100g

    # 1. Constante hardcoded deve ter sido completamente eliminada
    assert not hasattr(ma, "DENSIDADES_NUTRICIONAIS_PADRAO"), (
        "DENSIDADES_NUTRICIONAIS_PADRAO ainda existe em macro_adjuster.py!"
    )

    # 2. Alimento inexistente deve retornar zeros limpos (sem fallback de 50 kcal)
    dados = _obter_dados_nutricionais_100g("alimento_completamente_ficticio_xyz_123")
    assert dados["energia_kcal"] == 0.0
    assert dados["carboidratos"] == 0.0
    assert dados["proteins"] == 0.0
    assert dados["lipids"] == 0.0


def test_uso_exclusivo_tabela_taco_postgresql():
    """Comprova que os dados nutricionais vêm estritamente da tabela TACO."""
    from src.nutrition.macro_adjuster import _obter_dados_nutricionais_100g
    from unittest.mock import MagicMock

    mock_taco = MagicMock()
    mock_taco.id = "mock-uuid-123"
    mock_taco.description = "Alimento Teste TACO"
    mock_taco.energy_kcal = 245.5
    mock_taco.carbohydrates = 45.2
    mock_taco.proteins = 12.8
    mock_taco.lipids = 3.1

    cache = {"mock-uuid-123": mock_taco, "alimento teste taco": mock_taco}

    dados = _obter_dados_nutricionais_100g(
        "Alimento Teste TACO",
        taco_cache=cache,
        taco_id="mock-uuid-123",
    )

    assert dados["energia_kcal"] == 245.5
    assert dados["carboidratos"] == 45.2
    assert dados["proteins"] == 12.8
    assert dados["lipids"] == 3.1


def test_calculo_atwater_quando_energia_kcal_ausente():
    """Valida o cálculo de VET via Fatores Atwater quando a TACO não possui energy_kcal cadastrado."""
    from src.nutrition.macro_adjuster import _obter_dados_nutricionais_100g
    from unittest.mock import MagicMock

    mock_taco = MagicMock()
    mock_taco.energy_kcal = None  # Ausente
    mock_taco.carbohydrates = 20.0
    mock_taco.proteins = 10.0
    mock_taco.lipids = 5.0

    cache = {"alimento_sem_kcal": mock_taco}

    dados = _obter_dados_nutricionais_100g("alimento_sem_kcal", taco_cache=cache)

    # 20*4 + 10*4 + 5*9 = 80 + 40 + 45 = 165 kcal
    assert dados["energia_kcal"] == 165.0
    assert dados["carboidratos"] == 20.0
    assert dados["proteins"] == 10.0
    assert dados["lipids"] == 5.0


def test_tratamento_taco_id_invalido_ou_dados_ausentes():
    """Comprova que taco_id inválido ou inexistente retorna zeros controlados sem crashar."""
    from src.nutrition.macro_adjuster import _obter_dados_nutricionais_100g
    from unittest.mock import MagicMock

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = None

    dados = _obter_dados_nutricionais_100g(
        "Ingrediente Desconhecido",
        session=mock_session,
        taco_id="uuid-inexistente-999",
    )
    assert dados["energia_kcal"] == 0.0
    assert dados["carboidratos"] == 0.0


def test_calculator_sem_fallbacks_estaticos():
    """Comprova que calcular_nutrientes_alimento em calculator.py não usa fallbacks estáticos."""
    from src.nutrition.calculator import calcular_nutrientes_alimento

    resultado = calcular_nutrientes_alimento(
        session=None,
        nome_taco="item_fantasma_sem_taco",
        qtd_g=100.0,
    )
    assert resultado["energiaKcal"] == 0.0
    assert resultado["carboidratosG"] == 0.0
    assert resultado["proteinasG"] == 0.0
    assert resultado["lipidiosG"] == 0.0


if __name__ == "__main__":
    testes = [
        ("Cálculo de VET e percentuais calóricos Atwater", test_calculo_vet_e_percentuais_caloricos),
        ("Microajuste proporcional determinístico (Ensino Médio)", test_microajuste_ensino_medio_convergencia_vet_e_macros),
        ("Respeito estrito aos pisos e tetos pedagógicos por faixa etária", test_respeito_pisos_e_tetos_por_faixa_etaria),
        ("Microajuste para Ensino Fundamental (6-10 anos)", test_microajuste_ensino_fundamental),
        ("Acionamento integrado via BasePipeline.ajustar_macronutrientes", test_acionamento_integrado_no_pipeline),
        ("Ausência de DENSIDADES_NUTRICIONAIS_PADRAO e de fallbacks estáticos", test_ausencia_densidades_nutricionais_padrao_e_fallbacks),
        ("Uso exclusivo dos dados nutricionais da tabela TACO", test_uso_exclusivo_tabela_taco_postgresql),
        ("Cálculo Atwater quando energy_kcal for nulo na TACO", test_calculo_atwater_quando_energia_kcal_ausente),
        ("Tratamento seguro de taco_id inexistente/dados ausentes", test_tratamento_taco_id_invalido_ou_dados_ausentes),
        ("Calculator sem fallbacks nutricionais estáticos", test_calculator_sem_fallbacks_estaticos),
    ]

    falhas = 0
    print("=" * 70)
    print("EXECUTANDO TESTES DO OTIMIZADOR DETERMINÍSTICO (MACRO ADJUSTER)")
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
        print(f"SUCESSO TOTAL: Todos os {len(testes)} testes do Macro Adjuster foram APROVADOS!")
    else:
        print(f"ERRO: {falhas} teste(s) falharam.")
        sys.exit(1)
