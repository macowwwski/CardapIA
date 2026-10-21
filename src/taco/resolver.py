"""
Identificação de alimentos na Tabela TACO e cálculo das porções recomendadas por aluno.

Compara o prato ou ingrediente gerado no cardápio com a base oficial de alimentos,
considerando o modo de preparo (cozido, cru, grelhado) e aplicando critérios
cuidadosos para escolher a melhor opção nutricional para cada faixa etária.
"""
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from qdrant_client.models import (
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchValue,
    Prefetch,
    SparseVector,
)

from src.config import (
    TACO_MATCH_MIN_SCORE,
    PER_CAPITA_MATCH_MIN_SCORE,
)
from src.taco.client import (
    get_qdrant_client,
    get_dense_embedder,
    get_sparse_embedder,
)
from src.taco.synonyms import SINONIMOS_TACO

COLECAO_TACO = "taco_foods"
COLECAO_PER_CAPITA = "per_capita_items"

TOP_K = 20
LIMIAR_TACO = TACO_MATCH_MIN_SCORE
LIMIAR_PER_CAPITA = PER_CAPITA_MATCH_MIN_SCORE

STOPWORDS = {
    "de", "da", "do", "das", "dos", "e", "ou", "com", "sem", "ao", "a", "o",
    "em", "na", "no", "para", "alimento", "alimentos", "ingrediente", "ingredientes"
}
TOKENS_PREPARO = {"cozid", "cozido", "cozida", "preparad", "grelhad", "assad"}

PRATOS_COMPOSTOS = {
    "estrogonofe", "coxinha", "empada", "pastel", "bolinho", "croquete",
    "salpicao", "torta", "virado", "baiao", "feijoada", "acaraje",
    "yakisoba", "quibe", "lasanha", "panqueca", "nhoque", "torrada"
}

TOKENS_METODO = {
    "cozido", "cozida", "cozid", "cru", "crua", "frito", "frita", "frit",
    "assado", "assada", "assad", "grelhado", "grelhada", "grelhad",
    "refogado", "refogada", "refogad", "ralado", "ralada", "desfiado", "desfiada"
}


@dataclass(frozen=True)
class MatchTaco:
    """Alimento correspondente encontrado na Tabela TACO com sua pontuação de confiança."""
    taco_id: str
    description: str
    score: float
    payload: dict


def _norm(texto: object) -> str:
    """Padroniza o texto, tirando acentos e deixando todas as letras minúsculas."""
    t = unicodedata.normalize("NFD", str(texto or "").lower().strip())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _tokens(texto: object) -> set[str]:
    """Separa o texto em palavras-chave simplificadas para facilitar a comparação."""
    saida = set()
    for tok in re.findall(r"[a-z0-9]+", _norm(texto)):
        if tok in STOPWORDS:
            continue
        if tok in {"peixe", "peixes", "pescado", "pescados", "pescada"}:
            tok = "peix"
        elif len(tok) > 4 and tok[-1] in {"a", "o", "s"}:
            tok = tok[:-1]
        saida.add(tok)
    return saida


def _embed_dense(texto: str) -> list[float]:
    """Representa o sentido e significado das palavras para busca inteligente."""
    return list(get_dense_embedder().embed([texto]))[0].tolist()


def _embed_sparse(texto: str):
    """Destaca termos específicos e palavras raras para garantir correspondência exata."""
    return list(get_sparse_embedder().embed([texto]))[0]


def _rerank(consulta: str, hits, campo_texto: str, limiar: float) -> Optional[tuple]:
    """Avalia as opções encontradas e escolhe o alimento mais adequado."""
    tokens_q = _tokens(consulta)
    tokens_subst = tokens_q - TOKENS_METODO
    melhor = None
    for hit in hits:
        texto = hit.payload.get(campo_texto, "")
        cat = hit.payload.get("category", "")
        tokens_d = _tokens(texto)
        base = _norm(texto).split(",")[0].strip()
        tokens_base = _tokens(base)

        cobertura = len(tokens_q & tokens_d) / len(tokens_q) if tokens_q else 0.0

        # Dá preferência para ingredientes puros e evita salgados prontos (como coxinha ou pastel)
        bonus_preparado = 0.0
        if cat == "Alimentos preparados" or any(p in base for p in PRATOS_COMPOSTOS):
            bonus_preparado -= 4.0

        quer_cru = "cru" in tokens_q
        tem_cozido = any(p in tokens_d for p in ["cozid", "cozido", "cozida", "grelhad", "assad"])
        tem_cru = "cru" in tokens_d or "crua" in tokens_d
        bonus_preparo = 0.0
        if not quer_cru:
            if tem_cozido:
                bonus_preparo += 1.5
            elif tem_cru:
                bonus_preparo -= 0.5
        else:
            if tem_cru:
                bonus_preparo += 1.5

        quer_assado = any(p in tokens_q for p in ["assad", "assado", "assada"])
        tem_assado = any(p in tokens_d for p in ["assad", "assado", "assada"])
        if quer_assado and tem_assado:
            bonus_preparo += 2.0

        quer_grelhado = any(p in tokens_q for p in ["grelhad", "grelhado", "grelhada"])
        tem_grelhado = any(p in tokens_d for p in ["grelhad", "grelhado", "grelhada"])
        if quer_grelhado and tem_grelhado:
            bonus_preparo += 2.0

        quer_frito = any(p in tokens_q for p in ["frit", "frito", "frita", "empanad"])
        tem_frito = any(p in tokens_d for p in ["frit", "frito", "frita", "empanad"])
        if tem_frito and not quer_frito:
            bonus_preparo -= 3.0

        bonus_base = 0.0
        if tokens_subst & tokens_base:
            bonus_base += 2.5
        elif tokens_q & tokens_base:
            bonus_base += 1.0

        # Dá pontos extras se o alimento principal (como peixe, frango ou carne) for o mesmo
        if "peix" in tokens_q and any(p in (tokens_d | _tokens(cat)) for p in ["peix", "pescad"]):
            bonus_base += 2.0

        if "pure" in tokens_d and "pure" not in tokens_q:
            bonus_base -= 2.0
        if "suco" in tokens_d and "suco" not in tokens_q:
            bonus_base -= 3.0
        if any(d in tokens_d for d in ["doce", "calda", "confeit"]) and not any(d in tokens_q for d in ["doce", "calda"]):
            bonus_base -= 3.0

        # Exige que pelo menos a palavra principal do alimento esteja presente
        sinonimos = SINONIMOS_TACO.get(hit.payload.get("description", ""), "")
        tokens_alvo = tokens_d | tokens_base | _tokens(sinonimos) | _tokens(hit.payload.get("search_text", ""))
        if tokens_q and not (tokens_q & tokens_alvo):
            continue

        # Pontuação combinada levando em conta palavras em comum, modo de preparo e alimento base
        score = float(hit.score) * 20.0 + cobertura * 5.0 + bonus_preparo + bonus_base + bonus_preparado
        if melhor is None or score > melhor[1]:
            melhor = (hit, score)
    if melhor and melhor[1] >= limiar:
        return melhor
    return None


@lru_cache(maxsize=4096)
def resolver_taco(nome: str) -> Optional[MatchTaco]:
    """Encontra o alimento oficial correspondente na Tabela TACO a partir do nome do prato ou ingrediente gerado."""
    consulta = _norm(nome).strip()
    if not consulta:
        return None

    dv = _embed_dense(consulta)
    sv = _embed_sparse(consulta)

    client = get_qdrant_client()
    res = client.query_points(
        collection_name=COLECAO_TACO,
        prefetch=[
            Prefetch(query=dv, using="dense", limit=TOP_K),
            Prefetch(
                query=SparseVector(indices=sv.indices.tolist(), values=sv.values.tolist()),
                using="sparse",
                limit=TOP_K,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=TOP_K,
    )
    hits = res.points
    if not hits:
        return None

    escolhido = _rerank(consulta, hits, "description", LIMIAR_TACO)
    if not escolhido:
        return None
    hit, score = escolhido
    return MatchTaco(
        taco_id=str(hit.payload["taco_id"]),
        description=hit.payload["description"],
        score=round(score, 4),
        payload=dict(hit.payload),
    )


def _campo_per_capita(etapa: str) -> str:
    """Indica qual coluna de quantidade usar conforme a etapa escolar (creche, infantil, fundamental ou médio)."""
    mapeamento = {
        "creche": "per_capita_creche",
        "pre-escola": "per_capita_pre_escola",
        "pre escola": "per_capita_pre_escola",
        "pré-escola": "per_capita_pre_escola",
        "pré escola": "per_capita_pre_escola",
        "pre_escola": "per_capita_pre_escola",
        "ensino fundamental": "per_capita_fund",
        "ensino_fundamental": "per_capita_fund",
        "fundamental": "per_capita_fund",
        "fundamental_1": "per_capita_fund",
        "fundamental_2": "per_capita_fund",
        "ensino medio": "per_capita_medio_eja",
        "ensino médio": "per_capita_medio_eja",
        "ensino_medio": "per_capita_medio_eja",
        "ensino_médio": "per_capita_medio_eja",
        "medio": "per_capita_medio_eja",
        "médio": "per_capita_medio_eja",
        "eja": "per_capita_medio_eja",
    }
    campo = mapeamento.get(_norm(etapa))
    if not campo:
        raise ValueError(f"Etapa escolar invalida para per capita: {etapa}")
    return campo


TERMOS_CARNES = {
    "frango", "galinha", "sobrecoxa", "peito", "file de frango",
    "carne", "bovina", "boi", "patinho", "acem", "alcatra", "contra-file",
    "contrafile", "costela", "coxao", "maminha", "lagarto", "musculo",
    "peixe", "tilapia", "sardinha", "atum", "merluza", "pescada",
    "suina", "porco", "pernil", "lombo", "bisteca"
}


def _calibrar_per_capita_proteina(nome: str, etapa: str, valor: float) -> float:
    """Ajusta a porção de carnes para a idade do aluno, garantindo a quantidade certa de proteína sem exageros."""
    etapa_norm = _norm(etapa)
    nome_norm = _norm(nome)
    if any(t in nome_norm for t in TERMOS_CARNES):
        if etapa_norm in ("medio", "médio", "ensino medio", "ensino médio", "ensino_medio", "ensino_médio"):
            return 45.0
        elif etapa_norm in ("eja",):
            return 32.0
        elif etapa_norm in ("fundamental", "ensino fundamental", "fundamental_1", "fundamental_2", "ensino_fundamental"):
            return 28.0
        elif etapa_norm in ("pre_escola", "pré-escola", "pre-escola", "pre escola", "pré escola", "infantil"):
            return 18.0
        elif etapa_norm in ("creche", "bercario", "maternal", "creche_1_3", "creche_7_11"):
            return 10.0
    return valor


def resolver_per_capita(nome: str, etapa: str, taco_id: Optional[str] = None) -> Optional[float]:
    """
    Informa a quantidade recomendada em gramas por aluno para a etapa escolar informada.

    Primeiro tenta buscar diretamente pelo código do alimento na TACO; se não encontrar,
    faz a busca inteligente pelo nome do ingrediente. Não utiliza valores genéricos ou chutes.
    """
    campo = _campo_per_capita(etapa)
    client = get_qdrant_client()

    if taco_id:
        pontos, _ = client.scroll(
            collection_name=COLECAO_PER_CAPITA,
            scroll_filter=Filter(must=[FieldCondition(key="taco_id", match=MatchValue(value=str(taco_id)))]),
            limit=20,
            with_payload=True,
        )
        for ponto in pontos:
            valor = ponto.payload.get(campo)
            if valor is not None:
                return _calibrar_per_capita_proteina(nome, etapa, float(valor))

    consulta = _norm(nome).strip()
    if not consulta:
        return None

    dv = _embed_dense(consulta)
    sv = _embed_sparse(consulta)

    res = client.query_points(
        collection_name=COLECAO_PER_CAPITA,
        prefetch=[
            Prefetch(query=dv, using="dense", limit=TOP_K),
            Prefetch(
                query=SparseVector(indices=sv.indices.tolist(), values=sv.values.tolist()),
                using="sparse",
                limit=TOP_K,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=TOP_K,
    )
    hits = [h for h in res.points if h.payload.get(campo) is not None]
    if not hits:
        return None

    escolhido = _rerank(consulta, hits, "nome_alimento", LIMIAR_PER_CAPITA)
    if not escolhido:
        return None
    return _calibrar_per_capita_proteina(nome, etapa, float(escolhido[0].payload[campo]))
