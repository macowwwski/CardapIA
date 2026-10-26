"""
Classe base para pipelines especializados de geração e validação de cardápios escolares (PNAE).

Define o ciclo de vida e a interface comum para todos os perfis escolares:
1. Construção de prompts focados exclusivamente no perfil selecionado.
2. Aplicação de quantidades per capita e fatores de cocção oficiais.
3. Auditoria nutricional independente baseada nos parâmetros normativos do perfil.
4. Geração de instruções direcionadas para correção de inconformidades.
"""
from abc import ABC
from typing import List, Optional
from sqlalchemy.orm import Session
from db.database import engine
from src.pipelines.models import PerfilNutricional
from src.schemas_pydantic import CardapioSchema, InconformidadePNAESchema, IngredienteSchema, PratoSchema
from src.taco.resolver import resolver_taco, resolver_per_capita
from src.nutrition.classifier import _texto_normalizado, _classificar_alimento, _contem_token, _contem_termo_adicao_acucar, _eh_proteina_animal
from src.nutrition.calculator import _somar_nutriente, _dentro_intervalo, buscar_taco_por_nome, obter_vitamina_a_mcg_100g
from src.nutrition.culinary_validator import validar_coerencia_culinaria


class BasePipeline(ABC):
    """
    Pipeline base para processamento de cardápios escolares no âmbito do PNAE.
    Cada subclasse encapsula o conhecimento, as restrições e as diretrizes do seu perfil de atendimento.
    """

    def __init__(self, perfil: PerfilNutricional):
        self.perfil = perfil

    def construir_system_prompt(
        self,
        turno: str = "matutino",
        restricoes: Optional[List[str]] = None,
        total_dias: Optional[int] = None,
        num_semanas: int = 1,
        dias_letivos: Optional[List[str]] = None,
    ) -> str:
        """
        Gera o prompt do sistema customizado rigorosamente para este perfil.
        Elimina regras irrelevantes de outras etapas e foca nos parâmetros aplicáveis.
        """
        p = self.perfil
        n = p.nutricao
        lim = p.limites
        sem = p.metas_semanais
        restricoes = restricoes or []

        info_dias = f"- Total de dias letivos a planejar: {total_dias}\n" if total_dias else f"- Semanas a planejar: {num_semanas} semana(s) de 5 dias\n"
        if dias_letivos:
            info_dias += f"- Datas dos dias letivos: {', '.join(dias_letivos)}\n"

        aviso_restricoes = ""
        if restricoes:
            aviso_restricoes = f"""
    RESTRIÇÕES ALIMENTARES DA TURMA (PROIBIÇÃO ABSOLUTA):
    - É TERMINANTEMENTE PROIBIDO incluir qualquer ingrediente ou derivado de: {', '.join(restricoes)}.
    - Todas as preparações devem ser 100% seguras para os estudantes.
    """

        proibicoes_txt = ", ".join(p.alimentos_proibidos) if p.alimentos_proibidos else "Nenhum alimento adicional proibido."

        # Micronutrientes (se aplicável ao perfil, como creche)
        micro_txt = ""
        if n.vitamina_a_mcg is not None:
            micro_txt = f"""
    - Vitamina A: {n.vitamina_a_mcg} mcg
    - Vitamina C: {n.vitamina_c_mg} mg
    - Cálcio:     {n.calcio_mg} mg
    - Ferro:      {n.ferro_mg} mg
    """

        orientacoes_adicionais = "\n    ".join(f"- {o}" for o in p.orientacoes_especificas) if p.orientacoes_especificas else ""

        return f"""
    Você é um nutricionista escolar especialista no PNAE para o perfil '{p.id_perfil.upper()}'.
    Sua responsabilidade é elaborar um cardápio perfeitamente equilibrado, gastronômica e culinariamente coerente,
    atendendo aos requisitos normativos da Resolução CD/FNDE nº 06/2020.

    DADOS DO PERFIL DE ATENDIMENTO:
    - Etapa: {p.etapa.upper()} | Faixa Etária: {p.faixa_etaria}
    - Período: {p.periodo.upper()} ({p.num_refeicoes} refeição/refeições ao dia) | Turno: {turno}
    - Atendimento Nutricional: {p.percentual_label}
    {info_dias}
    {aviso_restricoes}
    ALIMENTOS PROIBIDOS NESTE PERFIL:
    - {proibicoes_txt}

    METAS NUTRICIONAIS OBRIGATÓRIAS (TOTAL DO DIA - {p.percentual_label}):
    - Energia:      {n.energia_kcal:.1f} kcal
    - Carboidratos: {n.carboidratos_g.minimo:.1f}g a {n.carboidratos_g.maximo:.1f}g
    - Proteínas:    {n.proteinas_g.minimo:.1f}g a {n.proteinas_g.maximo:.1f}g
    - Lipídios:     {n.lipidios_g.minimo:.1f}g a {n.lipidios_g.maximo:.1f}g
    - Sódio Máximo: {lim.max_sodio_mg:.0f} mg (equivalente a no máximo {lim.max_sodio_mg/400.0:.1f}g de sal total no dia)
    {micro_txt}
    {orientacoes_adicionais}

    DIRETRIZES DE COMPOSIÇÃO CULINÁRIA E EQUILÍBRIO:
    1. ESTRUTURA DA REFEIÇÃO PRINCIPAL:
       - 1 Base de Energia (Cereal ou Tubérculo): arroz, macarrão, mandioca/aipim, batata, polenta.
       - 1 Leguminosa: feijão (carioca, preto, fradinho) ou lentilha.
       - 1 Prato Proteico Principal: preparação com carne bovina, ave, peixe ou ovos. NUNCA sirva duas carnes distintas na mesma refeição.
       - 1 Hortaliça/Legume: salada crua ou legume refogado/cozido.
       - Sobremesa: NO MÁXIMO UMA fruta in natura (ex: banana, maçã, laranja, melancia). NUNCA coloque múltiplas frutas juntas.
    
    2. CUIDADOS CRÍTICOS COM INGREDIENTES:
       - NÃO liste "Água" como ingrediente avulso de receitas simples (o feijão e o arroz já são computados prontos/cozidos).
       - NÃO duplique nem triplique gorduras de preparo (azeite/óleo). Limite a no máximo 1 única porção (8g a 10g) no TOTAL da refeição inteira.
       - Controle rigorosamente o sal: NUNCA coloque sal em cada acompanhamento separadamente.
       - Atingir a meta calórica através de alimentos nutritivos (arroz, feijão, tubérculos e carnes magras) e NÃO por excesso de gordura.

    3. DIVERSIDADE E AGRICULTURA FAMILIAR:
       - Mínimo 45% de insumos da agricultura familiar.
       - Alterne as proteínas e hortaliças ao longo dos dias. Não repita a mesma preparação proteica consecutivamente.

    INSTRUÇÕES DE FORMATAÇÃO:
    - Retorne apenas o planejamento estruturado em texto corrido organizado por semanas, dias e refeições com pratos e ingredientes.
    - NÃO gere formato JSON nesta etapa.
    """.strip()

    def aplicar_per_capita(self, cardapio: CardapioSchema) -> CardapioSchema:
        """
        Aplica os valores per capita oficiais do perfil escolar e associa referências da TACO.
        Descarta água de cozimento duplicada, unifica óleos de preparo e calibra o sal para conformidade com o teto de sódio.
        """
        etapa_per_capita = self.perfil.etapa

        for semana in cardapio.semanas:
            ultima_proteina_tipo = None
            for dia in semana.dias:
                for refeicao in dia.refeicoes:
                    tem_oleo_coccao = False
                    tem_sal_adicionado = False
                    tem_proteina_animal = False
                    tipo_proteina_dia = None

                    # Identifica se a refeição já contém alimentos com alto teor de sódio intrínseco (ex: queijo)
                    tem_ingrediente_salgado = False
                    for prato in refeicao.pratos:
                        for ing in (prato.ingredientes or []):
                            i_norm = _texto_normalizado(ing.nome_taco or "")
                            if any(s in i_norm for s in ("queijo", "requeijao", "ricota salgada", "bacalhau", "embutido", "presunto", "mortadela", "conserva", "enlatad", "salmoura")):
                                tem_ingrediente_salgado = True
                                break
                        if tem_ingrediente_salgado:
                            break

                    for prato in refeicao.pratos:
                        if not prato.ingredientes and prato.nome:
                            if _eh_proteina_animal(prato.nome):
                                tem_proteina_animal = True
                            prato.ingredientes = [IngredienteSchema(nome_taco=prato.nome, quantidade_g=0.0)]
                        validos = []
                        for ingrediente in prato.ingredientes:
                            nome_norm = _texto_normalizado(ingrediente.nome_taco or prato.nome)

                            # 1. Descartar água de cozimento avulsa (evita casamento incorreto com água de coco na TACO)
                            if nome_norm in ("agua", "agua potavel", "agua de cozimento", "agua mineral"):
                                continue

                            # 2. Resolução TACO e leitura da categoria oficial da base
                            match = resolver_taco(ingrediente.nome_taco)
                            taco_id = match.taco_id if match else None
                            ingrediente._taco_id = taco_id
                            categoria_taco = match.payload.get("category") if (match and match.payload) else None

                            # Classificação oficial a partir da categoria TACO (com contingência para mocks sem payload)
                            eh_oleo_gordura = (categoria_taco == "Gorduras e óleos")
                            if not eh_oleo_gordura and not categoria_taco:
                                eh_oleo_gordura = any(t in nome_norm for t in ("azeite", "oleo", "gordura vegetal")) and not any(c in nome_norm for c in ("macarra", "arroz", "batat", "mandioc", "carne", "frang", "peix", "ovo", "salada", "legum"))

                            eh_proteina = (categoria_taco in ("Carnes e derivados", "Pescados e frutos do mar", "Ovos e derivados"))
                            if not eh_proteina:
                                eh_proteina = _eh_proteina_animal(nome_norm)

                            if eh_proteina:
                                tem_proteina_animal = True
                                if categoria_taco == "Pescados e frutos do mar" or any(p in nome_norm for p in ("peixe", "tilapia", "pescada", "sardinha", "atum")):
                                    tipo_proteina_dia = "peixe"
                                elif categoria_taco == "Ovos e derivados" or any(o in nome_norm for o in ("ovo", "ovos", "omelete")):
                                    tipo_proteina_dia = "ovo"
                                elif any(f in nome_norm for f in ("frango", "galinha", "ave", "sobrecoxa", "peito")):
                                    tipo_proteina_dia = "frango"
                                else:
                                    tipo_proteina_dia = "bovina"

                            # 3. Controlar gorduras e óleos de preparo: máximo 1 ocorrência por refeição
                            if eh_oleo_gordura:
                                if tem_oleo_coccao:
                                    continue
                                tem_oleo_coccao = True

                            # 4. Controlar sal de cozinha: máximo 1 ocorrência calibrada por refeição (ou zero se houver queijo)
                            eh_sal = "sal" in nome_norm and "salada" not in nome_norm and "salmao" not in nome_norm
                            if eh_sal:
                                if tem_sal_adicionado or tem_ingrediente_salgado:
                                    continue
                                tem_sal_adicionado = True

                            # 5. Resolução de Per Capita oficial (com fallback por categoria e tolerância a mocks legados)
                            if eh_sal:
                                max_sal_g = min(0.8, (self.perfil.limites.max_sodio_mg * 0.50) / 400.0)
                                ingrediente.quantidade_g = round(max_sal_g, 2)
                            else:
                                try:
                                    valor = resolver_per_capita(
                                        ingrediente.nome_taco,
                                        etapa_per_capita,
                                        taco_id=taco_id,
                                        categoria=categoria_taco,
                                    )
                                except TypeError:
                                    valor = resolver_per_capita(
                                        ingrediente.nome_taco,
                                        etapa_per_capita,
                                        taco_id=taco_id,
                                    )
                                if valor is not None:
                                    ingrediente.quantidade_g = valor
                                elif not ingrediente.quantidade_g or ingrediente.quantidade_g <= 0:
                                    continue

                            validos.append(ingrediente)

                        prato.ingredientes = validos

                    tipo_refeicao_norm = _texto_normalizado(refeicao.tipo.value if hasattr(refeicao.tipo, "value") else refeicao.tipo)
                    eh_principal = any(p in tipo_refeicao_norm for p in ("almoc", "jantar", "refeicao_principal"))
                    if eh_principal and refeicao.pratos:
                        if not tem_proteina_animal:
                            if ultima_proteina_tipo == "frango":
                                nome_prot_padrao = "patinho"
                                tipo_proteina_dia = "bovina"
                            elif ultima_proteina_tipo == "bovina":
                                nome_prot_padrao = "peixe"
                                tipo_proteina_dia = "peixe"
                            else:
                                nome_prot_padrao = "peito de frango"
                                tipo_proteina_dia = "frango"

                            match_prot = resolver_taco(nome_prot_padrao)
                            taco_prot_id = match_prot.taco_id if match_prot else None
                            qtd_prot = resolver_per_capita(nome_prot_padrao, etapa_per_capita, taco_id=taco_prot_id) or 45.0
                            ing_prot = IngredienteSchema(nome_taco=nome_prot_padrao, quantidade_g=qtd_prot)
                            ing_prot._taco_id = taco_prot_id
                            novo_prato = PratoSchema(
                                nome=nome_prot_padrao,
                                estado_preparacao="cozido",
                                ingredientes=[ing_prot],
                            )
                            pos = min(1, len(refeicao.pratos))
                            refeicao.pratos.insert(pos, novo_prato)

                        if tipo_proteina_dia:
                            ultima_proteina_tipo = tipo_proteina_dia

                        if not tem_oleo_coccao:
                            match_oleo = resolver_taco("Óleo de soja")
                            taco_oleo_id = match_oleo.taco_id if match_oleo else None
                            qtd_oleo = resolver_per_capita("Óleo de soja", etapa_per_capita, taco_id=taco_oleo_id) or 8.0
                            ing_oleo = IngredienteSchema(nome_taco="Óleo de soja", quantidade_g=qtd_oleo)
                            ing_oleo._taco_id = taco_oleo_id
                            refeicao.pratos[0].ingredientes.append(ing_oleo)

                        if not tem_sal_adicionado and not tem_ingrediente_salgado:
                            match_sal = resolver_taco("sal")
                            taco_sal_id = match_sal.taco_id if match_sal else None
                            max_sal_g = min(0.8, (self.perfil.limites.max_sodio_mg * 0.50) / 400.0)
                            ing_sal = IngredienteSchema(nome_taco="sal", quantidade_g=round(max_sal_g, 2))
                            ing_sal._taco_id = taco_sal_id
                            refeicao.pratos[0].ingredientes.append(ing_sal)

        return cardapio

    def ajustar_macronutrientes(self, cardapio: CardapioSchema) -> CardapioSchema:
        """
        Aplica microajustes proporcionais determinísticos nas gramaturas dos alimentos base
        (carboidratos, proteínas e lipídios de preparo) para assegurar o atingimento do VET
        e faixas de macronutrientes do PNAE com respeito aos limites pedagógicos por faixa etária.
        """
        from src.nutrition.macro_adjuster import ajustar_macronutrientes_cardapio
        return ajustar_macronutrientes_cardapio(cardapio, self.perfil)

    def auditar(
        self,
        cardapio: CardapioSchema,
        restricoes: Optional[List[str]] = None,
    ) -> List[InconformidadePNAESchema]:
        """
        Executa auditoria nutricional e culinária independente contra os requisitos deste perfil.
        """
        p = self.perfil
        n = p.nutricao
        lim = p.limites
        sem = p.metas_semanais
        restricoes = restricoes or []
        inconsistencias: List[InconformidadePNAESchema] = []

        with Session(engine) as session:
            nomes_ingredientes = {
                ingrediente.nome_taco
                for semana in cardapio.semanas
                for dia in semana.dias
                for refeicao in dia.refeicoes
                for prato in refeicao.pratos
                for ingrediente in prato.ingredientes
            }
            ingredientes_taco = {
                nome: buscar_taco_por_nome(session, nome)
                for nome in nomes_ingredientes
            }

        # 1. Auditoria Culinária e Restrições Alimentares
        inconsistencias.extend(validar_coerencia_culinaria(cardapio, p.etapa, restricoes, ingredientes_taco))

        # 2. Alimentos Proibidos do Perfil
        termos_por_proibicao = {
            "alimentos ricos em gorduras trans industrializadas": {"margarina", "hidrogenad", "interesterificad"},
            "alimentos ultraprocessados": {
                "biscoit", "bolach", "salsicha", "presunt", "mortadela",
                "salame", "refrigerante", "achocolatad", "sorvet",
            },
            "alimentos com adicao de acucar": {"acucar", "chocolate", "achocolatad", "doce"},
            "alimentos com adicao de mel": {"mel"},
            "alimentos com adicao de adocante": {"adocante", "adocad"},
        }

        vistos_proibidos = set()
        for semana in cardapio.semanas:
            for dia in semana.dias:
                for refeicao in dia.refeicoes:
                    for prato in refeicao.pratos:
                        for ingrediente in prato.ingredientes:
                            taco = ingredientes_taco.get(ingrediente.nome_taco)
                            texto = " ".join([
                                ingrediente.nome_taco,
                                prato.nome,
                                taco.category if taco else "",
                            ])
                            for proibicao in p.alimentos_proibidos:
                                chave = _texto_normalizado(proibicao)
                                termos = termos_por_proibicao.get(chave, set())
                                if not termos:
                                    continue

                                eh_ultra = (
                                    chave == "alimentos ultraprocessados"
                                    and taco
                                    and "industrializado" in _texto_normalizado(taco.category)
                                )
                                if chave == "alimentos com adicao de acucar":
                                    violou = _contem_termo_adicao_acucar(texto, taco.category if taco else "")
                                elif chave == "alimentos ricos em gorduras trans industrializadas":
                                    texto_norm = _texto_normalizado(texto)
                                    violou = _contem_token(texto, termos) or "gordura vegetal" in texto_norm or "gordura hidrogenada" in texto_norm
                                else:
                                    violou = _contem_token(texto, termos)

                                if violou or eh_ultra:
                                    id_visto = (semana.numero, dia.dia_semana, ingrediente.nome_taco, proibicao)
                                    if id_visto in vistos_proibidos:
                                        continue
                                    vistos_proibidos.add(id_visto)
                                    inconsistencias.append(InconformidadePNAESchema(
                                        escopo=f"semana {semana.numero} / {dia.dia_semana}",
                                        regra=f"Alimento proibido: {proibicao}",
                                        detalhe=f"Ingrediente '{ingrediente.nome_taco}' em '{prato.nome}'.",
                                        tipo="critico",
                                    ))

        # 3. Auditoria Nutricional Diária por Semana
        contagens_mes = {
            "produto_carneo": 0,
            "conserva": 0,
            "doce": 0,
            "liquido_lacteo_aditivado": 0,
        }

        for semana in cardapio.semanas:
            diversidade = set()
            flv_g = 0.0
            dias_com_fruta = set()
            dias_com_legume_verdura = set()
            contagens_semana = {
                "biscoito_pao_bolo": 0,
                "preparacao_doce": 0,
                "margarina_creme_vegetal": 0,
            }

            for dia in semana.dias:
                # -------------------------------------------------------------
                # Auditoria por Refeição: Quantidade e presença das refeições esperadas
                # -------------------------------------------------------------
                tipos_dia = [
                    _texto_normalizado(r.tipo.value if hasattr(r.tipo, "value") else r.tipo)
                    for r in dia.refeicoes
                ]

                if len(dia.refeicoes) != p.num_refeicoes:
                    inconsistencias.append(InconformidadePNAESchema(
                        escopo=f"semana {semana.numero} / {dia.dia_semana}",
                        regra="Quantidade de refeicoes divergente",
                        detalhe=(
                            f"Dia possui {len(dia.refeicoes)} refeicao(oes) planejada(s), "
                            f"mas o perfil '{p.id_perfil}' exige exatamente {p.num_refeicoes}."
                        ),
                        tipo="critico",
                    ))

                for dist in p.distribuicao_refeicoes:
                    tipo_alvo = _texto_normalizado(dist.tipo_refeicao)
                    alvo_encontrado = any(
                        tipo_alvo in t or t in tipo_alvo
                        or (tipo_alvo in ("desjejum", "lanche_manha", "cafe_manha") and any(x in t for x in ("desjejum", "cafe", "manha")))
                        or (tipo_alvo in ("almoco", "refeicao_principal") and "almoc" in t)
                        or (tipo_alvo in ("lanche da tarde", "lanche_tarde") and ("tarde" in t or "lanche" in t))
                        for t in tipos_dia
                    )
                    if not alvo_encontrado:
                        inconsistencias.append(InconformidadePNAESchema(
                            escopo=f"semana {semana.numero} / {dia.dia_semana}",
                            regra="Refeicao esperada ausente",
                            detalhe=(
                                f"A refeicao esperada '{dist.tipo_refeicao}' (ordem {dist.ordem}) "
                                f"nao foi encontrada no planejamento do dia."
                            ),
                            tipo="critico",
                        ))

                totais = {
                    "energia_kcal": 0.0,
                    "carboidratos_g": 0.0,
                    "proteinas_g": 0.0,
                    "lipidios_g": 0.0,
                    "sodio_mg": 0.0,
                    "vitamina_a_mcg": 0.0,
                    "vitamina_c_mg": 0.0,
                    "calcio_mg": 0.0,
                    "ferro_mg": 0.0,
                }
                classes_do_dia = set()

                for refeicao in dia.refeicoes:
                    for prato in refeicao.pratos:
                        for ingrediente in prato.ingredientes:
                            taco = ingredientes_taco.get(ingrediente.nome_taco)
                            categoria = taco.category if taco else ""
                            classes = (
                                _classificar_alimento(prato.nome, categoria)
                                | _classificar_alimento(ingrediente.nome_taco, categoria)
                            )
                            classes_do_dia.update(classes)
                            diversidade.add(_texto_normalizado(ingrediente.nome_taco))

                            if "fruta" in classes or "legume_verdura" in classes:
                                flv_g += ingrediente.quantidade_g
                            if "fruta" in classes:
                                dias_com_fruta.add(dia.dia_semana)
                            if "legume_verdura" in classes:
                                dias_com_legume_verdura.add(dia.dia_semana)

                            if not taco:
                                inconsistencias.append(InconformidadePNAESchema(
                                    escopo=f"semana {semana.numero} / {dia.dia_semana}",
                                    regra="Composicao TACO obrigatoria para validacao PNAE",
                                    detalhe=f"Ingrediente '{ingrediente.nome_taco}' nao encontrado na base TACO.",
                                    tipo="advertencia",
                                ))
                                continue

                            totais["energia_kcal"] += _somar_nutriente(taco.energy_kcal, ingrediente.quantidade_g)
                            totais["carboidratos_g"] += _somar_nutriente(taco.carbohydrates, ingrediente.quantidade_g)
                            totais["proteinas_g"] += _somar_nutriente(taco.proteins, ingrediente.quantidade_g)
                            totais["lipidios_g"] += _somar_nutriente(taco.lipids, ingrediente.quantidade_g)
                            totais["sodio_mg"] += _somar_nutriente(taco.sodium, ingrediente.quantidade_g)
                            totais["vitamina_a_mcg"] += _somar_nutriente(obter_vitamina_a_mcg_100g(taco, ingrediente.nome_taco), ingrediente.quantidade_g)
                            totais["vitamina_c_mg"] += _somar_nutriente(taco.c_vitamin, ingrediente.quantidade_g)
                            totais["calcio_mg"] += _somar_nutriente(taco.calcium, ingrediente.quantidade_g)
                            totais["ferro_mg"] += _somar_nutriente(taco.iron, ingrediente.quantidade_g)

                # Avaliação de Energia e Macronutrientes contra o Perfil
                referencias = {
                    "energia_kcal": (n.energia_kcal, n.energia_kcal),
                    "carboidratos_g": (n.carboidratos_g.minimo, n.carboidratos_g.maximo),
                    "proteinas_g": (n.proteinas_g.minimo, n.proteinas_g.maximo),
                    "lipidios_g": (n.lipidios_g.minimo, n.lipidios_g.maximo),
                }
                if n.vitamina_a_mcg is not None:
                    referencias["vitamina_a_mcg"] = (n.vitamina_a_mcg, None)
                    referencias["vitamina_c_mg"] = (n.vitamina_c_mg, None)
                    referencias["calcio_mg"] = (n.calcio_mg, None)
                    referencias["ferro_mg"] = (n.ferro_mg, None)

                for nutriente, (minimo, maximo) in referencias.items():
                    if not _dentro_intervalo(totais[nutriente], minimo, maximo, tolerancia=0.1):
                        eh_critico = False
                        if minimo is not None and totais[nutriente] < minimo * 0.7:
                            eh_critico = True
                        elif maximo is not None and totais[nutriente] > maximo * 1.3:
                            eh_critico = True

                        inconsistencias.append(InconformidadePNAESchema(
                            escopo=f"semana {semana.numero} / {dia.dia_semana}",
                            regra=f"Valor diario de {nutriente}",
                            detalhe=(
                                f"Total calculado {totais[nutriente]:.1f}; "
                                f"referencia PNAE {minimo}"
                                + (f" a {maximo}" if maximo != minimo else "")
                                + "."
                            ),
                            tipo="critico" if eh_critico else "advertencia",
                        ))

                # Limite de Sódio do Perfil
                if totais["sodio_mg"] > lim.max_sodio_mg * 1.1:
                    inconsistencias.append(InconformidadePNAESchema(
                        escopo=f"semana {semana.numero} / {dia.dia_semana}",
                        regra="Limite diario de sodio",
                        detalhe=f"Total calculado {totais['sodio_mg']:.1f} mg; limite PNAE {lim.max_sodio_mg:.0f} mg.",
                        tipo="advertencia",
                    ))

                for c in classes_do_dia & set(contagens_mes):
                    contagens_mes[c] += 1
                for c in classes_do_dia & set(contagens_semana):
                    contagens_semana[c] += 1

            # Metas Semanais (apenas se a semana tiver dias suficientes)
            total_dias_semana = len(semana.dias)
            if total_dias_semana >= 4 and len(diversidade) < sem.min_diversidade:
                inconsistencias.append(InconformidadePNAESchema(
                    escopo=f"semana {semana.numero}",
                    regra="Diversidade semanal de alimentos",
                    detalhe=f"Encontrados {len(diversidade)} alimentos diferentes; minimo PNAE {sem.min_diversidade}.",
                    tipo="advertencia",
                ))
            if total_dias_semana >= 4 and flv_g < sem.min_flv_g:
                inconsistencias.append(InconformidadePNAESchema(
                    escopo=f"semana {semana.numero}",
                    regra="Quantidade semanal de frutas, legumes e verduras",
                    detalhe=f"Total calculado {flv_g:.1f}g; minimo PNAE {sem.min_flv_g:.1f}g.",
                    tipo="advertencia",
                ))
            if total_dias_semana >= sem.min_frutas_dias and len(dias_com_fruta) < sem.min_frutas_dias:
                inconsistencias.append(InconformidadePNAESchema(
                    escopo=f"semana {semana.numero}",
                    regra="Oferta semanal de frutas",
                    detalhe=f"Encontrada em {len(dias_com_fruta)} dia(s); minimo PNAE {sem.min_frutas_dias}.",
                    tipo="advertencia",
                ))
            if total_dias_semana >= sem.min_legumes_verduras_dias and len(dias_com_legume_verdura) < sem.min_legumes_verduras_dias:
                inconsistencias.append(InconformidadePNAESchema(
                    escopo=f"semana {semana.numero}",
                    regra="Oferta semanal de legumes e verduras",
                    detalhe=f"Encontrada em {len(dias_com_legume_verdura)} dia(s); minimo PNAE {sem.min_legumes_verduras_dias}.",
                    tipo="advertencia",
                ))

            # Limite semanal de biscoito/pão/bolo
            if contagens_semana["biscoito_pao_bolo"] > sem.max_biscoito_semana:
                inconsistencias.append(InconformidadePNAESchema(
                    escopo=f"semana {semana.numero}",
                    regra="Frequencia semanal de biscoito/bolacha/pao/bolo",
                    detalhe=f"Encontrado {contagens_semana['biscoito_pao_bolo']} vez(es); maximo PNAE {sem.max_biscoito_semana}.",
                    tipo="advertencia",
                ))

        return inconsistencias

    def montar_prompt_correcao(self, texto_cardapio: str, erros_criticos: List[str]) -> str:
        """
        Gera prompt de autocorreção direcionado para os parâmetros específicos deste perfil.
        """
        p = self.perfil
        n = p.nutricao
        lista_erros = "\n".join(f"- {e}" for e in erros_criticos)

        return f"""
    Você é um nutricionista escolar revisando o cardápio do perfil '{p.id_perfil.upper()}'.
    O cardápio gerado apresentou as seguintes inconformidades que violam os requisitos deste perfil:

    PROBLEMAS CRÍTICOS IDENTIFICADOS:
    {lista_erros}

    METAS OBRIGATÓRIAS DO PERFIL:
    - Energia: {n.energia_kcal:.1f} kcal | Carboidratos: {n.carboidratos_g.minimo:.1f}g a {n.carboidratos_g.maximo:.1f}g
    - Proteínas: {n.proteinas_g.minimo:.1f}g a {n.proteinas_g.maximo:.1f}g | Lipídios: {n.lipidios_g.minimo:.1f}g a {n.lipidios_g.maximo:.1f}g

    INSTRUÇÕES DE CORREÇÃO:
    - Corrija APENAS as refeições problemáticas apontadas acima.
    - Mantenha inalteradas as refeições que já estavam corretas.
    - Garanta no máximo 1 fruta como sobremesa por refeição.
    - Se houver excesso de lipídios, restrinja o azeite/óleo de preparo a no máximo 1 porção de 8g a 10g no total da refeição.
    - Se faltar carboidratos ou calorias, fortaleça a base de cereais (arroz, macarrão, mandioca) ou leguminosas (feijão).
    - Remova qualquer ingrediente proibido para o perfil '{p.id_perfil}'.
    - Retorne o texto completo do cardápio corrigido no mesmo formato anterior (SEM JSON).

    CARDÁPIO ORIGINAL:
    {texto_cardapio}
    """.strip()
