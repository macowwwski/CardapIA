"""
Normalização e sanitização estrutural das respostas da LLM.

Garante que o JSON gerado seja corrigido e higienizado antes da validação estrita
contra o CardapioSchema do Pydantic.
"""
import re
from src.schemas_pydantic import (
    CardapioSchema,
    ORDEM_TIPOS_REFEICAO,
    TIPOS_REFEICAO_PERMITIDOS,
    TipoRefeicao,
)
from src.nutrition.classifier import _texto_normalizado


def _extrair_numero(valor: object, padrao: int) -> int:
    """Extrai dígitos inteiros de um valor textual ou numérico."""
    if isinstance(valor, int):
        return valor

    match = re.search(r"\d+", str(valor or ""))
    return int(match.group()) if match else padrao


def _tipo_refeicao_por_posicao(
    indice: int,
    num_refeicoes: int | None,
    turno: str | None = None,
) -> str:
    """Determina o tipo de refeição com base na posição ordinal e no turno escolar."""
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
    """Converte termos livres ou inconsistentes para um enum TipoRefeicao válido."""
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
    """
    Higieniza a estrutura do dicionário recebido da LLM para conformidade com CardapioSchema.
    Trata campos aninhados, enums, listas e dicionários com numeração ordinal.
    """
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

                        if not prato.get("ingredientes") and prato.get("nome"):
                            prato["ingredientes"] = [{
                                "nome_taco": prato["nome"],
                                "quantidade_g": 0.0
                            }]

    return dados


def validar_cardapio(
    resultado: object,
    mes_aplicacao: str,
    num_refeicoes: int,
    turno: str | None = None,
) -> CardapioSchema:
    """
    Converte e valida a resposta bruta da LLM contra o CardapioSchema.
    Aplica a higienização estrutural de corrigir_estrutura antes da validação.
    """
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
