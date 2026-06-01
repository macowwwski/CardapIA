from langchain_ollama import ChatOllama
import _bootstrap  # noqa: F401

from src.ai_service import CardapioSchema

llm = ChatOllama(model="gemma4:31b-cloud", temperature=0)


llm_structured = llm.with_structured_output(CardapioSchema)

res = llm_structured.invoke("""
Retorne EXATAMENTE este JSON:

{
  "mes_aplicacao": "teste",
  "semanas": [],
  "observacoes": "teste"
}
""")

print(res)

