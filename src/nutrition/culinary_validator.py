"""
Auditoria determinística de coerência culinária e gastronômica de cardápios escolares.

Verifica:
1. Excesso de frutas na mesma refeição (máximo 1 fruta independente).
2. Estrutura de refeições principais (cereal/tubérculo + proteína principal).
3. Carnes concorrentes na mesma refeição.
4. Cumprimento rigoroso de restrições alimentares declaradas (lactose, glúten, ovos).
5. Monotonia proteica semanal (mesma proteína por 3+ dias consecutivos).
"""
from db.models import Taco
from src.schemas_pydantic import CardapioSchema, InconformidadePNAESchema
from src.nutrition.classifier import (
    _texto_normalizado,
    _tokens_normalizados,
    _classificar_alimento,
    _identificar_frutas,
    GENERICOS_FRUTA,
)


def validar_coerencia_culinaria(
    cardapio: CardapioSchema,
    etapa: str,
    restricoes: list[str] | None = None,
    ingredientes_taco: dict[str, Taco | None] | None = None,
) -> list[InconformidadePNAESchema]:
    """
    Executa auditoria culinária e nutricional determinística no cardápio escolar.
    """
    inconformidades: list[InconformidadePNAESchema] = []
    restricoes_limpas = [_texto_normalizado(r) for r in (restricoes or []) if str(r).strip()]
    tem_restricao_lactose = any(r in {"lactose", "leite", "laticinios"} for r in restricoes_limpas)
    tem_restricao_gluten = any(r in {"gluten", "trigo", "doenca celiaca", "celiaco"} for r in restricoes_limpas)
    tem_restricao_ovo = any(r in {"ovo", "ovos"} for r in restricoes_limpas)

    ingredientes_taco = ingredientes_taco or {}

    for semana in cardapio.semanas:
        proteina_por_dia: list[str] = []

        for dia in semana.dias:
            proteina_principal_do_dia: str | None = None

            for refeicao in dia.refeicoes:
                tipo_str = str(refeicao.tipo.value if hasattr(refeicao.tipo, "value") else refeicao.tipo).lower()
                eh_principal = tipo_str in {"almoco", "almoço", "jantar"}

                frutas_avulsas = set()
                proteinas_refeicao = set()
                tem_cereal_tuberculo = False
                tem_proteina = False

                for prato in refeicao.pratos:
                    nome_prato_norm = _texto_normalizado(prato.nome)
                    eh_preparacao_composta = any(
                        termo in nome_prato_norm
                        for termo in ["suco", "vitamina", "salada de fruta", "salada de frutas", "molho", "creme", "doce", "geleia", "bolo", "torta", "ensopad", "grelhad", "assad", "arroz"]
                    ) or len(prato.ingredientes) > 1

                    frutas_prato = _identificar_frutas(prato.nome)
                    if not eh_preparacao_composta and frutas_prato:
                        for f in frutas_prato:
                            frutas_avulsas.add(f)

                    if prato.ingredientes:
                        for ing in prato.ingredientes:
                            taco = ingredientes_taco.get(ing.nome_taco)
                            categoria = taco.category if taco else ""
                            classes = _classificar_alimento(ing.nome_taco, categoria) | _classificar_alimento(prato.nome, categoria)

                            if "fruta" in classes and not eh_preparacao_composta:
                                frutas_ing = _identificar_frutas(ing.nome_taco, categoria)
                                for f in frutas_ing:
                                    frutas_avulsas.add(f)

                            if "cereal_tuberculo" in classes:
                                tem_cereal_tuberculo = True

                            if "proteina_animal" in classes or "leguminosa" in classes:
                                if "proteina_animal" in classes:
                                    tem_proteina = True
                                    toks = _tokens_normalizados(f"{ing.nome_taco} {prato.nome}")
                                    if toks & {"frango", "galinha", "ave"}:
                                        proteinas_refeicao.add("frango")
                                    elif toks & {"carne", "bovina", "boi", "patinho", "acem", "alcatra", "bolonhesa"}:
                                        proteinas_refeicao.add("carne bovina")
                                    elif toks & {"peixe", "tilapia", "sardinha", "atum", "merluza", "pescada"}:
                                        proteinas_refeicao.add("peixe")
                                    elif toks & {"ovo", "ovos", "omelete"}:
                                        proteinas_refeicao.add("ovo")
                                    elif toks & {"suina", "porco", "pernil", "lombo"}:
                                        proteinas_refeicao.add("carne suína")

                            # Verificação de restrições alimentares informadas
                            if tem_restricao_lactose and "laticinio" in classes:
                                inconformidades.append(InconformidadePNAESchema(
                                    escopo=f"semana {semana.numero} / {dia.dia_semana} / {tipo_str}",
                                    regra="Restrição alimentar violada: Lactose/Leite",
                                    detalhe=f"Ingrediente derivado de leite '{ing.nome_taco}' em '{prato.nome}'.",
                                    tipo="critico",
                                ))
                            if tem_restricao_gluten and "gluten" in classes:
                                inconformidades.append(InconformidadePNAESchema(
                                    escopo=f"semana {semana.numero} / {dia.dia_semana} / {tipo_str}",
                                    regra="Restrição alimentar violada: Glúten",
                                    detalhe=f"Ingrediente com glúten '{ing.nome_taco}' em '{prato.nome}'.",
                                    tipo="critico",
                                ))
                            if tem_restricao_ovo and (("ovo" in _tokens_normalizados(ing.nome_taco)) or (taco and "ovos" in _texto_normalizado(taco.category))):
                                inconformidades.append(InconformidadePNAESchema(
                                    escopo=f"semana {semana.numero} / {dia.dia_semana} / {tipo_str}",
                                    regra="Restrição alimentar violada: Ovos",
                                    detalhe=f"Ingrediente com ovo '{ing.nome_taco}' em '{prato.nome}'.",
                                    tipo="critico",
                                ))
                    else:
                        classes_prato = _classificar_alimento(prato.nome)
                        if "cereal_tuberculo" in classes_prato:
                            tem_cereal_tuberculo = True
                        if "proteina_animal" in classes_prato or "leguminosa" in classes_prato:
                            if "proteina_animal" in classes_prato:
                                tem_proteina = True
                                toks = _tokens_normalizados(prato.nome)
                                if toks & {"frango", "galinha", "ave"}:
                                    proteinas_refeicao.add("frango")
                                elif toks & {"carne", "bovina", "boi", "patinho", "acem", "alcatra", "bolonhesa"}:
                                    proteinas_refeicao.add("carne bovina")
                                elif toks & {"peixe", "tilapia", "sardinha", "atum", "merluza", "pescada"}:
                                    proteinas_refeicao.add("peixe")
                                elif toks & {"ovo", "ovos", "omelete"}:
                                    proteinas_refeicao.add("ovo")
                                elif toks & {"suina", "porco", "pernil", "lombo"}:
                                    proteinas_refeicao.add("carne suína")

                        if tem_restricao_lactose and "laticinio" in classes_prato:
                            inconformidades.append(InconformidadePNAESchema(
                                escopo=f"semana {semana.numero} / {dia.dia_semana} / {tipo_str}",
                                regra="Restrição alimentar violada: Lactose/Leite",
                                detalhe=f"Prato derivado de leite '{prato.nome}'.",
                                tipo="critico",
                            ))
                        elif tem_restricao_lactose and any(p in _tokens_normalizados(prato.nome) for p in ["pure", "creme", "estrogonofe", "strogonoff"]) and "sem lactose" not in _texto_normalizado(prato.nome):
                            inconformidades.append(InconformidadePNAESchema(
                                escopo=f"semana {semana.numero} / {dia.dia_semana} / {tipo_str}",
                                regra="Restrição alimentar: composição indeterminada",
                                detalhe=f"A preparação '{prato.nome}' possui composição não detalhada e pode conter leite ou manteiga em formulações convencionais. Necessária validação de ficha técnica.",
                                tipo="advertencia",
                            ))
                        if tem_restricao_gluten and "gluten" in classes_prato:
                            inconformidades.append(InconformidadePNAESchema(
                                escopo=f"semana {semana.numero} / {dia.dia_semana} / {tipo_str}",
                                regra="Restrição alimentar violada: Glúten",
                                detalhe=f"Prato com glúten '{prato.nome}'.",
                                tipo="critico",
                            ))
                        elif tem_restricao_gluten and any(p in _tokens_normalizados(prato.nome) for p in ["empanad", "torta", "empada", "quiche", "croquete", "coxinha", "pastel", "bolinho", "panqueca"]) and "sem gluten" not in _texto_normalizado(prato.nome) and "polvilho" not in _tokens_normalizados(prato.nome):
                            inconformidades.append(InconformidadePNAESchema(
                                escopo=f"semana {semana.numero} / {dia.dia_semana} / {tipo_str}",
                                regra="Restrição alimentar: composição indeterminada",
                                detalhe=f"A preparação '{prato.nome}' possui composição não especificada e pode conter farinha de trigo. Necessária validação de ficha técnica.",
                                tipo="advertencia",
                            ))
                        if tem_restricao_ovo and "ovo" in _tokens_normalizados(prato.nome):
                            inconformidades.append(InconformidadePNAESchema(
                                escopo=f"semana {semana.numero} / {dia.dia_semana} / {tipo_str}",
                                regra="Restrição alimentar violada: Ovos",
                                detalhe=f"Prato com ovo '{prato.nome}'.",
                                tipo="critico",
                            ))
                        elif tem_restricao_ovo and any(p in _tokens_normalizados(prato.nome) for p in ["maionese", "sufle", "quiche", "empanad", "creme", "mousse", "pudim"]):
                            inconformidades.append(InconformidadePNAESchema(
                                escopo=f"semana {semana.numero} / {dia.dia_semana} / {tipo_str}",
                                regra="Restrição alimentar: composição indeterminada",
                                detalhe=f"A preparação '{prato.nome}' possui composição não especificada e pode conter ovos. Necessária validação de ficha técnica.",
                                tipo="advertencia",
                            ))

                # 1. Regra de frutas independentes servidas separadamente na mesma refeição
                frutas_especificas = {f for f in frutas_avulsas if f not in GENERICOS_FRUTA}
                if frutas_especificas:
                    frutas_avulsas = frutas_especificas

                if len(frutas_avulsas) > 1:
                    eh_excesso_critico = len(frutas_avulsas) >= 3
                    inconformidades.append(InconformidadePNAESchema(
                        escopo=f"semana {semana.numero} / {dia.dia_semana} / {tipo_str}",
                        regra="Coerência culinária: excesso de frutas na mesma refeição" if eh_excesso_critico else "Coerência culinária: distribuição de frutas na mesma refeição",
                        detalhe=(
                            f"Foram encontradas {len(frutas_avulsas)} frutas avulsas distintas ({', '.join(sorted(frutas_avulsas))}). "
                            + ("Excesso redundante de sobremesas frutadas na mesma refeição segundo diretriz culinária interna." if eh_excesso_critico else "Recomendação culinária de montagem de cardápio: recomenda-se distribuir as frutas entre diferentes refeições ou dias para otimizar a aceitação.")
                        ),
                        tipo="critico" if eh_excesso_critico else "advertencia",
                    ))

                # 2. Estrutura de refeição principal (almoço/jantar)
                if eh_principal:
                    if not tem_proteina:
                        inconformidades.append(InconformidadePNAESchema(
                            escopo=f"semana {semana.numero} / {dia.dia_semana} / {tipo_str}",
                            regra="Coerência culinária: ausência de preparação proteica",
                            detalhe=f"A refeição principal '{tipo_str}' não possui prato proteico (carne bovina, frango, peixe ou ovos).",
                            tipo="critico",
                        ))
                    if not tem_cereal_tuberculo:
                        inconformidades.append(InconformidadePNAESchema(
                            escopo=f"semana {semana.numero} / {dia.dia_semana} / {tipo_str}",
                            regra="Coerência culinária: ausência de base energética",
                            detalhe=f"A refeição principal '{tipo_str}' não possui cereal ou tubérculo de base (arroz, macarrão, mandioca ou batata).",
                            tipo="critico",
                        ))
                    if len(proteinas_refeicao) > 1:
                        inconformidades.append(InconformidadePNAESchema(
                            escopo=f"semana {semana.numero} / {dia.dia_semana} / {tipo_str}",
                            regra="Coerência culinária: múltiplas carnes concorrentes",
                            detalhe=f"Refeição com preparações proteicas concorrentes ({', '.join(sorted(proteinas_refeicao))}). Sirva apenas uma carne principal.",
                            tipo="advertencia",
                        ))

                    if proteinas_refeicao:
                        if not proteina_principal_do_dia or "almoc" in tipo_str:
                            proteina_principal_do_dia = next(iter(proteinas_refeicao))

            if proteina_principal_do_dia:
                proteina_por_dia.append(proteina_principal_do_dia)

        # 3. Monotonia proteica: 3 ou mais dias consecutivos com a mesma proteína
        repeticoes_consecutivas = 1
        for i in range(1, len(proteina_por_dia)):
            if proteina_por_dia[i] == proteina_por_dia[i - 1]:
                repeticoes_consecutivas += 1
                if repeticoes_consecutivas >= 3:
                    inconformidades.append(InconformidadePNAESchema(
                        escopo=f"semana {semana.numero}",
                        regra="Variedade semanal: monotonia proteica",
                        detalhe=f"A preparação com {proteina_por_dia[i]} foi repetida em {repeticoes_consecutivas} dias consecutivos.",
                        tipo="advertencia",
                    ))
            else:
                repeticoes_consecutivas = 1

    return inconformidades
