import csv
import sys
from pathlib import Path

from sqlalchemy import text

# Adiciona a raiz do projeto ao path quando o script roda diretamente.
sys.path.append(str(Path(__file__).parent.parent))

from db.database import engine


def exportar_per_capita(caminho_saida: str = "data/per_capita_export.csv") -> Path:
    """
    Exporta o resultado de SELECT * FROM per_capita para um arquivo CSV.

    Retorna o caminho do arquivo gerado.
    """
    destino = Path(caminho_saida)
    destino.parent.mkdir(parents=True, exist_ok=True)

    with engine.connect() as conn:
        resultado = conn.execute(text("SELECT * FROM per_capita ORDER BY nome_alimento"))
        colunas = list(resultado.keys())
        linhas = resultado.fetchall()

    with destino.open("w", newline="", encoding="utf-8-sig") as arquivo:
        writer = csv.writer(arquivo)
        writer.writerow(colunas)
        writer.writerows(linhas)

    return destino


if __name__ == "__main__":
    arquivo = exportar_per_capita()
    print(f"Exportado para: {arquivo}")
