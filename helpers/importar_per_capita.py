import sys
from pathlib import Path

# Adiciona a raiz do projeto ao path
sys.path.append(str(Path(__file__).parent.parent))

import pdfplumber
import re
from sqlalchemy.orm import Session
from db.database import engine
from db.models import PerCapita

def parse_valor(valor: str) -> float | None:
    """
    Converte string do PDF para float.
    Retorna None para 'x', '*', '-' (restrito ou não aplicável).
    """
    valor = valor.strip().replace("g", "").replace("mL", "").replace(",", ".")
    if valor in ("x", "*", "-", ""):
        return None
    try:
        return float(valor)
    except ValueError:
        return None

def importar():
    fragmentos_invalidos = {
        "conserva", "drenado", "drenada", "gordura", "sabor",
        "cremoso", "amostras)", "calda", "amendoim", "queimado",
        "cracker", "óleo", "enlatada", "morango", "de qualquer sabor",
        "Iogurte de qualquer", "gordura"
    }

    registros = []

    with pdfplumber.open("data/manual_per_capita.pdf") as pdf:
        for page in pdf.pages:
            tabela = page.extract_table()
            if not tabela:
                continue

            for linha in tabela:
                if not linha or len(linha) < 7:
                    continue

                # Ignora cabeçalhos
                if linha[0] in (None, "Descrição dos alimentos", ""):
                    continue

                nome = linha[0].replace("\n", " ").strip() if linha[0] else None

                if not nome or len(nome) < 4:
                    continue

                if nome.lower() in {f.lower() for f in fragmentos_invalidos}:
                    continue

                if nome[0].islower():
                    continue

                try:
                    fc           = float(str(linha[1]).replace(",", ".")) if linha[1] else 1.0
                    fco          = float(str(linha[2]).replace(",", ".")) if linha[2] else 1.0
                    creche       = parse_valor(str(linha[3]))
                    pre_escola   = parse_valor(str(linha[4]))
                    fund         = parse_valor(str(linha[5]))
                    medio_eja    = parse_valor(str(linha[6]))
                except (ValueError, IndexError):
                    continue

                registros.append(PerCapita(
                    nome_alimento=nome,
                    fator_correcao=fc,
                    fator_coccao=fco,
                    per_capita_creche=creche,
                    per_capita_pre_escola=pre_escola,
                    per_capita_fund=fund,
                    per_capita_medio_eja=medio_eja
                ))

    with Session(engine) as session:
        session.add_all(registros)

        # Debug
#        nomes = [r.nome_alimento for r in registros]
#        duplicatas = [n for n in nomes if nomes.count(n) > 1]
#        print(f"Total de registros: {len(registros)}")
#        print(f"Duplicatas encontradas: {set(duplicatas)}")

#        for r in registros:
#            if len(r.nome_alimento) < 10:
#                print(f"Nome suspeito: '{r.nome_alimento}' | FC: {r.fator_correcao} | creche: {r.per_capita_creche}")


        session.commit()
        print(f"{len(registros)} registros importados.")

if __name__ == "__main__":
    importar()