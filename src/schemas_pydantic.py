from enum import Enum
from pydantic import BaseModel, PrivateAttr


class IngredienteSchema(BaseModel):
    nome_taco: str
    quantidade_g: float
    # Preenchido pela resolução semântica (Qdrant); fora do schema enviado à LLM
    _taco_id: str | None = PrivateAttr(default=None)


class PratoSchema(BaseModel):
    nome: str
    estado_preparacao: str
    ingredientes: list[IngredienteSchema]


class TipoRefeicao(str, Enum):
    desjejum = "desjejum"
    almoco = "almoço"
    reforco = "reforço"
    lanche_tarde = "lanche da tarde"
    jantar = "jantar"


class RefeicaoSchema(BaseModel):
    tipo: TipoRefeicao
    horario: str
    pratos: list[PratoSchema]


class DiaSchema(BaseModel):
    dia_semana: str
    refeicoes: list[RefeicaoSchema]


class SemanaSchema(BaseModel):
    numero: int
    dias: list[DiaSchema]


class CardapioSchema(BaseModel):
    mes_aplicacao: str
    semanas: list[SemanaSchema]
    observacoes: str


class InconformidadePNAESchema(BaseModel):
    escopo: str
    regra: str
    detalhe: str
    tipo: str = "critico"  # "critico" | "advertencia" | "recomendacao"


class StatusValidacao(str, Enum):
    aprovado = "aprovado"
    pendente_revisao = "pendente_revisao"
    reprovado = "reprovado"


class RelatorioValidacaoSchema(BaseModel):
    status: StatusValidacao
    aprovado: bool
    total_criticos: int
    total_advertencias: int
    inconformidades: list[InconformidadePNAESchema]
    resumo: str


TIPOS_REFEICAO_PERMITIDOS = {tipo.value for tipo in TipoRefeicao}

ORDEM_TIPOS_REFEICAO = [
    TipoRefeicao.desjejum.value,
    TipoRefeicao.almoco.value,
    TipoRefeicao.reforco.value,
    TipoRefeicao.lanche_tarde.value,
    TipoRefeicao.jantar.value,
]
