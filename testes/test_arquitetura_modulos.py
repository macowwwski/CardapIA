"""
Suíte de testes de arquitetura e integridade modular do CardapIA.

Valida que:
1. Todos os novos pacotes e submódulos são importáveis diretamente sem dependências circulares.
2. Todas as fachadas retrocompatíveis preservam as assinaturas e re-exportam seus símbolos.
3. O endpoint FastAPI de healthcheck e a inicialização da API continuam 100% íntegros.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_import_config():
    """Valida importação das configurações centralizadas."""
    from src import config
    assert hasattr(config, "DATABASE_URL")
    assert hasattr(config, "QDRANT_HOST")
    assert hasattr(config, "QDRANT_PORT")
    assert hasattr(config, "OLLAMA_MODEL")
    assert hasattr(config, "CAMINHO_PNAE_JSON")
    assert config.CAMINHO_PNAE_JSON.exists()


def test_import_taco_modular():
    """Valida módulo src.taco e submódulos."""
    from src.taco import (
        MatchTaco,
        resolver_taco,
        resolver_per_capita,
        SINONIMOS_TACO,
    )
    from src.taco.synonyms import SINONIMOS_TACO as SINONIMOS_DIRECT
    from src.taco.client import get_qdrant_client
    from src.taco.resolver import resolver_taco as RESOLVER_DIRECT

    assert callable(resolver_taco)
    assert callable(resolver_per_capita)
    assert isinstance(SINONIMOS_TACO, dict)
    assert len(SINONIMOS_TACO) > 30
    assert SINONIMOS_TACO == SINONIMOS_DIRECT
    assert resolver_taco == RESOLVER_DIRECT


def test_import_nutrition_modular():
    """Valida módulo src.nutrition e submódulos."""
    from src.nutrition import (
        validar_coerencia_culinaria,
        validar_cardapio_pnae,
        avaliar_status_cardapio,
        calcular_nutrientes_alimento,
        _classificar_alimento,
        _identificar_frutas,
    )
    from src.nutrition.classifier import FRUTAS_CONHECIDAS
    from src.nutrition.calculator import _dentro_intervalo, _somar_nutriente

    assert callable(validar_coerencia_culinaria)
    assert callable(validar_cardapio_pnae)
    assert callable(avaliar_status_cardapio)
    assert callable(calcular_nutrientes_alimento)
    assert "banana" in FRUTAS_CONHECIDAS
    assert _somar_nutriente(100.0, 50.0) == 50.0
    assert _dentro_intervalo(100.0, 95.0, 105.0)


def test_import_prompts_modular():
    """Valida módulo src.prompts e submódulos."""
    from src.prompts import (
        construir_contexto,
        REGRAS_PNAE,
        montar_prompt_geracao_cardapio,
        montar_prompt_correcao_cardapio,
        montar_prompt_conversao_json,
        montar_mensagem_conversao_json,
    )

    assert callable(construir_contexto)
    assert isinstance(REGRAS_PNAE, dict)
    assert "geral" in REGRAS_PNAE
    assert callable(montar_prompt_geracao_cardapio)
    assert callable(montar_prompt_correcao_cardapio)
    assert callable(montar_prompt_conversao_json)
    assert callable(montar_mensagem_conversao_json)


def test_import_services_modular():
    """Valida módulo src.services e submódulos."""
    from src.services import (
        gerar_cardapio,
        aplicar_per_capita,
        obter_per_capita,
        corrigir_estrutura,
        validar_cardapio,
    )

    assert callable(gerar_cardapio)
    assert callable(aplicar_per_capita)
    assert callable(obter_per_capita)
    assert callable(corrigir_estrutura)
    assert callable(validar_cardapio)


def test_import_repository():
    """Valida repositório de persistência do PostgreSQL."""
    from db.repository import salvar_cardapio_db
    from db.database import engine, SessionLocal

    assert callable(salvar_cardapio_db)
    assert engine is not None
    assert SessionLocal is not None


def test_retrocompatibilidade_fachadas():
    """Garante que nenhum import preexistente foi quebrado nas fachadas."""
    from src.ai_service import (
        gerar_cardapio,
        aplicar_per_capita,
        validar_coerencia_culinaria,
        validar_cardapio_pnae,
        avaliar_status_cardapio,
        CardapioSchema,
    )
    from src.taco_resolver import resolver_taco, resolver_per_capita, MatchTaco
    from src.prompt_builder import construir_contexto, REGRAS_PNAE
    from src.prompt_templates import (
        montar_prompt_geracao_cardapio,
        montar_prompt_correcao_cardapio,
    )

    assert callable(gerar_cardapio)
    assert callable(aplicar_per_capita)
    assert callable(validar_coerencia_culinaria)
    assert callable(validar_cardapio_pnae)
    assert callable(avaliar_status_cardapio)
    assert CardapioSchema is not None
    assert callable(resolver_taco)
    assert callable(resolver_per_capita)
    assert MatchTaco is not None
    assert callable(construir_contexto)
    assert isinstance(REGRAS_PNAE, dict)
    assert callable(montar_prompt_geracao_cardapio)
    assert callable(montar_prompt_correcao_cardapio)


def test_api_health_endpoint():
    """Valida o endpoint /health da API FastAPI."""
    from fastapi.testclient import TestClient
    from api_server import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "CardapIA"}


if __name__ == "__main__":
    testes = [
        ("Configuração centralizada", test_import_config),
        ("Módulo TACO e resolução semântica", test_import_taco_modular),
        ("Módulo Nutrição e PNAE", test_import_nutrition_modular),
        ("Módulo Prompts", test_import_prompts_modular),
        ("Módulo Serviços de Aplicação", test_import_services_modular),
        ("Repositório de Banco de Dados", test_import_repository),
        ("Retrocompatibilidade das Fachadas", test_retrocompatibilidade_fachadas),
        ("Endpoint /health do FastAPI", test_api_health_endpoint),
    ]

    print("=" * 70)
    print("EXECUTANDO TESTES DE ARQUITETURA E INTEGRIDADE MODULAR")
    print("=" * 70)
    falhas = 0
    for nome, fn in testes:
        try:
            fn()
            print(f"  [OK] {nome}")
        except Exception as e:
            falhas += 1
            print(f"  [FALHA] {nome}: {e}")
            import traceback
            traceback.print_exc()

    print("=" * 70)
    if falhas == 0:
        print(f"SUCESSO TOTAL: Todos os {len(testes)} testes de arquitetura passaram!")
    else:
        print(f"ERRO: {falhas} testes falharam.")
        sys.exit(1)
