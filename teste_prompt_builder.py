from prompt_builder import construir_contexto
import json
from pathlib import Path

with open("data/pnae.json", encoding="utf-8") as f:
    pnae = json.load(f)

print("Chaves em creche > referencias_nutricionais:")
print(list(pnae["creche"]["referencias_nutricionais"].keys()))

print("\nChaves em outras_etapas > referencias_nutricionais:")
print(list(pnae["outras_etapas_ensino_basico"]["referencias_nutricionais"].keys()))

casos = [
    {
        "descricao": "Creche - bebê - integral",
        "etapa": "creche",
        "faixa_etaria": "7 a 11 meses",
        "periodo": "integral",
        "num_refeicoes": 3,
    },
    {
        "descricao": "Creche - criança - parcial 1 refeição",
        "etapa": "creche",
        "faixa_etaria": "1 a 3 anos",
        "periodo": "parcial",
        "num_refeicoes": 1,
    },
    {
        "descricao": "Ensino fundamental - parcial 2 refeições - com restrições",
        "etapa": "ensino fundamental",
        "faixa_etaria": "6 a 10 anos",
        "periodo": "parcial",
        "num_refeicoes": 2,
        "restricoes": ["lactose", "glúten"],
    },
    {
        "descricao": "EJA - integral",
        "etapa": "EJA",
        "faixa_etaria": "31 a 60 anos",
        "periodo": "integral",
        "num_refeicoes": 3,
    },
    {
        "descricao": "Pré-escola - parcial 1 refeição",
        "etapa": "pré-escola",
        "faixa_etaria": "4 a 5 anos",
        "periodo": "parcial",
        "num_refeicoes": 1,
    },
]

for caso in casos:
    print(f"\n{'='*60}")
    print(f"CASO: {caso['descricao']}")
    print('='*60)
    try:
        contexto = construir_contexto(
            etapa=caso["etapa"],
            faixa_etaria=caso["faixa_etaria"],
            periodo=caso["periodo"],
            num_refeicoes=caso["num_refeicoes"],
            restricoes=caso.get("restricoes", []),
            num_semanas=1
        )
        print(contexto)
    except Exception as e:
        print(f"ERRO: {e}")