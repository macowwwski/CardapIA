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

# Mapear: funções que apenas "traduzem" as entradas do forms para nomes no JSON
# Obter: funções que navegam dentro do JSON

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


def _mapear_e_obter_faixa_etaria(etapa: str, faixa_etaria: str, subfaixas: dict) -> dict:
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


def _obter_referencias_nutricionais(etapa_bloco: dict, percentual: str) -> dict:
    """
    Navega até subfaixas_etarias dentro das referencias_nutricionais
    com base no percentual das necessidades diárias.
    """
    return etapa_bloco["referencias_nutricionais"][percentual]["subfaixas_etarias"]


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
# Função principal de montagem do contexto
# ---------------------------------------------------------

def construir_contexto(
    etapa: str,
    faixa_etaria: str,
    periodo: str,
    num_refeicoes: int,
    restricoes: list[str] | None = None,
    num_semanas: int = 1
) -> str:
    """
    Monta o bloco de contexto que será injetado no prompt da LLM.

    Parâmetros:
        etapa         : "creche" | "pré-escola" | "ensino fundamental" | "ensino médio" | "EJA"
        faixa_etaria  : ex: "6 a 10 anos", "7 a 11 meses"
        periodo       : "parcial" | "integral"
        num_refeicoes : número de refeições diárias
        restricoes    : lista de restrições alimentares da turma (opcional)
        num_semanas   : quantas semanas de cardápio gerar
    """
    restricoes = restricoes or []

    # --- Navegação no JSON ---
    geral        = REGRAS_PNAE["geral"]
    etapa_bloco  = _obter_etapa(etapa)
    percentual   = _mapear_percentual(periodo, num_refeicoes)
    subfaixas    = _obter_referencias_nutricionais(etapa_bloco, percentual)
    valores      = _mapear_e_obter_faixa_etaria(etapa, faixa_etaria, subfaixas)
    periodo_freq = _mapear_refeicoes_periodo(periodo, num_refeicoes)

    # --- Proibições: universais + específicas da etapa ---
    proibicoes = (
        geral.get("alimentos_proibidos", []) +
        etapa_bloco.get("alimentos_proibidos", [])
    )

    # --- Percentuais VET do bloco da etapa ---
    pvet = etapa_bloco["referencias_nutricionais"]["percentuais_vet"]

    # --- Frequências por período ---
    # Filtra cada item do bloco de frequências pelo período correto
    frequencias_periodo = {}
    for chave, valor in geral["frequencia_alimentos_por_periodo"].items():
        if chave == "description":
            continue
        if isinstance(valor, dict) and periodo_freq in valor:
            frequencias_periodo[chave] = valor[periodo_freq]
        else:
            frequencias_periodo[chave] = valor

    # --- Monta o texto ---
    contexto = f"""
## REGRAS DO PNAE — CONTEXTO PARA GERAÇÃO DE CARDÁPIO

### Configuração solicitada
- Etapa: {etapa}
- Faixa etária: {faixa_etaria}
- Período: {periodo} ({num_refeicoes} refeição/refeições por dia)
- Semanas a gerar: {num_semanas}
- Restrições alimentares da turma: {_formatar_lista(restricoes) if restricoes else "nenhuma"}

### Alimentos proibidos
{_formatar_lista(proibicoes)}

### Agricultura familiar
- Mínimo obrigatório: {geral['percentual_minimo_agricultura_familiar']}% dos insumos

### Frequências obrigatórias (todos os períodos)
{_formatar_frequencias(geral['frequencia_alimentos'])}

### Frequências para o período selecionado ({periodo}, {num_refeicoes} refeição/refeições)
{_formatar_frequencias(frequencias_periodo)}

### Diversidade de alimentos
{_formatar_frequencias(geral['recomendacao_diferenciacao_de_alimentos'])}

### Percentuais do VET
- Carboidratos: {pvet['carboidratos']['minimo']}% a {pvet['carboidratos']['maximo']}%
- Proteínas:    {pvet['proteinas']['minimo']}% a {pvet['proteinas']['maximo']}%
- Lipídios:     {pvet['lipidios']['minimo']}% a {pvet['lipidios']['maximo']}%

### Valores nutricionais absolutos por refeição ({percentual.replace('_', ' ')})
- Energia:      {valores['energia_kcal']} kcal
- Carboidratos: {valores['carboidratos_g']['minimo']}g a {valores['carboidratos_g']['maximo']}g
- Proteínas:    {valores['proteinas_g']['minimo']}g a {valores['proteinas_g']['maximo']}g
- Lipídios:     {valores['lipidios_g']['minimo']}g a {valores['lipidios_g']['maximo']}g
"""

    # Micronutrientes — só existem no bloco creche
    if "vitamina_a_mcg" in valores:
        contexto += f"""- Vitamina A:    {valores['vitamina_a_mcg']} mcg
- Vitamina C:    {valores['vitamina_c_mg']} mg
- Cálcio:        {valores['calcio_mg']} mg
- Ferro:         {valores['ferro_mg']} mg
"""

    return contexto.strip()