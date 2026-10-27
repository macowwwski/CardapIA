-- =============================================================
-- CardapIA — Schema do banco de dados
-- =============================================================


-- -------------------------------------------------------------
-- TABELA: taco
-- Fonte: Tabela Brasileira de Composição de Alimentos (TACO)
-- UNICAMP — 4ª edição
-- Valores por 100g da parte comestível
-- -------------------------------------------------------------

CREATE TABLE public.taco (
    id              UUID PRIMARY KEY,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP,
    deleted_at      TIMESTAMP,
    created_by      VARCHAR,
    updated_by      VARCHAR,
    deleted_by      VARCHAR,
    alternative_id  INTEGER,
    description     VARCHAR,        -- nome do alimento
    category        VARCHAR,        -- ex: "Cereais e derivados"
    humidity        FLOAT,          -- umidade (g)
    energy_kcal     FLOAT,          -- energia (kcal)
    energy_kj       FLOAT,          -- energia (kJ)
    proteins        FLOAT,          -- proteínas (g)
    lipids          FLOAT,          -- lipídios (g)
    cholesterol     FLOAT,          -- colesterol (mg)
    carbohydrates   FLOAT,          -- carboidratos (g)
    dietary_fiber   FLOAT,          -- fibra alimentar (g)
    ashe            FLOAT,          -- cinzas (g)
    calcium         FLOAT,          -- cálcio (mg)
    magnesium       FLOAT,          -- magnésio (mg)
    manganese       FLOAT,          -- manganês (mg)
    phosphoru       FLOAT,          -- fósforo (mg)
    iron            FLOAT,          -- ferro (mg)
    sodium          FLOAT,          -- sódio (mg)
    potassium       FLOAT,          -- potássio (mg)
    copper          FLOAT,          -- cobre (mg)
    zinc            FLOAT,          -- zinco (mg)
    retinol         FLOAT,          -- retinol (mcg)
    re              FLOAT,          -- equivalente de retinol (mcg)
    rae             FLOAT,          -- equivalente de atividade de retinol (mcg)
    thiamine        FLOAT,          -- tiamina / vitamina B1 (mg)
    riboflavin      FLOAT,          -- riboflavina / vitamina B2 (mg)
    pyridoxine      FLOAT,          -- piridoxina / vitamina B6 (mg)
    niacin          FLOAT,          -- niacina (mg)
    c_vitamin       FLOAT           -- vitamina C (mg)
);


-- -------------------------------------------------------------
-- TABELA: etapa_escolar
-- -------------------------------------------------------------
 
CREATE TABLE public.etapa_escolar (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    etapa        VARCHAR NOT NULL,    -- "creche", "pré-escola", "ensino fundamental", "ensino médio", "EJA"
    faixa_etaria VARCHAR NOT NULL,    
    UNIQUE (etapa, faixa_etaria)
);
 
 
-- -------------------------------------------------------------
-- TABELA: cardapio
-- Cardápio mensal gerado para uma etapa escolar específica
-- -------------------------------------------------------------
 
CREATE TABLE public.cardapio (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    etapa_escolar_id UUID NOT NULL REFERENCES public.etapa_escolar(id),
    periodo          VARCHAR NOT NULL,   -- "parcial", "integral"
    mes_aplicacao    TEXT,
    num_refeicoes    INTEGER NOT NULL,
    num_semanas      INTEGER NOT NULL DEFAULT 4,
    data_geracao     TIMESTAMP NOT NULL DEFAULT now(),
    aprovado         BOOLEAN NOT NULL DEFAULT false,
    observacoes      TEXT
);
 
 
-- -------------------------------------------------------------
-- TABELA: semana
-- Cada cardápio é dividido em semanas (1 a 4)
-- -------------------------------------------------------------
 
CREATE TABLE public.semana (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cardapio_id UUID NOT NULL REFERENCES public.cardapio(id) ON DELETE CASCADE,
    numero      INTEGER NOT NULL CHECK (numero BETWEEN 1 AND 4)
);
 
 
-- -------------------------------------------------------------
-- TABELA: dia
-- Cada semana é dividida em dias úteis (segunda a sexta)
-- -------------------------------------------------------------
 
CREATE TABLE public.dia (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    semana_id   UUID NOT NULL REFERENCES public.semana(id) ON DELETE CASCADE,
    dia_semana  VARCHAR NOT NULL    -- "segunda", "terça", "quarta", "quinta", "sexta"
);
 
 
-- -------------------------------------------------------------
-- TABELA: refeicao
-- Cada dia tem uma ou mais refeições
-- -------------------------------------------------------------
 
CREATE TABLE public.refeicao (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dia_id  UUID NOT NULL REFERENCES public.dia(id) ON DELETE CASCADE,
    tipo    VARCHAR NOT NULL,    -- "almoço", "lanche da manhã", "lanche da tarde", "jantar"
    horario TIME                 
);
 
 
-- -------------------------------------------------------------
-- TABELA: prato
-- Cada refeição é composta por um ou mais pratos
-- -------------------------------------------------------------
 
CREATE TABLE public.prato (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    refeicao_id        UUID NOT NULL REFERENCES public.refeicao(id) ON DELETE CASCADE,
    nome               VARCHAR NOT NULL,
    estado_preparacao  VARCHAR             -- "cozido", "grelhado", "cru", "assado"
);
 
 
-- -------------------------------------------------------------
-- TABELA: ingrediente
-- Cada prato é composto por ingredientes da TACO com quantidade
-- -------------------------------------------------------------
 
CREATE TABLE public.ingrediente (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prato_id     UUID NOT NULL REFERENCES public.prato(id) ON DELETE CASCADE,
    taco_id      UUID NOT NULL REFERENCES public.taco(id),
    quantidade_g FLOAT NOT NULL
);


-- -------------------------------------------------------------
-- TABELA: per_capita
-- Fonte: Manual de Per Capita PNAE / Resolução FNDE 06/2020
-- Porcionamento recomendado por faixa etária em gramas
-- -------------------------------------------------------------

CREATE TABLE public.per_capita (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    taco_id              UUID REFERENCES public.taco(id),  -- nullable: nem todo item do manual está na TACO
    nome_alimento        VARCHAR NOT NULL UNIQUE,
    fator_correcao       FLOAT NOT NULL DEFAULT 1.0,
    fator_coccao         FLOAT NOT NULL DEFAULT 1.0,
    per_capita_creche         FLOAT,   -- NULL = restrito para creche
    per_capita_pre_escola     FLOAT,   -- NULL = restrito para pré-escola
    per_capita_fund           FLOAT,   -- NULL = restrito para fundamental
    per_capita_medio_eja      FLOAT    -- NULL = restrito para médio/EJA
);