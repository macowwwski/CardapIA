from src.ai_service import listar_opcoes_taco, buscar_cn_ingrediente_taco

# Testa listagem por categoria
print("=== Frutas ===")
frutas = listar_opcoes_taco.invoke({"categoria": "Frutas e derivados"})
print(frutas[:5])  # mostra só os 5 primeiros

# Testa busca por nome exato
print("\n=== Busca por nome ===")
resultado = buscar_cn_ingrediente_taco.invoke({"nome_alimento": frutas[0]})
print(resultado)