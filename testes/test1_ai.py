# teste_ia.py
from src.ai_service import gerar_cardapio

cardapio = gerar_cardapio(
    etapa="ensino fundamental",
    faixa_etaria="6 a 10 anos",
    periodo="parcial",
    num_refeicoes=2,
    mes_aplicacao="maio de 2026",
    restricoes=[]
)

print(cardapio.model_dump_json(indent=2))