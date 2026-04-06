import json
from pathlib import Path

# Carrega o JSON uma única vez quando o módulo é importado
# Path(__file__) garante que o caminho funciona independente de onde o script é chamado
CAMINHO_JSON = Path(__file__).parent / "data" / "pnae.json"

with open(CAMINHO_JSON, encoding="utf-8") as f:
    REGRAS_PNAE = json.load(f)


# ---------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------

# def _mapear_percentual(periodo: str) -> str:
#     """
#     Traduz o período informado no formulário para a chave
#     correta no JSON.
#     """
#     mapeamento = {
#         "parcial_1_refeicao":  "20%_das_necessidades_diarias",
#         "parcial_2_refeicoes": "30%_das_necessidades_diarias",
#         "integral":            "70%_das_necessidades_diarias",
#     }
#     if periodo not in mapeamento:
#         raise ValueError(f"Combinação inváldia: '{periodo}'. "
#                          f"Valores aceitos: {list(mapeamento.keys())}")
#     return mapeamento[periodo]


def _mapear_percentual(periodo: str, num_refeicoes: int) -> str:
    if periodo == "integral":
        return "70%_das_necessidades_diarias"
    elif periodo == "parcial" and num_refeicoes == 1:
        return "20%_das_necessidades_diarias"
    elif periodo == "parcial" and num_refeicoes >= 2:
        return "30%_das_necessidades_diarias"
    else:
        raise ValueError(f"Combinação inválida: {periodo}, {num_refeicoes} refeições")


def _mapear_refeicoes_periodo(periodo: str, num_refeicoes: int) -> str:
    if periodo == "integral":
        return "integral"
    elif periodo == "parcial" and num_refeicoes == 1:
        return "parcial_1_refeicao"
    elif periodo == "parcial" and num_refeicoes >= 2:
        return "parcial_2_ou_mais_refeicoes"
    else:
        raise ValueError(f"Combinação inválida: {periodo}, {num_refeicoes} refeições")


def _obter_etapa(etapa: str) -> dict:
    """
    Decide entre os blocos raiz creche e outras_etapas.
    """
    if etapa == "creche":
        return REGRAS_PNAE["creche"]
    else:
        return REGRAS_PNAE["outras_etapas_ensino_basico"]
    

def _mapear_subfaixa_outras_etapas(etapa: str) -> str:
    """
    Busca a chave específica da subfaixa dentro de outras_etapas.
    """
    mapeamento = {
        "pré-escola":           "pre-escola",
        "ensino fundamental":   "ensino_fundamental",
        "ensino médio":         "ensino_medio",
        "EJA":                  "EJA"
    }
    
    if etapa not in mapeamento:
        raise ValueError(f"Etapa inválida: '{etapa}'")
    return mapeamento[etapa]


def _mapear_faixa_etaria(etapa: str, faixa_etaria: str, subfaixas: dict) -> dict:
    """
    Busca o bloco de faixa etária correto dentro de subfaixas_etarias.
    """
    if etapa == "creche":
        mapeamento = {
            "7 a 11 meses": "7_a_11_meses",
            "1 a 3 anos": "1_a_3_anos",
        }
        return subfaixas[mapeamento[faixa_etaria]]
    
    elif etapa == "ensino fundamental":
        mapeamento = {
            "6 a 10 anos": "6_a_10_anos",
            "11 a 15 anos": "11_a_15_anos",
        }
        return subfaixas["ensino_fundamental"][mapeamento[faixa_etaria]]
    
    elif etapa == "EJA":
        mapeamento = {
            "19 a 30 anos": "19_a_30_anos",
            "31 a 60 anos": "31_a_60_anos"
        }
        return subfaixas["EJA"][mapeamento[faixa_etaria]]
    
    else:
        mapeamento = {
            "pré-escola": "pre-escola",
            "ensino médio": "ensino_medio"
        }
        return subfaixas[mapeamento[etapa]]




def _obter_subfaixa(faixa_etaria: str, periodo: str) -> dict:
    """
    Navega até os valores nutricionais corretos dentro do JSON,
    cruzando faixa etária com o percentual do período.
    """
    segmento   = _obter_segmento(faixa_etaria)
    percentual = _mapear_percentual(periodo)

    referencias = segmento["referencias_nutricionais"]

    # Creche não tem bloco de 20% — valida combinação inválida
    if percentual not in referencias:
        raise ValueError(
            f"Combinação inválida: faixa '{faixa_etaria}' "
            f"não possui referência para '{percentual}'."
        )

    subfaixas = referencias[percentual]["subfaixas_etarias"]

    # Para ensino_fundamental, a subfaixa fica um nível mais fundo
    # ex: subfaixas["ensino_fundamental"]["6_a_10_anos"]
    if faixa_etaria in {"6_a_10_anos", "11_a_15_anos"}:
        return subfaixas["ensino_fundamental"][faixa_etaria]

    if faixa_etaria in {"19_a_30_anos", "31_a_60_anos"}:
        return subfaixas["EJA"][faixa_etaria]

    if faixa_etaria not in subfaixas:
        raise ValueError(f"Faixa etária '{faixa_etaria}' não encontrada no JSON.")

    return subfaixas[faixa_etaria]


def _formatar_lista(lista: list[str]) -> str:
    """Formata uma lista Python como texto corrido para o prompt."""
    return ", ".join(lista)


def _formatar_frequencias(frequencias: dict) -> str:
    """
    Itera o bloco de frequências ignorando a chave 'description',
    e formata cada regra como uma linha de texto.
    """
    linhas = []
    for chave, valor in frequencias.items():
        if chave == "description":
            continue
        if isinstance(valor, dict):
            # Tem subcampos (ex: frutas_e_legumes com parcial/integral)
            for subchave, subvalor in valor.items():
                if subchave == "observation":
                    linhas.append(f"  Obs: {subvalor}")
                elif isinstance(subvalor, dict):
                    for k, v in subvalor.items():
                        linhas.append(f"  {chave} > {subchave} > {k}: {v}")
                else:
                    linhas.append(f"  {chave} > {subchave}: {subvalor}")
        else:
            linhas.append(f"  {chave}: {valor}")
    return "\n".join(linhas)


# ---------------------------------------------------------
# Função principal
# ---------------------------------------------------------

def construir_contexto(
    faixa_etaria: str,
    periodo: str,
    restricoes: list[str] | None = None,
    num_semanas: int = 1
) -> str:
    """
    Monta o bloco de contexto que será injetado no prompt da LLM.

    Parâmetros:
        faixa_etaria : chave do JSON (ex: "6_a_10_anos")
        periodo      : "parcial_1_refeicao" | "parcial_2_refeicoes" | "integral"
        restricoes   : lista de restrições alimentares da turma (opcional)
        num_semanas  : quantas semanas de cardápio gerar

    Retorna:
        string formatada para ser inserida no prompt como contexto
    """
    restricoes = restricoes or []

    geral    = REGRAS_PNAE["geral"]
    segmento = _obter_segmento(faixa_etaria)
    subfaixa = _obter_subfaixa(faixa_etaria, periodo)

    # Junta proibições universais com as específicas da faixa etária
    proibicoes = (
        geral.get("alimentos_proibidos", []) +
        segmento.get("alimentos_proibidos", [])
    )

    # Percentuais VET do segmento
    pvet = segmento["referencias_nutricionais"]["percentuais_vet"]

    contexto = f"""
## REGRAS DO PNAE — CONTEXTO PARA GERAÇÃO DE CARDÁPIO

### Configuração solicitada
- Faixa etária: {faixa_etaria.replace("_", " ")}
- Período: {periodo.replace("_", " ")}
- Semanas a gerar: {num_semanas}
- Restrições alimentares da turma: {_formatar_lista(restricoes) if restricoes else "nenhuma"}

### Alimentos proibidos
{_formatar_lista(proibicoes)}

### Agricultura familiar
- Mínimo obrigatório: {geral['percentual_minimo_agricultura_familiar']}% dos insumos

### Frequências obrigatórias (válidas para todos os períodos)
{_formatar_frequencias(geral['frequencia_alimentos'])}

### Frequências por período ({periodo.replace("_", " ")})
{_formatar_frequencias({k: v[periodo] if periodo in v else v
    for k, v in geral['frequencia_alimentos_por_periodo'].items()
    if k != 'description'})}

### Diversidade de alimentos
- {num_semanas} semana(s): respeitar mínimo de alimentos diferentes por semana
  conforme número de refeições diárias

### Referências nutricionais por refeição
- Carboidratos: {pvet['carboidratos']['minimo']}% a {pvet['carboidratos']['maximo']}% do VET
- Proteínas:    {pvet['proteinas']['minimo']}% a {pvet['proteinas']['maximo']}% do VET
- Lipídios:     {pvet['lipidios']['minimo']}% a {pvet['lipidios']['maximo']}% do VET

Valores absolutos para a faixa etária e período selecionados:
- Energia:       {subfaixa['energia_kcal']} kcal
- Carboidratos:  {subfaixa['carboidratos_g']['minimo']}g a {subfaixa['carboidratos_g']['maximo']}g
- Proteínas:     {subfaixa['proteinas_g']['minimo']}g a {subfaixa['proteinas_g']['maximo']}g
- Lipídios:      {subfaixa['lipidios_g']['minimo']}g a {subfaixa['lipidios_g']['maximo']}g
"""

    # Micronutrientes — só existem no bloco creche
    if "vitamina_a_mcg" in subfaixa:
        contexto += f"""- Vitamina A:    {subfaixa['vitamina_a_mcg']} mcg
- Vitamina C:    {subfaixa['vitamina_c_mg']} mg
- Cálcio:        {subfaixa['calcio_mg']} mg
- Ferro:         {subfaixa['ferro_mg']} mg
"""

    return contexto.strip()