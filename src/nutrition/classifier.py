"""
Classificação de alimentos, grupos nutricionais e identificação lexical de ingredientes.

Identifica grupos alimentares conforme as diretrizes do PNAE (frutas, legumes/verduras,
leguminosas, cereais/tubérculos, proteínas animais, bebidas, laticínios, glúten, doces, etc.).
"""
import re
import unicodedata

# Categorias da Tabela TACO elegíveis para controle de adição de açúcar conforme o PNAE
CATEGORIAS_ADOCAVEIS: set[str] = {
    "cereais e derivados",
    "frutas e derivados",
    "leite e derivados",
    "acucares e produtos de confeitaria",
}

# Termos-chave utilizados para rastrear preparações doces ou sobremesas nas refeições
TOKENS_DOCE_POR_CATEGORIA: set[str] = {
    "doce",
    "sobremesa",
    "adocad",
    "adocado",
    "adocada",
    "sorvet",
    "chocolate",
    "acucar",
    "mel",
    "geleia",
    "goiabada",
}

FRUTAS_CONHECIDAS: set[str] = {
    "banana", "maca", "macas", "laranja", "melancia", "melao", "manga",
    "abacaxi", "mamao", "uva", "pera", "tangerina", "mexerica", "bergamota",
    "goiaba", "morango", "caju", "caqui", "kiwi", "ameixa", "pessego",
    "abacate", "maracuja", "acerola", "jabuticaba", "carambola", "figo",
    "graviola", "cupuacu", "acai", "pitanga"
}

GENERICOS_FRUTA: set[str] = {
    "fruta", "frutas", "fruta in natura", "frutas in natura",
    "fruta fresca", "frutas frescas", "fruta da estacao", "frutas da estacao",
    "sobremesa de fruta", "fruta picada", "fruta raspada", "fruta amassada"
}

HORTALICAS_LEGUMES_CONHECIDOS: set[str] = {
    "alface", "tomate", "cenoura", "beterraba", "couve", "repolho", "abobrinha",
    "chuchu", "pepino", "brocolis", "couve-flor", "espinafre", "rucula",
    "acelga", "abobora", "berinjela", "vagem", "quiabo", "agriao", "rabanete",
    "pimentao", "cebola", "alho", "salsa", "cebolinha", "coentro"
}

LEGUMINOSAS_CONHECIDAS: set[str] = {
    "feijao", "lentilha", "grao-de-bico", "grao de bico", "ervilha", "soja"
}

CEREAIS_TUBERCULOS_CONHECIDOS: set[str] = {
    "arroz", "macarrao", "espaguete", "mandioca", "aipim", "macaxeira",
    "batata", "polenta", "fuba", "cuscuz", "milho", "inhame", "cara",
    "aveia", "trigo", "quinoa", "canjica", "tapioca"
}

PROTEINAS_ANIMAIS_CONHECIDAS: set[str] = {
    "frango", "galinha", "ave", "carne", "bovina", "boi", "patinho", "acem",
    "alcatra", "peixe", "tilapia", "sardinha", "atum", "merluza", "pescada",
    "ovo", "ovos", "omelete", "suina", "porco", "pernil", "lombo",
    "musculo", "coxa", "sobrecoxa", "peito", "file", "figado", "almondega", "isca", "bife", "costela"
}


def _eh_proteina_animal(valor: object) -> bool:
    return _contem_token(valor, PROTEINAS_ANIMAIS_CONHECIDAS)

BEBIDAS_CONHECIDAS: set[str] = {
    "leite", "iogurte", "suco", "vitamina", "cha"
}

DERIVADOS_LACTEOS: set[str] = {
    "leite", "queijo", "queijinho", "manteiga", "requeijao", "iogurte",
    "ricota", "nata", "creme de leite"
}

CONTEM_GLUTEN: set[str] = {
    "trigo", "farinha de trigo", "pao", "macarrao", "biscoito", "bolacha",
    "bolo", "torrada", "centeio", "cevada"
}


def _texto_normalizado(valor: object) -> str:
    """Converte para minúsculas e remove acentos."""
    texto = str(valor or "").strip().lower()
    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caractere) != "Mn"
    )


def _tokens_normalizados(valor: object) -> set[str]:
    """Extrai tokens normalizados com preservação de palavra completa e stem leve."""
    texto = re.sub(r"[^a-z0-9]+", " ", _texto_normalizado(valor))
    tokens = set()

    for token in texto.split():
        if token in {"de", "da", "do", "das", "dos", "e", "ou", "com", "sem"}:
            continue

        tokens.add(token)

        if len(token) > 4 and token[-1] in {"a", "o", "s"}:
            tokens.add(token[:-1])

    return tokens


def _contem_token(texto: object, termos: set[str]) -> bool:
    return bool(_tokens_normalizados(texto) & termos)


def _categoria_adocavel(categoria: object) -> bool:
    tokens_categoria = _tokens_normalizados(categoria)
    if not tokens_categoria:
        return False

    return any(
        _tokens_normalizados(categoria_ref) <= tokens_categoria
        for categoria_ref in CATEGORIAS_ADOCAVEIS
    )


def _tem_token_doce_por_categoria(tokens: set[str], categoria: object) -> bool:
    return bool(tokens & TOKENS_DOCE_POR_CATEGORIA) and _categoria_adocavel(categoria)


def _contem_termo_adicao_acucar(texto: object, categoria: object) -> bool:
    tokens = _tokens_normalizados(texto)
    return bool(
        tokens
        & {
            "acucar",
            "achocolatad",
            "chocolate",
            "doce",
            "adocad",
            "adocado",
            "adocada",
        }
    ) and _categoria_adocavel(categoria)


def _identificar_frutas(nome: str, categoria: str = "") -> set[str]:
    """Identifica quais frutas estão presentes no texto ou categoria."""
    texto_bruto = _texto_normalizado(f"{nome} {categoria}")
    texto_limpo = re.sub(r"\blaranja\s*[,/-]?\s*pera\b", "laranja", texto_bruto)
    texto_limpo = re.sub(r"\bbanana\s*[,/-]?\s*maca\b", "banana", texto_limpo)
    tokens = _tokens_normalizados(texto_limpo)
    frutas = set()
    for tok in tokens:
        if tok in FRUTAS_CONHECIDAS:
            frutas.add(tok)
    if not frutas and ("frut" in tokens or "frutas e derivados" in _texto_normalizado(categoria)):
        nome_limpo = _texto_normalizado(nome)
        if nome_limpo and nome_limpo not in GENERICOS_FRUTA:
            frutas.add(nome_limpo)
    return frutas


def _classificar_alimento(nome: str, categoria: str = "") -> set[str]:
    """Classifica o alimento em grupos regulatórios e culinários."""
    texto = f"{nome} {categoria}"
    tokens = _tokens_normalizados(texto)
    cat_norm = _texto_normalizado(categoria)
    classes = set()

    if (tokens & {"frut", "fruta"}) or (tokens & FRUTAS_CONHECIDAS) or ("frutas e derivados" in cat_norm):
        classes.add("fruta")
    if (tokens & {"verdura", "hortalica", "hortalic", "legume"}) or (tokens & HORTALICAS_LEGUMES_CONHECIDOS) or ("verduras" in cat_norm):
        classes.add("legume_verdura")
    if (tokens & {"feijao", "lentilha", "leguminosa"}) or (tokens & LEGUMINOSAS_CONHECIDAS) or ("leguminosas" in cat_norm) or (tokens & {"baiao", "feijoada"}):
        classes.add("leguminosa")
    if (tokens & {"arroz", "macarrao", "tuberculo", "cereal", "risoto", "galinhada", "baiao", "escondidinho", "lasanha", "nhoque", "panqueca"}) or (tokens & CEREAIS_TUBERCULOS_CONHECIDOS) or ("cereais" in cat_norm):
        classes.add("cereal_tuberculo")
    if (tokens & {"carne", "frango", "peixe", "ovo", "proteina", "bolonhesa", "galinhada", "baiao", "escondidinho", "feijoada", "estrogonofe", "strogonoff"}) or (tokens & PROTEINAS_ANIMAIS_CONHECIDAS) or ("carnes" in cat_norm) or ("pescados" in cat_norm) or ("ovos" in cat_norm):
        classes.add("proteina_animal")
    if (tokens & BEBIDAS_CONHECIDAS) or ("bebida" in cat_norm):
        classes.add("bebida")
    eh_leite_vegetal = ("leite" in tokens) and bool(tokens & {"coco", "soja", "amendoa", "aveia", "arroz", "vegetal"})
    tem_laticinio_animal = bool(tokens & (DERIVADOS_LACTEOS - {"leite"})) or ("leite e derivados" in cat_norm and not eh_leite_vegetal)
    if tem_laticinio_animal or ("leite" in tokens and not eh_leite_vegetal):
        classes.add("laticinio")
    tem_indicador_sem_gluten = "sem gluten" in _texto_normalizado(texto) or "livre de gluten" in _texto_normalizado(texto)
    eh_preparacao_sem_gluten = bool(tokens & {"polvilho", "tapioca"}) or ("pao" in tokens and "queijo" in tokens and not (tokens & {"trigo", "centeio", "cevada"}))
    if (tokens & CONTEM_GLUTEN) and not tem_indicador_sem_gluten and not (eh_preparacao_sem_gluten and not (tokens & {"trigo", "centeio", "cevada"})):
        classes.add("gluten")
    if tokens & {"biscoit", "bolach", "pao", "bolo", "torrad"}:
        classes.add("biscoito_pao_bolo")
    if _tem_token_doce_por_categoria(tokens, categoria):
        classes.add("doce")
    if tokens & {"margarina"} or "creme vegetal" in _texto_normalizado(texto):
        classes.add("margarina_creme_vegetal")
    if tokens & {"conserva", "enlatad", "enlatado"}:
        classes.add("conserva")
    if tokens & {"presunt", "linguica", "salsicha", "salame", "mortadela", "hamburguer"}:
        classes.add("produto_carneo")
    if tokens & {"achocolatad", "adocad", "iogurte"} and tokens & {"leite", "lacteo", "lacteos"}:
        classes.add("liquido_lacteo_aditivado")
    if tokens & {"pudim", "canjica", "curau"} and _categoria_adocavel(categoria):
        classes.add("preparacao_doce")
    elif _tem_token_doce_por_categoria(tokens, categoria):
        classes.add("preparacao_doce")

    return classes
