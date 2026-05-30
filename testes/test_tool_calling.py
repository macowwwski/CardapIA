from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from src.ai_service import listar_opcoes_taco

llm = ChatOllama(model="gemma4:31b-cloud", temperature=0)

llm_tools = llm.bind_tools([listar_opcoes_taco])

mensagens = [
    SystemMessage(content="Use a tool se necessário."),
    HumanMessage(content="Liste alimentos da categoria Frutas e derivados")
]

res = llm_tools.invoke(mensagens)

print(res)
print("TOOL CALLS:", res.tool_calls)