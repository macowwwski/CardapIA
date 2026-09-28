"""
Servidor HTTP FastAPI do CardapIA.

Atua como microsserviço de geração de cardápios escolares:
- Recebe os parâmetros de planejamento do backend principal (CooperaAgro-Back).
- Invoca o serviço de Inteligência Artificial com regras do PNAE.
- Consulta e calcula os valores nutricionais de cada ingrediente na Tabela TACO.
- Formata a resposta com compatibilidade para o frontend/backend e persiste histórico no banco.
"""
import os
import sys
import uuid
import math
import re
import unicodedata
from pathlib import Path
from typing import List, Optional, Union
from datetime import datetime, time

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
for p in [str(PROJECT_ROOT), str(SRC_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict, AliasChoices
from sqlalchemy.orm import Session
from db.database import engine
from db.models import Cardapio, Dia, EtapaEscolar, Ingrediente, Prato, Refeicao, Semana, Taco
from src.ai_service import gerar_cardapio

app = FastAPI(
    title="CardapIA - Serviço de Inteligência Artificial",
    description="API simplificada para geração de cardápios escolares com IA e TACO",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MESES_MAPA = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
}


class GerarCardapioRequest(BaseModel):
    """Esquema de validação dos dados de entrada para geração de cardápio escolar."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    etapa: str = Field(default="creche", validation_alias=AliasChoices("etapa", "educationStage"))
    faixa_etaria: str = Field(default="1_3", validation_alias=AliasChoices("faixa_etaria", "ageRange", "faixaEtaria"))
    periodo: str = Field(default="parcial", validation_alias=AliasChoices("periodo", "period"))
    turno: Union[str, List[str]] = Field(default="matutino", validation_alias=AliasChoices("turno", "shift"))
    num_refeicoes: int = Field(default=2, validation_alias=AliasChoices("num_refeicoes", "mealsPerDay"))
    total_dias: Optional[int] = Field(default=None, validation_alias=AliasChoices("total_dias", "totalDias"))
    mes_aplicacao: Optional[Union[int, str]] = None
    meses_aplicacao: Optional[List[Union[int, str]]] = Field(default_factory=list)
    meses_numeros: Optional[List[int]] = Field(default_factory=list)
    dias_letivos: Optional[List[str]] = Field(default_factory=list, validation_alias=AliasChoices("dias_letivos", "schoolDays", "diasLetivos", "school_days"))
    restricoes: Optional[List[str]] = Field(default_factory=list)
    validar_pnae: Optional[bool] = False


ALIASES_TACO = {
    "arroz": "Arroz, tipo 1, cozido",
    "arroz branco": "Arroz, tipo 1, cozido",
    "arroz integral": "Arroz, integral, cozido",
    "feijao": "Feijão, carioca, cozido",
    "feijao carioca": "Feijão, carioca, cozido",
    "feijao preto": "Feijão, preto, cozido",
    "frango": "Frango, peito, sem pele, cozido",
    "peito de frango": "Frango, peito, sem pele, cozido",
    "carne": "Carne, bovina, moída, cozida",
    "carne moida": "Carne, bovina, moída, cozida",
    "carne bovina": "Carne, bovina, moída, cozida",
    "peixe": "Pescada, filé, cru",
    "leite": "Leite, de vaca, integral",
    "leite integral": "Leite, de vaca, integral",
    "banana": "Banana, prata, crua",
    "banana prata": "Banana, prata, crua",
    "maca": "Maçã, fuji, com casca, crua",
    "laranja": "Laranja, pera, crua",
    "mamao": "Mamão, papaia, cru",
    "cenoura": "Cenoura, cozida",
    "alface": "Alface, americana, crua",
    "tomate": "Tomate, com semente, cru",
    "ovo": "Ovo, de galinha, inteiro, cozido/10minutos",
    "ovo cozido": "Ovo, de galinha, inteiro, cozido/10minutos",
    "batata": "Batata, inglesa, cozida",
    "batata doce": "Batata, doce, cozida",
    "macarrao": "Macarrão, trigo, cru",
    "mandioca": "Mandioca, cozida",
    "abobora": "Abóbora, cabotian, cozida",
    "chuchu": "Chuchu, cozido",
    "beterraba": "Beterraba, cozida",
    "iogurte": "Iogurte, natural",
    "pao": "Pão, francês",
    "pao frances": "Pão, francês",
    "oleo": "Óleo, de soja",
    "azeite": "Azeite, de oliva",
}

_TACO_CACHE = None

def _norm_str(text: str) -> str:
    """Normaliza texto removendo acentos e convertendo para minúsculas."""
    t = unicodedata.normalize("NFD", str(text or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")

def _obter_taco_cache(session: Session):
    """Carrega e mantém em memória o cache de itens da Tabela TACO."""
    global _TACO_CACHE
    if _TACO_CACHE is None:
        tacos = session.query(Taco).filter(Taco.deleted_at == None).all()
        _TACO_CACHE = []
        for t in tacos:
            dn = _norm_str(t.description)
            base_name = dn.split(",")[0].strip()
            words = set(re.findall(r"\b[a-z0-9]+\b", dn))
            _TACO_CACHE.append({
                "taco": t,
                "norm": dn,
                "base": base_name,
                "words": words
            })
    return _TACO_CACHE

def _encontrar_taco(session: Session, nome: str) -> Optional[Taco]:
    """Busca o melhor registro correspondente na TACO por aliases e similaridade."""
    if not nome:
        return None
    cache = _obter_taco_cache(session)
    q = _norm_str(nome).strip()
    if not q:
        return None

    if q in ALIASES_TACO:
        target = _norm_str(ALIASES_TACO[q])
        for it in cache:
            if it["norm"] == target:
                return it["taco"]

    for it in cache:
        if q == it["norm"]:
            return it["taco"]

    q_words = [w for w in re.findall(r"\b[a-z0-9]+\b", q) if w not in {"de", "da", "do", "e", "com", "sem", "ao", "a", "o", "em"}]
    if not q_words:
        return None
    first = q_words[0]

    if first in ALIASES_TACO:
        target = _norm_str(ALIASES_TACO[first])
        for it in cache:
            if it["norm"] == target:
                return it["taco"]

    candidates = []
    for it in cache:
        if it["base"].startswith(first) or first in it["words"]:
            overlap = len(set(q_words) & it["words"])
            bonus = 2 if it["base"] == first or it["base"].startswith(first) else 0
            state_bonus = 0.5 if "cozid" in it["words"] or "prepar" in it["words"] else 0
            candidates.append((overlap + bonus + state_bonus, it["taco"]))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    return session.query(Taco).filter(Taco.description.ilike(f"%{first}%"), Taco.deleted_at == None).first()

def _buscar_nutrientes_taco(session: Session, nome_taco: str, qtd_g: float) -> dict:
    """Calcula os valores nutricionais escalados pela quantidade em gramas (per capita)."""
    fator = (qtd_g or 0) / 100.0
    taco = _encontrar_taco(session, nome_taco)
    if not taco:
        return {
            "energiaKcal": 0.0, "carboidratosG": 0.0, "proteinasG": 0.0,
            "lipidiosG": 0.0, "sodioMg": 0.0, "ferroMg": 0.0,
            "calcioMg": 0.0, "vitaminaAMcg": 0.0, "vitaminaCMg": 0.0
        }
    return {
        "energiaKcal": round(float(taco.energy_kcal or 0) * fator, 1),
        "carboidratosG": round(float(taco.carbohydrates or 0) * fator, 1),
        "proteinasG": round(float(taco.proteins or 0) * fator, 1),
        "lipidiosG": round(float(taco.lipids or 0) * fator, 1),
        "sodioMg": round(float(taco.sodium or 0) * fator, 1),
        "ferroMg": round(float(taco.iron or 0) * fator, 2),
        "calcioMg": round(float(taco.calcium or 0) * fator, 1),
        "vitaminaAMcg": round(float(taco.retinol or 0) * fator, 1),
        "vitaminaCMg": round(float(taco.c_vitamin or 0) * fator, 1),
    }


def salvar_cardapio_db(
    cardapio_schema,
    etapa: str,
    faixa_etaria: str,
    periodo: str,
    num_refeicoes: int,
    mes_aplicacao: str,
    observacoes: Optional[str] = None
) -> Optional[str]:
    """Persiste a estrutura do cardápio gerado (semanas, dias, refeições, pratos) no PostgreSQL."""
    try:
        with Session(engine) as session:
            etapa_obj = session.query(EtapaEscolar).filter(
                EtapaEscolar.etapa == etapa,
                EtapaEscolar.faixa_etaria == faixa_etaria
            ).first()
            if not etapa_obj:
                etapa_obj = EtapaEscolar(id=uuid.uuid4(), etapa=etapa, faixa_etaria=faixa_etaria)
                session.add(etapa_obj)
                session.flush()

            cardapio_id = uuid.uuid4()
            num_semanas = len(cardapio_schema.semanas)
            cardapio_db = Cardapio(
                id=cardapio_id,
                etapa_escolar_id=etapa_obj.id,
                periodo=periodo,
                mes_aplicacao=mes_aplicacao,
                num_refeicoes=num_refeicoes,
                num_semanas=num_semanas,
                data_geracao=datetime.now(),
                aprovado=False,
                observacoes=observacoes or getattr(cardapio_schema, "observacoes", None)
            )
            session.add(cardapio_db)

            for semana in cardapio_schema.semanas:
                semana_db = Semana(id=uuid.uuid4(), cardapio_id=cardapio_id, numero=semana.numero)
                session.add(semana_db)
                session.flush()

                for dia in semana.dias:
                    dia_db = Dia(id=uuid.uuid4(), semana_id=semana_db.id, dia_semana=dia.dia_semana)
                    session.add(dia_db)
                    session.flush()

                    for refeicao in dia.refeicoes:
                        tipo_valor = str(refeicao.tipo.value if hasattr(refeicao.tipo, "value") else refeicao.tipo)
                        refeicao_db = Refeicao(id=uuid.uuid4(), dia_id=dia_db.id, tipo=tipo_valor, horario=None)
                        session.add(refeicao_db)
                        session.flush()

                        for prato in refeicao.pratos:
                            prato_db = Prato(id=uuid.uuid4(), refeicao_id=refeicao_db.id, nome=prato.nome, estado_preparacao=getattr(prato, "estado_preparacao", None))
                            session.add(prato_db)
                            session.flush()

                            for ingrediente in prato.ingredientes:
                                taco = session.query(Taco).filter(Taco.description.ilike(f"%{ingrediente.nome_taco}%"), Taco.deleted_at == None).first()
                                if taco:
                                    ing_db = Ingrediente(id=uuid.uuid4(), prato_id=prato_db.id, taco_id=taco.id, quantidade_g=ingrediente.quantidade_g)
                                    session.add(ing_db)

            session.commit()
            return str(cardapio_id)
    except Exception as e:
        print(f"Aviso: Não foi possível persistir no PostgreSQL: {e}")
        return None


@app.get("/health")
def health_check():
    """Verifica se a API do CardapIA está ativa e respondendo."""
    return {"status": "ok", "service": "CardapIA"}


@app.post("/api/cardapios/generate")
def api_gerar_cardapio(payload: GerarCardapioRequest):
    """
    Endpoint principal para geração de cardápio escolar:
    1. Trata parâmetros de data, turno e semanas necessárias.
    2. Aciona o LLM via IA Service para estruturar o cardápio.
    3. Consulta a TACO para enriquecer cada alimento com dados nutricionais.
    4. Gera descrições das refeições e formata a resposta para o CooperaAgro-Back.
    """
    try:
        ano_atual = datetime.now().year
        lista_meses_str = []
        meses_para_processar = payload.meses_numeros or payload.meses_aplicacao
        if meses_para_processar:
            for item in meses_para_processar:
                if isinstance(item, int) and 1 <= item <= 12:
                    lista_meses_str.append(f"{MESES_MAPA.get(item, 'mês')} de {ano_atual}")
                elif str(item).isdigit() and 1 <= int(item) <= 12:
                    lista_meses_str.append(f"{MESES_MAPA.get(int(item), 'mês')} de {ano_atual}")
                else:
                    lista_meses_str.append(str(item))
        elif payload.mes_aplicacao is not None:
            val = payload.mes_aplicacao
            if isinstance(val, int) and 1 <= val <= 12:
                lista_meses_str.append(f"{MESES_MAPA.get(val, 'mês')} de {ano_atual}")
            elif str(val).isdigit() and 1 <= int(val) <= 12:
                lista_meses_str.append(f"{MESES_MAPA.get(int(val), 'mês')} de {ano_atual}")
            else:
                lista_meses_str.append(str(val))

        mes_final = ", ".join(lista_meses_str) if lista_meses_str else f"maio de {ano_atual}"

        if isinstance(payload.turno, list):
            turnos_lista = [str(t.value if hasattr(t, "value") else t).strip() for t in payload.turno if str(t).strip()]
        else:
            turnos_lista = [t.strip() for t in str(payload.turno.value if hasattr(payload.turno, "value") else payload.turno).split(",") if t.strip()]
        turno_str = turnos_lista[0] if turnos_lista else "matutino"

        num_semanas = 1
        if payload.dias_letivos and len(payload.dias_letivos) > 0:
            num_semanas = max(1, math.ceil(len(payload.dias_letivos) / 5))
        elif payload.total_dias and payload.total_dias > 0:
            num_semanas = max(1, math.ceil(payload.total_dias / 5))

        cardapio = gerar_cardapio(
            etapa=str(payload.etapa),
            faixa_etaria=str(payload.faixa_etaria),
            periodo=str(payload.periodo),
            num_refeicoes=payload.num_refeicoes,
            mes_aplicacao=mes_final,
            turno=turno_str,
            restricoes=payload.restricoes or [],
            num_semanas=num_semanas,
            validar_pnae=bool(payload.validar_pnae)
        )

        # Formata semanas para o formato esperado pelo frontend / backend
        semanas_formatadas = []
        dias_letivos_flat = []
        contador_dias = 0

        with Session(engine) as session:
            for semana in cardapio.semanas:
                dias_da_semana = []
                for dia in semana.dias:
                    refeicoes_formatadas = []
                    for refeicao in dia.refeicoes:
                        alimentos_formatados = []
                        nomes_pratos = []
                        totais = {
                            "energiaKcal": 0.0, "carboidratosG": 0.0, "proteinasG": 0.0,
                            "lipidiosG": 0.0, "sodioMg": 0.0, "ferroMg": 0.0,
                            "calcioMg": 0.0, "vitaminaAMcg": 0.0, "vitaminaCMg": 0.0
                        }

                        for prato in refeicao.pratos:
                            if prato.nome:
                                nomes_pratos.append(prato.nome.strip())
                            if prato.ingredientes:
                                for ing in prato.ingredientes:
                                    qtd = ing.quantidade_g if ing.quantidade_g and ing.quantidade_g > 0 else 50.0
                                    nutri = _buscar_nutrientes_taco(session, ing.nome_taco or prato.nome, qtd)
                                    for k in totais:
                                        totais[k] = round(totais[k] + nutri[k], 2)
                                    alimentos_formatados.append({
                                        "nome": ing.nome_taco or prato.nome,
                                        "quantidadeG": qtd,
                                        "nutrientes": nutri,
                                        "totaisNutricionais": nutri
                                    })
                            else:
                                qtd = 50.0
                                nutri = _buscar_nutrientes_taco(session, prato.nome, qtd)
                                for k in totais:
                                    totais[k] = round(totais[k] + nutri[k], 2)
                                alimentos_formatados.append({
                                    "nome": prato.nome,
                                    "quantidadeG": qtd,
                                    "nutrientes": nutri,
                                    "totaisNutricionais": nutri
                                })

                        tipo_str = str(refeicao.tipo.value if hasattr(refeicao.tipo, "value") else refeicao.tipo)
                        # Gera a descricao unindo os nomes de todos os alimentos por virgula
                        # dict.fromkeys preserva a ordem e remove nomes duplicados
                        nomes_alimentos = [a["nome"].strip() for a in alimentos_formatados if a.get("nome")]
                        descricao = ", ".join(dict.fromkeys(nomes_alimentos)) if nomes_alimentos else (", ".join(nomes_pratos) if nomes_pratos else tipo_str.capitalize())

                        # categoria e nutrientes sao aliases de tipo e totaisNutricionais
                        # para compatibilidade com o contrato do CooperaAgro-Back
                        refeicao_fmt = {
                            "id": str(uuid.uuid4()),
                            "tipo": tipo_str,
                            "categoria": tipo_str,
                            "descricao": descricao,
                            "totaisNutricionais": totais,
                            "nutrientes": totais,
                            "alimentos": alimentos_formatados
                        }
                        refeicoes_formatadas.append(refeicao_fmt)

                    data_label = payload.dias_letivos[contador_dias] if payload.dias_letivos and contador_dias < len(payload.dias_letivos) else (dia.dia_semana or f"Dia {contador_dias + 1}")
                    dia_semana_nome = dia.dia_semana.split("-")[0].capitalize() if dia.dia_semana else f"Dia {len(dias_da_semana) + 1}"

                    dados_dia = {
                        "numeroDia": len(dias_da_semana) + 1,
                        "diaSemana": dia_semana_nome,
                        "refeicoes": refeicoes_formatadas
                    }
                    dias_da_semana.append(dados_dia)

                    dias_letivos_flat.append({
                        "data": data_label,
                        "diaSemana": dia_semana_nome,
                        "turno": turno_str,
                        "refeicoes": refeicoes_formatadas
                    })
                    contador_dias += 1

                semanas_formatadas.append({
                    "numeroSemana": semana.numero,
                    "dias": dias_da_semana
                })

        # Remove avisos internos de per capita e PNAE do campo observacoes
        # para que apenas as notas nutricionais geradas pela IA cheguem ao frontend
        raw_obs = getattr(cardapio, "observacoes", "") or ""
        clean_obs = re.split(r"(?i)\n*(?:per capita nao aplicado|avisos pnae):?", raw_obs)[0].strip()

        salvar_cardapio_db(
            cardapio_schema=cardapio,
            etapa=str(payload.etapa),
            faixa_etaria=str(payload.faixa_etaria),
            periodo=str(payload.periodo),
            num_refeicoes=payload.num_refeicoes,
            mes_aplicacao=mes_final,
            observacoes=clean_obs
        )

        nome_mes = MESES_MAPA.get(payload.meses_numeros[0], "Maio").capitalize() if payload.meses_numeros else "Maio"
        nome_cardapio = f"Cardápio {str(payload.etapa).capitalize()} {nome_mes} {ano_atual}"

        especificacao = {
            "nome": nome_cardapio,
            "etapaEducacao": str(payload.etapa),
            "faixaEtaria": str(payload.faixa_etaria),
            "periodo": str(payload.periodo),
            "turno": turno_str,
            "refeicoesPorDia": payload.num_refeicoes,
            "totalDias": contador_dias,
            "restricoes": payload.restricoes or []
        }

        return {
            "id": str(uuid.uuid4()),
            "dataCriacao": datetime.utcnow().strftime("%Y-%m-%d"),
            "especificacao": especificacao,
            "observacoes": clean_obs,
            "semanas": semanas_formatadas,
            "diasLetivos": dias_letivos_flat,
            "totalDias": contador_dias
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro durante a geração de cardápio: {str(e)}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8005))
    uvicorn.run("api_server:app", host="0.0.0.0", port=port, reload=True)
