"""
Cálculos matemáticos e nutricionais a partir da Tabela TACO.

Responsável pela conversão per capita proporcional e verificação de intervalos
de referência nutricional (energia, macronutrientes, micronutrientes).
"""
from typing import Optional
from sqlalchemy.orm import Session
from db.models import Taco
from src.taco.resolver import resolver_taco
from src.nutrition.classifier import _texto_normalizado


def _somar_nutriente(valor_100g: float | None, quantidade_g: float) -> float:
    """Escala o nutriente de referência (base 100g) para a quantidade em gramas."""
    if valor_100g is None:
        return 0.0
    return float(valor_100g) * float(quantidade_g or 0) / 100.0


def _dentro_intervalo(
    valor: float,
    minimo: float | None,
    maximo: float | None,
    tolerancia: float = 0.1,
) -> bool:
    """Verifica se o valor atende aos limites regulatórios com margem de tolerância."""
    eps = 1e-4
    if minimo is not None and (valor + eps) < minimo * (1 - tolerancia):
        return False
    if maximo is not None and (valor - eps) > maximo * (1 + tolerancia):
        return False
    return True


def buscar_taco_por_nome(session: Optional[Session], nome_alimento: str) -> Taco | None:
    """Resolve o alimento na TACO por correspondência direta ou similaridade semântica (Qdrant) e busca no banco."""
    try:
        if session is not None:
            exato = session.query(Taco).filter(
                Taco.description == nome_alimento,
                Taco.deleted_at == None,
            ).first()
            if exato:
                return exato

        match = resolver_taco(nome_alimento)
        if not match:
            return None

        if session is not None:
            return session.query(Taco).filter(
                Taco.id == match.taco_id,
                Taco.deleted_at == None,
            ).first()
    except Exception:
        return None
    return None


PRO_VITAMINA_A_MCG_POR_100G: dict[str, float] = {
    "cenoura": 835.0,
    "abobora": 400.0,
    "mamao": 47.0,
    "manga": 54.0,
    "couve": 250.0,
    "espinafre": 469.0,
    "batata doce": 700.0,
    "batata-doce": 700.0,
    "melao": 169.0,
    "tomate": 42.0,
    "pimentao": 157.0,
    "acerola": 38.0,
    "maracuja": 64.0,
    "agriao": 160.0,
    "rucula": 119.0,
}


def obter_vitamina_a_mcg_100g(taco: Taco | None, nome_alimento: str = "") -> float:
    """
    Retorna a Vitamina A total em mcg RAE (Retinol Activity Equivalents).
    Alimentos de origem animal fornecem retinol pré-formado (taco.retinol).
    Alimentos de origem vegetal ricos em carotenoides pró-vitamina A fornecem beta-caroteno/RAE,
    que não constam na coluna retinol da TACO 4ª edição.
    """
    if taco and taco.retinol:
        return float(taco.retinol)

    texto = _texto_normalizado(f"{nome_alimento} {taco.description if taco else ''}")
    for termo, valor in PRO_VITAMINA_A_MCG_POR_100G.items():
        if termo in texto:
            return valor
    return 0.0


def calcular_nutrientes_alimento(
    session: Optional[Session],
    nome_taco: str,
    qtd_g: float,
    taco_id: Optional[str] = None,
) -> dict:
    """
    Calcula os valores nutricionais escalados pela quantidade em gramas (per capita).
    Utilizado para montagem do payload de refeições do contrato HTTP.
    """
    fator = (qtd_g or 0) / 100.0
    taco = None
    if session is not None and nome_taco:
        try:
            taco = buscar_taco_por_nome(session, nome_taco)
        except Exception:
            taco = None

    if not taco and taco_id and session is not None:
        try:
            taco = session.query(Taco).filter(Taco.id == taco_id, Taco.deleted_at == None).first()
        except Exception:
            taco = None

    if not taco and not taco_id:
        try:
            match = resolver_taco(nome_taco)
            taco_id = match.taco_id if match else None
            if taco_id and session is not None:
                taco = session.query(Taco).filter(Taco.id == taco_id, Taco.deleted_at == None).first()
        except Exception:
            pass

    payload_qdrant = None
    if not taco:
        try:
            match = resolver_taco(nome_taco)
            if match and match.payload:
                payload_qdrant = match.payload
        except Exception:
            payload_qdrant = None

    if not taco and not payload_qdrant:
        return {
            "energiaKcal": 0.0,
            "carboidratosG": 0.0,
            "proteinasG": 0.0,
            "lipidiosG": 0.0,
            "sodioMg": 0.0,
            "ferroMg": 0.0,
            "calcioMg": 0.0,
            "vitaminaAMcg": 0.0,
            "vitaminaCMg": 0.0,
        }

    if taco:
        energia = float(taco.energy_kcal or 0.0)
        carbo = float(taco.carbohydrates or 0.0)
        prot = float(taco.proteins or 0.0)
        lip = float(taco.lipids or 0.0)
        sodio = float(taco.sodium or 0.0)
        ferro = float(taco.iron or 0.0)
        calcio = float(taco.calcium or 0.0)
        vit_c = float(taco.c_vitamin or 0.0)
        vit_a = obter_vitamina_a_mcg_100g(taco, nome_taco)
    else:
        energia = float(payload_qdrant.get("energy_kcal") or 0.0)
        carbo = float(payload_qdrant.get("carbohydrates") or 0.0)
        prot = float(payload_qdrant.get("proteins") or 0.0)
        lip = float(payload_qdrant.get("lipids") or 0.0)
        sodio = float(payload_qdrant.get("sodium") or 0.0)
        ferro = float(payload_qdrant.get("iron") or 0.0)
        calcio = float(payload_qdrant.get("calcium") or 0.0)
        vit_c = float(payload_qdrant.get("c_vitamin") or 0.0)
        vit_a = float(payload_qdrant.get("retinol") or 0.0) or obter_vitamina_a_mcg_100g(None, nome_taco)

    if energia <= 0.0 and (carbo > 0.0 or prot > 0.0 or lip > 0.0):
        energia = round(carbo * 4.0 + prot * 4.0 + lip * 9.0, 2)

    return {
        "energiaKcal": round(energia * fator, 1),
        "carboidratosG": round(carbo * fator, 1),
        "proteinasG": round(prot * fator, 1),
        "lipidiosG": round(lip * fator, 1),
        "sodioMg": round(sodio * fator, 1),
        "ferroMg": round(ferro * fator, 2),
        "calcioMg": round(calcio * fator, 1),
        "vitaminaAMcg": round(vit_a * fator, 1),
        "vitaminaCMg": round(vit_c * fator, 1),
    }
