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
-- TABELAS DE CARDÁPIOS
-- (a ser adicionado nas próximas etapas do projeto)
-- -------------------------------------------------------------