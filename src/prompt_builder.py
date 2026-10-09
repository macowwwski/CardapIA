"""
Construtor de contexto e regras nutricionais do PNAE para o prompt da IA.

Responsável por:
- Carregar as diretrizes da Resolução CD/FNDE nº 6/2020 (data/pnae.json).
- Normalizar parâmetros recebidos da API (etapa escolar, faixas etárias, turnos).
- Filtrar proibições, percentuais do VET, limites de sódio, açúcar e micronutrientes.
- Montar o texto estruturado que orienta o modelo de IA na elaboração do cardápio.
"""
import json
from pathlib import Path

# Carrega o JSON uma única vez quando o módulo é importado
# Path(__file__) garante que o caminho funciona independente de onde o script é chamado
CAMINHO_JSON = Path(__file__).resolve().parent.parent / "data" / "pnae.json"

with open(CAMINHO_JSON, encoding="utf-8") as f:
    REGRAS_PNAE = json.load(f)

# Mapeia variações de etapas escolares (IDs e formatos do frontend/backend)
# para a nomenclatura padrão esperada nas regras do pnae.json
MAPA_ETAPAS = {
    "creche": "creche",
    "pre_escola": "pré-escola",
    "pre-escola": "pré-escola",
    "pré-escola": "pré-escola",
    "fundamental_1": "ensino fundamental",
    "fundamental_2": "ensino fundamental",
    "fundamental": "ensino fundamental",
    "ensino_fundamental": "ensino fundamental",
    "ensino fundamental": "ensino fundamental",
    "medio": "ensino médio",
    "ensino_medio": "ensino médio",
    "ensino médio": "ensino médio",
    "eja": "EJA",
    "EJA": "EJA",
}

# Mapeia identificadores de faixas etárias (ex: "1_3", "6_10")
# para a descrição textual utilizada nas tabelas do PNAE
MAPA_FAIXAS = {
    "7_11": "7 a 11 meses",
    "7 a 11 meses": "7 a 11 meses",
    "1_3": "1 a 3 anos",
    "1 a 3 anos": "1 a 3 anos",
    "4_5": "4 a 5 anos",
    "4 a 5 anos": "4 a 5 anos",
    "6_10": "6 a 10 anos",
    "6 a 10 anos": "6 a 10 anos",
    "11_14": "11 a 15 anos",
    "11_15": "11 a 15 anos",
    "11 a 15 anos": "11 a 15 anos",
    "16_18": "16 a 18 anos",
    "16 a 18 anos": "16 a 18 anos",
    "19_30": "19 a 30 anos",
    "19 a 30 anos": "19 a 30 anos",
    "31_60": "31 a 60 anos",
    "31 a 60 anos": "31 a 60 anos",
}

# ---------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------

# Mapear: funções que apenas "traduzem" as entradas do forms para nomes no JSON
# Obter: funções que navegam dentro do JSON

def _mapear_percentual(periodo: str, num_refeicoes: int) -> str:
    """Mapeia período e número de refeições para a chave de percentual das necessidades diárias do PNAE."""
    if periodo == "integral":
        return "70pct_das_necessidades_diarias"
    elif num_refeicoes == 1:
        return "20pct_das_necessidades_diarias"
    else:
        return "30pct_das_necessidades_diarias"


def _mapear_refeicoes_periodo(periodo: str, num_refeicoes: int) -> str:
    """Mapeia período e número de refeições para a chave de frequência de atendimento."""
    if periodo == "integral":
        return "integral"
    elif num_refeicoes == 1:
        return "parcial_1_refeicao"
    else:
        return "parcial_2_ou_mais_refeicoes"


def _validar_configuracao(etapa: str, periodo: str, num_refeicoes: int) -> None:
    """Ponto de validação de consistência entre etapa, período e número de refeições."""
    pass


def resolver_tipos_refeicao(etapa: str, periodo: str, turno: str, faixa_etaria: str) -> list[str]:
    """
    Resolve os tipos de refeicao esperados para a combinacao etapa/periodo/turno.
    """
    if etapa == "creche" and periodo == "parcial" and turno == "matutino":
        return ["desjejum", "almoço"]

    if etapa == "creche" and periodo == "parcial" and turno == "vespertino":
        return ["reforço", "jantar"]
    
    if etapa == "creche" and periodo == "integral" and faixa_etaria == "7 a 11 meses":
        return ["desjejum", "almoço", "reforço", "lanche da tarde", "jantar"]
    
    if etapa == "creche" and periodo == "integral" and faixa_etaria == "1 a 3 anos":
        return ["desjejum", "almoço", "lanche da tarde", "jantar"]

    if etapa in ("pré-escola", "ensino fundamental", "ensino médio", "EJA") and periodo == "parcial" and turno == "matutino":
        return ["almoço"]
    
    if etapa in ("pré-escola", "ensino fundamental", "ensino médio", "EJA") and periodo == "parcial" and turno == "vespertino":
        return ["jantar"]

    return []

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
            "7 a 11 meses": ("7_a_11_meses", "7_11_meses"),
            "1 a 3 anos": ("1_a_3_anos", "1_3_anos"),
        }
        chaves = mapeamento.get(faixa_etaria, ("1_a_3_anos", "1_3_anos"))
        for chave in chaves:
            if chave in subfaixas:
                return subfaixas[chave]
        return list(subfaixas.values())[0] if subfaixas else {}

    elif etapa == "ensino fundamental":
        mapeamento = {
            "6 a 10 anos": "6_a_10_anos",
            "11 a 15 anos": "11_a_15_anos",
        }
        chave = mapeamento.get(faixa_etaria, "6_a_10_anos")
        bloco_fund = subfaixas.get("ensino_fundamental", {})
        if chave in bloco_fund:
            return bloco_fund[chave]
        return list(bloco_fund.values())[0] if bloco_fund else (list(subfaixas.values())[0] if subfaixas else {})

    elif etapa == "EJA":
        mapeamento = {
            "19 a 30 anos": "19_a_30_anos",
            "31 a 60 anos": "31_a_60_anos"
        }
        chave = mapeamento.get(faixa_etaria, "19_a_30_anos")
        bloco_eja = subfaixas.get("EJA", {})
        if chave in bloco_eja:
            return bloco_eja[chave]
        return list(bloco_eja.values())[0] if bloco_eja else (list(subfaixas.values())[0] if subfaixas else {})

    else:
        mapeamento = {
            "pré-escola": "pre-escola",
            "ensino médio": "ensino_medio"
        }
        chave = mapeamento.get(etapa, "pre-escola")
        if chave in subfaixas:
            return subfaixas[chave]
        return list(subfaixas.values())[0] if subfaixas else {}


def _obter_recomendacoes_quantidade(etapa_bloco: dict) -> dict | None:
    """
    Retorna o bloco recomendacoes_quantidade se existir.
    Retorna None para creche, que não possui esse bloco.
    """
    return etapa_bloco.get("recomendacoes_quantidade", None)


def _obter_referencias_nutricionais(etapa_bloco: dict, percentual: str) -> dict:
    """
    Navega até subfaixas_etarias dentro das referencias_nutricionais
    com base no percentual das necessidades diárias.
    """
    refs = etapa_bloco.get("referencias_nutricionais", {})
    if percentual in refs and "subfaixas_etarias" in refs[percentual]:
        return refs[percentual]["subfaixas_etarias"]
    for chave in ("30pct_das_necessidades_diarias", "20pct_das_necessidades_diarias", "70pct_das_necessidades_diarias"):
        if chave in refs and "subfaixas_etarias" in refs[chave]:
            return refs[chave]["subfaixas_etarias"]
    return {}


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
    turno: str = "matutino",
    restricoes: list[str] | None = None,
    num_semanas: int = 1,
    total_dias: int | None = None,
    dias_letivos: list[str] | None = None
) -> str:
    """
    Monta o bloco de contexto que será injetado no prompt da LLM.

    Parâmetros:
        etapa         : "creche" | "pré-escola" | "ensino fundamental" | "ensino médio" | "EJA"
        faixa_etaria  : ex: "6 a 10 anos", "7 a 11 meses"
        periodo       : "parcial" | "integral"
        turno         : "matutino" | "vespertino" | "integral"
        num_refeicoes : número de refeições diárias
        restricoes    : lista de restrições alimentares da turma (opcional)
        num_semanas   : quantas semanas de cardápio gerar
        total_dias    : quantidade exata de dias letivos a planejar (opcional)
        dias_letivos  : lista de datas específicas dos dias letivos (opcional)
    """
    restricoes = restricoes or []
    etapa = MAPA_ETAPAS.get(str(etapa).lower().strip(), etapa)
    faixa_etaria = MAPA_FAIXAS.get(str(faixa_etaria).lower().strip(), faixa_etaria)
    _validar_configuracao(etapa, periodo, num_refeicoes)

    # --- Navegação no JSON ---
    geral        = REGRAS_PNAE["geral"]
    etapa_bloco  = _obter_etapa(etapa)
    percentual   = _mapear_percentual(periodo, num_refeicoes)
    subfaixas    = _obter_referencias_nutricionais(etapa_bloco, percentual)
    valores      = _mapear_e_obter_faixa_etaria(etapa, faixa_etaria, subfaixas)
    periodo_freq = _mapear_refeicoes_periodo(periodo, num_refeicoes)
    tipos_refeicao = resolver_tipos_refeicao(etapa, periodo, turno, faixa_etaria)

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
        if isinstance(valor, dict):
            if periodo_freq in valor:      # ex: biscoito_bolacha
                frequencias_periodo[chave] = valor[periodo_freq]
            elif periodo in valor:         # ex: frutas_legumes, liquidos_lacteos
                frequencias_periodo[chave] = valor[periodo]
            else:
                frequencias_periodo[chave] = valor
        else:
            frequencias_periodo[chave] = valor

    # --- Diversidade de alimentos por período ---
    # Filtra o bloco de recomendacao_diversidade_de_alimentos pelo período correto
    diversidade_periodo = {}
    for chave, valor in geral["recomendacao_diversidade_de_alimentos"].items():
        if chave in ("description", "observation"):
            continue
        if chave == periodo_freq:
            diversidade_periodo[chave] = valor

    # --- Monta o texto ---
    info_dias = f"- Total de dias letivos a gerar: {total_dias}\n" if total_dias else ""
    if dias_letivos:
        info_dias += f"- Datas dos dias letivos: {', '.join(dias_letivos)}\n"

    contexto = f"""
## REGRAS DO PNAE — CONTEXTO PARA GERAÇÃO DE CARDÁPIO

### Configuração solicitada
- Etapa: {etapa}
- Faixa etária: {faixa_etaria}
- Período: {periodo} ({num_refeicoes} refeição/refeições por dia)
- Turno: {turno}
- Semanas a gerar: {num_semanas}
{info_dias}- Restrições alimentares da turma: {_formatar_lista(restricoes) if restricoes else "nenhuma"}

### Tipos de refeição obrigatórios
{_formatar_lista(tipos_refeicao) if tipos_refeicao else "nenhum tipo específico configurado"}

### Alimentos proibidos
{_formatar_lista(proibicoes)}

### Agricultura familiar
- Mínimo obrigatório: {geral['percentual_minimo_agricultura_familiar']}% dos insumos

### Frequências obrigatórias (todos os períodos)
{_formatar_frequencias(geral['frequencia_alimentos'])}

### Frequências para o período selecionado ({periodo}, {num_refeicoes} refeição/refeições)
{_formatar_frequencias(frequencias_periodo)}

### Diversidade de alimentos para ({periodo}, {num_refeicoes} refeição/refeições)
{_formatar_frequencias(diversidade_periodo)}

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
        
    # Recomendações quantidade energia total e sódio — só existe em outras_etapas
    recomendacoes = _obter_recomendacoes_quantidade(etapa_bloco)

    if recomendacoes:
        contexto += f"""
### Recomendações de quantidade
- Açúcar simples adicionado: máximo {recomendacoes['percentual_energia_total']['acucar_simples_adicionado']}% do VET
- Gorduras totais: {recomendacoes['percentual_energia_total']['gorduras_totais']['minimo']}% a {recomendacoes['percentual_energia_total']['gorduras_totais']['maximo']}% do VET
- Gordura saturada: máximo {recomendacoes['percentual_energia_total']['gordura_saturada']}% do VET
- Sódio ({periodo}, {num_refeicoes} refeição/refeições): {recomendacoes['maximo_sodio'][periodo_freq]}
"""
    
    return contexto.strip()
