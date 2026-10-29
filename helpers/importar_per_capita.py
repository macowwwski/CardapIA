"""
Script utilitário para importação de dados de per capita a partir do manual PDF.

Lê as tabelas do arquivo data/manual_per_capita.pdf utilizando pdfplumber,
extrai as porções recomendadas para cada etapa escolar (creche, pré-escola,
ensino fundamental e médio/EJA) e persiste registros novos na tabela per_capita.
"""
import sys
from pathlib import Path

DIR_RAIZ = Path(__file__).resolve().parent.parent
sys.path.append(str(DIR_RAIZ))

import pdfplumber
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
    """
    Extrai as tabelas de alimentos do PDF manual_per_capita.pdf, filtra
    linhas de cabeçalho ou fragmentos inválidos e insere registros inéditos no banco.
    """
    fragmentos_invalidos = {
        "conserva", "drenado", "drenada", "gordura", "sabor",
        "cremoso", "amostras)", "calda", "amendoim", "queimado",
        "cracker", "óleo", "enlatada", "morango", "de qualquer sabor",
        "Iogurte de qualquer", "gordura"
    }

    registros = []

    caminho_pdf = DIR_RAIZ / "data" / "manual_per_capita.pdf"
    with pdfplumber.open(caminho_pdf) as pdf:
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
        existentes = {r[0] for r in session.query(PerCapita.nome_alimento).all()}
        novos = [r for r in registros if r.nome_alimento not in existentes]
        if novos:
            session.add_all(novos)
            session.commit()
            print(f"{len(novos)} novos registros importados (de {len(registros)} encontrados no manual).")
        else:
            print(f"Todos os {len(registros)} registros do manual já estão presentes no banco.")

if __name__ == "__main__":
    importar()