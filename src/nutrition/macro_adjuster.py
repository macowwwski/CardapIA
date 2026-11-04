"""
Módulo de otimização matemática determinística para Valor Energético Total (VET)
e macronutrientes do Programa Nacional de Alimentação Escolar (PNAE).

Audita o cardápio gerado e aplica microajustes proporcionais nas gramaturas dos alimentos
base da refeição (arroz/tubérculos para carboidratos, carnes/leguminosas para proteínas
e óleos/azeites para lipídios), respeitando pisos e tetos pedagógicos e gastronômicos
estipulados por faixa etária (Resolução CD/FNDE nº 06/2020).
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any
from sqlalchemy.orm import Session

from src.schemas_pydantic import CardapioSchema, DiaSchema, IngredienteSchema
from src.pipelines.models import PerfilNutricional
from src.nutrition.classifier import _texto_normalizado
from db.models import Taco
from db.database import engine


# =========================================================================
# 1. Estruturas de Dados do Ajuste Nutricional
# =========================================================================

@dataclass
class StatusMacronutrientesDia:
    """Diagnóstico do VET e distribuição percentual calórica dos macronutrientes no dia."""
    energia_kcal: float
    carboidratos_g: float
    proteinas_g: float
    lipidios_g: float
    pct_carboidratos: float   # % do VET (kcal)
    pct_proteinas: float      # % do VET (kcal)
    pct_lipidios: float       # % do VET (kcal)
    delta_vet: float          # VET_meta - energia_kcal
    delta_carbo_g: float      # Carbo_alvo - carboidratos_g
    delta_proteina_g: float   # Prot_alvo - proteinas_g
    delta_lipidio_g: float    # Lip_alvo - lipidios_g
    dentro_margem_vet: bool
    dentro_faixas_macros: bool


@dataclass(frozen=True)
class LimitesGramaturaPorFaixa:
    """Pisos e tetos pedagógicos e gastronômicos por refeição/dia por faixa etária."""
    piso_amido_g: float
    teto_amido_g: float
    piso_leguminosa_g: float
    teto_leguminosa_g: float
    piso_proteina_g: float
    teto_proteina_g: float
    piso_oleo_g: float
    teto_oleo_g: float


@dataclass
class RelatorioAjusteNutricional:
    """Relatório comparativo pré e pós-otimização determinística."""
    status_inicial: Dict[str, StatusMacronutrientesDia] = field(default_factory=dict)
    status_final: Dict[str, StatusMacronutrientesDia] = field(default_factory=dict)
    ajustes_realizados: List[dict] = field(default_factory=list)
    media_calorica_inicial: float = 0.0
    media_calorica_final: float = 0.0
    meta_vet: float = 0.0
    convergido: bool = False


# =========================================================================
# 2. Pisos e Tetos Pedagógicos/Gastronômicos por Faixa Etária
# =========================================================================

LIMITES_POR_FAIXA: Dict[str, LimitesGramaturaPorFaixa] = {
    "creche_7_11_meses": LimitesGramaturaPorFaixa(
        piso_amido_g=8.0, teto_amido_g=50.0,
        piso_leguminosa_g=8.0, teto_leguminosa_g=32.0,
        piso_proteina_g=5.0, teto_proteina_g=15.0,
        piso_oleo_g=1.0, teto_oleo_g=4.5,
    ),
    "creche_1_3_anos": LimitesGramaturaPorFaixa(
        piso_amido_g=25.0, teto_amido_g=70.0,
        piso_leguminosa_g=12.0, teto_leguminosa_g=35.0,
        piso_proteina_g=10.0, teto_proteina_g=30.0,
        piso_oleo_g=1.5, teto_oleo_g=5.5,
    ),
    "pre_escola_4_5_anos": LimitesGramaturaPorFaixa(
        piso_amido_g=40.0, teto_amido_g=95.0,
        piso_leguminosa_g=20.0, teto_leguminosa_g=55.0,
        piso_proteina_g=15.0, teto_proteina_g=45.0,
        piso_oleo_g=2.0, teto_oleo_g=8.5,
    ),
    "ensino_fundamental_6_10_anos": LimitesGramaturaPorFaixa(
        piso_amido_g=55.0, teto_amido_g=140.0,
        piso_leguminosa_g=25.0, teto_leguminosa_g=75.0,
        piso_proteina_g=18.0, teto_proteina_g=55.0,
        piso_oleo_g=3.0, teto_oleo_g=11.0,
    ),
    "ensino_fundamental_11_15_anos": LimitesGramaturaPorFaixa(
        piso_amido_g=75.0, teto_amido_g=175.0,
        piso_leguminosa_g=35.0, teto_leguminosa_g=95.0,
        piso_proteina_g=22.0, teto_proteina_g=70.0,
        piso_oleo_g=4.0, teto_oleo_g=13.0,
    ),
    "ensino_medio_16_18_anos": LimitesGramaturaPorFaixa(
        piso_amido_g=85.0, teto_amido_g=210.0,
        piso_leguminosa_g=40.0, teto_leguminosa_g=110.0,
        piso_proteina_g=25.0, teto_proteina_g=80.0,
        piso_oleo_g=4.5, teto_oleo_g=15.0,
    ),
    "eja_19_30_anos": LimitesGramaturaPorFaixa(
        piso_amido_g=80.0, teto_amido_g=200.0,
        piso_leguminosa_g=40.0, teto_leguminosa_g=110.0,
        piso_proteina_g=25.0, teto_proteina_g=75.0,
        piso_oleo_g=4.0, teto_oleo_g=14.0,
    ),
    "eja_31_60_anos": LimitesGramaturaPorFaixa(
        piso_amido_g=80.0, teto_amido_g=200.0,
        piso_leguminosa_g=40.0, teto_leguminosa_g=110.0,
        piso_proteina_g=25.0, teto_proteina_g=75.0,
        piso_oleo_g=4.0, teto_oleo_g=14.0,
    ),
}


def _resolver_limites_faixa(etapa: str, faixa_etaria: str) -> LimitesGramaturaPorFaixa:
    """Retorna os limites pedagógicos/gastronômicos calibrados para a etapa e faixa etária."""
    chave = f"{_texto_normalizado(etapa)}_{_texto_normalizado(faixa_etaria)}"
    if chave in LIMITES_POR_FAIXA:
        return LIMITES_POR_FAIXA[chave]

    etapa_norm = _texto_normalizado(etapa)
    faixa_norm = _texto_normalizado(faixa_etaria)

    if "creche" in etapa_norm or "bercario" in etapa_norm or "maternal" in etapa_norm:
        if "7" in faixa_norm or "11" in faixa_norm or "mes" in faixa_norm:
            return LIMITES_POR_FAIXA["creche_7_11_meses"]
        return LIMITES_POR_FAIXA["creche_1_3_anos"]
    elif "pre" in etapa_norm or "infantil" in etapa_norm:
        return LIMITES_POR_FAIXA["pre_escola_4_5_anos"]
    elif "fundamental" in etapa_norm:
        if "11" in faixa_norm or "15" in faixa_norm or "2" in faixa_norm:
            return LIMITES_POR_FAIXA["ensino_fundamental_11_15_anos"]
        return LIMITES_POR_FAIXA["ensino_fundamental_6_10_anos"]
    elif "medio" in etapa_norm:
        return LIMITES_POR_FAIXA["ensino_medio_16_18_anos"]
    elif "eja" in etapa_norm:
        if "31" in faixa_norm or "60" in faixa_norm:
            return LIMITES_POR_FAIXA["eja_31_60_anos"]
        return LIMITES_POR_FAIXA["eja_19_30_anos"]

    # Fallback seguro: Ensino Fundamental 1
    return LIMITES_POR_FAIXA["ensino_fundamental_6_10_anos"]


# =========================================================================
# 3. Referência Nutricional dos Alimentos (Tabela TACO Oficial)
# =========================================================================

def _obter_dados_nutricionais_100g(
    nome: str,
    taco_cache: Optional[Dict[str, Any]] = None,
    session: Optional[Session] = None,
    taco_id: Optional[str] = None,
) -> Dict[str, float]:
    """
    Retorna energia_kcal, carboidratos, proteins e lipids por 100g do alimento
    consultando exclusivamente os dados oficiais da Tabela TACO (PostgreSQL ou Qdrant).

    Caso o alimento não seja localizado ou não possua dados cadastrados, retorna 0.0
    sem aplicar nenhuma estimativa, média ou densidade estática hardcoded.
    """
    taco = None
    nome_norm = _texto_normalizado(nome)

    # 1. Busca em cache em lote (por taco_id, nome original ou normalizado)
    if taco_cache:
        if taco_id and str(taco_id) in taco_cache:
            taco = taco_cache[str(taco_id)]
        elif nome in taco_cache:
            taco = taco_cache[nome]
        elif nome_norm in taco_cache:
            taco = taco_cache[nome_norm]

    # 2. Busca no PostgreSQL se ainda não localizado no cache
    if not taco and session:
        try:
            if taco_id:
                taco = session.query(Taco).filter(Taco.id == taco_id, Taco.deleted_at == None).first()
            if not taco:
                from src.nutrition.calculator import buscar_taco_por_nome
                taco = buscar_taco_por_nome(session, nome)
        except Exception:
            taco = None

    # 3. Contingência via base oficial indexada no Qdrant
    payload_oficial = None
    if not taco:
        try:
            from src.taco.resolver import resolver_taco
            match = resolver_taco(nome)
            if match and match.payload:
                payload_oficial = match.payload
        except Exception:
            payload_oficial = None

    if not taco and not payload_oficial:
        return {"energia_kcal": 0.0, "carboidratos": 0.0, "proteins": 0.0, "lipids": 0.0}

    if taco:
        if isinstance(taco, dict):
            energia = float(taco.get("energy_kcal") or 0.0)
            carbo = float(taco.get("carbohydrates") or 0.0)
            prot = float(taco.get("proteins") or 0.0)
            lip = float(taco.get("lipids") or 0.0)
        else:
            energia = float(taco.energy_kcal or 0.0)
            carbo = float(taco.carbohydrates or 0.0)
            prot = float(taco.proteins or 0.0)
            lip = float(taco.lipids or 0.0)
    else:
        energia = float(payload_oficial.get("energy_kcal") or 0.0)
        carbo = float(payload_oficial.get("carbohydrates") or 0.0)
        prot = float(payload_oficial.get("proteins") or 0.0)
        lip = float(payload_oficial.get("lipids") or 0.0)

    # Cálculo oficial de VET via Fatores Atwater da FAO (norma técnica do PNAE):
    # Se a energia vier zerada/nula na base mas houver macronutrientes medidos
    if energia <= 0.0 and (carbo > 0.0 or prot > 0.0 or lip > 0.0):
        energia = round(carbo * 4.0 + prot * 4.0 + lip * 9.0, 2)

    return {
        "energia_kcal": round(energia, 2),
        "carboidratos": round(carbo, 2),
        "proteins": round(prot, 2),
        "lipids": round(lip, 2),
    }


# =========================================================================
# 4. Classificação Funcional dos Alimentos via Categoria Oficial da TACO
# =========================================================================

def obter_categoria_taco(
    nome: str,
    taco_id: Optional[str] = None,
    taco_cache: Optional[Dict[str, Any]] = None,
    session: Optional[Session] = None,
) -> Optional[str]:
    """Retorna a categoria oficial cadastrada na base TACO (PostgreSQL ou Qdrant)."""
    taco = None
    nome_norm = _texto_normalizado(nome)

    if taco_cache:
        if taco_id and str(taco_id) in taco_cache:
            taco = taco_cache[str(taco_id)]
        elif nome in taco_cache:
            taco = taco_cache[nome]
        elif nome_norm in taco_cache:
            taco = taco_cache[nome_norm]

    if not taco and session:
        try:
            if taco_id:
                taco = session.query(Taco).filter(Taco.id == taco_id, Taco.deleted_at == None).first()
            if not taco:
                from src.nutrition.calculator import buscar_taco_por_nome
                taco = buscar_taco_por_nome(session, nome)
        except Exception:
            taco = None

    if not taco:
        try:
            from src.taco.resolver import resolver_taco
            match = resolver_taco(nome)
            if match and match.payload:
                return match.payload.get("category")
        except Exception:
            pass

    if taco:
        if isinstance(taco, dict):
            return taco.get("category")
        return getattr(taco, "category", None)

    return None


def _classificar_categoria_taco(categoria: Optional[str], nome: str = "") -> str:
    """Classifica o alimento a partir de sua categoria oficial da TACO."""
    nome_norm = _texto_normalizado(nome)
    eh_tuberculo_raiz = any(t in nome_norm for t in ("batat", "mandioc", "aipim", "macaxeir", "inhame", "cara", "polvilho", "fecula", "farinha", "pure"))

    if categoria:
        cat_norm = _texto_normalizado(categoria)
        if "gordura" in cat_norm or "oleo" in cat_norm:
            return "oleo"
        if any(p in cat_norm for p in ("carne", "pescad", "ovo")):
            return "proteina"
        if "leguminosa" in cat_norm:
            return "leguminosa"
        if "cereal" in cat_norm or eh_tuberculo_raiz:
            return "amido"
        if any(h in cat_norm for h in ("verdura", "hortalica", "legume")):
            return "amido" if eh_tuberculo_raiz else "hortalica"
        if "fruta" in cat_norm:
            return "fruta"

    # Fallback se não houver categoria no banco
    if any(t in nome_norm for t in ("azeite", "oleo", "gordura", "manteiga", "margarina")) and not any(c in nome_norm for c in ("macarra", "arroz", "batat", "mandioc", "carne", "frang", "peix", "ovo", "salada", "legum")):
        return "oleo"
    if any(t in nome_norm for t in ("frango", "galinha", "carne", "bovina", "boi", "patinho", "acem", "alcatra", "peixe", "tilapia", "pescada", "merluza", "sardinha", "atum", "suina", "porco", "lombo", "pernil", "ovo", "ovos", "omelete", "musculo", "coxa", "sobrecoxa", "peito", "file", "figado", "almondega", "isca", "bife")):
        return "proteina"
    if any(t in nome_norm for t in ("feijao", "lentilha", "grao de bico", "grao-de-bico", "ervilha")):
        return "leguminosa"
    if any(t in nome_norm for t in ("arroz", "macarrao", "espaguete", "mandioca", "aipim", "macaxeira", "batata", "mandioquinha", "polenta", "fuba", "cuscuz", "milho", "inhame", "cara", "aveia", "pao", "torrada", "farinha", "tapioca", "pure")):
        return "amido"
    return "outro"


# =========================================================================
# 5. Cálculo do VET e Percentuais de Macronutrientes do Dia
# =========================================================================

def auditar_vet_e_macros(
    dia: DiaSchema,
    perfil: PerfilNutricional,
    taco_cache: Optional[Dict[str, Any]] = None,
    session: Optional[Session] = None,
) -> StatusMacronutrientesDia:
    """
    Calcula o VET total e a distribuição percentual calórica dos macronutrientes do dia,
    comparando contra os parâmetros normativos do perfil escolar.
    """
    sessao_local = None
    if session is None and not taco_cache:
        try:
            sessao_local = Session(engine)
            session = sessao_local
        except Exception:
            session = None

    try:
        totais = {"energia_kcal": 0.0, "carboidratos_g": 0.0, "proteinas_g": 0.0, "lipidios_g": 0.0}

        for refeicao in dia.refeicoes:
            for prato in refeicao.pratos:
                for ing in prato.ingredientes:
                    if not ing.quantidade_g or ing.quantidade_g <= 0:
                        continue
                    taco_id = getattr(ing, "_taco_id", None)
                    dens = _obter_dados_nutricionais_100g(
                        ing.nome_taco or prato.nome,
                        taco_cache=taco_cache,
                        session=session,
                        taco_id=taco_id,
                    )
                    fator = ing.quantidade_g / 100.0
                    totais["energia_kcal"] += dens["energia_kcal"] * fator
                    totais["carboidratos_g"] += dens["carboidratos"] * fator
                    totais["proteinas_g"] += dens["proteins"] * fator
                    totais["lipidios_g"] += dens["lipids"] * fator
    finally:
        if sessao_local is not None:
            sessao_local.close()

    vet_real = totais["energia_kcal"]
    c_g = totais["carboidratos_g"]
    p_g = totais["proteinas_g"]
    l_g = totais["lipidios_g"]

    # Fatores Atwater: Carbo 4 kcal/g, Proteína 4 kcal/g, Lipídios 9 kcal/g
    # Para o percentual do VET, usamos o VET real calculado
    divisor_vet = vet_real if vet_real > 0 else 1.0
    pct_c = (c_g * 4.0 / divisor_vet) * 100.0
    pct_p = (p_g * 4.0 / divisor_vet) * 100.0
    pct_l = (l_g * 9.0 / divisor_vet) * 100.0

    p_nutri = perfil.nutricao
    vet_meta = p_nutri.energia_kcal

    # Alvos em gramas (centro das faixas do perfil)
    c_alvo = (p_nutri.carboidratos_g.minimo + p_nutri.carboidratos_g.maximo) / 2.0
    p_alvo = (p_nutri.proteinas_g.minimo + p_nutri.proteinas_g.maximo) / 2.0
    l_alvo = (p_nutri.lipidios_g.minimo + p_nutri.lipidios_g.maximo) / 2.0

    delta_vet = round(vet_meta - vet_real, 2)
    delta_carbo_g = round(c_alvo - c_g, 2)
    delta_proteina_g = round(p_alvo - p_g, 2)
    delta_lipidio_g = round(l_alvo - l_g, 2)

    # Margem de tolerância de 10% no VET conforme praxe de auditoria do PNAE
    dentro_vet = (vet_meta * 0.90) <= vet_real <= (vet_meta * 1.10)

    # Faixas percentuais do PNAE (Resolução CD/FNDE nº 06/2020):
    # Carbo: 55% a 65% (tolerância 50% a 70%)
    # Proteína: 10% a 15% (tolerância 9% a 17%)
    # Lipídios: 15% a 30% (ou 35% para creche, tolerância 14% a 36%)
    teto_lip_pct = 35.0 if "creche" in _texto_normalizado(perfil.etapa) else 30.0
    dentro_faixas_macros = (
        (50.0 <= pct_c <= 70.0)
        and (9.0 <= pct_p <= 17.0)
        and (14.0 <= pct_l <= (teto_lip_pct + 2.0))
        and p_nutri.carboidratos_g.contem(c_g, tolerancia=0.10)
        and p_nutri.proteinas_g.contem(p_g, tolerancia=0.10)
        and p_nutri.lipidios_g.contem(l_g, tolerancia=0.10)
    )

    return StatusMacronutrientesDia(
        energia_kcal=round(vet_real, 1),
        carboidratos_g=round(c_g, 1),
        proteinas_g=round(p_g, 1),
        lipidios_g=round(l_g, 1),
        pct_carboidratos=round(pct_c, 1),
        pct_proteinas=round(pct_p, 1),
        pct_lipidios=round(pct_l, 1),
        delta_vet=delta_vet,
        delta_carbo_g=delta_carbo_g,
        delta_proteina_g=delta_proteina_g,
        delta_lipidio_g=delta_lipidio_g,
        dentro_margem_vet=dentro_vet,
        dentro_faixas_macros=dentro_faixas_macros,
    )


# =========================================================================
# 6. Otimizador Determinístico com Microajustes Bounded
# =========================================================================

def _ajustar_dia_macronutrientes(
    dia: DiaSchema,
    perfil: PerfilNutricional,
    limites: LimitesGramaturaPorFaixa,
    taco_cache: Optional[Dict[str, Taco]] = None,
    session: Optional[Session] = None,
    max_iteracoes: int = 5,
) -> Tuple[DiaSchema, List[dict]]:
    """
    Aplica microajustes proporcionais nas gramaturas dos alimentos base de um dia,
    convergindo deterministicamente para o VET e faixas de macronutrientes do PNAE.
    """
    ajustes_realizados = []
    p_nutri = perfil.nutricao
    vet_meta = p_nutri.energia_kcal

    # Alvos em gramas
    c_alvo = (p_nutri.carboidratos_g.minimo + p_nutri.carboidratos_g.maximo) / 2.0
    p_alvo = (p_nutri.proteinas_g.minimo + p_nutri.proteinas_g.maximo) / 2.0
    l_alvo = (p_nutri.lipidios_g.minimo + p_nutri.lipidios_g.maximo) / 2.0

    for _ in range(max_iteracoes):
        status = auditar_vet_e_macros(dia, perfil, taco_cache=taco_cache, session=session)
        diff_vet_pct = abs(status.delta_vet) / (vet_meta if vet_meta > 0 else 1.0)
        if diff_vet_pct <= 0.04 and status.dentro_faixas_macros:
            break

        # Identifica alimentos base elegíveis para microajustes no dia
        itens_oleo: List[IngredienteSchema] = []
        itens_proteina: List[IngredienteSchema] = []
        itens_leguminosa: List[IngredienteSchema] = []
        itens_amido: List[IngredienteSchema] = []

        for refeicao in dia.refeicoes:
            for prato in refeicao.pratos:
                for ing in prato.ingredientes:
                    if not ing.quantidade_g or ing.quantidade_g <= 0:
                        continue
                    cat_ing = obter_categoria_taco(ing.nome_taco, ing._taco_id, taco_cache, session)
                    tipo_ing = _classificar_categoria_taco(cat_ing, ing.nome_taco or "")
                    if tipo_ing == "oleo":
                        itens_oleo.append(ing)
                    elif tipo_ing == "proteina":
                        itens_proteina.append(ing)
                    elif tipo_ing == "leguminosa":
                        itens_leguminosa.append(ing)
                    elif tipo_ing == "amido":
                        itens_amido.append(ing)
                    elif prato.nome and len(prato.ingredientes) == 1:
                        cat_prato = obter_categoria_taco(prato.nome, ing._taco_id, taco_cache, session)
                        tipo_prato = _classificar_categoria_taco(cat_prato, prato.nome)
                        if tipo_prato == "oleo":
                            itens_oleo.append(ing)
                        elif tipo_prato == "proteina":
                            itens_proteina.append(ing)
                        elif tipo_prato == "leguminosa":
                            itens_leguminosa.append(ing)
                        elif tipo_prato == "amido":
                            itens_amido.append(ing)

        # -------------------------------------------------------------
        # 1. Microajuste de Lipídios (Óleo/Azeite de Preparo)
        # Densidade lipídica real obtida da base oficial TACO
        # -------------------------------------------------------------
        if itens_oleo:
            delta_l = l_alvo - status.lipidios_g
            if abs(delta_l) > 0.5:
                densidades_oleo = []
                for item in itens_oleo:
                    d = _obter_dados_nutricionais_100g(
                        item.nome_taco,
                        taco_cache=taco_cache,
                        session=session,
                        taco_id=getattr(item, "_taco_id", None),
                    )
                    densidades_oleo.append((d["lipids"] / 100.0) if d["lipids"] > 0 else 1.0)

                media_dens_lip = sum(densidades_oleo) / len(densidades_oleo) if densidades_oleo else 1.0
                ajuste_por_item = (delta_l / media_dens_lip) / len(itens_oleo)
                for item in itens_oleo:
                    qtd_antiga = item.quantidade_g
                    nova_qtd = max(limites.piso_oleo_g, min(limites.teto_oleo_g, qtd_antiga + ajuste_por_item))
                    item.quantidade_g = round(nova_qtd, 1)
                    if abs(item.quantidade_g - qtd_antiga) >= 0.1:
                        ajustes_realizados.append({
                            "alimento": item.nome_taco,
                            "tipo": "gordura",
                            "anterior_g": qtd_antiga,
                            "novo_g": item.quantidade_g,
                        })

        # -------------------------------------------------------------
        # 2. Microajuste de Proteínas (Carnes, Peixes, Ovos e Leguminosas)
        # Densidade proteica real calculada a partir do registro oficial TACO de cada alimento
        # -------------------------------------------------------------
        if itens_proteina:
            status_meio = auditar_vet_e_macros(dia, perfil, taco_cache=taco_cache, session=session)
            delta_p = p_alvo - status_meio.proteinas_g
            if abs(delta_p) > 0.5:
                densidades_prot = []
                for item in itens_proteina:
                    d = _obter_dados_nutricionais_100g(
                        item.nome_taco,
                        taco_cache=taco_cache,
                        session=session,
                        taco_id=getattr(item, "_taco_id", None),
                    )
                    densidades_prot.append((d["proteins"] / 100.0) if d["proteins"] > 0 else 0.0)

                validos = [(it, dp) for it, dp in zip(itens_proteina, densidades_prot) if dp > 0.05]
                if validos:
                    delta_p_item = delta_p / len(validos)
                    # Quando há excesso de proteína (delta_p < 0), permite que a carne reduza até o piso necessário para proteger o teto PNAE
                    piso_base = limites.piso_proteina_g if delta_p >= 0 else max(6.0, limites.piso_proteina_g * 0.35)
                    teto_base = limites.teto_proteina_g
                    piso_item = round(piso_base / len(validos), 1) if len(validos) > 1 else round(piso_base, 1)
                    teto_item = round(teto_base / len(validos), 1) if len(validos) > 1 else round(teto_base, 1)
                    for item, dp in validos:
                        delta_carne_g = delta_p_item / dp
                        qtd_antiga = item.quantidade_g
                        nova_qtd = max(piso_item, min(teto_item, qtd_antiga + delta_carne_g))
                        item.quantidade_g = round(nova_qtd, 1)
                        if abs(item.quantidade_g - qtd_antiga) >= 0.1:
                            ajustes_realizados.append({
                                "alimento": item.nome_taco,
                                "tipo": "proteina",
                                "anterior_g": qtd_antiga,
                                "novo_g": item.quantidade_g,
                                "delta_proteina_g": delta_p,
                            })

        # Calibração complementar de leguminosas em caso de excesso persistente de proteína
        if itens_leguminosa:
            status_pos_p = auditar_vet_e_macros(dia, perfil, taco_cache=taco_cache, session=session)
            if status_pos_p.proteinas_g > p_nutri.proteinas_g.maximo:
                excesso_p = status_pos_p.proteinas_g - p_alvo
                for leg in itens_leguminosa:
                    d_leg = _obter_dados_nutricionais_100g(
                        leg.nome_taco,
                        taco_cache=taco_cache,
                        session=session,
                        taco_id=getattr(leg, "_taco_id", None),
                    )
                    dens_leg_p = (d_leg["proteins"] / 100.0) if d_leg["proteins"] > 0 else 0.05
                    if dens_leg_p > 0.03:
                        delta_leg_g = (excesso_p / len(itens_leguminosa)) / dens_leg_p
                        qtd_ant = leg.quantidade_g
                        piso_leg = max(12.0, limites.piso_leguminosa_g * 0.35)
                        nova_leg = max(piso_leg, qtd_ant - delta_leg_g)
                        leg.quantidade_g = round(nova_leg, 1)
                        if abs(leg.quantidade_g - qtd_ant) >= 0.5:
                            ajustes_realizados.append({
                                "alimento": leg.nome_taco,
                                "tipo": "leguminosa",
                                "anterior_g": qtd_ant,
                                "novo_g": leg.quantidade_g,
                            })

        # -------------------------------------------------------------
        # 3. Microajuste de Carboidratos e VET residual (Amidos / Cereais / Tubérculos)
        # Densidade de carboidratos e energia real da TACO para calibração precisa
        # -------------------------------------------------------------
        if itens_amido:
            status_pos = auditar_vet_e_macros(dia, perfil, taco_cache=taco_cache, session=session)
            delta_c = c_alvo - status_pos.carboidratos_g
            delta_vet = vet_meta - status_pos.energia_kcal

            # Se houver déficit calórico e de carbo, ajusta proporcionalmente o amido
            if abs(delta_c) > 1.0 or abs(delta_vet) > (vet_meta * 0.04):
                itens_com_dados = []
                soma_carbo_amidos = 0.0

                for item in itens_amido:
                    dados = _obter_dados_nutricionais_100g(
                        item.nome_taco,
                        taco_cache=taco_cache,
                        session=session,
                        taco_id=getattr(item, "_taco_id", None),
                    )
                    carbo_100g = dados.get("carboidratos", 0.0)
                    densidade = (carbo_100g / 100.0) if carbo_100g > 0 else 0.0
                    if densidade <= 0.0:
                        kcal = dados.get("energia_kcal", 0.0)
                        if kcal > 0:
                            densidade = (kcal / 100.0) / 4.0

                    if densidade > 0.05:
                        carbo_item = item.quantidade_g * densidade
                        soma_carbo_amidos += carbo_item
                        itens_com_dados.append((item, densidade, carbo_item))

                if soma_carbo_amidos > 0:
                    for item, densidade, carbo_item in itens_com_dados:
                        qtd_antiga = item.quantidade_g
                        # Proporção balanceada pela contribuição real de carboidratos
                        proporcao_carbo = carbo_item / soma_carbo_amidos

                        # Fator de calibração para amidos secos/densos vs alta umidade
                        fator_densidade = max(0.35, min(1.8, 0.28 / densidade))
                        piso_base = limites.piso_amido_g * fator_densidade
                        teto_base = limites.teto_amido_g * fator_densidade

                        # Pisos e tetos pedagógicos estritos quando há mais de um amido no prato
                        if len(itens_amido) > 1:
                            # Piso mínimo absoluto de 10g para permitir convergência em perfis infantis (evita estouro de carbo)
                            piso_item = max(10.0, round(piso_base * 0.35, 1))
                            teto_item = max(piso_item + 10.0, min(180.0, round(teto_base * 0.70, 1)))
                        else:
                            piso_item = round(piso_base, 1)
                            # Tubérculos isolados de baixa densidade (ex: batata inglesa) podem atingir até 375g para suprir o VET
                            teto_item = min(375.0, round(teto_base, 1)) if densidade < 0.20 else round(teto_base, 1)

                        delta_item = (delta_c * proporcao_carbo) / densidade
                        nova_qtd = max(piso_item, min(teto_item, qtd_antiga + delta_item))
                        item.quantidade_g = round(nova_qtd, 1)
                        if abs(item.quantidade_g - qtd_antiga) >= 0.1:
                            ajustes_realizados.append({
                                "alimento": item.nome_taco,
                                "tipo": "amido",
                                "anterior_g": qtd_antiga,
                                "novo_g": item.quantidade_g,
                                "delta_carbo_g": delta_c,
                            })
                else:
                    # Fallback quando dados nutricionais não estão disponíveis (ex: testes sem banco/Qdrant)
                    soma_amidos = sum(a.quantidade_g for a in itens_amido)
                    if soma_amidos > 0:
                        for item in itens_amido:
                            qtd_antiga = item.quantidade_g
                            proporcao = qtd_antiga / soma_amidos
                            piso_item = max(8.0, round(limites.piso_amido_g * proporcao, 1)) if len(itens_amido) > 1 else limites.piso_amido_g
                            teto_item = min(180.0, round(limites.teto_amido_g * proporcao, 1)) if len(itens_amido) > 1 else limites.teto_amido_g
                            item.quantidade_g = round(max(piso_item, min(teto_item, qtd_antiga)), 1)

        # -------------------------------------------------------------
        # 4. Salvaguarda Estrita do Teto PNAE de Proteínas
        # Contém excedente proteico introduzido pelo amido (ex: massas/macarrão)
        # -------------------------------------------------------------
        status_pos_amido = auditar_vet_e_macros(dia, perfil, taco_cache=taco_cache, session=session)
        if status_pos_amido.proteinas_g > p_nutri.proteinas_g.maximo:
            excesso_total_p = status_pos_amido.proteinas_g - p_alvo
            if itens_proteina:
                for item in itens_proteina:
                    d = _obter_dados_nutricionais_100g(
                        item.nome_taco,
                        taco_cache=taco_cache,
                        session=session,
                        taco_id=getattr(item, "_taco_id", None),
                    )
                    dp = (d["proteins"] / 100.0) if d["proteins"] > 0 else 0.20
                    if dp > 0.05 and excesso_total_p > 0:
                        delta_carne = (excesso_total_p / len(itens_proteina)) / dp
                        piso_carne = max(6.0, limites.piso_proteina_g * 0.35)
                        reducao = min(item.quantidade_g - piso_carne, delta_carne)
                        if reducao > 0:
                            item.quantidade_g = round(item.quantidade_g - reducao, 1)
                            excesso_total_p -= reducao * dp

            if excesso_total_p > 0 and itens_leguminosa:
                for leg in itens_leguminosa:
                    d_leg = _obter_dados_nutricionais_100g(
                        leg.nome_taco,
                        taco_cache=taco_cache,
                        session=session,
                        taco_id=getattr(leg, "_taco_id", None),
                    )
                    dp_leg = (d_leg["proteins"] / 100.0) if d_leg["proteins"] > 0 else 0.06
                    if dp_leg > 0.03 and excesso_total_p > 0:
                        delta_leg = (excesso_total_p / len(itens_leguminosa)) / dp_leg
                        piso_l = max(12.0, limites.piso_leguminosa_g * 0.35)
                        reducao_l = min(leg.quantidade_g - piso_l, delta_leg)
                        if reducao_l > 0:
                            leg.quantidade_g = round(leg.quantidade_g - reducao_l, 1)
                            excesso_total_p -= reducao_l * dp_leg

    return dia, ajustes_realizados


def ajustar_macronutrientes_cardapio(
    cardapio: CardapioSchema,
    perfil: PerfilNutricional,
    taco_cache: Optional[Dict[str, Any]] = None,
    session: Optional[Session] = None,
) -> CardapioSchema:
    """
    Componente determinístico de pós-processamento:
    Audita o VET e os macronutrientes de cada dia do cardápio e aplica microajustes
    proporcionais nos alimentos base (arroz/tubérculos, carnes, óleos) respeitando
    pisos e tetos gastronômicos e pedagógicos por faixa etária, utilizando exclusivamente
    os dados oficiais da Tabela TACO do PostgreSQL/Qdrant.
    """
    limites = _resolver_limites_faixa(perfil.etapa, perfil.faixa_etaria)

    cache_local: Dict[str, Any] = dict(taco_cache) if taco_cache else {}
    sessao_contexto = None

    if session is None:
        try:
            sessao_contexto = Session(engine)
            session_ativa = sessao_contexto
        except Exception:
            session_ativa = None
    else:
        session_ativa = session

    try:
        # Carregamento em lote de todos os ingredientes do cardápio para evitar queries N+1
        if session_ativa:
            taco_ids = set()
            nomes_sem_id = set()
            for semana in cardapio.semanas:
                for dia in semana.dias:
                    for refeicao in dia.refeicoes:
                        for prato in refeicao.pratos:
                            for ing in prato.ingredientes:
                                t_id = getattr(ing, "_taco_id", None)
                                if t_id:
                                    taco_ids.add(str(t_id))
                                elif ing.nome_taco:
                                    nomes_sem_id.add(ing.nome_taco)

            if taco_ids:
                try:
                    registros = session_ativa.query(Taco).filter(
                        Taco.id.in_(taco_ids),
                        Taco.deleted_at == None
                    ).all()
                    for reg in registros:
                        cache_local[str(reg.id)] = reg
                        cache_local[reg.description] = reg
                        cache_local[_texto_normalizado(reg.description)] = reg
                except Exception:
                    pass

            if nomes_sem_id:
                from src.nutrition.calculator import buscar_taco_por_nome
                for nome in nomes_sem_id:
                    if nome not in cache_local and _texto_normalizado(nome) not in cache_local:
                        try:
                            t = buscar_taco_por_nome(session_ativa, nome)
                            if t:
                                cache_local[nome] = t
                                cache_local[str(t.id)] = t
                                cache_local[_texto_normalizado(t.description)] = t
                        except Exception:
                            pass

        relatorio = RelatorioAjusteNutricional(meta_vet=perfil.nutricao.energia_kcal)
        soma_calorica_inicial = 0.0
        soma_calorica_final = 0.0
        total_dias = 0

        for semana in cardapio.semanas:
            for dia in semana.dias:
                chave_dia = f"sem_{semana.numero}_{dia.dia_semana}"

                # Diagnóstico Inicial
                status_init = auditar_vet_e_macros(dia, perfil, taco_cache=cache_local, session=session_ativa)
                relatorio.status_inicial[chave_dia] = status_init
                soma_calorica_inicial += status_init.energia_kcal

                # Executa Microajustes Bounded com dados TACO
                dia, ajustes = _ajustar_dia_macronutrientes(
                    dia,
                    perfil,
                    limites,
                    taco_cache=cache_local,
                    session=session_ativa,
                )
                relatorio.ajustes_realizados.extend(ajustes)

                # Diagnóstico Pós-Ajuste
                status_fim = auditar_vet_e_macros(dia, perfil, taco_cache=cache_local, session=session_ativa)
                relatorio.status_final[chave_dia] = status_fim
                soma_calorica_final += status_fim.energia_kcal
                total_dias += 1

        if total_dias > 0:
            relatorio.media_calorica_inicial = round(soma_calorica_inicial / total_dias, 1)
            relatorio.media_calorica_final = round(soma_calorica_final / total_dias, 1)
            relatorio.convergido = all(
                st.dentro_margem_vet for st in relatorio.status_final.values()
            )

        # Armazena relatório como metadado privado no schema do cardápio
        setattr(cardapio, "_relatorio_microajustes", relatorio)

        return cardapio

    finally:
        if sessao_contexto is not None:
            sessao_contexto.close()
