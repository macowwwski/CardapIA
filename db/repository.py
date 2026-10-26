"""
Salva os cardápios escolares no banco de dados PostgreSQL.

Guarda toda a estrutura do cardápio gerado pela IA (etapa, semanas, dias, refeições,
pratos e ingredientes) com as quantidades em gramas e a identificação na Tabela TACO.
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from db.database import engine
from db.models import (
    Cardapio,
    Dia,
    EtapaEscolar,
    Ingrediente,
    Prato,
    Refeicao,
    Semana,
)
from src.taco.resolver import resolver_taco, resolver_per_capita
from src.nutrition.classifier import _texto_normalizado


def salvar_cardapio_db(
    cardapio_schema,
    etapa: str,
    faixa_etaria: str,
    periodo: str,
    num_refeicoes: int,
    mes_aplicacao: str,
    observacoes: Optional[str] = None,
    aprovado: bool = False,
) -> Optional[str]:
    """
    Grava o cardápio completo no banco de dados, organizando por semanas, dias, refeições,
    pratos e seus respectivos ingredientes com peso e código TACO.
    """
    session = None
    try:
        with Session(engine) as session:
            etapa_obj = session.query(EtapaEscolar).filter(
                EtapaEscolar.etapa == etapa,
                EtapaEscolar.faixa_etaria == faixa_etaria,
            ).first()
            if not etapa_obj:
                etapa_obj = EtapaEscolar(id=uuid.uuid4(), etapa=etapa, faixa_etaria=faixa_etaria)
                session.add(etapa_obj)
                session.flush()

            cardapio_id = uuid.uuid4()
            num_semanas = len(cardapio_schema.semanas)
            cardapio_db = Cardapio(
                id=cardapio_id,
                etapa_escolar_id=etapa_obj.id,
                periodo=periodo,
                mes_aplicacao=mes_aplicacao,
                num_refeicoes=num_refeicoes,
                num_semanas=num_semanas,
                data_geracao=datetime.now(),
                aprovado=aprovado,
                observacoes=observacoes or getattr(cardapio_schema, "observacoes", None),
            )
            session.add(cardapio_db)

            for semana in cardapio_schema.semanas:
                if not getattr(semana, "dias", None):
                    continue
                semana_db = Semana(id=uuid.uuid4(), cardapio_id=cardapio_id, numero=semana.numero)
                session.add(semana_db)
                session.flush()

                for dia in semana.dias:
                    if not getattr(dia, "refeicoes", None):
                        continue
                    dia_db = Dia(id=uuid.uuid4(), semana_id=semana_db.id, dia_semana=dia.dia_semana)
                    session.add(dia_db)
                    session.flush()

                    for refeicao in dia.refeicoes:
                        tipo_valor = str(refeicao.tipo.value if hasattr(refeicao.tipo, "value") else refeicao.tipo)
                        refeicao_db = Refeicao(id=uuid.uuid4(), dia_id=dia_db.id, tipo=tipo_valor, horario=None)
                        session.add(refeicao_db)
                        session.flush()

                        for prato in refeicao.pratos:
                            prato_db = Prato(
                                id=uuid.uuid4(),
                                refeicao_id=refeicao_db.id,
                                nome=prato.nome,
                                estado_preparacao=getattr(prato, "estado_preparacao", None),
                            )
                            session.add(prato_db)
                            session.flush()

                            if prato.ingredientes:
                                for ingrediente in prato.ingredientes:
                                    taco_id = getattr(ingrediente, "_taco_id", None)
                                    if not taco_id:
                                        match = resolver_taco(ingrediente.nome_taco)
                                        taco_id = match.taco_id if match else None
                                    if not taco_id:
                                        print(f"Aviso: ingrediente sem taco_id, não persistido: {ingrediente.nome_taco}")
                                        continue
                                    ing_db = Ingrediente(
                                        id=uuid.uuid4(),
                                        prato_id=prato_db.id,
                                        taco_id=taco_id,
                                        quantidade_g=ingrediente.quantidade_g,
                                    )
                                    session.add(ing_db)
                            else:
                                nome_norm = _texto_normalizado(prato.nome)
                                eh_composta = any(
                                    termo in nome_norm
                                    for termo in [
                                        "galinhada", "baiao", "feijoada", "escondidinho", "risoto",
                                        "estrogonofe", "strogonoff", "lasanha", "panqueca", "nhoque",
                                        "torta", "quibe", "salpicao", "yakisoba", "salada de fruta",
                                        "com ", "ao molho", "a bolonhesa", "à bolonhesa", "rechead"
                                    ]
                                )
                                if eh_composta:
                                    print(f"Aviso: prato composto '{prato.nome}' sem lista explícita de ingredientes não foi forçado a um único ingrediente TACO.")
                                else:
                                    match = resolver_taco(prato.nome)
                                    taco_id = match.taco_id if match else None
                                    if taco_id:
                                        qtd = resolver_per_capita(prato.nome, etapa, taco_id=taco_id)
                                        if qtd and qtd > 0:
                                            ing_db = Ingrediente(
                                                id=uuid.uuid4(),
                                                prato_id=prato_db.id,
                                                taco_id=taco_id,
                                                quantidade_g=qtd,
                                            )
                                            session.add(ing_db)

            session.commit()
            return str(cardapio_id)
    except Exception as e:
        if session is not None:
            try:
                session.rollback()
            except Exception:
                pass
        print(f"Aviso: Não foi possível persistir no PostgreSQL: {e}")
        return None

