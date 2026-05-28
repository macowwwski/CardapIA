import argparse
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from sqlalchemy.orm import Session

# Adiciona a raiz do projeto ao path quando o script roda diretamente.
sys.path.append(str(Path(__file__).parent.parent))

from db.database import engine
from db.models import PerCapita, Taco


def normalizar_texto(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", valor)
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    texto = texto.lower()
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def chave_por_partes(nome: str) -> tuple[str, ...]:
    """
    Normaliza nomes alimentares e ignora a ordem das partes separadas por virgula.

    Exemplo:
    - "Arroz, branco, cru"
    - "arroz, cru, branco"

    Ambos viram a mesma chave: ("arroz", "branco", "cru").
    """
    partes = [
        normalizar_texto(parte)
        for parte in nome.split(",")
        if normalizar_texto(parte)
    ]
    return tuple(sorted(partes))


def montar_indice_taco(tacos: list[Taco]) -> dict[tuple[str, ...], list[Taco]]:
    indice = defaultdict(list)
    for taco in tacos:
        indice[chave_por_partes(taco.description)].append(taco)
    return dict(indice)


def linkar_per_capita_taco(dry_run: bool = False, overwrite: bool = False) -> dict[str, int]:
    with Session(engine) as session:
        tacos = session.query(Taco).order_by(Taco.description).all()
        per_capitas_query = session.query(PerCapita).order_by(PerCapita.nome_alimento)

        if not overwrite:
            per_capitas_query = per_capitas_query.filter(PerCapita.taco_id.is_(None))

        per_capitas = per_capitas_query.all()
        indice_taco = montar_indice_taco(tacos)

        vinculados = 0
        ambiguos = []
        sem_match = []

        for per_capita in per_capitas:
            chave = chave_por_partes(per_capita.nome_alimento)
            candidatos = indice_taco.get(chave, [])

            if len(candidatos) == 1:
                per_capita.taco_id = candidatos[0].id
                vinculados += 1
                print(f"OK: {per_capita.nome_alimento} -> {candidatos[0].description}")
            elif len(candidatos) > 1:
                ambiguos.append((per_capita, candidatos))
                nomes = "; ".join(taco.description for taco in candidatos)
                print(f"AMBIGUO: {per_capita.nome_alimento} -> {nomes}")
            else:
                sem_match.append(per_capita)

        if dry_run:
            session.rollback()
        else:
            session.commit()

    return {
        "analisados": len(per_capitas),
        "vinculados": vinculados,
        "ambiguos": len(ambiguos),
        "sem_match": len(sem_match),
    }


def buscar_per_capita_sem_match() -> list[dict[str, object]]:
    """
    Retorna os registros de per_capita que seguem sem equivalencia na TACO.

    Na pratica, sao os registros em que per_capita.taco_id ainda esta NULL
    depois do processo de link.
    """
    with Session(engine) as session:
        registros = (
            session.query(PerCapita)
            .filter(PerCapita.taco_id.is_(None))
            .order_by(PerCapita.nome_alimento)
            .all()
        )

        return [
            {
                "id": str(registro.id),
                "nome_alimento": registro.nome_alimento,
                "fator_correcao": registro.fator_correcao,
                "fator_coccao": registro.fator_coccao,
                "per_capita_creche": registro.per_capita_creche,
                "per_capita_pre_escola": registro.per_capita_pre_escola,
                "per_capita_fund": registro.per_capita_fund,
                "per_capita_medio_eja": registro.per_capita_medio_eja,
            }
            for registro in registros
        ]


def imprimir_per_capita_sem_match() -> None:
    registros = buscar_per_capita_sem_match()

    print(f"Registros sem match: {len(registros)}")
    for registro in registros:
        print(f"- {registro['nome_alimento']} ({registro['id']})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preenche per_capita.taco_id quando o nome equivale ao da TACO."
    )
    parser.add_argument(
        "--sem-match",
        action="store_true",
        help="Lista registros de per_capita que continuam sem taco_id e nao executa o link.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra os vinculos que seriam feitos, sem gravar no banco.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Reprocessa tambem registros que ja possuem taco_id.",
    )
    args = parser.parse_args()

    if args.sem_match:
        imprimir_per_capita_sem_match()
        return

    resumo = linkar_per_capita_taco(dry_run=args.dry_run, overwrite=args.overwrite)

    acao = "Simulacao concluida" if args.dry_run else "Vinculo concluido"
    print(f"\n{acao}:")
    print(f"- analisados: {resumo['analisados']}")
    print(f"- vinculados: {resumo['vinculados']}")
    print(f"- ambiguos: {resumo['ambiguos']}")
    print(f"- sem match: {resumo['sem_match']}")


if __name__ == "__main__":
    main()
