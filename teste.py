from prompt_builder import construir_contexto

contexto = construir_contexto(
    faixa_etaria="6_a_10_anos",
    periodo="parcial_2_refeicoes",
    restricoes=["lactose"],
    num_semanas=1
)

print(contexto)
