import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db.models import Taco

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))

# ---------------------------------------------------------
# Tools de consulta à TACO
# ---------------------------------------------------------

@tool
def listar_opcoes_taco(categoria: str) -> list[str]:
    """
    Lista os alimentos disponíveis na TACO para uma categoria.
    Deve ser usada ANTES de escolher um ingrediente para compor
    o cardápio, para descobrir os omes exatos disponíveis.

    Categorias disponíveis:
    - Cereais e derivados
    - Verduras, hortaliças e derivados
    - Frutas e derivados
    - Carnes e derivados
    - Pescados e frutos do mar
    - Leite e derivados
    - Ovos e derivados
    - Leguminosas e derivados
    - Gorduras e óleos
    - Nozes e sementes
    """
    with Session(engine) as session:
        resultados = session.query(Taco.description).filter(
            Taco.category.ilike(f"%{categoria}%"),
            Taco.deleted_at == None
        ).all()

        if not resultados:
            return [f"Nenhum alimento encontrado para a categoria '{categoria}'"]
        
        return [r.description for r in resultados]
    

@tool
def buscar_cn_ingrediente_taco(nome_alimento: str) -> dict:
    """
    Retorna a composição nutricional de um alimento da TACO para 100g.
    Usar o nome exato retornado por listar_opcoes_taco.
    """

    with Session(engine) as session:
        resultado = session.query(Taco).filter(
            Taco.description == nome_alimento,
            Taco.deleted_at == None
        ).first()

        if not resultado:
            return {"erro": f"Alimento '{nome_alimento}' não encontrado. Use listar_opcoes_taco para ver os nomes exatos."}
        
        return {
            "nome": resultado.description,
            "categoria": resultado.category,
            "energia_kcal": resultado.energy_kcal,
            "proteinas_g": resultado.proteins,
            "carboidratos_g": resultado.carbohydrates,
            "lipidios_g": resultado.lipids,
            "sodio_mg": resultado.sodium,
            "ferro_mg": resultado.iron,
            "calcio_mg": resultado.calcium,
            "vitamina_a_mcg": resultado.retinol,
            "vitamina_c_mg": resultado.c_vitamin
        }
