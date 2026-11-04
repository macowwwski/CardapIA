"""
Seletor determinístico de pipelines nutricionais especializados do PNAE.

Interpreta e normaliza o payload da requisição, valida a combinação de etapa,
faixa etária e quantidade de refeições, e instancia o pipeline especializado correspondente.
"""
from typing import Optional
from src.pipelines.registry import resolver_perfil
from src.pipelines.base import BasePipeline
from src.pipelines.especializados import (
    CrechePipeline,
    PreEscolaPipeline,
    EnsinoFundamentalPipeline,
    EnsinoMedioPipeline,
    EJAPipeline,
)


def selecionar_pipeline(
    etapa: str,
    faixa_etaria: str,
    periodo: Optional[str] = None,
    num_refeicoes: Optional[int] = None,
) -> BasePipeline:
    """
    Seleciona e instancia determinísticamente o pipeline especializado para os parâmetros informados.

    Levanta PerfilNaoSuportadoError com mensagem descritiva caso a combinação
    seja inválida ou não suportada pelas diretrizes oficiais do PNAE.
    """
    perfil = resolver_perfil(
        etapa=etapa,
        faixa_etaria=faixa_etaria,
        periodo=periodo,
        num_refeicoes=num_refeicoes,
    )

    mapeamento_classes = {
        "creche": CrechePipeline,
        "pre_escola": PreEscolaPipeline,
        "ensino_fundamental": EnsinoFundamentalPipeline,
        "ensino_medio": EnsinoMedioPipeline,
        "eja": EJAPipeline,
    }

    classe_pipeline = mapeamento_classes.get(perfil.etapa)
    if not classe_pipeline:
        classe_pipeline = BasePipeline

    return classe_pipeline(perfil)
