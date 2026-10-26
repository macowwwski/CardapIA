"""
Modelos de dados tipados para perfis nutricionais e pipelines do PNAE.

Representa os requisitos normativos da Resolução CD/FNDE nº 06/2020 de forma
estruturada, eliminando a dependência de dicionários genéricos e navegações frágeis.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass(frozen=True)
class IntervaloNutricional:
    """Intervalo de valores mínimo e máximo para um nutriente."""
    minimo: float
    maximo: float

    def contem(self, valor: float, tolerancia: float = 0.10) -> bool:
        """Verifica se o valor está dentro do intervalo considerando margem de tolerância."""
        piso = self.minimo * (1.0 - tolerancia)
        teto = self.maximo * (1.0 + tolerancia)
        return piso <= valor <= teto


@dataclass(frozen=True)
class ParametrosNutricionais:
    """Parâmetros e metas de energia e nutrientes para uma etapa e percentual do VET."""
    energia_kcal: float
    carboidratos_g: IntervaloNutricional
    proteinas_g: IntervaloNutricional
    lipidios_g: IntervaloNutricional
    # Micronutrientes aplicáveis especificamente à etapa Creche
    vitamina_a_mcg: Optional[float] = None
    vitamina_c_mg: Optional[float] = None
    calcio_mg: Optional[float] = None
    ferro_mg: Optional[float] = None


@dataclass(frozen=True)
class LimitesComposicao:
    """Limites máximos de adição de ingredientes críticos e sódio conforme a norma."""
    max_sodio_mg: float
    max_acucar_adicionado_pct: Optional[float] = 7.0
    max_gordura_saturada_pct: Optional[float] = 7.0
    gorduras_totais_pct: Optional[IntervaloNutricional] = IntervaloNutricional(15.0, 30.0)


@dataclass(frozen=True)
class MetasSemanais:
    """Metas de frequência e diversidade alimentar semanais (para semanas completas >= 4 dias)."""
    min_diversidade: int
    min_flv_g: float
    min_frutas_dias: int
    min_legumes_verduras_dias: int
    max_biscoito_semana: int
    max_doce_semana: Optional[int] = None
    max_margarina_semana: Optional[int] = None


@dataclass(frozen=True)
class FrequenciasMensais:
    """Limites máximos mensais de alimentos controlados pela Resolução CD/FNDE."""
    max_produtos_carneos: int = 2
    max_conservas: int = 1
    max_doces: int = 1
    max_liquidos_lacteos: int = 1


class PerfilIncompletoError(ValueError):
    """Levantada quando um perfil existente não possui configuração nutricional completa."""
    pass


class DistribuicaoNaoConfiguradaError(ValueError):
    """Levantada quando o perfil escolar não possui distribuição de refeições validada por responsável técnico."""
    pass


class DistribuicaoInvalidaError(ValueError):
    """Levantada quando os percentuais ou parâmetros de distribuição entre refeições são inconsistentes."""
    pass


class RefeicaoEsperadaAusenteError(ValueError):
    """Levantada quando uma refeição prevista na distribuição do perfil não é encontrada no dia."""
    pass


@dataclass(frozen=True)
class DistribuicaoRefeicao:
    """
    Configuração de participação de uma refeição individual nas metas do perfil.
    Define ordem, percentual de energia (quando validado normativamente),
    regras de porcionamento per capita e composição culinária esperada.
    """
    tipo_refeicao: str
    ordem: int
    percentual_energia: Optional[float] = None
    energia_kcal_alvo: Optional[float] = None
    composicao_esperada: List[str] = field(default_factory=list)
    regras_especificas: Dict[str, any] = field(default_factory=dict)
    ativo: bool = True


@dataclass(frozen=True)
class PerfilNutricional:
    """
    Especificação completa e imutável de um perfil de atendimento escolar no PNAE.
    Combina etapa de ensino, faixa etária, período e quantidade de refeições diárias.
    Separa a meta global diária da distribuição por refeição.
    """
    id_perfil: str
    etapa: str
    faixa_etaria: str
    periodo: str
    num_refeicoes: int
    percentual_atendimento: int
    percentual_label: str
    nutricao: ParametrosNutricionais
    limites: LimitesComposicao
    metas_semanais: MetasSemanais
    distribuicao_refeicoes: List[DistribuicaoRefeicao] = field(default_factory=list)
    frequencias_mensais: FrequenciasMensais = field(default_factory=FrequenciasMensais)
    alimentos_proibidos: List[str] = field(default_factory=list)
    refeicoes_esperadas: Dict[str, List[str]] = field(default_factory=dict)
    orientacoes_especificas: List[str] = field(default_factory=list)
    configuracao_normativa: str = "Resolução CD/FNDE nº 06/2020"
    ativo: bool = True

    def validar_distribuicao(self) -> None:
        """
        Valida a consistência entre o número de refeições do perfil e sua distribuição configurada.
        Garante que a soma dos percentuais de energia seja consistente com o percentual de atendimento.
        """
        if not self.distribuicao_refeicoes:
            raise DistribuicaoNaoConfiguradaError(
                f"Perfil '{self.id_perfil}' não possui distribuição de refeições validada por responsável técnico."
            )

        if len(self.distribuicao_refeicoes) != self.num_refeicoes:
            raise DistribuicaoInvalidaError(
                f"Perfil '{self.id_perfil}' exige {self.num_refeicoes} refeição(ões), "
                f"mas possui {len(self.distribuicao_refeicoes)} configurada(s)."
            )

        pcts = [d.percentual_energia for d in self.distribuicao_refeicoes if d.percentual_energia is not None]
        if len(pcts) == len(self.distribuicao_refeicoes):
            soma_pct = sum(pcts)
            esperado_pct = self.percentual_atendimento / 100.0
            if abs(soma_pct - esperado_pct) > 0.01:
                raise DistribuicaoInvalidaError(
                    f"Soma dos percentuais de energia da distribuição ({soma_pct:.2f}) "
                    f"diverge do percentual de atendimento do perfil ({esperado_pct:.2f}) no perfil '{self.id_perfil}'."
                )
