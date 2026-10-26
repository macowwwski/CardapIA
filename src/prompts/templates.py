"""
Templates de prompts especializados para interação com a LLM.

Define os prompts para:
1. Geração textual inicial de cardápios escolares com regras culinárias rigorosas do PNAE.
2. Correção direcionada de inconformidades críticas identificadas pela auditoria.
3. Conversão de texto livre para JSON rigorosamente compatível com o CardapioSchema.
"""
import json
from src.schemas_pydantic import CardapioSchema


def montar_prompt_geracao_cardapio(
    contexto: str,
    total_dias: int | None = None,
    num_semanas: int = 1,
) -> str:
    """Monta o prompt do sistema para geração de cardápio escolar."""
    if total_dias and total_dias > 0:
        instrucao_escopo = f"- Planeje o cardápio para EXATAMENTE {total_dias} dia(s) letivo(s) solicitado(s). NÃO gere dias adicionais nem semanas extras."
    else:
        instrucao_escopo = f"- Planeje o cardápio para {num_semanas} semana(s) com 5 dias cada."

    return f"""
    Você é um nutricionista escolar especialista no PNAE (Programa Nacional de Alimentação Escolar).
    Sua função é planejar refeições escolares completas, saborosas, culinariamente coerentes e nutricionalmente adequadas.

    DIRETRIZES DE COMPOSIÇÃO CULINÁRIA (OBRIGATÓRIO):
    1. ESTRUTURA DE REFEIÇÃO PRINCIPAL (Almoço ou Jantar):
       Cada refeição principal DEVE ser composta por pratos que harmonizem entre si, contendo:
       - 1 Base de Energia (Cereal ou Tubérculo): arroz (branco ou integral), macarrão, mandioca/aipim, batata, polenta/fubá, etc. Escolha APENAS UM cereal ou tubérculo principal por refeição. NUNCA misture dois amidos na mesma refeição (ex: NUNCA coloque macarrão com batata ou arroz com macarrão juntos).
       - 1 Leguminosa: feijão (carioca, preto, fradinho) ou lentilha.
       - 1 Prato Proteico Principal: preparação com carne bovina, frango, peixe ou ovos (ex: frango ensopado com legumes, carne moída refogada, iscas de carne, filé de peixe assado). NUNCA deixe nenhuma refeição principal sem carne/proteína animal (100% dos dias letivos). NUNCA sirva duas fontes de carne diferentes na mesma refeição.
       - 1 Hortaliça/Legume: salada crua (alface, tomate, cenoura ralada, repolho) OU legume cozido/refogado (abobrinha, chuchu, beterraba, couve).
       - Sobremesa: NO MÁXIMO UMA fruta in natura (ex: banana, maçã, laranja, melancia).
       * REGRA CRÍTICA: É TERMINANTEMENTE PROIBIDO colocar múltiplas frutas diferentes na mesma refeição (ex: nada de banana + maçã + manga juntos). A sobremesa tem no máximo UMA única fruta!

    2. ESTRUTURA DE REFEIÇÃO LEVE (Desjejum, Lanche da Tarde, Reforço):
       - 1 Bebida ou Líquido nutritivo: leite integral (puro ou com cacau 100%), iogurte natural, vitamina de fruta, ou suco natural da fruta sem açúcar.
       - 1 Alimento à base de cereal/farináceo: pão (integral ou caseiro), biscoito simples (respeitando limites semanais), bolo simples caseiro ou cuscuz de milho.
       - Opcionalmente: NO MÁXIMO 1 fruta in natura.

    3. VARIEDADE PLANEJADA AO LONGO DA SEMANA (5 DIAS):
       - A diversidade de alimentos deve ser distribuída ao longo dos dias da semana, e NÃO concentrada no mesmo dia.
       - Alterne as fontes proteicas principais a cada dia (ex: Segunda: Frango; Terça: Carne bovina; Quarta: Ovos ou Peixe; Quinta: Carne suína ou Frango; Sexta: Carne bovina). NÃO repita o mesmo prato proteico em dias consecutivos.
       - Alterne as frutas ao longo dos 5 dias (ex: Segunda: Banana; Terça: Maçã; Quarta: Laranja; Quinta: Mamão; Sexta: Melancia).
       - Respeite rigorosamente todas as restrições alimentares informadas para a turma.

    4. CONTROLE DE GORDURAS, ÓLEOS E TEMPEROS (MÁXIMO 1 PORÇÃO DE ÓLEO POR REFEIÇÃO):
       - Gorduras de preparo (azeite de oliva, óleo vegetal): utilize NO MÁXIMO 1 única porção de óleo ou azeite (8g a 10g) no TOTAL da refeição inteira.
       - É TERMINANTEMENTE PROIBIDO adicionar azeite ou óleo em múltiplos pratos da mesma refeição (ex: NUNCA coloque azeite no arroz + azeite no feijão + azeite na salada). Isso triplica a gordura e estoura o limite crítico de lipídios do PNAE (15 a 21g no Ensino Médio).
       - Não repita o mesmo ingrediente de tempero (como alho, cebola, azeite) repetidas vezes na lista da mesma refeição.
       - CONTROLE DE SÓDIO: NUNCA adicione sal de cozinha em refeições que já contenham queijo branco ou ingredientes salgados. O limite de sódio não pode ultrapassar 600 mg.
       - Não liste limão in natura avulso como prato principal de almoço (utilize apenas como tempero ou molho se aplicável).

    5. EQUILÍBRIO DE MACRONUTRIENTES E ENERGIA:
       - A energia da refeição deve provir prioritariamente de carboidratos complexos (arroz, feijão, milho, macarrão, tubérculos) para atingir com segurança a meta do PNAE (75g a 88g no Ensino Médio), sem tentar suprir calorias inflando gorduras/óleos.
       - A carne bovina, ave ou peixe já contribui com 4g a 6g de gordura natural. Com 1 única porção de 8g a 10g de azeite/óleo de preparo, a refeição fecha perfeitamente na meta de 15g a 21g de lipídios.

    DIRETRIZES NUTRICIONAIS E REGRAS DO PNAE:
    {contexto}

    INSTRUÇÕES DE FORMATAÇÃO:
    {instrucao_escopo}
    - Organize de forma clara por semanas, dias e refeições, listando os pratos e ingredientes de cada preparação.
    - NÃO gere JSON
    - NÃO use formatação técnica
    - Apenas texto estruturado e organizado
    """.strip()


def montar_prompt_correcao_cardapio(
    texto_cardapio: str,
    inconsistencias: list[str],
) -> str:
    """Monta o prompt para correção focada de inconsistências críticas."""
    lista_erros = "\n".join(f"- {erro}" for erro in inconsistencias)
    return f"""
    Você é um nutricionista escolar revisando um cardápio do PNAE.
    O cardápio gerado anteriormente apresentou as seguintes inconformidades que violam regras culinárias ou do PNAE:

    PROBLEMAS IDENTIFICADOS:
    {lista_erros}

    INSTRUÇÕES DE CORREÇÃO:
    - Corrija APENAS as refeições problemáticas apontadas acima.
    - Mantenha inalteradas as refeições que já estavam corretas.
    - Garanta que cada refeição principal tenha no máximo 1 fruta como sobremesa.
    - Garanta a presença de cereal/tubérculo e prato proteico no almoço/jantar.
    - Se houver excesso de lipídios (gorduras), limite o azeite/óleo a no máximo 1 porção de 8g a 10g no total de toda a refeição e remova azeites/óleos duplicados nos acompanhamentos.
    - Se faltar carboidratos, reforce a base de cereal (arroz, macarrão), leguminosa (feijão) ou tubérculo para atingir a meta estipulada sem inflar gordura.
    - Remova qualquer ingrediente proibido ou restrito.
    - Retorne o texto completo do cardápio corrigido no mesmo formato textual anterior (SEM JSON).

    CARDÁPIO ORIGINAL:
    {texto_cardapio}
    """.strip()


def montar_prompt_conversao_json() -> str:
    """Monta as instruções do sistema para parser em JSON estruturado."""
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

    4. REGRA OBRIGATÓRIA PARA OS INGREDIENTES DOS PRATOS (DECOMPOSIÇÃO EM ALIMENTOS BÁSICOS TACO):
        - No campo "ingredientes" de cada prato, liste SEMPRE os alimentos básicos individuais da Tabela TACO.
        - NUNCA repita o nome composto ou culinário do prato como ingrediente único!
        - Exemplos corretos de decomposição:
          * Prato "Macarrão alho e óleo" -> ingredientes: [{{"nome_taco": "Macarrão", "quantidade_g": 0.0}}]
          * Prato "Carne moída com milho" -> ingredientes: [{{"nome_taco": "Carne moída", "quantidade_g": 0.0}}, {{"nome_taco": "Milho verde", "quantidade_g": 0.0}}]
          * Prato "Frango ensopado com batata" -> ingredientes: [{{"nome_taco": "Peito de frango", "quantidade_g": 0.0}}, {{"nome_taco": "Batata", "quantidade_g": 0.0}}]
          * Prato "Polenta cremosa" -> ingredientes: [{{"nome_taco": "Fubá de milho", "quantidade_g": 0.0}}]
          * Prato "Salada de alface e tomate" -> ingredientes: [{{"nome_taco": "Alface", "quantidade_g": 0.0}}, {{"nome_taco": "Tomate", "quantidade_g": 0.0}}]
        - Use sempre nomes simples e diretos de alimentos da alimentação escolar (ex: arroz, feijão, carne bovina, frango, peixe, ovo, batata, cenoura, alface, banana, maçã).

    5. Todos os campos obrigatórios devem estar presentes.

    6. Tipos devem ser respeitados:
        - números como números (ex: 0.0)
        - strings como strings
        - listas como listas

    7. Antes de responder, execute esta validação mental:
        - O JSON está válido?
        - Todos os enums estão corretos?
        - Os pratos foram decompostos em ingredientes básicos simples?
        - Se houver erro, CORRIJA antes de responder

    8. Se estiver em dúvida entre gerar algo inválido ou corrigir, sempre CORRIJA.

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
    """Monta a mensagem de usuário contendo o texto a ser convertido para JSON."""
    return f"""
  {prompt_conversao}

  CONTEÚDO PARA CONVERTER:
  O texto abaixo deve ser convertido fielmente para o schema.
  NÃO invente informações novas.
  NÃO altere o significado.
  Apenas estruture corretamente.

  {texto_cardapio}
    """.strip()
