
from ai_service import gerar_cardapio

cardapio = gerar_cardapio(
    etapa="creche",
    faixa_etaria="7 a 11 meses",
    periodo="integral",
    num_refeicoes=4,
    mes_aplicacao="maio de 2026",
    restricoes=[]
)

print(cardapio.model_dump_json(indent=2))