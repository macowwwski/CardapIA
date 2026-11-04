"""
Servidor HTTP FastAPI do CardapIA.

Atua como microsserviço de geração de cardápios escolares:
- Recebe os parâmetros de planejamento do backend principal (CooperaAgro-Back).
- Invoca o serviço de Inteligência Artificial com regras do PNAE.
- Consulta e calcula os valores nutricionais de cada ingrediente na Tabela TACO.
- Formata a resposta com compatibilidade para o frontend/backend e persiste histórico no banco.
"""
import sys
import uuid
import math
from pathlib import Path
from typing import List, Optional, Union
from datetime import datetime

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
from db.repository import salvar_cardapio_db
from src.ai_service import gerar_cardapio
from src.nutrition.calculator import calcular_nutrientes_alimento
from src.nutrition.classifier import _texto_normalizado
from src.taco.resolver import resolver_taco, resolver_per_capita
from src.pipelines import (
    PerfilNaoSuportadoError,
    PerfilIncompletoError,
    DistribuicaoNaoConfiguradaError,
    DistribuicaoInvalidaError,
    RefeicaoEsperadaAusenteError,
)


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

# =========================================================
# Modelos de Entrada (DTOs) e Mapeamentos
# =========================================================

# Mapeamento de números de meses para seus nomes por extenso em português
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


# =========================================================
# Resolução de Nutrientes TACO e Persistência
# =========================================================

# Mantido como alias para total retrocompatibilidade
_buscar_nutrientes_taco = calcular_nutrientes_alimento



# =========================================================
# Endpoints da API HTTP (Rotas FastAPI)
# =========================================================

@app.get("/health")
def health_check():
    """Verifica se a API do CardapIA está ativa e respondendo."""
    return {"status": "ok", "service": "CardapIA"}


@app.post("/api/cardapios/generate")
def api_gerar_cardapio(payload: GerarCardapioRequest):
    """
    Endpoint principal para geração de cardápio escolar:
    - Fase 1: Trata parâmetros de data, turno e semanas necessárias.
    - Fase 2: Aciona o pipeline de Inteligência Artificial para estruturar o cardápio.
    - Fase 3: Consulta a TACO para enriquecer cada alimento com dados nutricionais.
    - Fase 4: Higieniza observações e persiste o histórico no PostgreSQL.
    """
    try:
        # ---------------------------------------------------------
        # FASE 1: Sanitização de parâmetros de data, turno e dias
        # ---------------------------------------------------------
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

        limite_dias = None
        if payload.dias_letivos and len(payload.dias_letivos) > 0:
            limite_dias = len(payload.dias_letivos)
        elif payload.total_dias and payload.total_dias > 0:
            limite_dias = payload.total_dias

        num_semanas = 1
        if limite_dias:
            num_semanas = max(1, math.ceil(limite_dias / 5))

        # ---------------------------------------------------------
        # FASE 2: Invocação do pipeline de IA (LLM + PNAE)
        # ---------------------------------------------------------
        cardapio = gerar_cardapio(
            etapa=str(payload.etapa),
            faixa_etaria=str(payload.faixa_etaria),
            periodo=str(payload.periodo),
            num_refeicoes=payload.num_refeicoes,
            mes_aplicacao=mes_final,
            turno=turno_str,
            restricoes=payload.restricoes or [],
            num_semanas=num_semanas,
            validar_pnae=bool(payload.validar_pnae),
            total_dias=limite_dias,
            dias_letivos=payload.dias_letivos or [],
        )

        # ---------------------------------------------------------
        # FASE 3: Enriquecimento nutricional com TACO e estruturação
        # ---------------------------------------------------------
        semanas_formatadas = []
        dias_letivos_flat = []
        contador_dias = 0

        session = None
        try:
            session = Session(engine)
        except Exception:
            session = None

        try:
            for semana in cardapio.semanas:
                if limite_dias is not None and contador_dias >= limite_dias:
                    break
                dias_da_semana = []
                for dia in semana.dias:
                    if limite_dias is not None and contador_dias >= limite_dias:
                        break
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
                                    # Quantidade já definida pelo per capita oficial; sem fallback fixo
                                    if not ing.quantidade_g or ing.quantidade_g <= 0:
                                        continue
                                    qtd = ing.quantidade_g
                                    nutri = _buscar_nutrientes_taco(session, ing.nome_taco or prato.nome, qtd, getattr(ing, "_taco_id", None))
                                    for k in totais:
                                        totais[k] = round(totais[k] + nutri[k], 2)
                                    alimentos_formatados.append({
                                        "nome": ing.nome_taco or prato.nome,
                                        "quantidadeG": qtd,
                                        "nutrientes": nutri,
                                        "totaisNutricionais": nutri
                                    })
                            else:
                                nome_norm = _texto_normalizado(prato.nome)
                                eh_composta = any(
                                    termo in nome_norm
                                    for termo in [
                                        "galinhada", "baiao", "feijoada", "escondidinho", "risoto",
                                        "estrogonofe", "strogonoff", "lasanha", "panqueca", "nhoque",
                                        "torta", "quibe", "salpicao", "yakisoba", "salada de fruta",
                                        "com ", "ao molho", "a bolonhesa", "à bolonhesa", "rechead"
                                    ]
                                )
                                if not eh_composta:
                                    match_prato = None
                                    try:
                                        match_prato = resolver_taco(prato.nome)
                                    except Exception:
                                        match_prato = None
                                    qtd = None
                                    try:
                                        qtd = resolver_per_capita(prato.nome, str(payload.etapa), taco_id=match_prato.taco_id if match_prato else None)
                                    except Exception:
                                        qtd = None
                                    if qtd and qtd > 0:
                                        nutri = _buscar_nutrientes_taco(session, prato.nome, qtd, match_prato.taco_id if match_prato else None)
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

                if dias_da_semana:
                    semanas_formatadas.append({
                        "numeroSemana": semana.numero,
                        "dias": dias_da_semana
                    })
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass

        # ---------------------------------------------------------
        # FASE 4: Higienização de observações e persistência relacional
        # ---------------------------------------------------------
        raw_obs = getattr(cardapio, "observacoes", "") or ""
        status_validacao = getattr(cardapio, "_status_validacao_nome", "pendente_revisao")
        aprovado_flag = bool(getattr(cardapio, "_aprovado", False))
        inconformidades_lista = getattr(cardapio, "_inconformidades_json", [])
        resumo_validacao = getattr(cardapio, "_resumo_validacao", "")

        db_cardapio_id = salvar_cardapio_db(
            cardapio_schema=cardapio,
            etapa=str(payload.etapa),
            faixa_etaria=str(payload.faixa_etaria),
            periodo=str(payload.periodo),
            num_refeicoes=payload.num_refeicoes,
            mes_aplicacao=mes_final,
            observacoes=raw_obs,
            aprovado=aprovado_flag,
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
            "id": db_cardapio_id or str(uuid.uuid4()),
            "dataCriacao": datetime.utcnow().strftime("%Y-%m-%d"),
            "especificacao": especificacao,
            "observacoes": raw_obs,
            "statusValidacao": status_validacao,
            "aprovado": aprovado_flag,
            "inconformidades": inconformidades_lista,
            "resumoValidacao": resumo_validacao,
            "semanas": semanas_formatadas,
            "diasLetivos": dias_letivos_flat,
            "totalDias": contador_dias
        }

    except PerfilNaoSuportadoError as pe:
        raise HTTPException(status_code=400, detail=str(pe))
    except (PerfilIncompletoError, DistribuicaoNaoConfiguradaError, DistribuicaoInvalidaError, RefeicaoEsperadaAusenteError) as de:
        raise HTTPException(status_code=422, detail=str(de))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro durante a geração de cardápio: {str(e)}")


if __name__ == "__main__":
    from src.config import SERVER_PORT
    uvicorn.run("api_server:app", host="0.0.0.0", port=SERVER_PORT, reload=True)

