import pandas as pd
import re
import difflib

# 1. Carregar os dados
per_capita_df = pd.read_csv('per_capita_export.csv')
taco_unmatched_df = pd.read_csv('taco_sem_per_capita_por_nome.csv')

# 2. Função para limpar e extrair a raiz do alimento
def limpar_nome(nome):
    nome = str(nome).lower()
    # Remove estados de preparo para facilitar o match com os alimentos crus
    termos_remover = [
        'cozido', 'cozida', 'assado', 'assada', 'frito', 'frita', 
        'grelhado', 'grelhada', 'cru', 'crua', 'com sal', 'sem sal',
        'tipo 1', 'tipo 2', 'enlatado', 'drenado'
    ]
    for termo in termos_remover:
        nome = re.sub(r'\b' + termo + r'\b', '', nome)
    nome = re.sub(r'[^\w\s]', ' ', nome)
    return re.sub(r'\s+', ' ', nome).strip()

# 3. Preparar dicionários de busca
per_capita_dict = {row['id']: row['nome_alimento'] for _, row in per_capita_df.iterrows()}
per_capita_clean_names = {row['id']: limpar_nome(row['nome_alimento']) for _, row in per_capita_df.iterrows()}

matches = []

# 4. Processar os alimentos da TACO sem correspondência
for _, taco_row in taco_unmatched_df.iterrows():
    taco_id = taco_row['id']
    taco_desc = taco_row['description']
    taco_clean = limpar_nome(taco_desc)
    
    best_match_id = None
    best_score = 0
    
    # Compara a similaridade das strings já limpas
    for pc_id, pc_clean in per_capita_clean_names.items():
        score = difflib.SequenceMatcher(None, taco_clean, pc_clean).ratio()
        if score > best_score:
            best_score = score
            best_match_id = pc_id
            
    # Filtro de Segurança: Só aceita se tiver mais de 75% de similaridade
    if best_score >= 0.75:
        matches.append({
            'taco_id': taco_id,
            'taco_descricao': taco_desc,
            'per_capita_id': best_match_id,
            'per_capita_nome': per_capita_dict[best_match_id],
            'confianca': round(best_score * 100, 2)
        })
    else:
        matches.append({
            'taco_id': taco_id,
            'taco_descricao': taco_desc,
            'per_capita_id': 'NENHUMA CORRESPONDÊNCIA SEGURA',
            'per_capita_nome': 'NENHUMA CORRESPONDÊNCIA SEGURA',
            'confianca': round(best_score * 100, 2)
        })

# 5. Exportar para análise manual
df_matches = pd.DataFrame(matches)
df_matches.to_csv('sugestao_mapeamento_taco_per_capita.csv', index=False, encoding='utf-8')

print("Mapeamento concluído! Verifique o arquivo 'sugestao_mapeamento_taco_per_capita.csv'.")