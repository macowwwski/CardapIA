import os
import json
import time
import re
import unicodedata
from dotenv import load_dotenv
from enum import Enum
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session
from db.models import Taco, PerCapita
from src.prompt_templates import (
      montar_mensagem_conversao_json,
      montar_prompt_conversao_json,
      montar_prompt_geracao_cardapio,
  )


load_dotenv()
print("\n dotenv loaded \n")

engine = create_engine(os.getenv("DATABASE_URL"))


# ---------------------------------------------------------
# Import do Schema Pydantic do cardápio
# ---------------------------------------------------------
from src.schemas_pydantic import (
      CardapioSchema,
      InconformidadePNAESchema,
      ORDEM_TIPOS_REFEICAO,
      TIPOS_REFEICAO_PERMITIDOS,
      TipoRefeicao,
)


# ---------------------------------------------------------
# Tools de consulta à TACO
# ---------------------------------------------------------

@tool
def listar_opcoes_taco(categoria: str) -> list[str]:
    """
    Lista os alimentos disponíveis na TACO para UMA categoria por vez.
    Chame essa tool separadamente para cada categoria que precisar consultar.
    NÃO passe uma lista — passe apenas uma string com um nome de categoria.

    Exemplo correto: categoria="Frutas e derivados"
    Exemplo errado: categoria=["Frutas e derivados", "Cereais e derivados"]

    Categorias disponíveis:
    - Cereais e derivados
    - Verduras, hortaliças e derivados
    - Frutas e derivados
    - Carnes e derivados
    - Pescados e frutos do mar
    - Leite e derivados
    - Ovos e derivados
    - Leguminosas e derivados
    - Gorduras e óleos
    - Nozes e sementes
    """
    with Session(engine) as session:
        resultados = session.query(Taco.description).filter(
            Taco.category.ilike(f"%{categoria}%"),
            Taco.deleted_at == None
        ).all()

        if not resultados:
            return [f"Nenhum alimento encontrado para a categoria '{categoria}'"]

        return [r.description for r in resultados]
    

@tool
def buscar_cn_ingrediente_taco(nome_alimento: str) -> dict:
    """
    Retorna a composição nutricional de um alimento da TACO para 100g.
    Usar o nome exato retornado por listar_opcoes_taco.
    """

    with Session(engine) as session:
        resultado = session.query(Taco).filter(
            Taco.description == nome_alimento,
            Taco.deleted_at == None
        ).first()

        if not resultado:
            return {"erro": f"Alimento '{nome_alimento}' não encontrado. Use listar_opcoes_taco para ver os nomes exatos."}
        
        return {
            "nome": resultado.description,
            "categoria": resultado.category,
            "energia_kcal": resultado.energy_kcal,
            "proteinas_g": resultado.proteins,
            "carboidratos_g": resultado.carbohydrates,
            "lipidios_g": resultado.lipids,
            "sodio_mg": resultado.sodium,
            "ferro_mg": resultado.iron,
            "calcio_mg": resultado.calcium,
            "vitamina_a_mcg": resultado.retinol,
            "vitamina_c_mg": resultado.c_vitamin
        }


def _texto_normalizado(valor: object) -> str:
    texto = str(valor or "").strip().lower()
    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caractere) != "Mn"
    )


def _extrair_numero(valor: object, padrao: int) -> int:
    if isinstance(valor, int):
        return valor

    match = re.search(r"\d+", str(valor or ""))
    return int(match.group()) if match else padrao


def _tipo_refeicao_por_posicao(
    indice: int,
    num_refeicoes: int | None,
    turno: str | None = None,
) -> str:
    if not num_refeicoes or num_refeicoes >= len(ORDEM_TIPOS_REFEICAO):
        return ORDEM_TIPOS_REFEICAO[min(indice, len(ORDEM_TIPOS_REFEICAO) - 1)]

    if num_refeicoes == 1:
        ordem = [TipoRefeicao.almoco.value]
    elif num_refeicoes == 2:
        if _texto_normalizado(turno) == "vespertino":
            ordem = [TipoRefeicao.reforco.value, TipoRefeicao.jantar.value]
        else:
            ordem = [TipoRefeicao.almoco.value, TipoRefeicao.lanche_tarde.value]
    elif num_refeicoes == 3:
        ordem = [
            TipoRefeicao.desjejum.value,
            TipoRefeicao.almoco.value,
            TipoRefeicao.lanche_tarde.value,
        ]
    else:
        ordem = ORDEM_TIPOS_REFEICAO[:num_refeicoes]

    return ordem[min(indice, len(ordem) - 1)]


def _normalizar_tipo_refeicao(
    valor: object,
    indice: int,
    num_refeicoes: int | None,
    turno: str | None = None,
) -> str:
    if valor in TIPOS_REFEICAO_PERMITIDOS:
        return str(valor)

    texto = _texto_normalizado(valor)
    if "desjejum" in texto:
        return TipoRefeicao.desjejum.value
    if "almoco" in texto:
        return TipoRefeicao.almoco.value
    if "reforco" in texto:
        return TipoRefeicao.reforco.value
    if "lanche" in texto and ("tarde" in texto or "vespertino" in texto):
        return TipoRefeicao.lanche_tarde.value
    if "jantar" in texto or "ceia" in texto:
        return TipoRefeicao.jantar.value

    match = re.search(r"\d+", texto)
    if match:
        return _tipo_refeicao_por_posicao(
            int(match.group()) - 1,
            num_refeicoes,
            turno,
        )

    return _tipo_refeicao_por_posicao(indice, num_refeicoes, turno)


def corrigir_estrutura(
    dados: dict,
    mes_aplicacao: str | None = None,
    num_refeicoes: int | None = None,
    turno: str | None = None,
) -> dict:
    if "cardapio" in dados:
        dados = dados["cardapio"]

    if "mes" in dados:
        dados["mes_aplicacao"] = f"{dados.pop('mes')} de {dados.pop('ano', '')}"

    dados.setdefault("mes_aplicacao", mes_aplicacao or "")
    dados.setdefault("observacoes", "")
    dados.setdefault("semanas", [])

    if isinstance(dados["semanas"], dict):
        dados["semanas"] = list(dados["semanas"].values())

    if isinstance(dados["semanas"], list):
        for indice_semana, s in enumerate(dados["semanas"], start=1):
            if "semana" in s:
                s["numero"] = s.pop("semana")

            s["numero"] = _extrair_numero(s.get("numero"), indice_semana)
            s.setdefault("dias", [])

            if isinstance(s["dias"], dict):
                s["dias"] = list(s["dias"].values())

            for d in s.get("dias", []):
                if "dia" in d:
                    d["dia_semana"] = d.pop("dia")

                d.setdefault("dia_semana", "")
                d.setdefault("refeicoes", [])

                if isinstance(d["refeicoes"], dict):
                    d["refeicoes"] = list(d["refeicoes"].values())

                for indice_refeicao, r in enumerate(d.get("refeicoes", [])):
                    r.setdefault("horario", "")

                    if "itens" in r:
                        r["pratos"] = [{
                            "nome": ", ".join(r.pop("itens")),
                            "estado_preparacao": "preparado",
                            "ingredientes": []
                        }]

                    r["tipo"] = _normalizar_tipo_refeicao(
                        r.get("tipo"),
                        indice_refeicao,
                        num_refeicoes,
                        turno,
                    )
                    r.setdefault("pratos", [])

                    if isinstance(r["pratos"], dict):
                        r["pratos"] = list(r["pratos"].values())

                    for prato in r.get("pratos", []):
                        prato.setdefault("nome", "")
                        prato.setdefault("estado_preparacao", "preparado")
                        prato.setdefault("ingredientes", [])

                        if isinstance(prato["ingredientes"], dict):
                            prato["ingredientes"] = list(prato["ingredientes"].values())

                        for ingrediente in prato.get("ingredientes", []):
                            if "nome" in ingrediente and "nome_taco" not in ingrediente:
                                ingrediente["nome_taco"] = ingrediente.pop("nome")
                            if "alimento" in ingrediente and "nome_taco" not in ingrediente:
                                ingrediente["nome_taco"] = ingrediente.pop("alimento")
                            if "quantidade" in ingrediente and "quantidade_g" not in ingrediente:
                                ingrediente["quantidade_g"] = ingrediente.pop("quantidade")

                            ingrediente.setdefault("nome_taco", "")
                            ingrediente.setdefault("quantidade_g", 0.0)
                        
    return dados


def validar_cardapio(
    resultado: object,
    mes_aplicacao: str,
    num_refeicoes: int,
    turno: str | None = None,
) -> CardapioSchema:
    if isinstance(resultado, CardapioSchema):
        return resultado

    if isinstance(resultado, dict):
        dados = resultado
    elif hasattr(resultado, "model_dump"):
        dados = resultado.model_dump()
    else:
        raise ValueError("Formato inesperado da resposta estruturada")

    dados = corrigir_estrutura(
        dados,
        mes_aplicacao=mes_aplicacao,
        num_refeicoes=num_refeicoes,
        turno=turno,
    )
    return CardapioSchema.model_validate(dados)


def _tokens_normalizados(valor: object) -> set[str]:
    texto = re.sub(r"[^a-z0-9]+", " ", _texto_normalizado(valor))
    tokens = set()

    for token in texto.split():
        if token in {"de", "da", "do", "das", "dos", "e", "ou", "com", "sem"}:
            continue

        if len(token) > 4 and token[-1] in {"a", "o", "s"}:
            token = token[:-1]

        tokens.add(token)

    return tokens


def _contem_token(texto: object, termos: set[str]) -> bool:
    return bool(_tokens_normalizados(texto) & termos)


def _somar_nutriente(valor_100g: float | None, quantidade_g: float) -> float:
    if valor_100g is None:
        return 0.0
    return float(valor_100g) * float(quantidade_g or 0) / 100


def _dentro_intervalo(valor: float, minimo: float | None, maximo: float | None, tolerancia: float = 0.1) -> bool:
    if minimo is not None and valor < minimo * (1 - tolerancia):
        return False
    if maximo is not None and valor > maximo * (1 + tolerancia):
        return False
    return True


def _resolver_regras_pnae(etapa: str, faixa_etaria: str, periodo: str, num_refeicoes: int) -> dict:
    from prompt_builder import (
        REGRAS_PNAE,
        _mapear_e_obter_faixa_etaria,
        _mapear_percentual,
        _mapear_refeicoes_periodo,
        _obter_etapa,
        _obter_referencias_nutricionais,
    )

    etapa_bloco = _obter_etapa(etapa)
    percentual = _mapear_percentual(periodo, num_refeicoes)
    subfaixas = _obter_referencias_nutricionais(etapa_bloco, percentual)

    return {
        "geral": REGRAS_PNAE["geral"],
        "etapa_bloco": etapa_bloco,
        "percentual": percentual,
        "periodo_freq": _mapear_refeicoes_periodo(periodo, num_refeicoes),
        "valores": _mapear_e_obter_faixa_etaria(etapa, faixa_etaria, subfaixas),
    }


def _buscar_taco_por_nome(session: Session, nome_alimento: str) -> Taco | None:
    candidatos = _candidatos_per_capita(nome_alimento)

    for candidato in candidatos:
        registro = session.query(Taco).filter(
            Taco.description.ilike(candidato),
            Taco.deleted_at == None,
        ).first()
        if registro:
            return registro

    for candidato in candidatos:
        if len(candidato) < 4:
            continue

        registro = session.query(Taco).filter(
            Taco.description.ilike(f"%{candidato}%"),
            Taco.deleted_at == None,
        ).first()
        if registro:
            return registro

    tokens_candidatos = [_tokens_normalizados(candidato) for candidato in candidatos]
    todos_registros = session.query(Taco).filter(Taco.deleted_at == None).all()
    for registro in todos_registros:
        tokens_registro = _tokens_normalizados(registro.description)
        if any(tokens and tokens <= tokens_registro for tokens in tokens_candidatos):
            return registro

    return None


CATEGORIAS_ADOCAVEIS: set[str] = {
    "cereais e derivados",
    "frutas e derivados",
    "leite e derivados",
    "acucares e produtos de confeitaria",
}

TOKENS_DOCE_POR_CATEGORIA: set[str] = {
    "doce",
    "sobremesa",
    "adocad",
    "adocado",
    "adocada",
    "sorvet",
    "chocolate",
    "acucar",
    "mel",
    "geleia",
    "goiabada",
}


def _categoria_adocavel(categoria: object) -> bool:
    tokens_categoria = _tokens_normalizados(categoria)
    if not tokens_categoria:
        return False

    return any(
        _tokens_normalizados(categoria_ref) <= tokens_categoria
        for categoria_ref in CATEGORIAS_ADOCAVEIS
    )


def _tem_token_doce_por_categoria(tokens: set[str], categoria: object) -> bool:
    return bool(tokens & TOKENS_DOCE_POR_CATEGORIA) and _categoria_adocavel(categoria)


def _classificar_alimento(nome: str, categoria: str = "") -> set[str]:
    texto = f"{nome} {categoria}"
    tokens = _tokens_normalizados(texto)
    classes = set()

    if tokens & {"frut", "fruta"}:
        classes.add("fruta")
    if tokens & {"verdura", "hortalica", "hortalic", "legume", "leguminosa"}:
        classes.add("legume_verdura")
    if tokens & {"biscoit", "bolach", "pao", "bolo", "torrad"}:
        classes.add("biscoito_pao_bolo")
    if _tem_token_doce_por_categoria(tokens, categoria):
        classes.add("doce")
    if tokens & {"margarina"} or "creme vegetal" in _texto_normalizado(texto):
        classes.add("margarina_creme_vegetal")
    if tokens & {"conserva", "enlatad", "enlatado"}:
        classes.add("conserva")
    if tokens & {"presunt", "linguica", "salsicha", "salame", "mortadela", "hamburguer"}:
        classes.add("produto_carneo")
    if tokens & {"achocolatad", "adocad", "iogurte"} and tokens & {"leite", "lacteo", "lacteos"}:
        classes.add("liquido_lacteo_aditivado")
    if tokens & {"pudim", "canjica", "curau"} and _categoria_adocavel(categoria):
        classes.add("preparacao_doce")
    elif _tem_token_doce_por_categoria(tokens, categoria):
        classes.add("preparacao_doce")

    return classes


def _contem_termo_adicao_acucar(texto: object, categoria: object) -> bool:
    tokens = _tokens_normalizados(texto)
    return bool(
        tokens
        & {
            "acucar",
            "achocolatad",
            "chocolate",
            "doce",
            "adocad",
            "adocado",
            "adocada",
        }
    ) and _categoria_adocavel(categoria)


def _violacoes_proibicoes(
    cardapio: CardapioSchema,
    regras: dict,
    ingredientes_taco: dict[str, Taco | None],
) -> list[InconformidadePNAESchema]:
    proibicoes = (
        regras["geral"].get("alimentos_proibidos", [])
        + regras["etapa_bloco"].get("alimentos_proibidos", [])
    )
    violacoes = []

    termos_por_proibicao = {
        "alimentos ricos em gorduras trans industrializadas": {"margarina", "hidrogenad", "vegetal"},
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
                                ))

    return violacoes


def validar_cardapio_pnae(
    cardapio: CardapioSchema,
    etapa: str,
    faixa_etaria: str,
    periodo: str,
    num_refeicoes: int,
) -> list[InconformidadePNAESchema]:
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
            nome: _buscar_taco_por_nome(session, nome)
            for nome in nomes_ingredientes
        }

    inconsistencias.extend(_violacoes_proibicoes(cardapio, regras, ingredientes_taco))

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

    min_diversidade = {
        "parcial_1_refeicao": 10,
        "parcial_2_ou_mais_refeicoes": 14,
        "integral": 23,
    }.get(periodo_freq)
    min_flv_g = 520 if periodo == "integral" else 280
    min_frutas_dias = 4 if periodo == "integral" else 2
    min_legumes_verduras_dias = 5 if periodo == "integral" else 3

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
                                detalhe=f"Ingrediente '{ingrediente.nome_taco}' nao encontrado na TACO.",
                            ))
                            continue

                        totais["energia_kcal"] += _somar_nutriente(taco.energy_kcal, ingrediente.quantidade_g)
                        totais["carboidratos_g"] += _somar_nutriente(taco.carbohydrates, ingrediente.quantidade_g)
                        totais["proteinas_g"] += _somar_nutriente(taco.proteins, ingrediente.quantidade_g)
                        totais["lipidios_g"] += _somar_nutriente(taco.lipids, ingrediente.quantidade_g)
                        totais["sodio_mg"] += _somar_nutriente(taco.sodium, ingrediente.quantidade_g)
                        totais["vitamina_a_mcg"] += _somar_nutriente(taco.retinol, ingrediente.quantidade_g)
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
                if not _dentro_intervalo(totais[nutriente], minimo, maximo):
                    inconsistencias.append(InconformidadePNAESchema(
                        escopo=f"semana {semana.numero} / {dia.dia_semana}",
                        regra=f"Valor diario de {nutriente}",
                        detalhe=(
                            f"Total calculado {totais[nutriente]:.1f}; "
                            f"referencia PNAE {minimo}"
                            + (f" a {maximo}" if maximo != minimo else "")
                            + "."
                        ),
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
                    ))

        for classe, limite in limites_semanais.items():
            maximo = limite["maximo"]
            if maximo is not None and contagens_semana[classe] > maximo:
                inconsistencias.append(InconformidadePNAESchema(
                    escopo=f"semana {semana.numero}",
                    regra=f"Frequencia semanal de {limite['regra']}",
                    detalhe=f"Encontrado {contagens_semana[classe]} vez(es); maximo PNAE {maximo}.",
                ))

        if min_diversidade is not None and len(diversidade) < min_diversidade:
            inconsistencias.append(InconformidadePNAESchema(
                escopo=f"semana {semana.numero}",
                regra="Diversidade semanal de alimentos",
                detalhe=f"Encontrados {len(diversidade)} alimentos diferentes; minimo PNAE {min_diversidade}.",
            ))
        if flv_g < min_flv_g:
            regra = frequencias["frutas_legumes_e_verduras_in_natura"][periodo]["quantidade"]
            inconsistencias.append(InconformidadePNAESchema(
                escopo=f"semana {semana.numero}",
                regra="Quantidade semanal de frutas, legumes e verduras",
                detalhe=f"Total calculado {flv_g:.1f}g; regra PNAE {regra}.",
            ))
        if len(dias_com_fruta) < min_frutas_dias:
            inconsistencias.append(InconformidadePNAESchema(
                escopo=f"semana {semana.numero}",
                regra="Oferta semanal de frutas",
                detalhe=f"Encontrada em {len(dias_com_fruta)} dia(s); minimo PNAE {min_frutas_dias}.",
            ))
        if len(dias_com_legume_verdura) < min_legumes_verduras_dias:
            inconsistencias.append(InconformidadePNAESchema(
                escopo=f"semana {semana.numero}",
                regra="Oferta semanal de legumes e verduras",
                detalhe=f"Encontrada em {len(dias_com_legume_verdura)} dia(s); minimo PNAE {min_legumes_verduras_dias}.",
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
            ))

    return inconsistencias


def _selecionar_registro_per_capita(registros: list[PerCapita], campo: str) -> PerCapita | None:
    for registro in registros:
        if getattr(registro, campo) is not None:
            return registro

    return registros[0] if registros else None


def _candidatos_per_capita(nome_alimento: str) -> list[str]:
    aliases = {
        "mandioquinha": "Batata, baroa",
        "mandioquinha salsa": "Batata, baroa",
        "batata baroa": "Batata, baroa",
    }

    candidatos = [
        candidato.strip()
        for candidato in re.split(r"\s*/\s*", nome_alimento)
        if candidato.strip()
    ]
    if nome_alimento not in candidatos:
        candidatos.insert(0, nome_alimento)

    for candidato in list(candidatos):
        alias = aliases.get(_texto_normalizado(candidato))
        if alias and alias not in candidatos:
            candidatos.append(alias)

    return candidatos


def obter_per_capita(nome_alimento: str, etapa: str) -> float:
    """
    Retorna o per capita em gramas para um alimento e etapa escolar.
    Fonte: Manual de Per Capita PNAE / Resolucao FNDE 06/2020.
    """
    mapeamento_etapa = {
        "creche": "per_capita_creche",
        "pre-escola": "per_capita_pre_escola",
        "pre escola": "per_capita_pre_escola",
        "ensino fundamental": "per_capita_fund",
        "fundamental": "per_capita_fund",
        "ensino medio": "per_capita_medio_eja",
        "medio": "per_capita_medio_eja",
        "eja": "per_capita_medio_eja",
    }

    campo_per_capita = mapeamento_etapa.get(_texto_normalizado(etapa))
    if not campo_per_capita:
        raise ValueError(f"Etapa escolar invalida para per capita: {etapa}")

    candidatos = _candidatos_per_capita(nome_alimento)

    with Session(engine) as session:
        query_base = session.query(PerCapita).outerjoin(
            Taco,
            PerCapita.taco_id == Taco.id,
        ).order_by(PerCapita.nome_alimento)
        registro = None

        for candidato in candidatos:
            registros = query_base.filter(
                or_(
                    PerCapita.nome_alimento.ilike(candidato),
                    Taco.description.ilike(candidato),
                )
            ).all()
            registro = _selecionar_registro_per_capita(registros, campo_per_capita)
            if registro:
                break

        if not registro:
            for candidato in candidatos:
                if len(candidato) < 4:
                    continue

                padrao = f"%{candidato}%"
                registros = query_base.filter(
                    or_(
                        PerCapita.nome_alimento.ilike(padrao),
                        Taco.description.ilike(padrao),
                    )
                ).all()
                registro = _selecionar_registro_per_capita(registros, campo_per_capita)
                if registro:
                    break

        if not registro:
            todos_registros = query_base.all()
            for candidato in candidatos:
                tokens_candidato = _tokens_normalizados(candidato)
                if not tokens_candidato:
                    continue

                registros = [
                    registro
                    for registro in todos_registros
                    if tokens_candidato <= _tokens_normalizados(registro.nome_alimento)
                    or (
                        registro.taco
                        and tokens_candidato <= _tokens_normalizados(registro.taco.description)
                    )
                ]
                registro = _selecionar_registro_per_capita(registros, campo_per_capita)
                if registro:
                    break

        if not registro:
            raise ValueError(f"Per capita nao encontrado para alimento: {nome_alimento}")

        valor = getattr(registro, campo_per_capita)
        if valor is None:
            raise ValueError(
                f"Alimento restrito ou sem per capita para a etapa '{etapa}': {nome_alimento}"
            )

        return float(valor)


def aplicar_per_capita(cardapio: CardapioSchema, etapa: str) -> CardapioSchema:
    avisos = []
    avisos_vistos = set()

    for semana in cardapio.semanas:
        for dia in semana.dias:
            for refeicao in dia.refeicoes:
                for prato in refeicao.pratos:
                    for ingrediente in prato.ingredientes:
                        try:
                            ingrediente.quantidade_g = obter_per_capita(
                                ingrediente.nome_taco,
                                etapa,
                            )
                        except ValueError as erro:
                            aviso = str(erro)
                            if aviso not in avisos_vistos:
                                avisos.append(aviso)
                                avisos_vistos.add(aviso)

    if avisos:
        observacao = "Per capita nao aplicado para alguns ingredientes: " + "; ".join(avisos)
        cardapio.observacoes = (
            f"{cardapio.observacoes}\n{observacao}".strip()
            if cardapio.observacoes
            else observacao
        )

    return cardapio

# ---------------------------------------------------------
# Função principal
# ---------------------------------------------------------

def gerar_cardapio(
    etapa: str,
    faixa_etaria: str,
    periodo: str,
    num_refeicoes: int,
    mes_aplicacao: str,
    turno: str = "matutino",
    restricoes: list[str] | None = None,
    validar_pnae: bool = False,
) -> CardapioSchema:

    from prompt_builder import construir_contexto

    contexto = construir_contexto(
        etapa=etapa,
        faixa_etaria=faixa_etaria,
        periodo=periodo,
        num_refeicoes=num_refeicoes,
        turno=turno,
        restricoes=restricoes,
        num_semanas=1
    )

    # - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # ETAPA 1 — Geração com Tools em texto livre
    # - - - - - - - - - - - - - - - - - - - - - - - - - - -

    llm_tools = ChatOllama(
        model="gemma4:31b-cloud",
        temperature=0.3
    ).bind_tools([listar_opcoes_taco, buscar_cn_ingrediente_taco])

    system_prompt_1 = montar_prompt_geracao_cardapio(contexto)

    mensagens = [
        SystemMessage(content=system_prompt_1),
        HumanMessage(content=f"Gere o cardápio de {num_refeicoes} refeições diárias para {mes_aplicacao}.")
    ]

    while True:
        resposta = llm_tools.invoke(mensagens)
        mensagens.append(resposta)

        if not getattr(resposta, "tool_calls", None):
            texto_cardapio = resposta.content
            break

        for tool_call in resposta.tool_calls:
            if tool_call["name"] == "listar_opcoes_taco":
                resultado = listar_opcoes_taco.invoke(tool_call["args"])

            elif tool_call["name"] == "buscar_cn_ingrediente_taco":
                resultado = buscar_cn_ingrediente_taco.invoke(tool_call["args"])

            else:
                resultado = {"erro": "Tool desconhecida"}

            mensagens.append(
                ToolMessage(
                    content=json.dumps(resultado, ensure_ascii=False),
                    tool_call_id=tool_call["id"]
                )
            )

    # - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # ETAPA 2 — Conversão para JSON estruturado
    # - - - - - - - - - - - - - - - - - - - - - - - - - - -

    llm_structured = ChatOllama(
        model="gemma4:31b-cloud",
        temperature=0
    ).with_structured_output(CardapioSchema)

    schema_json = json.dumps(CardapioSchema.model_json_schema(), ensure_ascii=False, indent=2)

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

    cardapio = aplicar_per_capita(cardapio, etapa)

    if validar_pnae:
        inconformidades = validar_cardapio_pnae(
            cardapio=cardapio,
            etapa=etapa,
            faixa_etaria=faixa_etaria,
            periodo=periodo,
            num_refeicoes=num_refeicoes,
        )
        if inconformidades:
            detalhes = "\n".join(
                f"- {item.escopo}: {item.regra}. {item.detalhe}"
                for item in inconformidades
            )
            raise ValueError(
                "Cardapio gerado nao atende as regras do PNAE:\n"
                f"{detalhes}"
            )

    return cardapio
