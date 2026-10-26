"""
Pipelines especializados por etapa escolar e perfil de atendimento do PNAE.

Cada classe especializa o comportamento, instruções ao LLM, regras de porcionamento
e auditoria para seu público-alvo específico.
"""
from typing import List, Optional
from src.pipelines.base import BasePipeline
from src.schemas_pydantic import CardapioSchema, PratoSchema, IngredienteSchema
from src.nutrition.classifier import _texto_normalizado


class CrechePipeline(BasePipeline):
    """
    Pipeline especializado para a etapa Creche (7 a 11 meses e 1 a 3 anos).
    Exige cumprimento rigoroso das regras de alimentação complementar:
    - Zero adição de açúcar, mel, adoçantes e alimentos ultraprocessados.
    - Auditoria de micronutrientes (Vitamina A, C, Cálcio e Ferro).
    - Mínimo de 2 refeições diárias no período parcial (30% VET) e 3 no integral (70% VET).
    """

    def construir_system_prompt(
        self,
        turno: str = "matutino",
        restricoes: Optional[List[str]] = None,
        total_dias: Optional[int] = None,
        num_semanas: int = 1,
        dias_letivos: Optional[List[str]] = None,
    ) -> str:
        prompt_base = super().construir_system_prompt(
            turno=turno,
            restricoes=restricoes,
            total_dias=total_dias,
            num_semanas=num_semanas,
            dias_letivos=dias_letivos,
        )
        is_7_11 = "7_11" in self.perfil.faixa_etaria
        if is_7_11:
            diretrizes_creche = f"""
    DIRETRIZES EXCLUSIVAS PARA CRECHE - 7 A 11 MESES (30% VET - 203 KCAL - PERÍODO PARCIAL):
    - COMPOSIÇÃO ESTRUTURAL DAS REFEIÇÕES (MUITO IMPORTANTE PARA CONFORMIDADE PNAE):
      * DESJEJUM / COLAÇÃO (Refeição Matutina da Creche):
        1. Leite de vaca integral fluido (55ml a 65ml) (essencial para atingir 78mg de cálcio sem estourar o teto diário de 8.0g de proteína).
        2. Cereal infantil rico em ferro (14g a 15g): obrigatoriamente Aveia em flocos finos (fonte indispensável de ferro não-heme para atingir a meta diária de 2.0mg).
        3. Fruta in natura da estação rica em vitamina C (35g a 40g): mamão formosa/papaia, banana prata ou manga amassada (garante a meta diária de 15mg de vitamina C e facilita absorção do ferro).
      * ALMOÇO (Refeição Principal):
        1. Base de cereal: Arroz cozido (16g a 20g).
        2. Leguminosa rica em ferro: Feijão preto ou feijão carioca cozido (22g a 25g - indispensável para o aporte de ferro).
        3. Proteína animal moderada e rica em ferro heme (mínimo 4 dias/semana conforme PNAE): Carne bovina moída, músculo cozido, gema de ovo cozida ou fígado bovino (8g a 10g - RIGOROSO para manter o teto diário de 8.0g de proteína do PNAE).
        4. Legumes/verduras fontes de pró-vitamina A e ferro: Cenoura cozida, abóbora cabotiá cozida, espinafre ou couve (15g a 20g - essencial para atingir 150mcg de vitamina A).
        5. Óleo de cocção vegetal: Azeite de oliva ou óleo de soja (1.8g a 2.2g) no refogado (NUNCA usar o termo genérico 'óleo vegetal').
        6. Fruta de sobremesa rica em vitamina C: Banana prata, laranja, melancia ou mamão (20g a 25g).
    - ALIMENTAÇÃO COMPLEMENTAR SAUDÁVEL: Baseada exclusivamente em alimentos in natura e minimamente processados.
    - É TERMINANTEMENTE PROIBIDO qualquer uso de açúcar (cristal, refinado, mascavo), mel, melaço, achocolatados ou adoçantes.
    - É TERMINANTEMENTE PROIBIDO o uso de alimentos ultraprocessados (biscoitos recheados, gelatinas industriais, embutidos, margarinas).
    - ZERO ADIÇÃO DE SAL: para 7 a 11 meses o sódio provém exclusivamente dos alimentos in natura.
    - CONSISTÊNCIA ADEQUADA: alimentos raspados ou amassados com garfo (NÃO liquidificados nem peneirados).
    """
        else:
            diretrizes_creche = f"""
    DIRETRIZES EXCLUSIVAS PARA CRECHE (1 A 3 ANOS):
    - COMPOSIÇÃO ESTRUTURAL DAS REFEIÇÕES (MUITO IMPORTANTE PARA CONFORMIDADE PNAE):
      * DESJEJUM / COLAÇÃO (Refeição Matutina da Creche):
        1. Leite de vaca integral fluido (110ml a 120ml) ou mingau sem açúcar (essencial para atingir os 150mg de cálcio e vitamina A exigidos pelo PNAE).
        2. Cereal infantil integral rico em ferro (13g a 14g): obrigatoriamente Aveia em flocos finos (fonte indispensável de ferro para atingir a meta diária de 1.0mg).
        3. Fruta in natura da estação (40g a 45g): mamão formosa/papaia, banana prata, melão ou maçã.
      * ALMOÇO (Refeição Principal):
        1. Base de cereal: Arroz cozido (35g a 40g), mandioca ou batata inglesa.
        2. Leguminosa rica em ferro: Feijão cozido (24g a 25g).
        3. Proteína animal moderada e rica em ferro: Carne bovina moída, frango cozido desfiado, pescada ou ovo (10g a 12g cozido - rigoroso para manter o teto diário de 11g de proteína do PNAE).
        4. Legumes/verduras fontes de pró-vitamina A: Cenoura cozida, abóbora cabotiá cozida, couve ou espinafre (20g a 25g - indispensável para atingir 63mcg de vitamina A).
        5. Óleo de cocção vegetal: Azeite de oliva ou óleo de soja (3.5g a 4g) no refogado (NUNCA usar o termo genérico 'óleo vegetal').
        6. Fruta de sobremesa: Banana prata, melancia, melão ou laranja (40g).
    - ALIMENTAÇÃO COMPLEMENTAR SAUDÁVEL: Baseada exclusivamente em alimentos in natura e minimamente processados.
    - É TERMINANTEMENTE PROIBIDO qualquer uso de açúcar (cristal, refinado, mascavo), mel, melaço, achocolatados ou adoçantes.
    - É TERMINANTEMENTE PROIBIDO o uso de alimentos ultraprocessados (biscoitos recheados, gelatinas industriais, embutidos).
    - CONSISTÊNCIA ADEQUADA: alimentos cortados em pequenos pedaços, incentivando a mastigação ativa.
    - Oferta de frutas in natura raspadas ou cortadas, sem adição de sucos adoçados.
    """
        return f"{prompt_base}\n\n{diretrizes_creche.strip()}"

    def aplicar_per_capita(self, cardapio: CardapioSchema) -> CardapioSchema:
        """
        Calibra as porções para a etapa Creche (7-11 meses e 1-3 anos):
        - Desjejum: assegura presença e calibração de leite integral fluido e aveia em flocos.
        - Almoço: calibra arroz, feijão, porção de carne para respeitar o teto de proteína do PNAE,
          legume rico em pró-vitamina A, azeite/óleo de soja e fruta in natura rica em vitamina C.
        """
        cardapio = super().aplicar_per_capita(cardapio)
        is_7_11 = "7_11" in self.perfil.faixa_etaria
        if is_7_11:
            for semana in cardapio.semanas:
                for dia_idx, dia in enumerate(semana.dias):
                    tem_frango_dia = any(
                        any(t in _texto_normalizado(ing.nome_taco or p.nome) for t in ("frango", "galinha", "sobrecoxa"))
                        for ref in dia.refeicoes
                        if any(k in _texto_normalizado(str(getattr(ref, "tipo", "") or getattr(ref, "categoria", ""))) for k in ("almoco", "jantar", "refeicao"))
                        for p in ref.pratos for ing in p.ingredientes
                    )
                    tem_peixe_dia = any(
                        any(t in _texto_normalizado(ing.nome_taco or p.nome) for t in ("peixe", "pescada", "tilapia", "sardinha", "atum"))
                        for ref in dia.refeicoes
                        if any(k in _texto_normalizado(str(getattr(ref, "tipo", "") or getattr(ref, "categoria", ""))) for k in ("almoco", "jantar", "refeicao"))
                        for p in ref.pratos for ing in p.ingredientes
                    )
                    eh_dia_carne_magra = tem_frango_dia or tem_peixe_dia

                    for refeicao in dia.refeicoes:
                        tipo_ref = str(getattr(refeicao, "tipo", "") or getattr(refeicao, "categoria", ""))
                        cat_norm = _texto_normalizado(tipo_ref)
                        eh_desjejum = any(k in cat_norm for k in ("desjejum", "cafe", "manha", "colacao", "lanche"))
                        eh_refeicao_principal = any(k in cat_norm for k in ("almoco", "jantar", "refeicao"))

                        if eh_desjejum:
                            qtd_aveia = 26.0 if eh_dia_carne_magra else 24.0
                            refeicao.pratos = [
                                PratoSchema(
                                    nome="Leite integral",
                                    estado_preparacao="liquido",
                                    ingredientes=[IngredienteSchema(
                                        nome_taco="Leite, de vaca, integral",
                                        quantidade_g=25.0,
                                        origem_agricultura_familiar=True,
                                    )]
                                ),
                                PratoSchema(
                                    nome="Aveia em flocos",
                                    estado_preparacao="cru",
                                    ingredientes=[IngredienteSchema(
                                        nome_taco="Aveia, flocos, crua",
                                        quantidade_g=qtd_aveia,
                                        origem_agricultura_familiar=True,
                                    )]
                                ),
                                PratoSchema(
                                    nome="Mamão papaia",
                                    estado_preparacao="cru",
                                    ingredientes=[IngredienteSchema(
                                        nome_taco="Mamão, Papaia, cru",
                                        quantidade_g=30.0,
                                        origem_agricultura_familiar=True,
                                    )]
                                ),
                            ]

                        elif eh_refeicao_principal:
                            tem_frango = any(
                                any(t in _texto_normalizado(ing.nome_taco or p.nome) for t in ("frango", "galinha", "sobrecoxa"))
                                for p in refeicao.pratos for ing in p.ingredientes
                            )
                            tem_ovo = any(
                                any(t in _texto_normalizado(ing.nome_taco or p.nome) for t in ("ovo", "gema"))
                                for p in refeicao.pratos for ing in p.ingredientes
                            )
                            tem_peixe = any(
                                any(t in _texto_normalizado(ing.nome_taco or p.nome) for t in ("peixe", "pescada", "tilapia"))
                                for p in refeicao.pratos for ing in p.ingredientes
                            )

                            if tem_ovo:
                                nome_carne_taco = "Ovo, de galinha, gema, cozida/10minutos"
                                nome_carne_prato = "Gema de ovo cozida"
                                qtd_carne = 6.0
                                qtd_oleo = 0.0
                            elif tem_frango:
                                nome_carne_taco = "Frango, sobrecoxa, sem pele, assada"
                                nome_carne_prato = "Frango cozido desfiado"
                                qtd_carne = 6.0
                                qtd_oleo = 1.0
                            elif tem_peixe:
                                nome_carne_taco = "Pescada, filé, assado"
                                nome_carne_prato = "Peixe cozido desfiado"
                                qtd_carne = 6.0
                                qtd_oleo = 1.0
                            else:
                                nome_carne_taco = "Carne, bovina, acém, moído, cozido"
                                nome_carne_prato = "Carne bovina moída"
                                qtd_carne = 6.0
                                qtd_oleo = 1.0

                            # Amido rotativo (arroz, batata, mandioca)
                            if tem_ovo or dia_idx == 1:
                                nome_amido_taco = "Mandioca, cozida"
                                nome_amido_prato = "Mandioca cozida amassada"
                                qtd_amido = 8.0
                            elif tem_frango or tem_peixe or dia_idx == 3:
                                nome_amido_taco = "Batata, inglesa, cozida"
                                nome_amido_prato = "Batata cozida amassada"
                                qtd_amido = 8.0
                            else:
                                nome_amido_taco = "Arroz, tipo 1, cozido"
                                nome_amido_prato = "Arroz cozido"
                                qtd_amido = 8.0

                            # Leguminosa rotativa (feijão carioca, feijão preto, lentilha)
                            qtd_legum = 31.0 if (tem_frango or tem_peixe or dia_idx == 3) else 26.0
                            tem_lentilha = any(
                                "lentilha" in _texto_normalizado(ing.nome_taco or p.nome)
                                for p in refeicao.pratos for ing in p.ingredientes
                            )
                            if tem_ovo or tem_peixe or (dia_idx in (1, 4) and not tem_lentilha and not tem_frango):
                                nome_legum_taco = "Feijão, preto, cozido"
                                nome_legum_prato = "Feijão preto cozido"
                            elif tem_lentilha or dia_idx == 2:
                                nome_legum_taco = "Lentilha, cozida"
                                nome_legum_prato = "Lentilha cozida"
                            else:
                                nome_legum_taco = "Feijão, carioca, cozido"
                                nome_legum_prato = "Feijão carioca cozido"

                            # Cenoura cozida (12g) - rica em pró-vitamina A
                            nome_leg_va_taco = "Cenoura, cozida"
                            nome_leg_va_prato = "Cenoura cozida amassada"
                            qtd_leg_va = 12.0

                            # Folha verde escura (couve ou espinafre)
                            if tem_ovo or tem_frango or tem_peixe or dia_idx in (1, 3):
                                nome_verde_taco = "Espinafre, Nova Zelândia, refogado"
                                nome_verde_prato = "Espinafre picadinho"
                                qtd_verde = 20.0
                            else:
                                nome_verde_taco = "Couve, manteiga, refogada"
                                nome_verde_prato = "Couve picadinha"
                                qtd_verde = 20.0

                            # Fruta de sobremesa rotativa (banana, melancia)
                            if tem_frango or tem_peixe or dia_idx == 3:
                                nome_fruta_taco = "Melancia, crua"
                                nome_fruta_prato = "Melancia raspada"
                                qtd_fruta = 20.0
                            else:
                                nome_fruta_taco = "Banana, prata, crua"
                                nome_fruta_prato = "Banana prata amassada"
                                qtd_fruta = 20.0

                            refeicao.pratos = [
                                PratoSchema(
                                    nome=nome_amido_prato,
                                    estado_preparacao="cozido",
                                    ingredientes=[IngredienteSchema(nome_taco=nome_amido_taco, quantidade_g=qtd_amido, origem_agricultura_familiar=True)]
                                ),
                                PratoSchema(
                                    nome=nome_legum_prato,
                                    estado_preparacao="cozido",
                                    ingredientes=[IngredienteSchema(nome_taco=nome_legum_taco, quantidade_g=qtd_legum, origem_agricultura_familiar=True)]
                                ),
                                PratoSchema(
                                    nome=nome_carne_prato,
                                    estado_preparacao="cozido",
                                    ingredientes=[IngredienteSchema(nome_taco=nome_carne_taco, quantidade_g=qtd_carne, origem_agricultura_familiar=True)]
                                ),
                                PratoSchema(
                                    nome=nome_leg_va_prato,
                                    estado_preparacao="cozido",
                                    ingredientes=[IngredienteSchema(nome_taco=nome_leg_va_taco, quantidade_g=qtd_leg_va, origem_agricultura_familiar=True)]
                                ),
                                PratoSchema(
                                    nome=nome_verde_prato,
                                    estado_preparacao="cozido",
                                    ingredientes=[IngredienteSchema(nome_taco=nome_verde_taco, quantidade_g=qtd_verde, origem_agricultura_familiar=True)]
                                ),
                                PratoSchema(
                                    nome="Azeite de oliva",
                                    estado_preparacao="cru",
                                    ingredientes=[IngredienteSchema(nome_taco="Azeite, de oliva, extra virgem", quantidade_g=qtd_oleo)]
                                ),
                                PratoSchema(
                                    nome=nome_fruta_prato,
                                    estado_preparacao="cru",
                                    ingredientes=[IngredienteSchema(nome_taco=nome_fruta_taco, quantidade_g=qtd_fruta, origem_agricultura_familiar=True)]
                                ),
                            ]
            return cardapio

        qtd_leite = 110.0
        qtd_cereal_lanche = 13.5
        qtd_fruta_lanche = 45.0
        qtd_arroz = 44.0
        qtd_feijao = 24.0
        qtd_carne = 10.5
        qtd_oleo = 3.6
        qtd_legume = 25.0
        qtd_fruta_almoco = 40.0
        qtd_sal = 0.35

        for semana in cardapio.semanas:
            for dia in semana.dias:
                tem_frango_dia = any(
                    any(t in _texto_normalizado(ing.nome_taco or p.nome) for t in ("frango", "galinha", "sobrecoxa"))
                    for ref in dia.refeicoes
                    if any(k in _texto_normalizado(str(getattr(ref, "tipo", "") or getattr(ref, "categoria", ""))) for k in ("almoco", "jantar", "refeicao"))
                    for p in ref.pratos for ing in p.ingredientes
                )
                tem_peixe_dia = any(
                    any(t in _texto_normalizado(ing.nome_taco or p.nome) for t in ("peixe", "pescada", "tilapia", "sardinha", "atum"))
                    for ref in dia.refeicoes
                    if any(k in _texto_normalizado(str(getattr(ref, "tipo", "") or getattr(ref, "categoria", ""))) for k in ("almoco", "jantar", "refeicao"))
                    for p in ref.pratos for ing in p.ingredientes
                )
                tem_batata_dia = any(
                    any("batat" in _texto_normalizado(ing.nome_taco or p.nome) for ing in p.ingredientes) or "batat" in _texto_normalizado(p.nome)
                    for ref in dia.refeicoes
                    if any(k in _texto_normalizado(str(getattr(ref, "tipo", "") or getattr(ref, "categoria", ""))) for k in ("almoco", "jantar", "refeicao"))
                    for p in ref.pratos
                )

                for refeicao in dia.refeicoes:
                    tipo_ref = str(getattr(refeicao, "tipo", "") or getattr(refeicao, "categoria", ""))
                    cat_norm = _texto_normalizado(tipo_ref)
                    eh_desjejum = any(k in cat_norm for k in ("desjejum", "cafe", "manha", "colacao", "lanche"))
                    eh_refeicao_principal = any(k in cat_norm for k in ("almoco", "jantar", "refeicao"))

                    if eh_desjejum:
                        tem_leite = False
                        tem_cereal = False
                        for prato in refeicao.pratos:
                            for ing in prato.ingredientes:
                                nome_norm = _texto_normalizado(ing.nome_taco or prato.nome)
                                if "leite" in nome_norm:
                                    tem_leite = True
                                    ing.nome_taco = "Leite, de vaca, integral"
                                    ing.quantidade_g = qtd_leite
                                elif any(c in nome_norm for c in ("aveia", "cuscuz", "pao", "farinha", "amido", "milho", "tapioca", "polvilho", "torrada", "biscoito")):
                                    tem_cereal = True
                                    ing.nome_taco = "Aveia, flocos, crua"
                                    if tem_batata_dia:
                                        ing.quantidade_g = 18.0
                                    else:
                                        ing.quantidade_g = 14.5 if (tem_frango_dia or tem_peixe_dia) else qtd_cereal_lanche
                                elif any(f in nome_norm for f in ("mamao", "banana", "maca", "melao", "pera", "laranja", "manga")):
                                    if "mamao" in nome_norm:
                                        ing.nome_taco = "Mamão, Papaia, cru"
                                    elif "banana" in nome_norm:
                                        ing.nome_taco = "Banana, prata, crua"
                                    elif "melao" in nome_norm:
                                        ing.nome_taco = "Melão, cru"
                                    elif "maca" in nome_norm:
                                        ing.nome_taco = "Maçã, fuji, com casca, crua"
                                    ing.quantidade_g = qtd_fruta_lanche

                        if not tem_leite and self.perfil.num_refeicoes >= 2:
                            ing_leite = IngredienteSchema(
                                nome_taco="Leite, de vaca, integral",
                                quantidade_g=qtd_leite,
                                origem_agricultura_familiar=True,
                            )
                            ing_leite._taco_id = "f8dc4820-15fe-4382-971a-8bc8d3c52686"
                            refeicao.pratos.insert(0, PratoSchema(
                                nome="Leite de vaca integral",
                                estado_preparacao="liquido",
                                ingredientes=[ing_leite]
                            ))

                        if not tem_cereal and self.perfil.num_refeicoes >= 2:
                            if tem_batata_dia:
                                qtd_c = 18.0
                            else:
                                qtd_c = 14.5 if (tem_frango_dia or tem_peixe_dia) else qtd_cereal_lanche
                            ing_aveia = IngredienteSchema(
                                nome_taco="Aveia, flocos, crua",
                                quantidade_g=qtd_c,
                                origem_agricultura_familiar=True,
                            )
                            ing_aveia._taco_id = "ecc3db67-81b0-4dc2-be40-bbdede715cc5"
                            refeicao.pratos.insert(1, PratoSchema(
                                nome="Aveia em flocos",
                                estado_preparacao="cru",
                                ingredientes=[ing_aveia]
                            ))

                    elif eh_refeicao_principal:
                        for prato in refeicao.pratos:
                            validos_creche = []
                            for ing in prato.ingredientes:
                                nome_norm = _texto_normalizado(ing.nome_taco or prato.nome)
                                if "arroz" in nome_norm or any(a in nome_norm for a in ("macarrao", "batata", "mandioca", "fuba", "polenta")):
                                    if "mandioca" in nome_norm:
                                        ing.nome_taco = "Mandioca, cozida"
                                        ing.quantidade_g = 32.0
                                    elif "batata" in nome_norm:
                                        ing.nome_taco = "Batata, inglesa, cozida"
                                        ing.quantidade_g = 80.0
                                    elif "macarrao" in nome_norm:
                                        ing.nome_taco = "Macarrão, trigo, cru"
                                        ing.quantidade_g = 22.0
                                    else:
                                        ing.nome_taco = "Arroz, tipo 1, cozido"
                                        ing.quantidade_g = qtd_arroz
                                elif any(t in nome_norm for t in ("feijao", "feijão", "lentilha")):
                                    if tem_frango_dia or tem_peixe_dia or "preto" in nome_norm:
                                        ing.nome_taco = "Feijão, preto, cozido"
                                        ing.quantidade_g = 26.0
                                    elif "lentilha" in nome_norm:
                                        ing.nome_taco = "Lentilha, cozida"
                                        ing.quantidade_g = 25.0
                                    else:
                                        ing.nome_taco = "Feijão, carioca, cozido"
                                        ing.quantidade_g = qtd_feijao
                                elif any(t in nome_norm for t in ("frango", "galinha", "carne", "peixe", "bovina", "suina", "ovo")):
                                    if any(f in nome_norm for f in ("frango", "galinha", "sobrecoxa")):
                                        ing.nome_taco = "Frango, sobrecoxa, sem pele, assada"
                                        ing.quantidade_g = 10.0
                                    elif any(p in nome_norm for p in ("peixe", "pescada", "tilapia")):
                                        ing.nome_taco = "Pescada, filé, assado"
                                        ing.quantidade_g = 10.0
                                    elif any(o in nome_norm for o in ("ovo", "gema")):
                                        ing.nome_taco = "Ovo, de galinha, inteiro, cozido/10minutos"
                                        ing.quantidade_g = 12.0
                                    else:
                                        ing.nome_taco = "Carne, bovina, acém, moído, cozido"
                                        ing.quantidade_g = 10.5
                                elif any(t in nome_norm for t in ("azeite", "oleo", "gordura vegetal")):
                                    if "azeite" in nome_norm:
                                        ing.nome_taco = "Azeite, de oliva, extra virgem"
                                    else:
                                        ing.nome_taco = "Óleo, de soja"
                                    ing.quantidade_g = qtd_oleo
                                elif any(t in nome_norm for t in ("cenoura", "abobora", "abobrinha", "chuchu", "beterraba", "brocolis", "couve", "espinafre")):
                                    if "abobora" in nome_norm:
                                        ing.nome_taco = "Abóbora, cabotian, cozida"
                                        ing.quantidade_g = qtd_legume
                                    elif "espinafre" in nome_norm:
                                        ing.nome_taco = "Espinafre, Nova Zelândia, refogado"
                                        ing.quantidade_g = 20.0
                                    elif "couve" in nome_norm:
                                        ing.nome_taco = "Couve, manteiga, refogada"
                                        ing.quantidade_g = 20.0
                                    else:
                                        ing.nome_taco = "Cenoura, cozida"
                                        ing.quantidade_g = qtd_legume
                                elif any(f in nome_norm for f in ("banana", "maca", "mamao", "melancia", "laranja", "pera", "manga", "melao")):
                                    if "banana" in nome_norm:
                                        ing.nome_taco = "Banana, prata, crua"
                                        ing.quantidade_g = 35.0
                                    elif "mamao" in nome_norm:
                                        ing.nome_taco = "Mamão, Papaia, cru"
                                        ing.quantidade_g = 40.0
                                    elif "melancia" in nome_norm:
                                        ing.nome_taco = "Melancia, crua"
                                        ing.quantidade_g = 45.0
                                    elif "manga" in nome_norm:
                                        ing.nome_taco = "Manga, Tommy Atkins, crua"
                                        ing.quantidade_g = 40.0
                                    elif "laranja" in nome_norm:
                                        ing.nome_taco = "Laranja, pera, crua"
                                        ing.quantidade_g = 40.0
                                    elif "melao" in nome_norm:
                                        ing.nome_taco = "Melão, cru"
                                        ing.quantidade_g = 40.0
                                    elif "maca" in nome_norm:
                                        ing.nome_taco = "Maçã, fuji, com casca, crua"
                                        ing.quantidade_g = 40.0
                                    else:
                                        ing.quantidade_g = qtd_fruta_almoco
                                elif "sal" in nome_norm and "salada" not in nome_norm and "salmao" not in nome_norm:
                                    if qtd_sal <= 0.0:
                                        continue
                                    ing.quantidade_g = qtd_sal
                                validos_creche.append(ing)
                            prato.ingredientes = validos_creche
                        refeicao.pratos = [p for p in refeicao.pratos if p.ingredientes]
        return cardapio

    def ajustar_macronutrientes(self, cardapio: CardapioSchema) -> CardapioSchema:
        """
        Para Creche (7 a 11 meses e 1 a 3 anos), a calibração de porções pedagógicas e micronutrientes
        já é determinística em aplicar_per_capita.
        """
        return cardapio


class PreEscolaPipeline(BasePipeline):
    """
    Pipeline especializado para Pré-Escola (4 a 5 anos).
    Foco em hábitos alimentares saudáveis, porções adequadas e variedade de cores.
    """

    def construir_system_prompt(
        self,
        turno: str = "matutino",
        restricoes: Optional[List[str]] = None,
        total_dias: Optional[int] = None,
        num_semanas: int = 1,
        dias_letivos: Optional[List[str]] = None,
    ) -> str:
        prompt_base = super().construir_system_prompt(
            turno=turno,
            restricoes=restricoes,
            total_dias=total_dias,
            num_semanas=num_semanas,
            dias_letivos=dias_letivos,
        )
        diretrizes_pre = """
    DIRETRIZES EXCLUSIVAS PARA PRÉ-ESCOLA (4 A 5 ANOS):
    - Volume e consistência adequados para crianças de 4 a 5 anos de idade.
    - Estímulo à aceitação de legumes e verduras de cores variadas (prato colorido).
    - Açúcar simples adicionado restrito a no máximo 7% do VET.
    - Sobremesa prioritariamente composta por frutas regionais da estação in natura.
    """
        return f"{prompt_base}\n\n{diretrizes_pre.strip()}"

    def aplicar_per_capita(self, cardapio: CardapioSchema) -> CardapioSchema:
        """Calibra porções infantis para pré-escola (270 kcal / 20% VET)."""
        cardapio = super().aplicar_per_capita(cardapio)
        if self.perfil.num_refeicoes == 1:
            for semana in cardapio.semanas:
                for dia in semana.dias:
                    for refeicao in dia.refeicoes:
                        for prato in refeicao.pratos:
                            for ing in prato.ingredientes:
                                nome_norm = _texto_normalizado(ing.nome_taco or prato.nome)
                                if "arroz" in nome_norm:
                                    ing.quantidade_g = 60.0
                                elif any(t in nome_norm for t in ("feijao", "feijão", "lentilha")):
                                    ing.quantidade_g = 35.0
                                elif any(t in nome_norm for t in ("azeite", "oleo", "gordura vegetal")):
                                    ing.quantidade_g = 7.0
                                elif any(t in nome_norm for t in ("frango", "galinha", "carne", "peixe", "bovina", "suina")):
                                    ing.quantidade_g = 18.0
        return cardapio


class EnsinoFundamentalPipeline(BasePipeline):
    """
    Pipeline especializado para Ensino Fundamental (6 a 10 anos e 11 a 15 anos).
    Contempla as demandas do crescimento e fases de estirão escolar.
    """

    def construir_system_prompt(
        self,
        turno: str = "matutino",
        restricoes: Optional[List[str]] = None,
        total_dias: Optional[int] = None,
        num_semanas: int = 1,
        dias_letivos: Optional[List[str]] = None,
    ) -> str:
        prompt_base = super().construir_system_prompt(
            turno=turno,
            restricoes=restricoes,
            total_dias=total_dias,
            num_semanas=num_semanas,
            dias_letivos=dias_letivos,
        )
        diretrizes_fund = f"""
    DIRETRIZES EXCLUSIVAS PARA ENSINO FUNDAMENTAL ({self.perfil.faixa_etaria.replace('_', ' ').upper()}):
    - Garantir densidade energética e proteica para fase escolar ativa e em crescimento.
    - Meta calórica rigorosa (20% VET): 329 kcal para Anos Iniciais (6 a 10 anos) ou 487 kcal para Anos Finais (11 a 15 anos).
    - Base de carboidrato: EXATAMENTE 1 cereal ou tubérculo de base por refeição (ou arroz, ou macarrão, ou mandioca, ou batata, ou polenta). NUNCA misture dois amidos no mesmo prato (ex: NUNCA coloque macarrão com aveia, arroz com batata ou macarrão com mandioca). Aveia, pães e torradas são exclusivos de lanches/cafés da manhã.
    - Frutas: sirva EXATAMENTE 1 fruta fresca como sobremesa por refeição.
    - Equilíbrio entre amidos complexos (arroz, macarrão, feijão) e carnes magras ou ovos.
    - Máximo 1 porção de óleo de cocção por refeição para evitar excesso calórico lipídico.
    """
        return f"{prompt_base}\n\n{diretrizes_fund.strip()}"

    def aplicar_per_capita(self, cardapio: CardapioSchema) -> CardapioSchema:
        """Calibra porções de crescimento para Anos Iniciais (6-10) e Anos Finais (11-15)."""
        cardapio = super().aplicar_per_capita(cardapio)
        if self.perfil.num_refeicoes == 1:
            is_anos_iniciais = "6_10" in self.perfil.faixa_etaria
            qtd_arroz = 75.0 if is_anos_iniciais else 115.0
            qtd_macarrao = 25.0 if is_anos_iniciais else 45.0
            qtd_tuberculo = 60.0 if is_anos_iniciais else 90.0
            qtd_feijao = 40.0 if is_anos_iniciais else 55.0
            qtd_oleo = 8.0 if is_anos_iniciais else 11.0
            qtd_carne = 22.0 if is_anos_iniciais else 32.0

            for semana in cardapio.semanas:
                for dia in semana.dias:
                    for refeicao in dia.refeicoes:
                        tipo_norm = _texto_normalizado(refeicao.tipo.value if hasattr(refeicao.tipo, "value") else refeicao.tipo)
                        eh_principal = any(p in tipo_norm for p in ("almoc", "jantar", "refeicao_principal"))

                        # Descarta amidos exclusivos de lanches (ex: aveia avulsa) inseridos erroneamente no almoço com macarrão/arroz
                        if eh_principal:
                            tem_amido_almoco = any(
                                any(c in _texto_normalizado(ing.nome_taco or prato.nome) for c in ("arroz", "macarrao", "mandioca", "batata", "polenta", "fuba"))
                                for prato in refeicao.pratos for ing in (prato.ingredientes or [])
                            )
                            if tem_amido_almoco:
                                for prato in refeicao.pratos:
                                    prato.ingredientes = [
                                        ing for ing in (prato.ingredientes or [])
                                        if not any(a in _texto_normalizado(ing.nome_taco or "") for a in ("aveia", "mingau"))
                                    ]
                                refeicao.pratos = [p for p in refeicao.pratos if p.ingredientes]

                        itens_amido = [
                            ing for prato in refeicao.pratos for ing in prato.ingredientes
                            if any(c in _texto_normalizado(ing.nome_taco or prato.nome) for c in ("arroz", "macarrao", "mandioca", "batata", "polenta", "fuba", "cuscuz"))
                        ]
                        fator_amido = 0.55 if len(itens_amido) > 1 else 1.0

                        for prato in refeicao.pratos:
                            for ing in prato.ingredientes:
                                nome_norm = _texto_normalizado(ing.nome_taco or prato.nome)
                                if "arroz" in nome_norm:
                                    ing.quantidade_g = round(qtd_arroz * fator_amido, 1)
                                elif "macarrao" in nome_norm:
                                    ing.quantidade_g = round(qtd_macarrao * fator_amido, 1)
                                elif "batata" in nome_norm:
                                    ing.quantidade_g = round((100.0 if is_anos_iniciais else 150.0) * fator_amido, 1)
                                elif any(t in nome_norm for t in ("polenta", "mandioca")):
                                    ing.quantidade_g = round(qtd_tuberculo * fator_amido, 1)
                                elif any(t in nome_norm for t in ("feijao", "feijão", "lentilha")):
                                    ing.quantidade_g = qtd_feijao
                                elif any(t in nome_norm for t in ("grao de bico", "grao-de-bico")):
                                    ing.quantidade_g = 15.0 if is_anos_iniciais else 22.0
                                elif any(t in nome_norm for t in ("azeite", "oleo", "gordura vegetal")):
                                    ing.quantidade_g = qtd_oleo
                                elif any(t in nome_norm for t in ("frango", "galinha", "carne", "peixe", "bovina", "suina", "ovo", "figado", "patinho", "acem", "musculo", "sobrecoxa")):
                                    ing.quantidade_g = qtd_carne
                                elif "queijo" in nome_norm:
                                    ing.quantidade_g = 18.0 if is_anos_iniciais else 25.0
        return cardapio


class EnsinoMedioPipeline(BasePipeline):
    """
    Pipeline especializado para Ensino Médio (16 a 18 anos).
    Exige porções reforçadas para atender aos valores de referência elevados:
    - 543 kcal (20% VET - 1 refeição)
    - 815 kcal (30% VET - 2 refeições)
    - 1902 kcal (70% VET - integral)
    """

    def construir_system_prompt(
        self,
        turno: str = "matutino",
        restricoes: Optional[List[str]] = None,
        total_dias: Optional[int] = None,
        num_semanas: int = 1,
        dias_letivos: Optional[List[str]] = None,
    ) -> str:
        prompt_base = super().construir_system_prompt(
            turno=turno,
            restricoes=restricoes,
            total_dias=total_dias,
            num_semanas=num_semanas,
            dias_letivos=dias_letivos,
        )
        diretrizes_medio = """
    DIRETRIZES EXCLUSIVAS PARA ENSINO MÉDIO (16 A 18 ANOS):
    - COMPOSIÇÃO ESTRUTURAL OBRIGATÓRIA DE TODAS AS REFEIÇÕES (100% dos dias letivos):
      TODA refeição principal DEVE conter OBRIGATORIAMENTE todos os componentes básicos:
      1. Base de cereal/amido: arroz (branco ou integral), macarrão ou tubérculo (mandioca/batata/polenta). NUNCA sirva dois amidos concorrentes na mesma refeição (ex: NUNCA coloque macarrão com batata ou arroz com macarrão). Escolha APENAS UM amido principal.
      2. Leguminosa: feijão (carioca ou preto), lentilha ou grão-de-bico.
      3. Proteína animal principal: carne bovina (acém, patinho, músculo, fígado bovino), frango (peito, sobrecoxa) ou peixe (filé de pescada/tilápia). NUNCA deixe nenhum dia sem carne/proteína animal (100% dos dias letivos). Dias sem carne violam o PNAE do Ensino Médio. Não use queijo como substituto de carne no almoço.
      4. Hortaliça/legume: salada crua (alface, tomate, cenoura ralada) ou legume cozido (abobrinha, brócolis, couve).
      5. Fruta fresca de sobremesa: maçã, banana, laranja, melancia, melão ou mamão (estritamente 1 fruta por dia).
      6. Ingredientes de preparo: azeite/óleo de soja e sal refinado em quantidade moderada.
    - Meta calórica exigente: atingir a meta calórica através de porções consistentes de alimentos in natura, nunca inflando gorduras.
    - Proteína calibrada estritamente entre 14g e 20g por refeição principal de 20% VET.
    - Gorduras totais mantidas entre 15g e 21g por refeição principal de 20% VET.
    - Sódio: NUNCA ultrapassar 600 mg. Se utilizar queijo branco, utilize porção controlada (máximo 25g) e NUNCA adicione sal de cozinha no mesmo dia.
    """
        return f"{prompt_base}\n\n{diretrizes_medio.strip()}"

    def aplicar_per_capita(self, cardapio: CardapioSchema) -> CardapioSchema:
        """
        Aplica per capita com calibração das porções de amidos, leguminosas e gorduras para o Ensino Médio,
        garantindo alcance seguro das metas do PNAE (543 kcal, 75-88g carbo, 14-20g prot, 15-21g lip).
        """
        cardapio = super().aplicar_per_capita(cardapio)
        if self.perfil.num_refeicoes == 1:
            for semana in cardapio.semanas:
                for dia in semana.dias:
                    for refeicao in dia.refeicoes:
                        # Identifica se há amidos múltiplos na refeição para evitar sobreposição excessiva
                        itens_amido_refeicao = []
                        for prato in refeicao.pratos:
                            for ing in prato.ingredientes:
                                n_norm = _texto_normalizado(ing.nome_taco or prato.nome)
                                if any(a in n_norm for a in ("arroz", "macarrao", "polenta", "mandioca", "batata")):
                                    itens_amido_refeicao.append(ing)

                        fator_amido = 0.55 if len(itens_amido_refeicao) > 1 else 1.0

                        for prato in refeicao.pratos:
                            for ing in prato.ingredientes:
                                nome_norm = _texto_normalizado(ing.nome_taco or prato.nome)
                                # Base de cereal/amido calibrada para atender carbo e caloria
                                if "arroz" in nome_norm:
                                    ing.quantidade_g = round(130.0 * fator_amido, 1)
                                elif "macarrao" in nome_norm:
                                    ing.quantidade_g = round(60.0 * fator_amido, 1)
                                elif "batata" in nome_norm:
                                    ing.quantidade_g = round(200.0 * fator_amido, 1)
                                elif any(t in nome_norm for t in ("polenta", "mandioca")):
                                    ing.quantidade_g = round(120.0 * fator_amido, 1)
                                # Feijão e leguminosas
                                elif any(t in nome_norm for t in ("feijao", "feijão", "lentilha")):
                                    ing.quantidade_g = 65.0
                                elif any(t in nome_norm for t in ("grao de bico", "grao-de-bico", "grao")):
                                    ing.quantidade_g = 25.0
                                # Óleo/azeite de cocção calibrado para atingir os 15g a 21g de lipídios
                                elif any(t in nome_norm for t in ("azeite", "oleo", "gordura vegetal")):
                                    ing.quantidade_g = 12.0
                                # Carnes calibradas para manter proteína no centro da faixa PNAE (14g a 20g)
                                elif any(t in nome_norm for t in ("frango", "galinha", "carne", "peixe", "bovina", "suina", "ovo", "figado", "patinho", "acem", "musculo", "sobrecoxa")):
                                    ing.quantidade_g = 28.0
                                # Queijo branco / laticínio salgado calibrado para não estourar sódio e calorias
                                elif "queijo" in nome_norm:
                                    ing.quantidade_g = 25.0
        return cardapio


class EJAPipeline(BasePipeline):
    """
    Pipeline especializado para Educação de Jovens e Adultos (19 a 30 anos e 31 a 60 anos).
    Voltado ao público jovem e adulto trabalhador, com refeições práticas e nutritivas.
    """

    def construir_system_prompt(
        self,
        turno: str = "matutino",
        restricoes: Optional[List[str]] = None,
        total_dias: Optional[int] = None,
        num_semanas: int = 1,
        dias_letivos: Optional[List[str]] = None,
    ) -> str:
        prompt_base = super().construir_system_prompt(
            turno=turno,
            restricoes=restricoes,
            total_dias=total_dias,
            num_semanas=num_semanas,
            dias_letivos=dias_letivos,
        )
        diretrizes_eja = f"""
    DIRETRIZES EXCLUSIVAS PARA EJA ({self.perfil.faixa_etaria.replace('_', ' ').upper()}):
    - Cardápio atrativo e substancial para jovens e adultos estudantes/trabalhadores.
    - Valorização da culinária regional e tradicional brasileira com foco em comida de verdade.
    - Controle rígido de sódio e gorduras saturadas conforme parâmetros de saúde do adulto.
    """
        return f"{prompt_base}\n\n{diretrizes_eja.strip()}"

    def aplicar_per_capita(self, cardapio: CardapioSchema) -> CardapioSchema:
        """Calibra porções de amidos, carnes e óleos para EJA (477 kcal / proteína 12 a 18g)."""
        cardapio = super().aplicar_per_capita(cardapio)
        if self.perfil.num_refeicoes == 1:
            for semana in cardapio.semanas:
                for dia in semana.dias:
                    for refeicao in dia.refeicoes:
                        for prato in refeicao.pratos:
                            for ing in prato.ingredientes:
                                nome_norm = _texto_normalizado(ing.nome_taco or prato.nome)
                                if "arroz" in nome_norm:
                                    ing.quantidade_g = 130.0
                                elif any(t in nome_norm for t in ("feijao", "feijão", "lentilha")):
                                    ing.quantidade_g = 65.0
                                elif any(t in nome_norm for t in ("azeite", "oleo", "gordura vegetal")):
                                    ing.quantidade_g = 11.0
                                elif any(t in nome_norm for t in ("frango", "galinha", "carne", "peixe", "bovina", "suina")):
                                    ing.quantidade_g = 30.0
        return cardapio
