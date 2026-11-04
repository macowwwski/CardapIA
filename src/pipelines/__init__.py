"""
Módulo de pipelines especializados por perfil escolar do CardapIA (PNAE).
"""
from src.pipelines.models import (
    PerfilNutricional,
    ParametrosNutricionais,
    IntervaloNutricional,
    LimitesComposicao,
    MetasSemanais,
    FrequenciasMensais,
    DistribuicaoRefeicao,
    PerfilIncompletoError,
    DistribuicaoNaoConfiguradaError,
    DistribuicaoInvalidaError,
    RefeicaoEsperadaAusenteError,
)
from src.pipelines.registry import (
    resolver_perfil,
    PerfilNaoSuportadoError,
    CATALOGO_PERFIS,
)
from src.pipelines.base import BasePipeline
from src.pipelines.especializados import (
    CrechePipeline,
    PreEscolaPipeline,
    EnsinoFundamentalPipeline,
    EnsinoMedioPipeline,
    EJAPipeline,
)
from src.pipelines.selector import selecionar_pipeline

__all__ = [
    "PerfilNutricional",
    "ParametrosNutricionais",
    "IntervaloNutricional",
    "LimitesComposicao",
    "MetasSemanais",
    "FrequenciasMensais",
    "DistribuicaoRefeicao",
    "PerfilIncompletoError",
    "DistribuicaoNaoConfiguradaError",
    "DistribuicaoInvalidaError",
    "RefeicaoEsperadaAusenteError",
    "resolver_perfil",
    "PerfilNaoSuportadoError",
    "CATALOGO_PERFIS",
    "BasePipeline",
    "CrechePipeline",
    "PreEscolaPipeline",
    "EnsinoFundamentalPipeline",
    "EnsinoMedioPipeline",
    "EJAPipeline",
    "selecionar_pipeline",
]
