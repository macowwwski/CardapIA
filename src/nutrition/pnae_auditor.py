"""
Motor de regras, auditoria e conformidade regulatória com o PNAE (Resolução CD/FNDE nº 06/2020).

Avalia:
- Alimentos proibidos para o público escolar (gorduras trans, ultraprocessados, açúcar simples em creches, etc.).
- Limites semanais de doces, biscoitos/bolos/pães, margarinas.
- Limites mensais de alimentos em conserva, embutidos e carnes processadas.
- Metas semanais de diversidade alimentar (alimentos distintos) e oferta de FLV in natura (gramas e dias).
- Atendimento aos limites nutricionais diários (energia, macronutrientes, micronutrientes, sódio).
- Classificação do parecer final (Aprovado, Pendente de Revisão, Reprovado).
"""
import re
from sqlalchemy.orm import Session
from db.database import engine
from db.models import Taco
from src.schemas_pydantic import (
    CardapioSchema,
    InconformidadePNAESchema,
    RelatorioValidacaoSchema,
    StatusValidacao,
)
from src.nutrition.classifier import (
    _texto_normalizado,
    _classificar_alimento,
    _contem_token,
    _contem_termo_adicao_acucar,
)
from src.nutrition.calculator import (
    _somar_nutriente,
    _dentro_intervalo,
    buscar_taco_por_nome,
    obter_vitamina_a_mcg_100g,
)
from src.nutrition.culinary_validator import validar_coerencia_culinaria


def _resolver_regras_pnae(etapa: str, faixa_etaria: str, periodo: str, num_refeicoes: int) -> dict:
    """Carrega as regras normativas e referências nutricionais do PNAE."""
    try:
        from src.prompts.builder import (
            REGRAS_PNAE,
            normalizar_etapa,
            normalizar_faixa_etaria,
            _mapear_e_obter_faixa_etaria,
            _mapear_percentual,
            _mapear_refeicoes_periodo,
            _obter_etapa,
            _obter_referencias_nutricionais,
        )
    except ImportError:
        from prompt_builder import (
            REGRAS_PNAE,
            normalizar_etapa,
            normalizar_faixa_etaria,
            _mapear_e_obter_faixa_etaria,
            _mapear_percentual,
            _mapear_refeicoes_periodo,
            _obter_etapa,
            _obter_referencias_nutricionais,
        )

    etapa_norm = normalizar_etapa(etapa)
    faixa_norm = normalizar_faixa_etaria(faixa_etaria)
    etapa_bloco = _obter_etapa(etapa_norm)
    percentual = _mapear_percentual(periodo, num_refeicoes)
    subfaixas = _obter_referencias_nutricionais(etapa_bloco, percentual)

    return {
        "geral": REGRAS_PNAE["geral"],
        "etapa_bloco": etapa_bloco,
        "percentual": percentual,
        "periodo_freq": _mapear_refeicoes_periodo(periodo, num_refeicoes),
        "valores": _mapear_e_obter_faixa_etaria(etapa_norm, faixa_norm, subfaixas),
    }


def _violacoes_proibicoes(
    cardapio: CardapioSchema,
    regras: dict,
    ingredientes_taco: dict[str, Taco | None],
) -> list[InconformidadePNAESchema]:
    """Identifica alimentos expressamente proibidos pelo PNAE para a etapa."""
    proibicoes = (
        regras["geral"].get("alimentos_proibidos", [])
        + regras["etapa_bloco"].get("alimentos_proibidos", [])
    )
    violacoes = []

    termos_por_proibicao = {
        "alimentos ricos em gorduras trans industrializadas": {"margarina", "hidrogenad", "interesterificad"},
        "alimentos ultraprocessados": {
            "biscoit", "bolach", "salsicha", "presunt", "mortadela",
            "salame", "refrigerante", "achocolatad", "sorvet",
        },
        "alimentos com adicao de acucar": {"acucar", "chocolate", "achocolatad", "doce"},
        "alimentos com adicao de mel": {"mel"},
        "alimentos com adicao de adocante": {"adocante", "adocad"},
    }

    vistos = set()
    for semana in cardapio.semanas:
        for dia in semana.dias:
            for refeicao in dia.refeicoes:
                for prato in refeicao.pratos:
                    for ingrediente in prato.ingredientes:
                        taco = ingredientes_taco.get(ingrediente.nome_taco)
                        texto = " ".join([
                            ingrediente.nome_taco,
                            prato.nome,
                            taco.category if taco else "",
                        ])
                        for proibicao in proibicoes:
                            chave = _texto_normalizado(proibicao)
                            termos = termos_por_proibicao.get(chave, set())
                            if not termos:
                                continue

                            eh_ultraprocessado_por_categoria = (
                                chave == "alimentos ultraprocessados"
                                and taco
                                and "industrializado" in _texto_normalizado(taco.category)
                            )
                            if chave == "alimentos com adicao de acucar":
                                tem_violacao = _contem_termo_adicao_acucar(
                                    texto,
                                    taco.category if taco else "",
                                    )
                            elif chave == "alimentos ricos em gorduras trans industrializadas":
                                texto_norm = _texto_normalizado(texto)
                                tem_violacao = _contem_token(texto, termos) or "gordura vegetal" in texto_norm or "gordura hidrogenada" in texto_norm
                            else:
                                tem_violacao = _contem_token(texto, termos)

                            if tem_violacao or eh_ultraprocessado_por_categoria:
                                identificador = (semana.numero, dia.dia_semana, ingrediente.nome_taco, proibicao)
                                if identificador in vistos:
                                    continue
                                vistos.add(identificador)
                                violacoes.append(InconformidadePNAESchema(
                                    escopo=f"semana {semana.numero} / {dia.dia_semana}",
                                    regra=f"Alimento proibido: {proibicao}",
                                    detalhe=f"Ingrediente '{ingrediente.nome_taco}' em '{prato.nome}'.",
                                    tipo="critico",
                                ))

    return violacoes


def validar_cardapio_pnae(
    cardapio: CardapioSchema,
    etapa: str,
    faixa_etaria: str,
    periodo: str,
    num_refeicoes: int,
    restricoes: list[str] | None = None,
) -> list[InconformidadePNAESchema]:
    """
    Executa auditoria abrangente das diretrizes do PNAE e coerência culinária:
    1. Coerência gastronômica e restrições alimentares declaradas.
    2. Alimentos proibidos.
    3. Frequências semanais e mensais de grupos alimentares controlados.
    4. Diversidade de alimentos e metas de FLV in natura.
    5. Adequação dos macronutrientes, micronutrientes e sódio.
    """
    try:
        from src.pipelines import selecionar_pipeline
        pipeline = selecionar_pipeline(
            etapa=etapa,
            faixa_etaria=faixa_etaria,
            periodo=periodo,
            num_refeicoes=num_refeicoes,
        )
        return pipeline.auditar(cardapio, restricoes)
    except Exception:
        pass

    regras = _resolver_regras_pnae(etapa, faixa_etaria, periodo, num_refeicoes)
    valores = regras["valores"]
    frequencias = regras["geral"]["frequencia_alimentos_por_periodo"]
    periodo_freq = regras["periodo_freq"]
    inconsistencias: list[InconformidadePNAESchema] = []
    ingredientes_taco: dict[str, Taco | None] = {}

    with Session(engine) as session:
        nomes_ingredientes = {
            ingrediente.nome_taco
            for semana in cardapio.semanas
            for dia in semana.dias
            for refeicao in dia.refeicoes
            for prato in refeicao.pratos
            for ingrediente in prato.ingredientes
        }
        ingredientes_taco = {
            nome: buscar_taco_por_nome(session, nome)
            for nome in nomes_ingredientes
        }

    # 1. Auditoria de coerência culinária e respeito a restrições alimentares
    inconsistencias.extend(validar_coerencia_culinaria(cardapio, etapa, restricoes, ingredientes_taco))

    # 2. Alimentos proibidos pelo PNAE
    inconsistencias.extend(_violacoes_proibicoes(cardapio, regras, ingredientes_taco))

    # Limites semanais de ocorrência para grupos alimentares controlados pela Resolução CD/FNDE
    limites_semanais = {
        "biscoito_pao_bolo": {
            "regra": "biscoito/bolacha/pao/bolo",
            "maximo": {
                "parcial_1_refeicao": 2,
                "parcial_2_ou_mais_refeicoes": 3,
                "integral": 7,
            }.get(periodo_freq),
        },
        "preparacao_doce": {
            "regra": "preparacoes doces",
            "maximo": 1 if periodo == "integral" else None,
        },
        "margarina_creme_vegetal": {
            "regra": "margarina ou creme vegetal",
            "maximo": 1 if periodo == "integral" else None,
        },
    }

    # Metas mínimas semanais do PNAE: diversidade de alimentos distintos e oferta de FLV in natura
    min_diversidade = {
        "parcial_1_refeicao": 10,
        "parcial_2_ou_mais_refeicoes": 14,
        "integral": 23,
    }.get(periodo_freq)
    min_flv_g = 520 if periodo == "integral" else 280
    min_frutas_dias = 4 if periodo == "integral" else 2
    min_legumes_verduras_dias = 5 if periodo == "integral" else 3

    # Contadores de frequência mensal para alimentos com restrição estrita por mês
    contagens_mes = {
        "produto_carneo": 0,
        "conserva": 0,
        "doce": 0,
        "liquido_lacteo_aditivado": 0,
        "preparacao_doce": 0,
        "margarina_creme_vegetal": 0,
    }

    for semana in cardapio.semanas:
        diversidade = set()
        flv_g = 0.0
        dias_com_fruta = set()
        dias_com_legume_verdura = set()
        contagens_semana = {chave: 0 for chave in limites_semanais}

        for dia in semana.dias:
            totais = {
                "energia_kcal": 0.0,
                "carboidratos_g": 0.0,
                "proteinas_g": 0.0,
                "lipidios_g": 0.0,
                "sodio_mg": 0.0,
                "vitamina_a_mcg": 0.0,
                "vitamina_c_mg": 0.0,
                "calcio_mg": 0.0,
                "ferro_mg": 0.0,
            }
            classes_do_dia = set()

            for refeicao in dia.refeicoes:
                for prato in refeicao.pratos:
                    for ingrediente in prato.ingredientes:
                        taco = ingredientes_taco.get(ingrediente.nome_taco)
                        categoria = taco.category if taco else ""
                        classes = (
                            _classificar_alimento(prato.nome, categoria)
                            | _classificar_alimento(ingrediente.nome_taco, categoria)
                        )
                        classes_do_dia.update(classes)
                        diversidade.add(_texto_normalizado(ingrediente.nome_taco))

                        if "fruta" in classes or "legume_verdura" in classes:
                            flv_g += ingrediente.quantidade_g
                        if "fruta" in classes:
                            dias_com_fruta.add(dia.dia_semana)
                        if "legume_verdura" in classes:
                            dias_com_legume_verdura.add(dia.dia_semana)

                        if not taco:
                            inconsistencias.append(InconformidadePNAESchema(
                                escopo=f"semana {semana.numero} / {dia.dia_semana}",
                                regra="Composicao TACO obrigatoria para validacao PNAE",
                                detalhe=f"Ingrediente '{ingrediente.nome_taco}' nao encontrado na base TACO.",
                                tipo="advertencia",
                            ))
                            continue

                        totais["energia_kcal"] += _somar_nutriente(taco.energy_kcal, ingrediente.quantidade_g)
                        totais["carboidratos_g"] += _somar_nutriente(taco.carbohydrates, ingrediente.quantidade_g)
                        totais["proteinas_g"] += _somar_nutriente(taco.proteins, ingrediente.quantidade_g)
                        totais["lipidios_g"] += _somar_nutriente(taco.lipids, ingrediente.quantidade_g)
                        totais["sodio_mg"] += _somar_nutriente(taco.sodium, ingrediente.quantidade_g)
                        totais["vitamina_a_mcg"] += _somar_nutriente(obter_vitamina_a_mcg_100g(taco, ingrediente.nome_taco), ingrediente.quantidade_g)
                        totais["vitamina_c_mg"] += _somar_nutriente(taco.c_vitamin, ingrediente.quantidade_g)
                        totais["calcio_mg"] += _somar_nutriente(taco.calcium, ingrediente.quantidade_g)
                        totais["ferro_mg"] += _somar_nutriente(taco.iron, ingrediente.quantidade_g)

            referencias = {
                "energia_kcal": (valores.get("energia_kcal"), valores.get("energia_kcal")),
                "carboidratos_g": (
                    valores["carboidratos_g"]["minimo"],
                    valores["carboidratos_g"]["maximo"],
                ),
                "proteinas_g": (
                    valores["proteinas_g"]["minimo"],
                    valores["proteinas_g"]["maximo"],
                ),
                "lipidios_g": (
                    valores["lipidios_g"]["minimo"],
                    valores["lipidios_g"]["maximo"],
                ),
            }
            for nutriente in ("vitamina_a_mcg", "vitamina_c_mg", "calcio_mg", "ferro_mg"):
                if nutriente in valores:
                    referencias[nutriente] = (valores[nutriente], None)

            for nutriente, (minimo, maximo) in referencias.items():
                if not _dentro_intervalo(totais[nutriente], minimo, maximo, tolerancia=0.1):
                    eh_critico = False
                    if minimo is not None and totais[nutriente] < minimo * 0.7:
                        eh_critico = True
                    elif maximo is not None and totais[nutriente] > maximo * 1.3:
                        eh_critico = True

                    inconsistencias.append(InconformidadePNAESchema(
                        escopo=f"semana {semana.numero} / {dia.dia_semana}",
                        regra=f"Valor diario de {nutriente}",
                        detalhe=(
                            f"Total calculado {totais[nutriente]:.1f}; "
                            f"referencia PNAE {minimo}"
                            + (f" a {maximo}" if maximo != minimo else "")
                            + "."
                        ),
                        tipo="critico" if eh_critico else "advertencia",
                    ))

            for classe in classes_do_dia & set(contagens_mes):
                contagens_mes[classe] += 1
            for classe in classes_do_dia & set(contagens_semana):
                contagens_semana[classe] += 1

            recomendacoes = regras["etapa_bloco"].get("recomendacoes_quantidade")
            if recomendacoes:
                max_sodio_texto = recomendacoes["maximo_sodio"][periodo_freq]
                match_sodio = re.search(r"\d+", max_sodio_texto)
                if match_sodio and totais["sodio_mg"] > int(match_sodio.group()) * 1.1:
                    inconsistencias.append(InconformidadePNAESchema(
                        escopo=f"semana {semana.numero} / {dia.dia_semana}",
                        regra="Limite diario de sodio",
                        detalhe=f"Total calculado {totais['sodio_mg']:.1f} mg; limite PNAE {max_sodio_texto}.",
                        tipo="advertencia",
                    ))

        for classe, limite in limites_semanais.items():
            maximo = limite["maximo"]
            if maximo is not None and contagens_semana[classe] > maximo:
                inconsistencias.append(InconformidadePNAESchema(
                    escopo=f"semana {semana.numero}",
                    regra=f"Frequencia semanal de {limite['regra']}",
                    detalhe=f"Encontrado {contagens_semana[classe]} vez(es); maximo PNAE {maximo}.",
                    tipo="advertencia",
                ))

        total_dias_semana = len(semana.dias)

        if min_diversidade is not None and total_dias_semana >= 4 and len(diversidade) < min_diversidade:
            inconsistencias.append(InconformidadePNAESchema(
                escopo=f"semana {semana.numero}",
                regra="Diversidade semanal de alimentos",
                detalhe=f"Encontrados {len(diversidade)} alimentos diferentes; minimo PNAE {min_diversidade}.",
                tipo="advertencia",
            ))
        if total_dias_semana >= 4 and flv_g < min_flv_g:
            regra = frequencias["frutas_legumes_e_verduras_in_natura"][periodo]["quantidade"]
            inconsistencias.append(InconformidadePNAESchema(
                escopo=f"semana {semana.numero}",
                regra="Quantidade semanal de frutas, legumes e verduras",
                detalhe=f"Total calculado {flv_g:.1f}g; regra PNAE {regra}.",
                tipo="advertencia",
            ))
        if total_dias_semana >= min_frutas_dias and len(dias_com_fruta) < min_frutas_dias:
            inconsistencias.append(InconformidadePNAESchema(
                escopo=f"semana {semana.numero}",
                regra="Oferta semanal de frutas",
                detalhe=f"Encontrada em {len(dias_com_fruta)} dia(s); minimo PNAE {min_frutas_dias}.",
                tipo="advertencia",
            ))
        if total_dias_semana >= min_legumes_verduras_dias and len(dias_com_legume_verdura) < min_legumes_verduras_dias:
            inconsistencias.append(InconformidadePNAESchema(
                escopo=f"semana {semana.numero}",
                regra="Oferta semanal de legumes e verduras",
                detalhe=f"Encontrada em {len(dias_com_legume_verdura)} dia(s); minimo PNAE {min_legumes_verduras_dias}.",
                tipo="advertencia",
            ))

    limites_mensais = {
        "produto_carneo": ("produtos carneos", 2),
        "conserva": ("alimentos em conserva", 1),
        "doce": ("doces", 1),
        "liquido_lacteo_aditivado": (
            "liquidos lacteos com aditivos ou adocados",
            2 if periodo == "integral" else 1,
        ),
        "preparacao_doce": (
            "preparacoes doces",
            None if periodo == "integral" else 2,
        ),
        "margarina_creme_vegetal": (
            "margarina ou creme vegetal",
            None if periodo == "integral" else 2,
        ),
    }
    for classe, (regra, maximo) in limites_mensais.items():
        if maximo is not None and contagens_mes[classe] > maximo:
            inconsistencias.append(InconformidadePNAESchema(
                escopo="cardapio mensal",
                regra=f"Frequencia mensal de {regra}",
                detalhe=f"Encontrado {contagens_mes[classe]} vez(es); maximo PNAE {maximo}.",
                tipo="advertencia",
            ))

    return inconsistencias


def avaliar_status_cardapio(inconformidades: list[InconformidadePNAESchema]) -> RelatorioValidacaoSchema:
    """Classifica o resultado da auditoria em Aprovado, Pendente de Revisão ou Reprovado."""
    total_criticos = sum(1 for i in inconformidades if getattr(i, "tipo", "critico") == "critico")
    total_advertencias = sum(1 for i in inconformidades if getattr(i, "tipo", "critico") != "critico")

    if total_criticos > 0:
        status = StatusValidacao.reprovado
        aprovado = False
        resumo = f"Reprovado: {total_criticos} inconsistência(s) crítica(s) identificada(s)."
    elif total_advertencias > 0:
        status = StatusValidacao.pendente_revisao
        aprovado = False
        resumo = f"Pendente de revisão nutricional: {total_advertencias} advertência(s) encontrada(s)."
    else:
        status = StatusValidacao.aprovado
        aprovado = True
        resumo = "Aprovado: Cardápio culinariamente coerente e em conformidade com as diretrizes do PNAE."

    return RelatorioValidacaoSchema(
        status=status,
        aprovado=aprovado,
        total_criticos=total_criticos,
        total_advertencias=total_advertencias,
        inconformidades=inconformidades,
        resumo=resumo,
    )
