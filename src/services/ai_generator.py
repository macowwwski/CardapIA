"""
Orquestrador do Pipeline de Inteligência Artificial para geração e correção de cardápios.

Coordena:
1. Construção do contexto PNAE.
2. Invocação do modelo LLM para planejamento textual.
3. Extração e validação do CardapioSchema estruturado.
4. Resolução de ingredientes na TACO e aplicação de porções per capita oficiais.
5. Auditoria culinária e nutricional com tentativa controlada de autocorreção.
6. Emissão de parecer regulatório e formatação final.
"""
import time
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from src.config import (
    OLLAMA_MODEL,
    OLLAMA_TEMPERATURE,
)
from src.schemas_pydantic import CardapioSchema, RelatorioValidacaoSchema
from src.taco.resolver import resolver_taco, resolver_per_capita
from src.pipelines import selecionar_pipeline
from src.prompts.templates import (
    montar_prompt_conversao_json,
    montar_mensagem_conversao_json,
)
from src.services.normalizer import validar_cardapio
from src.nutrition.classifier import _texto_normalizado
from src.nutrition.pnae_auditor import (
    avaliar_status_cardapio,
)


def obter_per_capita(nome_alimento: str, etapa: str, taco_id: str | None = None) -> float:
    """
    Retorna o per capita em gramas para um alimento e etapa escolar.
    Fonte: Manual de Per Capita PNAE / Resolução FNDE 06/2020.
    """
    valor = resolver_per_capita(nome_alimento, etapa, taco_id=taco_id)
    if valor is None:
        raise ValueError(
            f"Per capita não encontrado (ou alimento restrito) para a etapa '{etapa}': {nome_alimento}"
        )
    return valor


def aplicar_per_capita(cardapio: CardapioSchema, etapa: str) -> CardapioSchema:
    """
    Resolve cada ingrediente na TACO (preenchendo o taco_id) e ajusta a quantidade
    com o per capita oficial da etapa escolar.

    Sem fallback para valor fixo: se não houver per capita oficial, mantém a quantidade
    sugerida pela IA (quando válida); caso contrário o ingrediente é descartado.
    Descarta água avulsa de cocção, deduplica óleos/gorduras de preparo e calibra o sal de cozinha.
    """
    for semana in cardapio.semanas:
        for dia in semana.dias:
            for refeicao in dia.refeicoes:
                tem_oleo_coccao = False
                tem_sal_adicionado = False
                for prato in refeicao.pratos:
                    validos = []
                    for ingrediente in prato.ingredientes:
                        nome_norm = _texto_normalizado(ingrediente.nome_taco or prato.nome)

                        # 1. Descartar água de cozimento avulsa
                        if nome_norm in ("agua", "agua potavel", "agua de cozimento", "agua mineral"):
                            continue

                        # 2. Controlar gorduras e óleos de preparo: máximo 1 ocorrência por refeição
                        eh_prato_composto = any(c in nome_norm for c in ("macarra", "arroz", "batat", "mandioc", "carne", "frang", "peix", "ovo", "salada", "legum"))
                        eh_oleo_gordura = any(t in nome_norm for t in ("azeite", "oleo", "gordura vegetal")) and not eh_prato_composto
                        if eh_oleo_gordura:
                            if tem_oleo_coccao:
                                continue
                            tem_oleo_coccao = True

                        # 3. Controlar sal de cozinha: máximo 1 ocorrência calibrada por refeição
                        eh_sal = "sal" in nome_norm and "salada" not in nome_norm and "salmao" not in nome_norm
                        if eh_sal:
                            if tem_sal_adicionado:
                                continue
                            tem_sal_adicionado = True

                        match = resolver_taco(ingrediente.nome_taco)
                        taco_id = match.taco_id if match else None
                        ingrediente._taco_id = taco_id

                        if eh_sal:
                            ingrediente.quantidade_g = 1.5
                        else:
                            valor = resolver_per_capita(ingrediente.nome_taco, etapa, taco_id=taco_id)
                            if valor is not None:
                                ingrediente.quantidade_g = valor
                            elif not ingrediente.quantidade_g or ingrediente.quantidade_g <= 0:
                                print(f"Aviso: ingrediente descartado sem per capita oficial: {ingrediente.nome_taco}")
                                continue
                        validos.append(ingrediente)
                    prato.ingredientes = validos

    return cardapio


def _avaliar_aceitacao_correcao(
    cardapio_orig: CardapioSchema,
    relatorio_orig: RelatorioValidacaoSchema,
    cardapio_corr: CardapioSchema,
    relatorio_corr: RelatorioValidacaoSchema,
) -> tuple[bool, str]:
    """
    Avalia rigorosamente se a autocorreção da LLM deve substituir o cardápio original.
    Impede que a correção elimine um problema mas introduza violação de restrição alimentar,
    alimento proibido, perda de dias letivos ou piora nutricional crítica.
    """
    if len(cardapio_corr.semanas) < len(cardapio_orig.semanas):
        return False, "Correção descartada: reduziu o número de semanas planejadas."

    total_dias_orig = sum(len(s.dias) for s in cardapio_orig.semanas)
    total_dias_corr = sum(len(s.dias) for s in cardapio_corr.semanas)
    if total_dias_corr < total_dias_orig:
        return False, "Correção descartada: reduziu o total de dias planejados."

    criticos_restricao_orig = sum(
        1 for i in relatorio_orig.inconformidades
        if "restrição alimentar violada" in i.regra.lower() and i.tipo == "critico"
    )
    criticos_restricao_corr = sum(
        1 for i in relatorio_corr.inconformidades
        if "restrição alimentar violada" in i.regra.lower() and i.tipo == "critico"
    )
    if criticos_restricao_corr > criticos_restricao_orig:
        return False, "Correção descartada: introduziu novas violações de restrição alimentar."

    proibidos_orig = sum(
        1 for i in relatorio_orig.inconformidades
        if "alimento proibido" in i.regra.lower() and i.tipo == "critico"
    )
    proibidos_corr = sum(
        1 for i in relatorio_corr.inconformidades
        if "alimento proibido" in i.regra.lower() and i.tipo == "critico"
    )
    if proibidos_corr > proibidos_orig:
        return False, "Correção descartada: introduziu alimentos proibidos pelo PNAE."

    nutri_criticos_orig = sum(
        1 for i in relatorio_orig.inconformidades
        if "valor diario" in i.regra.lower() and i.tipo == "critico"
    )
    nutri_criticos_corr = sum(
        1 for i in relatorio_corr.inconformidades
        if "valor diario" in i.regra.lower() and i.tipo == "critico"
    )
    if nutri_criticos_corr > nutri_criticos_orig:
        return False, "Correção descartada: agravou o déficit nutricional crítico diário."

    melhorou_criticos = relatorio_corr.total_criticos < relatorio_orig.total_criticos
    iguais_criticos = relatorio_corr.total_criticos == relatorio_orig.total_criticos
    melhorou_advertencias = relatorio_corr.total_advertencias < relatorio_orig.total_advertencias

    if melhorou_criticos:
        return True, "Correção aceita: reduziu inconsistências críticas com segurança."
    elif iguais_criticos and melhorou_advertencias:
        return True, "Correção aceita: manteve críticos e reduziu advertências."

    return False, "Correção descartada: não apresentou melhora suficiente em relação ao original."


def gerar_cardapio(
    etapa: str,
    faixa_etaria: str,
    periodo: str,
    num_refeicoes: int,
    mes_aplicacao: str,
    turno: str = "matutino",
    restricoes: list[str] | None = None,
    num_semanas: int = 1,
    validar_pnae: bool = False,
    total_dias: int | None = None,
    dias_letivos: list[str] | None = None,
) -> CardapioSchema:
    """
    Gera o cardápio escolar orquestrando o modelo LLM e regras do PNAE.

    Parâmetros:
        num_semanas: Quantidade de semanas de cardápio a planejar.
        validar_pnae: Quando ativado, anexa inconsistências do PNAE às observações sem abortar a geração.
        total_dias: Quantidade exata de dias letivos a planejar.
        dias_letivos: Lista de datas específicas dos dias letivos.
    """
    pipeline = selecionar_pipeline(
        etapa=etapa,
        faixa_etaria=faixa_etaria,
        periodo=periodo,
        num_refeicoes=num_refeicoes,
    )

    # - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # ETAPA 1 — Geração de texto livre do cardápio via LLM
    # - - - - - - - - - - - - - - - - - - - - - - - - - - -
    llm = ChatOllama(
        model=OLLAMA_MODEL,
        temperature=OLLAMA_TEMPERATURE,
    )

    system_prompt_1 = pipeline.construir_system_prompt(
        turno=turno,
        restricoes=restricoes or [],
        total_dias=total_dias,
        num_semanas=num_semanas,
        dias_letivos=dias_letivos,
    )

    dias_txt = f" para {total_dias} dia(s) letivo(s)" if total_dias else ""
    mensagens = [
        SystemMessage(content=system_prompt_1),
        HumanMessage(content=f"Gere o cardápio de {num_refeicoes} refeições diárias para {mes_aplicacao}{dias_txt}."),
    ]

    resposta = llm.invoke(mensagens)
    texto_cardapio = resposta.content

    # - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # ETAPA 2 — Conversão para JSON estruturado com Schema Pydantic
    # - - - - - - - - - - - - - - - - - - - - - - - - - - -
    llm_structured = ChatOllama(
        model=OLLAMA_MODEL,
        temperature=0,
    ).with_structured_output(CardapioSchema)

    prompt_2 = montar_prompt_conversao_json()

    for tentativa in range(3):
        try:
            resultado = llm_structured.invoke(
                montar_mensagem_conversao_json(prompt_2, texto_cardapio)
            )

            cardapio = validar_cardapio(
                resultado,
                mes_aplicacao=mes_aplicacao,
                num_refeicoes=num_refeicoes,
                turno=turno,
            )
            break

        except Exception as e:
            print(f"Erro na etapa 2 (tentativa {tentativa+1}): {e}")
            time.sleep(1)

    else:
        raise RuntimeError("Falha ao converter cardápio para estrutura válida.")

    # - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # ETAPA 3 — Injeção de porções de Per Capita do PNAE
    # - - - - - - - - - - - - - - - - - - - - - - - - - - -
    cardapio = pipeline.aplicar_per_capita(cardapio)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # ETAPA 3.5 — Otimização Matemática Determinística (VET e Macronutrientes)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - -
    cardapio = pipeline.ajustar_macronutrientes(cardapio)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # ETAPA 4 — Auditoria Culinária, Nutricional e Regras PNAE
    # - - - - - - - - - - - - - - - - - - - - - - - - - - -
    inconformidades = pipeline.auditar(
        cardapio=cardapio,
        restricoes=restricoes or [],
    )
    relatorio = avaliar_status_cardapio(inconformidades)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # ETAPA 5 — Tentativa Controlada de Correção para Falhas Críticas
    # - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if relatorio.total_criticos > 0:
        print(f"Cardápio gerado com {relatorio.total_criticos} inconformidade(s) crítica(s). Tentando correção orientada...")
        try:
            erros_criticos = [
                f"{i.escopo}: {i.regra} - {i.detalhe}"
                for i in inconformidades if i.tipo == "critico"
            ]
            prompt_correcao = pipeline.montar_prompt_correcao(texto_cardapio, erros_criticos)
            resposta_corr = llm.invoke([
                SystemMessage(content=system_prompt_1),
                HumanMessage(content=prompt_correcao),
            ])
            texto_corr = resposta_corr.content

            resultado_corr = llm_structured.invoke(
                montar_mensagem_conversao_json(prompt_2, texto_corr)
            )
            cardapio_corr = validar_cardapio(
                resultado_corr,
                mes_aplicacao=mes_aplicacao,
                num_refeicoes=num_refeicoes,
                turno=turno,
            )
            cardapio_corr = pipeline.aplicar_per_capita(cardapio_corr)
            cardapio_corr = pipeline.ajustar_macronutrientes(cardapio_corr)
            inconformidades_corr = pipeline.auditar(
                cardapio=cardapio_corr,
                restricoes=restricoes or [],
            )
            relatorio_corr = avaliar_status_cardapio(inconformidades_corr)

            aceito, motivo = _avaliar_aceitacao_correcao(
                cardapio_orig=cardapio,
                relatorio_orig=relatorio,
                cardapio_corr=cardapio_corr,
                relatorio_corr=relatorio_corr,
            )
            print(f"Parecer sobre autocorreção da LLM: {motivo}")
            if aceito:
                cardapio = cardapio_corr
                inconformidades = inconformidades_corr
                relatorio = relatorio_corr
        except Exception as e_corr:
            print(f"Aviso: falha na tentativa de correção orientada: {e_corr}")

    # Registra o resultado da validação no cardápio
    setattr(cardapio, "_relatorio_validacao", relatorio)
    setattr(cardapio, "_aprovado", relatorio.aprovado)
    setattr(cardapio, "_status_validacao_nome", relatorio.status.value)
    setattr(cardapio, "_inconformidades_json", [i.model_dump() for i in inconformidades])
    setattr(cardapio, "_resumo_validacao", relatorio.resumo)

    # Formata parecer para o campo observações
    parecer = f"PARECER PNAE [{relatorio.status.value.upper()}]: {relatorio.resumo}"
    if inconformidades:
        detalhes = "\n".join(
            f"- [{item.tipo.upper()}] {item.escopo}: {item.regra}. {item.detalhe}"
            for item in inconformidades
        )
        parecer = f"{parecer}\n{detalhes}"

    cardapio.observacoes = (
        f"{cardapio.observacoes}\n\n{parecer}".strip()
        if cardapio.observacoes
        else parecer
    )

    return cardapio
