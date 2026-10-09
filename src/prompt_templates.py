import json
from src.schemas_pydantic import CardapioSchema


def montar_prompt_geracao_cardapio(
    contexto: str,
    total_dias: int | None = None,
    num_semanas: int = 1
) -> str:
    if total_dias and total_dias > 0:
        instrucao_escopo = f"- Planeje o cardápio para EXATAMENTE {total_dias} dia(s) letivo(s) solicitado(s). NÃO gere dias adicionais nem semanas extras."
    else:
        instrucao_escopo = f"- Planeje o cardápio para {num_semanas} semana(s) com 5 dias cada."

    return f"""
    Você é um nutricionista escolar especialista nas normas do PNAE.
    Monte o cardápio solicitado seguindo rigorosamente as diretrizes nutricionais.
    
    Siga essas regras:
    {contexto}

    INSTRUÇÕES:
    {instrucao_escopo}
    - Organize de forma clara por semanas, dias e refeições
    - NÃO gere JSON
    - NÃO use formatação técnica
    - Apenas texto estruturado e organizado
  """.strip()


def montar_prompt_conversao_json() -> str:
    schema_json = json.dumps(
        CardapioSchema.model_json_schema(),
        ensure_ascii=False,
        indent=2,
    )

    return f"""
    Você é um gerador de JSON estrito.

    Sua tarefa é gerar um objeto que seja 100% válido de acordo com o schema CardapioSchema.

    REGRAS CRÍTICAS (OBRIGATÓRIAS):
    1. Retorne APENAS JSON válido.
        - Não inclua explicações
        - Não inclua comentários
        - Não use markdown
        - Não escreva nada antes ou depois do JSON

    2. O JSON deve ser totalmente compatível com validação Pydantic.

    SCHEMA PYDANTIC EM JSON:
    {schema_json}

    3. Campos enum devem respeitar EXATAMENTE os valores permitidos.

    Para o campo "tipo" das refeições, use SOMENTE UM dos valores abaixo:
        - "desjejum"
        - "almoço"
        - "reforço"
        - "lanche da tarde"
        - "jantar"

    REGRAS IMPORTANTES:
        - Não invente valores como "Refeição 1", "Refeição 2"
        - Não use abreviações
        - Respeite acentuação exatamente como acima

    4. Todos os campos obrigatórios devem estar presentes.

    5. Tipos devem ser respeitados:
        - números como números (ex: 0.0)
        - strings como strings
        - listas como listas

    6. Antes de responder, execute esta validação mental:
        - O JSON está válido?
        - Todos os enums estão corretos?
        - Existe algum valor fora do permitido?
        - Se houver erro, CORRIJA antes de responder

    7. Se estiver em dúvida entre gerar algo inválido ou corrigir, sempre CORRIJA.

    ---

    EXEMPLOS:

    Exemplo válido:
    {{
        "tipo": "almoço"
    }}

    Exemplo inválido (NUNCA FAZER):
    {{
        "tipo": "Refeição 1"
    }}

    ---

    SAÍDA:
    Retorne apenas o JSON final válido.
  """.strip()


def montar_mensagem_conversao_json(prompt_conversao: str, texto_cardapio: str) -> str:
    return f"""
  {prompt_conversao}

  CONTEÚDO PARA CONVERTER:
  O texto abaixo deve ser convertido fielmente para o schema.
  NÃO invente informações novas.
  NÃO altere o significado.
  Apenas estruture corretamente.

  {texto_cardapio}
  """.strip()
