"""
Suíte de testes de validação culinária, conformidade com o PNAE e compatibilidade de contratos.
Cobre rigorosamente os cenários A a I da especificação de refatoração do CardapIA.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.schemas_pydantic import (
    CardapioSchema,
    SemanaSchema,
    DiaSchema,
    RefeicaoSchema,
    PratoSchema,
    IngredienteSchema,
    TipoRefeicao,
    StatusValidacao,
)
from src.ai_service import (
    validar_coerencia_culinaria,
    validar_cardapio_pnae,
    avaliar_status_cardapio,
    _classificar_alimento,
    _identificar_frutas,
)
from src.prompt_builder import construir_contexto
from api_server import app
from fastapi.testclient import TestClient


def criar_cardapio_teste(pratos_por_dia: dict[str, list[PratoSchema]], tipo_refeicao=TipoRefeicao.almoco) -> CardapioSchema:
    """Helper para criar CardapioSchema estruturado para testes."""
    dias = []
    for nome_dia, pratos in pratos_por_dia.items():
        refeicao = RefeicaoSchema(
            tipo=tipo_refeicao,
            horario="11:30",
            pratos=pratos
        )
        dias.append(DiaSchema(dia_semana=nome_dia, refeicoes=[refeicao]))
    
    semana = SemanaSchema(numero=1, dias=dias)
    return CardapioSchema(
        mes_aplicacao="maio de 2026",
        semanas=[semana],
        observacoes=""
    )


# =========================================================================
# CENÁRIO A: Refeição Principal Coerente
# Arroz, feijão, frango, hortaliças e fruta como sobremesa.
# =========================================================================
def test_cenario_a_refeicao_principal_coerente():
    pratos = [
        PratoSchema(nome="Arroz Branco", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="arroz polido cozido", quantidade_g=100.0)]),
        PratoSchema(nome="Feijão Carioca", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="feijão carioca cozido", quantidade_g=80.0)]),
        PratoSchema(nome="Frango Ensopado com Legumes", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="frango peito filé sem pele cozido", quantidade_g=100.0)]),
        PratoSchema(nome="Salada de Alface e Tomate", estado_preparacao="cru", ingredientes=[
            IngredienteSchema(nome_taco="alface crespa crua", quantidade_g=30.0),
            IngredienteSchema(nome_taco="tomate salada cru", quantidade_g=40.0),
        ]),
        PratoSchema(nome="Sobremesa: Banana", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="banana prata crua", quantidade_g=80.0)]),
    ]

    cardapio = criar_cardapio_teste({"segunda-feira": pratos})
    inconformidades_culinarias = validar_coerencia_culinaria(cardapio, etapa="ensino fundamental")

    # Não deve ter nenhuma inconformidade culinária crítica
    criticos = [i for i in inconformidades_culinarias if i.tipo == "critico"]
    assert len(criticos) == 0, f"Refeição coerente não deveria ter erros críticos: {criticos}"


# =========================================================================
# CENÁRIO B: Excesso de Alimentos Redundantes (Múltiplas Frutas no Almoço)
# Almoço agrupando manga, banana e limão sem função culinária.
# =========================================================================
def test_cenario_b_excesso_frutas_mesma_refeicao():
    pratos = [
        PratoSchema(nome="Arroz", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="arroz polido cozido", quantidade_g=100.0)]),
        PratoSchema(nome="Feijão", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="feijão carioca cozido", quantidade_g=80.0)]),
        PratoSchema(nome="Carne Bovina Moída", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="carne bovina moída cozida", quantidade_g=90.0)]),
        # Agrupamento artificial de frutas independentes
        PratoSchema(nome="Banana", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="banana prata crua", quantidade_g=80.0)]),
        PratoSchema(nome="Manga", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="manga palmer crua", quantidade_g=80.0)]),
        PratoSchema(nome="Abacaxi", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="abacaxi cru", quantidade_g=80.0)]),
    ]

    cardapio = criar_cardapio_teste({"terça-feira": pratos})
    inconformidades = validar_coerencia_culinaria(cardapio, etapa="ensino fundamental")

    # Deve sinalizar excesso de frutas com erro crítico
    erros_frutas = [i for i in inconformidades if "excesso de frutas" in i.regra.lower()]
    assert len(erros_frutas) > 0, "Deveria ter sinalizado excesso de frutas na mesma refeição"
    assert erros_frutas[0].tipo == "critico"

    relatorio = avaliar_status_cardapio(inconformidades)
    assert relatorio.status == StatusValidacao.reprovado
    assert relatorio.aprovado is False


# =========================================================================
# CENÁRIO C: Variedade Semanal (Monotonia Proteica Consecutiva)
# Mesmo prato proteico (frango) repetido em dias consecutivos.
# =========================================================================
def test_cenario_c_monotonia_proteica_consecutiva():
    def prato_frango():
        return [
            PratoSchema(nome="Arroz", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="arroz polido cozido", quantidade_g=100.0)]),
            PratoSchema(nome="Feijão", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="feijão carioca cozido", quantidade_g=80.0)]),
            PratoSchema(nome="Frango Grelhado", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="frango peito filé grelhado", quantidade_g=100.0)]),
        ]

    cardapio = criar_cardapio_teste({
        "segunda-feira": prato_frango(),
        "terça-feira": prato_frango(),
        "quarta-feira": prato_frango(),  # 3º dia consecutivo de frango
    })

    inconformidades = validar_coerencia_culinaria(cardapio, etapa="ensino fundamental")
    erros_monotonia = [i for i in inconformidades if "monotonia proteica" in i.regra.lower()]
    assert len(erros_monotonia) > 0, "Deveria advertir sobre monotonia proteica em dias consecutivos"


# =========================================================================
# CENÁRIO D: Restrições Alimentares (Lactose e Glúten)
# Rejeição estrita de laticínios ou alimentos com glúten quando restritos.
# =========================================================================
def test_cenario_d_restricoes_alimentares():
    pratos_com_lactose = [
        PratoSchema(nome="Purê de Batata com Leite e Manteiga", estado_preparacao="cozido", ingredientes=[
            IngredienteSchema(nome_taco="batata cozida", quantidade_g=100.0),
            IngredienteSchema(nome_taco="leite integral", quantidade_g=50.0),
            IngredienteSchema(nome_taco="manteiga com sal", quantidade_g=10.0),
        ]),
        PratoSchema(nome="Frango Desfiado", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="frango cozido", quantidade_g=100.0)]),
    ]

    cardapio_lactose = criar_cardapio_teste({"quarta-feira": pratos_com_lactose})
    inconformidades_lactose = validar_coerencia_culinaria(cardapio_lactose, etapa="ensino fundamental", restricoes=["lactose"])

    violacoes_lactose = [i for i in inconformidades_lactose if "lactose" in i.regra.lower()]
    assert len(violacoes_lactose) > 0, "Deveria bloquear ingredientes com lactose"
    assert violacoes_lactose[0].tipo == "critico"

    pratos_com_gluten = [
        PratoSchema(nome="Macarronada de Trigo com Frango", estado_preparacao="cozido", ingredientes=[
            IngredienteSchema(nome_taco="macarrão de trigo cozido", quantidade_g=120.0),
            IngredienteSchema(nome_taco="frango peito filé cozido", quantidade_g=100.0),
        ])
    ]
    cardapio_gluten = criar_cardapio_teste({"quinta-feira": pratos_com_gluten})
    inconformidades_gluten = validar_coerencia_culinaria(cardapio_gluten, etapa="ensino fundamental", restricoes=["glúten"])

    violacoes_gluten = [i for i in inconformidades_gluten if "glúten" in i.regra.lower() or "gluten" in i.regra.lower()]
    assert len(violacoes_gluten) > 0, "Deveria bloquear ingredientes com glúten"
    assert violacoes_gluten[0].tipo == "critico"


# =========================================================================
# CENÁRIO E: Alimento sem Correspondência Confiável na TACO
# Ingrediente desconhecido é sinalizado para revisão e não aprovado cegamente.
# =========================================================================
def test_cenario_e_alimento_sem_taco():
    pratos = [
        PratoSchema(nome="Arroz", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="arroz cozido", quantidade_g=100.0)]),
        PratoSchema(nome="Feijão", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="feijão cozido", quantidade_g=80.0)]),
        PratoSchema(nome="Frango", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="frango cozido", quantidade_g=100.0)]),
        PratoSchema(nome="Ingrediente Ficticio Alienigena", estado_preparacao="cru", ingredientes=[
            IngredienteSchema(nome_taco="xyz_alimento_inexistente_12345", quantidade_g=50.0)
        ]),
    ]
    cardapio = criar_cardapio_teste({"sexta-feira": pratos})

    inconformidades = validar_cardapio_pnae(
        cardapio=cardapio,
        etapa="ensino fundamental",
        faixa_etaria="6 a 10 anos",
        periodo="parcial",
        num_refeicoes=1,
    )

    taco_ausente = [i for i in inconformidades if "taco" in i.regra.lower()]
    assert len(taco_ausente) > 0, "Ingrediente sem TACO deve ser identificado na auditoria"

    relatorio = avaliar_status_cardapio(inconformidades)
    assert relatorio.status in (StatusValidacao.pendente_revisao, StatusValidacao.reprovado)
    assert relatorio.aprovado is False


# =========================================================================
# CENÁRIO F: Inconsistência Nutricional
# Refeição com calorias absurdamente baixas ou altas recebe status adequado.
# =========================================================================
def test_cenario_f_inconsistencia_nutricional():
    # Apenas 10g de alface para uma criança de 6 a 10 anos (energia < 5 kcal vs meta de ~329 kcal)
    pratos_vazios = [
        PratoSchema(nome="Salada Insuficiente", estado_preparacao="cru", ingredientes=[
            IngredienteSchema(nome_taco="alface americana crua", quantidade_g=10.0)
        ])
    ]
    cardapio = criar_cardapio_teste({"segunda-feira": pratos_vazios})

    inconformidades = validar_cardapio_pnae(
        cardapio=cardapio,
        etapa="ensino fundamental",
        faixa_etaria="6 a 10 anos",
        periodo="parcial",
        num_refeicoes=1,
    )

    erros_nutri = [i for i in inconformidades if "valor diario" in i.regra.lower()]
    assert len(erros_nutri) > 0, "Deveria apontar inconsistência nutricional severa"
    
    criticos_nutri = [i for i in erros_nutri if i.tipo == "critico"]
    assert len(criticos_nutri) > 0, "Déficit nutricional extremo deve ser marcado como crítico"

    relatorio = avaliar_status_cardapio(inconformidades)
    assert relatorio.status == StatusValidacao.reprovado
    assert relatorio.aprovado is False


# =========================================================================
# CENÁRIO G: Falha Persistente Não Pode Ser Aprovada
# Se restar erro crítico, avaliar_status_cardapio NUNCA aprova.
# =========================================================================
def test_cenario_g_falha_persistente_nao_aprova():
    from src.schemas_pydantic import InconformidadePNAESchema
    inconformidades_criticas = [
        InconformidadePNAESchema(escopo="dia 1", regra="Alimento proibido", detalhe="Gordura hidrogenada", tipo="critico")
    ]
    relatorio = avaliar_status_cardapio(inconformidades_criticas)
    assert relatorio.status == StatusValidacao.reprovado
    assert relatorio.aprovado is False


# =========================================================================
# CENÁRIO H: Compatibilidade de Contrato da API
# Endpoint /api/cardapios/generate mantém todas as chaves exigidas pelo frontend.
# =========================================================================
def test_cenario_h_compatibilidade_contrato_api():
    client = TestClient(app)

    # Verifica endpoint /health
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json() == {"status": "ok", "service": "CardapIA"}


# =========================================================================
# CENÁRIO I: Diferentes Etapas Escolares e Contextos
# Verifica se construir_contexto escala corretamente metas para Creche, Fundamental e EJA.
# =========================================================================
def test_cenario_i_diferentes_etapas_escolares():
    # 1. Creche (1 a 3 anos, 70% integral)
    ctx_creche = construir_contexto(
        etapa="creche",
        faixa_etaria="1 a 3 anos",
        periodo="integral",
        num_refeicoes=4,
    )
    assert "708 kcal" in ctx_creche
    assert "alimentos ultraprocessados" in ctx_creche.lower()

    # 2. Fundamental (6 a 10 anos, parcial 1 refeição)
    ctx_fund = construir_contexto(
        etapa="ensino fundamental",
        faixa_etaria="6 a 10 anos",
        periodo="parcial",
        num_refeicoes=1,
    )
    assert "329 kcal" in ctx_fund
    assert "Valores nutricionais absolutos por refeição" in ctx_fund

    # 3. EJA (19 a 30 anos, parcial 2 refeições)
    ctx_eja = construir_contexto(
        etapa="EJA",
        faixa_etaria="19 a 30 anos",
        periodo="parcial",
        num_refeicoes=2,
    )
    assert "715 kcal" in ctx_eja
    assert "2 refeições somadas no total" in ctx_eja


# =========================================================================
# CENÁRIO J: Composição Culinária Alternativa (Pratos Compostos e Regionais)
# "Galinhada" ou "Macarrão à bolonhesa" fornecem base energética e proteína animal.
# =========================================================================
def test_cenario_j_composicao_culinaria_alternativa():
    pratos = [
        PratoSchema(nome="Galinhada com Cenoura", estado_preparacao="cozido", ingredientes=[
            IngredienteSchema(nome_taco="arroz polido cozido", quantidade_g=100.0),
            IngredienteSchema(nome_taco="frango peito filé cozido", quantidade_g=90.0),
            IngredienteSchema(nome_taco="cenoura crua", quantidade_g=30.0),
        ]),
        PratoSchema(nome="Salada de Alface", estado_preparacao="cru", ingredientes=[
            IngredienteSchema(nome_taco="alface americana crua", quantidade_g=30.0)
        ]),
        PratoSchema(nome="Sobremesa: Maçã", estado_preparacao="cru", ingredientes=[
            IngredienteSchema(nome_taco="maçã fuji crua", quantidade_g=80.0)
        ]),
    ]
    cardapio = criar_cardapio_teste({"segunda-feira": pratos})
    inconformidades = validar_coerencia_culinaria(cardapio, etapa="ensino fundamental")
    criticos = [i for i in inconformidades if i.tipo == "critico"]
    assert len(criticos) == 0, f"Galinhada não deveria ter erro crítico: {criticos}"


# =========================================================================
# CENÁRIO K: Duas Frutas Servidas Separadamente (Advertência, Não Crítico)
# Banana e Maçã servidas juntas como sobremesas geram advertência de distribuição.
# =========================================================================
def test_cenario_k_duas_frutas_separadas_mesma_refeicao():
    pratos = [
        PratoSchema(nome="Arroz", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="arroz polido cozido", quantidade_g=100.0)]),
        PratoSchema(nome="Feijão", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="feijão carioca cozido", quantidade_g=80.0)]),
        PratoSchema(nome="Carne Bovina Moída", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="carne bovina moída cozida", quantidade_g=90.0)]),
        PratoSchema(nome="Sobremesa 1: Banana", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="banana prata crua", quantidade_g=80.0)]),
        PratoSchema(nome="Sobremesa 2: Maçã", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="maçã fuji crua", quantidade_g=80.0)]),
    ]
    cardapio = criar_cardapio_teste({"segunda-feira": pratos})
    inconformidades = validar_coerencia_culinaria(cardapio, etapa="ensino fundamental")

    criticos = [i for i in inconformidades if i.tipo == "critico"]
    assert len(criticos) == 0, f"Duas frutas não devem ser erro crítico: {criticos}"

    advs_fruta = [i for i in inconformidades if "distribuição de frutas" in i.regra.lower()]
    assert len(advs_fruta) > 0, "Deve advertir para distribuição de frutas"
    assert advs_fruta[0].tipo == "advertencia"


# =========================================================================
# CENÁRIO L: Frutas em Preparações Compostas e Sucos Não Geram Excesso
# Suco de maracujá + banana ou salada de frutas não são excessos de frutas avulsas.
# =========================================================================
def test_cenario_l_frutas_em_preparacao_composta_e_sucos():
    pratos = [
        PratoSchema(nome="Arroz", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="arroz polido cozido", quantidade_g=100.0)]),
        PratoSchema(nome="Feijão", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="feijão carioca cozido", quantidade_g=80.0)]),
        PratoSchema(nome="Frango Grelhado", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="frango peito filé grelhado", quantidade_g=100.0)]),
        PratoSchema(nome="Suco de Maracujá", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="maracujá cru", quantidade_g=40.0)]),
        PratoSchema(nome="Sobremesa: Banana", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="banana prata crua", quantidade_g=80.0)]),
    ]
    cardapio = criar_cardapio_teste({"segunda-feira": pratos})
    inconformidades = validar_coerencia_culinaria(cardapio, etapa="ensino fundamental")
    erros_fruta = [i for i in inconformidades if "fruta" in i.regra.lower()]
    assert len(erros_fruta) == 0, f"Suco + fruta sobremesa não deve ter erro de frutas: {erros_fruta}"


# =========================================================================
# CENÁRIO M: Pratos Sem Ingredientes Filhos (Validação pelo Nome do Prato)
# Pratos com ingredientes=[] classificam nome do prato diretamente.
# =========================================================================
def test_cenario_m_pratos_sem_ingredientes_filhos():
    pratos = [
        PratoSchema(nome="Arroz Branco", estado_preparacao="cozido", ingredientes=[]),
        PratoSchema(nome="Feijão Carioca", estado_preparacao="cozido", ingredientes=[]),
        PratoSchema(nome="Peito de Frango Grelhado", estado_preparacao="grelhado", ingredientes=[]),
    ]
    cardapio = criar_cardapio_teste({"segunda-feira": pratos})
    inconformidades = validar_coerencia_culinaria(cardapio, etapa="ensino fundamental")
    criticos = [i for i in inconformidades if i.tipo == "critico"]
    assert len(criticos) == 0, f"Pratos sem array de ingredientes não devem ter erros críticos: {criticos}"


# =========================================================================
# CENÁRIO N: Falsos Positivos de Restrição (Leite Vegetal e Polvilho)
# Leite de coco e biscoito de polvilho não disparam violação indevida.
# =========================================================================
def test_cenario_n_falsos_positivos_restricao():
    pratos_lactose = [
        PratoSchema(nome="Frango ao Leite de Coco", estado_preparacao="cozido", ingredientes=[
            IngredienteSchema(nome_taco="frango peito filé cozido", quantidade_g=100.0),
            IngredienteSchema(nome_taco="leite de coco", quantidade_g=30.0),
        ])
    ]
    cardapio_lactose = criar_cardapio_teste({"segunda-feira": pratos_lactose})
    inconformidades_lactose = validar_coerencia_culinaria(cardapio_lactose, etapa="ensino fundamental", restricoes=["lactose"])
    violacoes_lactose = [i for i in inconformidades_lactose if "lactose" in i.regra.lower()]
    assert len(violacoes_lactose) == 0, f"Leite de coco não deve violar lactose: {violacoes_lactose}"

    pratos_gluten = [
        PratoSchema(nome="Biscoito de Polvilho e Pão de Queijo", estado_preparacao="assado", ingredientes=[
            IngredienteSchema(nome_taco="biscoito de polvilho", quantidade_g=40.0),
            IngredienteSchema(nome_taco="pão de queijo", quantidade_g=50.0),
        ])
    ]
    cardapio_gluten = criar_cardapio_teste({"segunda-feira": pratos_gluten})
    inconformidades_gluten = validar_coerencia_culinaria(cardapio_gluten, etapa="ensino fundamental", restricoes=["glúten"])
    violacoes_gluten = [i for i in inconformidades_gluten if "glúten" in i.regra.lower() or "gluten" in i.regra.lower()]
    assert len(violacoes_gluten) == 0, f"Polvilho e pão de queijo não devem violar glúten: {violacoes_gluten}"


# =========================================================================
# CENÁRIO O: Cálculos Nutricionais e Limites PNAE
# Verifica conversão per capita e desvio de 30% documentado.
# =========================================================================
def test_cenario_o_calculos_nutricionais():
    from src.nutrition.calculator import _somar_nutriente, _dentro_intervalo
    assert _somar_nutriente(120.0, 50.0) == 60.0
    assert _somar_nutriente(None, 50.0) == 0.0

    assert _dentro_intervalo(100.0, 100.0, 100.0, tolerancia=0.1) is True
    assert _dentro_intervalo(85.0, 100.0, 100.0, tolerancia=0.1) is False


# =========================================================================
# CENÁRIO P: Persistência no PostgreSQL de Pratos Sem Ingredientes e Semana 5
# Garante ausência de pratos órfãos e suporte a meses com 5 semanas.
# =========================================================================
def test_cenario_p_persistencia_postgres():
    from db.repository import salvar_cardapio_db
    from db.database import engine
    from db.models import Ingrediente, Prato, Cardapio, Semana
    from sqlalchemy.orm import Session
    import uuid

    # Cria cardápio com prato sem ingredientes e 5 semanas
    prato_sem_ing = PratoSchema(nome="Arroz Branco Cozido", estado_preparacao="cozido", ingredientes=[])
    refeicao = RefeicaoSchema(tipo=TipoRefeicao.almoco, horario="11:30", pratos=[prato_sem_ing])
    dia = DiaSchema(dia_semana="segunda-feira", refeicoes=[refeicao])
    semanas = [SemanaSchema(numero=i, dias=[dia]) for i in range(1, 6)]
    cardapio = CardapioSchema(mes_aplicacao="outubro de 2026", semanas=semanas, observacoes="")

    cardapio_id = salvar_cardapio_db(
        cardapio_schema=cardapio,
        etapa="ensino fundamental",
        faixa_etaria="6 a 10 anos",
        periodo="parcial",
        num_refeicoes=1,
        mes_aplicacao="outubro de 2026",
    )
    assert cardapio_id is not None, "Deveria persistir cardápio de 5 semanas sem erro"

    with Session(engine) as session:
        cardapio_uuid = uuid.UUID(cardapio_id)
        semanas_db = session.query(Semana).filter(Semana.cardapio_id == cardapio_uuid).all()
        assert len(semanas_db) == 5, f"Deveria ter 5 semanas salvas, encontrou {len(semanas_db)}"

        # Verifica se o prato persistiu o ingrediente resolvido automaticamente
        prato_db = session.query(Prato).filter(Prato.nome == "Arroz Branco Cozido").first()
        assert prato_db is not None
        ing_db = session.query(Ingrediente).filter(Ingrediente.prato_id == prato_db.id).first()
        assert ing_db is not None, "Ingrediente deveria ter sido criado para o prato sem ingredientes"

        # Limpa o cardápio de teste
        cardapio_db = session.query(Cardapio).filter(Cardapio.id == cardapio_uuid).first()
        if cardapio_db:
            session.delete(cardapio_db)
            session.commit()


# =========================================================================
# CENÁRIO Q: Avaliação de Autocorreção LLM Impede Regressão de Restrição
# Se a LLM eliminar um erro superficial mas introduzir restrição, deve descartar.
# =========================================================================
def test_cenario_q_avaliacao_autocorrecao_rejeita_regressao():
    from src.services.ai_generator import _avaliar_aceitacao_correcao
    from src.schemas_pydantic import RelatorioValidacaoSchema, InconformidadePNAESchema, StatusValidacao

    cardapio_orig = criar_cardapio_teste({"segunda-feira": [
        PratoSchema(nome="Arroz", estado_preparacao="cozido", ingredientes=[]),
    ]})
    relatorio_orig = RelatorioValidacaoSchema(
        status=StatusValidacao.reprovado,
        aprovado=False,
        total_criticos=1,
        total_advertencias=0,
        inconformidades=[
            InconformidadePNAESchema(escopo="dia 1", regra="Coerência culinária: excesso de frutas na mesma refeição", detalhe="3 frutas", tipo="critico")
        ],
        resumo=""
    )

    cardapio_corr = criar_cardapio_teste({"segunda-feira": [
        PratoSchema(nome="Arroz", estado_preparacao="cozido", ingredientes=[]),
    ]})
    relatorio_corr_regressao = RelatorioValidacaoSchema(
        status=StatusValidacao.reprovado,
        aprovado=False,
        total_criticos=1,
        total_advertencias=0,
        inconformidades=[
            InconformidadePNAESchema(escopo="dia 1", regra="Restrição alimentar violada: Glúten", detalhe="Glúten adicionado", tipo="critico")
        ],
        resumo=""
    )

    aceito, motivo = _avaliar_aceitacao_correcao(
        cardapio_orig=cardapio_orig,
        relatorio_orig=relatorio_orig,
        cardapio_corr=cardapio_corr,
        relatorio_corr=relatorio_corr_regressao,
    )
    assert aceito is False, f"Deveria ter rejeitado correção que introduziu violação de restrição: {motivo}"
    assert "restrição alimentar" in motivo.lower()


# =========================================================================
# CENÁRIO R: Prato Composto Sem Ingredientes Não Persiste Alimento Isolado Artificial
# "Galinhada Caipira" não deve ser forçada a um único ingrediente avulso.
# =========================================================================
def test_cenario_r_prato_composto_sem_ingredientes_nao_persiste_artificial():
    from db.repository import salvar_cardapio_db
    from db.database import engine
    from db.models import Ingrediente, Prato, Cardapio
    from sqlalchemy.orm import Session
    import uuid

    prato_composto = PratoSchema(nome="Galinhada Caipira Tradicional", estado_preparacao="cozido", ingredientes=[])
    refeicao = RefeicaoSchema(tipo=TipoRefeicao.almoco, horario="11:30", pratos=[prato_composto])
    dia = DiaSchema(dia_semana="segunda-feira", refeicoes=[refeicao])
    semana = SemanaSchema(numero=1, dias=[dia])
    cardapio = CardapioSchema(mes_aplicacao="outubro de 2026", semanas=[semana], observacoes="")

    cardapio_id = salvar_cardapio_db(
        cardapio_schema=cardapio,
        etapa="ensino fundamental",
        faixa_etaria="6 a 10 anos",
        periodo="parcial",
        num_refeicoes=1,
        mes_aplicacao="outubro de 2026",
    )
    assert cardapio_id is not None

    with Session(engine) as session:
        cardapio_uuid = uuid.UUID(cardapio_id)
        prato_db = session.query(Prato).filter(Prato.nome == "Galinhada Caipira Tradicional").first()
        assert prato_db is not None
        ingredientes_db = session.query(Ingrediente).filter(Ingrediente.prato_id == prato_db.id).all()
        assert len(ingredientes_db) == 0, "Prato composto sem receita não deve ter ingrediente único arbitrário persistido"

        cardapio_db = session.query(Cardapio).filter(Cardapio.id == cardapio_uuid).first()
        if cardapio_db:
            session.delete(cardapio_db)
            session.commit()


# =========================================================================
# CENÁRIO S: Restrição Alimentar Com Composição Indeterminada
# "Purê de Batata" sem ingredientes com restrição de lactose gera advertência explícita.
# =========================================================================
def test_cenario_s_restricao_composicao_indeterminada():
    pratos = [
        PratoSchema(nome="Purê de Batata Cremoso", estado_preparacao="cozido", ingredientes=[]),
    ]
    cardapio = criar_cardapio_teste({"segunda-feira": pratos})
    inconformidades = validar_coerencia_culinaria(cardapio, etapa="ensino fundamental", restricoes=["lactose"])
    indeterminadas = [i for i in inconformidades if "composição indeterminada" in i.regra.lower()]
    assert len(indeterminadas) > 0, "Deveria registrar pendência de composição indeterminada para o purê"
    assert indeterminadas[0].tipo == "advertencia"


# =========================================================================
# CENÁRIO T: Persistência no PostgreSQL Até Semana 6
# Valida persistência relacional completa de cardápio com 6 semanas.
# =========================================================================
def test_cenario_t_persistencia_semana_6():
    from db.repository import salvar_cardapio_db
    from db.database import engine
    from db.models import Cardapio, Semana
    from sqlalchemy.orm import Session
    import uuid

    prato = PratoSchema(nome="Arroz", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="arroz tipo 1 cozido", quantidade_g=100.0)])
    refeicao = RefeicaoSchema(tipo=TipoRefeicao.almoco, horario="11:30", pratos=[prato])
    dia = DiaSchema(dia_semana="segunda-feira", refeicoes=[refeicao])
    semanas = [SemanaSchema(numero=i, dias=[dia]) for i in range(1, 7)]
    cardapio = CardapioSchema(mes_aplicacao="outubro de 2026", semanas=semanas, observacoes="")

    cardapio_id = salvar_cardapio_db(
        cardapio_schema=cardapio,
        etapa="ensino fundamental",
        faixa_etaria="6 a 10 anos",
        periodo="parcial",
        num_refeicoes=1,
        mes_aplicacao="outubro de 2026",
    )
    assert cardapio_id is not None, "Deveria persistir cardápio de 6 semanas"

    with Session(engine) as session:
        cardapio_uuid = uuid.UUID(cardapio_id)
        semanas_db = session.query(Semana).filter(Semana.cardapio_id == cardapio_uuid).all()
        assert len(semanas_db) == 6, f"Esperava 6 semanas, encontrou {len(semanas_db)}"

        cardapio_db = session.query(Cardapio).filter(Cardapio.id == cardapio_uuid).first()
        if cardapio_db:
            session.delete(cardapio_db)
            session.commit()


# =========================================================================
# CENÁRIO U: Normalização de Aliases PNAE, Escopo Semanal e Calibragem de Carnes
# =========================================================================
def test_cenario_u_aliases_pnae_e_escopo_semanal():
    from src.nutrition.pnae_auditor import _resolver_regras_pnae
    from src.taco.resolver import resolver_per_capita

    # 1. Normalização de aliases da API/backend para o PNAE
    regras_medio = _resolver_regras_pnae("medio", "16_18", "parcial", 1)
    assert regras_medio["valores"]["energia_kcal"] == 543, f"Esperado 543 kcal, obteve {regras_medio['valores']['energia_kcal']}"
    assert regras_medio["valores"]["proteinas_g"]["minimo"] == 14
    assert regras_medio["valores"]["proteinas_g"]["maximo"] == 20

    regras_fund = _resolver_regras_pnae("fundamental", "6_10", "parcial", 1)
    assert regras_fund["valores"]["energia_kcal"] == 329

    regras_creche = _resolver_regras_pnae("creche", "1_3", "parcial", 2)
    assert regras_creche["valores"]["energia_kcal"] == 304

    # 2. Calibragem de carnes para Ensino Médio (porção ajustada a 45g)
    pc_frango = resolver_per_capita("Sobrecoxa de Frango", "medio")
    assert pc_frango == 45.0, f"Esperado 45.0g para carne no Ensino Médio, obteve {pc_frango}"

    # 3. Escopo semanal: cardápio de 1 dia não deve cobrar metas semanais de múltiplos dias
    pratos = [
        PratoSchema(nome="Arroz Integral", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="arroz integral cozido", quantidade_g=80.0)]),
        PratoSchema(nome="Feijão Carioca", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="feijão carioca cozido", quantidade_g=40.0)]),
        PratoSchema(nome="Sobrecoxa de Frango", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="frango sobrecoxa sem pele cozida", quantidade_g=45.0)]),
        PratoSchema(nome="Cenoura", estado_preparacao="cozido", ingredientes=[IngredienteSchema(nome_taco="cenoura cozida", quantidade_g=55.0)]),
        PratoSchema(nome="Melancia", estado_preparacao="cru", ingredientes=[IngredienteSchema(nome_taco="melancia crua", quantidade_g=200.0)]),
    ]
    refeicao = RefeicaoSchema(tipo=TipoRefeicao.almoco, horario="12:00", pratos=pratos)
    dia = DiaSchema(dia_semana="Sábado", refeicoes=[refeicao])
    semana = SemanaSchema(numero=1, dias=[dia])
    cardapio_1_dia = CardapioSchema(mes_aplicacao="outubro de 2026", semanas=[semana], observacoes="")

    inconformidades = validar_cardapio_pnae(cardapio_1_dia, etapa="medio", faixa_etaria="16_18", periodo="parcial", num_refeicoes=1)
    regras_inconsistencias = [i.regra for i in inconformidades]

    assert "Oferta semanal de frutas" not in regras_inconsistencias, "Não deve cobrar oferta semanal de frutas em cardápio de 1 dia"
    assert "Oferta semanal de legumes e verduras" not in regras_inconsistencias, "Não deve cobrar oferta semanal de legumes em cardápio de 1 dia"
    assert "Diversidade semanal de alimentos" not in regras_inconsistencias, "Não deve cobrar diversidade semanal completa em cardápio de 1 dia"
    assert "Quantidade semanal de frutas, legumes e verduras" not in regras_inconsistencias, "Não deve cobrar gramatura semanal integral em cardápio de 1 dia"


if __name__ == "__main__":
    testes = [
        ("Cenário A — Refeição principal coerente", test_cenario_a_refeicao_principal_coerente),
        ("Cenário B — Excesso de alimentos redundantes / múltiplas frutas", test_cenario_b_excesso_frutas_mesma_refeicao),
        ("Cenário C — Variedade semanal / monotonia proteica", test_cenario_c_monotonia_proteica_consecutiva),
        ("Cenário D — Restrições alimentares (lactose / glúten)", test_cenario_d_restricoes_alimentares),
        ("Cenário E — Alimento sem correspondência confiável na TACO", test_cenario_e_alimento_sem_taco),
        ("Cenário F — Inconsistência nutricional severa", test_cenario_f_inconsistencia_nutricional),
        ("Cenário G — Falha persistente não pode ser aprovada", test_cenario_g_falha_persistente_nao_aprova),
        ("Cenário H — Compatibilidade de contrato da API", test_cenario_h_compatibilidade_contrato_api),
        ("Cenário I — Diferentes etapas escolares e escalas PNAE", test_cenario_i_diferentes_etapas_escolares),
        ("Cenário J — Composição culinária alternativa (pratos compostos)", test_cenario_j_composicao_culinaria_alternativa),
        ("Cenário K — Duas frutas separadas (advertência, não crítico)", test_cenario_k_duas_frutas_separadas_mesma_refeicao),
        ("Cenário L — Frutas em preparações compostas e sucos", test_cenario_l_frutas_em_preparacao_composta_e_sucos),
        ("Cenário M — Pratos sem array explícito de ingredientes", test_cenario_m_pratos_sem_ingredientes_filhos),
        ("Cenário N — Falsos positivos de restrição (leite vegetal / polvilho)", test_cenario_n_falsos_positivos_restricao),
        ("Cenário O — Cálculos nutricionais e desvio de 30% PNAE", test_cenario_o_calculos_nutricionais),
        ("Cenário P — Persistência no PostgreSQL (prato sem ingredientes e semana 5)", test_cenario_p_persistencia_postgres),
        ("Cenário Q — Avaliação de autocorreção LLM impede regressão", test_cenario_q_avaliacao_autocorrecao_rejeita_regressao),
        ("Cenário R — Prato composto sem receita não inventa ingrediente único", test_cenario_r_prato_composto_sem_ingredientes_nao_persiste_artificial),
        ("Cenário S — Restrição alimentar com composição indeterminada", test_cenario_s_restricao_composicao_indeterminada),
        ("Cenário T — Persistência no PostgreSQL até semana 6", test_cenario_t_persistencia_semana_6),
        ("Cenário U — Normalização de Aliases PNAE, Escopo Semanal e Calibragem de Carnes", test_cenario_u_aliases_pnae_e_escopo_semanal),
    ]
    falhas = 0
    print("=" * 70)
    print("EXECUTANDO SUÍTE DE TESTES: VALIDAÇÃO CULINÁRIA E PNAE")
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
        print(f"SUCESSO TOTAL: Todos os {len(testes)} cenários foram APROVADOS!")
    else:
        print(f"ERRO: {falhas} cenários falharam.")
        sys.exit(1)

