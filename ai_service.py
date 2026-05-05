import os
import json
import time
from dotenv import load_dotenv
from enum import Enum
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db.models import Taco


load_dotenv()
print("\n dotenv loaded \n")

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

class TipoRefeicao(str, Enum):
    cafe_da_manha = "café da manhã"
    lanche_manha = "lanche da manhã"
    almoco = "almoço"
    lanche_tarde = "lanche da tarde"
    jantar = "jantar"

class RefeicaoSchema(BaseModel):
    tipo: TipoRefeicao
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


def corrigir_estrutura(dados: dict):
    if "cardapio" in dados:
        dados = dados["cardapio"]

    if "mes" in dados:
        dados["mes_aplicacao"] = f"{dados.pop('mes')} de {dados.pop('ano', '')}"

    if "semanas" in dados:
        for s in dados["semanas"]:
            if "semana" in s:
                s["numero"] = s.pop("semana")

            for d in s.get("dias", []):
                if "dia" in d:
                    d["dia_semana"] = d.pop("dia")

                for r in d.get("refeicoes", []):
                    # corrigir "itens" → pratos (já existe no seu código)
                    if "itens" in r:
                        r["pratos"] = [{
                            "nome": ", ".join(r.pop("itens")),
                            "estado_preparacao": "preparado",
                            "ingredientes": []
                        }]

                    # 🛠️ NOVO: corrigir tipo de refeição
                    tipo = r.get("tipo", "").lower()

                    if "1" in tipo:
                        r["tipo"] = "café da manhã"
                    elif "2" in tipo:
                        r["tipo"] = "almoço"
                    elif "lanche" in tipo:
                        r["tipo"] = "lanche da tarde"
                    else:
                        r["tipo"] = "almoço"  # fallback seguro
                        
    return dados


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

    from prompt_builder import construir_contexto

    contexto = construir_contexto(
        etapa=etapa,
        faixa_etaria=faixa_etaria,
        periodo=periodo,
        num_refeicoes=num_refeicoes,
        restricoes=restricoes,
        num_semanas=4
    )

    # - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # ETAPA 1 — Geração com Tools em texto livre
    # - - - - - - - - - - - - - - - - - - - - - - - - - - -

    llm_tools = ChatOllama(
        model="gemma4:31b-cloud",
        temperature=0.3
    ).bind_tools([listar_opcoes_taco, buscar_cn_ingrediente_taco])

    system_prompt_1 = f"""
Você é um nutricionista escolar.

Use as ferramentas disponíveis para montar um cardápio mensal.

REGRAS:
{contexto}

INSTRUÇÕES:
- Use as tools sempre que necessário
- Monte o cardápio completo (4 semanas com 5 dias cada)
- Organize de forma clara por semanas, dias e refeições
- NÃO gere JSON
- NÃO use formatação técnica
- Apenas texto estruturado e organizado
"""

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
                    content=json.dumps(resultado),
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

    prompt_2 = f"""
Você é um gerador de JSON estrito.

Sua tarefa é gerar um objeto que seja 100% válido de acordo com o schema CardapioSchema.

REGRAS CRÍTICAS (OBRIGATÓRIAS):

1. Retorne APENAS JSON válido.
   - Não inclua explicações
   - Não inclua comentários
   - Não use markdown
   - Não escreva nada antes ou depois do JSON

2. O JSON deve ser totalmente compatível com validação Pydantic.

3. Campos enum devem respeitar EXATAMENTE os valores permitidos.

Para o campo "tipo" das refeições, use SOMENTE UM dos valores abaixo:
- "café da manhã"
- "lanche da manhã"
- "almoço"
- "lanche da tarde"
- "jantar"

REGRAS IMPORTANTES:
- Não invente valores como "Refeição 1", "Refeição 2"
- Não use abreviações
- Respeite acentuação exatamente como acima

4. Todos os campos obrigatórios devem estar presentes.

5. Tipos devem ser respeitados:
- números como números (ex: 0.0)
- strings como strings
- listas como listas

6. Antes de responder, execute esta validação mental:
   - O JSON está válido?
   - Todos os enums estão corretos?
   - Existe algum valor fora do permitido?
   - Se houver erro, CORRIJA antes de responder

7. Se estiver em dúvida entre gerar algo inválido ou corrigir, sempre CORRIJA.

---

EXEMPLOS:

Exemplo válido:
{
  "tipo": "almoço"
}

Exemplo inválido (NUNCA FAZER):
{
  "tipo": "Refeição 1"
}

---

SAÍDA:
Retorne apenas o JSON final válido.
"""
    
    for tentativa in range(3):
        try:
            resultado = llm_structured.invoke(f"""
            {prompt_2}

            CONTEÚDO PARA CONVERTER:
            O texto abaixo deve ser convertido fielmente para o schema.
            NÃO invente informações novas.
            NÃO altere o significado.
            Apenas estruture corretamente.

            {texto_cardapio}
            """)

            # ✅ caso ideal
            if isinstance(resultado, CardapioSchema):
                return resultado

            # ⚠️ fallback: transformar em dict
            if isinstance(resultado, dict):
                dados = resultado
            elif hasattr(resultado, "model_dump"):
                dados = resultado.model_dump()
            else:
                raise ValueError("Formato inesperado da resposta")

            # tenta validar direto
            try:
                return CardapioSchema(**dados)
            except:
                # 🛠️ corrige estrutura
                dados_corrigidos = corrigir_estrutura(dados)
                return CardapioSchema(**dados_corrigidos)

        except Exception as e:
            print(f"Erro na etapa 2 (tentativa {tentativa+1}): {e}")
            time.sleep(1)

    raise RuntimeError("Falha ao converter cardápio para estrutura válida.")