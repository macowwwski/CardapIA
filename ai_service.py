import os
import json
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db.models import Taco

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))


# ---------------------------------------------------------
# Schema Pydantic do cardápio
# ---------------------------------------------------------

class IngredienteSchema(BaseModel):
    nome_taco: str
    quantidade_g: float

class PratoSchema(BaseModel):
    nome: str
    estado_preparacao: str
    ingredientes: list[IngredienteSchema]

class RefeicaoSchema(BaseModel):
    tipo: str
    horario: str
    pratos: list[PratoSchema]

class DiaSchema(BaseModel):
    dia_semana: str
    refeicoes: list[RefeicaoSchema]

class SemanaSchema(BaseModel):
    numero: int
    dias: list[DiaSchema]

class CardapioSchema(BaseModel):
    mes_aplicacao: str
    semanas: list[SemanaSchema]
    observacoes: str


# ---------------------------------------------------------
# Tools de consulta à TACO
# ---------------------------------------------------------

@tool
def listar_opcoes_taco(categoria: str) -> list[str]:
    """
    Lista os alimentos disponíveis na TACO para uma categoria.
    Deve ser usada ANTES de escolher um ingrediente para compor
    o cardápio, para descobrir os omes exatos disponíveis.

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


# ---------------------------------------------------------
# Função principal
# ---------------------------------------------------------

def gerar_cardapio(
        etapa: str,
        faixa_etaria: str,
        periodo: str,
        num_refeicoes: int,
        mes_aplicacao: str,
        restricoes: list[str] | None = None,
) -> CardapioSchema:
    """
    Gera um cardápio mensal completo usando a LLM com acesso à TACO
    e regras do PNAE.
    """
    from prompt_builder import construir_contexto

    # 1. Montar contexto com as regras do PNAE
    contexto = construir_contexto(
        etapa=etapa,
        faixa_etaria=faixa_etaria,
        periodo=periodo,
        num_refeicoes=num_refeicoes,
        restricoes=restricoes,
        num_semanas=4
    )

    # 2. Configurar LLM com as tools
    llm = ChatOllama(model="llama3.2:3b", temperature=0.3)
    tools = [listar_opcoes_taco, buscar_cn_ingrediente_taco]
    llm_tools = llm.bind_tools(tools)

    # 3. Montar as mensagens
    system_prompt = f"""Você é um nutricionista especializado em alimentação escolar.
Sua tarefa é gerar um cardápio mensal (4 semanas, segunda a sexta) respeitando
TODAS as regras do PNAE abaixo.

REGRAS OBRIGATÓRIAS:
{contexto}

INSTRUÇÕES PARA GERAR O CARDÁPIO:
1. Use SEMPRE listar_opcoes_taco antes de escolher um ingrediente
2. Use SEMPRE buscar_ingrediente_taco para verificar os valores nutricionais
3. Garanta que cada refeição respeite os valores nutricionais de referência
4. Varie os alimentos ao longo da semana
5. Retorne o cardápio APENAS em JSON válido seguindo exatamente este schema:

{json.dumps(CardapioSchema.model_json_schema(), indent=2, ensure_ascii=False)}

Não inclua nenhum texto fora do JSON."""
    
    mensagens = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Gere o cardápio de {num_refeicoes} refeição/refeições diárias para {mes_aplicacao}.")
    ]

    # 4. Loop de tool calling
    while True:
        resposta = llm_tools.invoke(mensagens)
        mensagens.append(resposta)

        if not resposta.tool_calls:
            break

        for tool_call in resposta.tool_calls:
            if tool_call["name"] == "listar_opcoes_taco":
                resultado = listar_opcoes_taco.invoke(tool_call["args"])
            elif tool_call["name"] == "buscar_cn_ingrediente_taco":
                resultado = buscar_cn_ingrediente_taco.invoke(tool_call["args"])

            from langchain_core.messages import ToolMessage
            mensagens.append(ToolMessage(
                content=str(resultado),
                tool_call_id=tool_call["id"]
            ))

    # 5. Parsear JSON retornado pela LLM
    conteudo = resposta.content.strip()
    dados = json.loads(conteudo)
    return CardapioSchema(**dados)