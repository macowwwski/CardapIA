# Como rodar o projeto

### 1. Pré-requisitos
- Python 3.11+;
- Docker Desktop rodando na máquina;
- Ter uma conta e chave do Ollama compatível com o modelo _gemma4:31b-cloud_;

### 2. Criar o ambiente virtual
Já dentro da pasta do projeto, rode os comandos: 
```
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configurar o arquivo .env
As informações mínimas necessárias são:
```
DATABASE_URL=postgresql://cardapia:cardapia@localhost:5433/cardapia
OLLAMA_HOST=https://api.ollama.com
OLLAMA_API_KEY=sua_chave
```

### 4. Subir o PostgreSQL no Docker
`docker compose up -d db`

### 5. Criar as tabelas do BD
Execute isso apenas no banco novo, zerado:
```
Get-Content db\schema.sql | docker compose exec -T db psql -U cardapia -d cardapia
Get-Content db\taco_final.sql | docker compose exec -T db psql -U cardapia -d cardapia
```

### 6. Importar os dados de per capita e vincular com a TACO
```
python helpers\importar_per_capita.py
python helpers\linkar_per_capita_taco.py
```

## Testando a configuração
### 1. Teste do banco de dados
O comando a seguir deve retornar uma lista dos alimentos na categoria "Frutas e derivados":
`python testes\test_tools.py`

### 2. Teste da geração de cardápio
Este comando devolverá, no terminal, o JSON de um cardápio para creche integral:
`python testes\test_creche_integral.py`

Para rodar o projeto outras vezes, é necessário criar um arquivo de especificações no mesmo estilo de _test_creche_integral_, pois ele simula os dados vindos do frontend.
