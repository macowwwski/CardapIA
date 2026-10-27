-- Transação para deleção de alimentos proibidos da base de dados:
-- Os alimentos foram avaliados à mão utilizando a Planilha_PlanPNAE_versao_4atualizada221121 para comparação (25/10/2026).


BEGIN; 

-- 1. Deleção da relação dos alimentos na tabela per_capita
DELETE FROM per_capita WHERE taco_id IN (
    SELECT id FROM taco WHERE description IN(
        'Açaí, polpa, com xarope de guaraná e glucose',
        'Achocolatado, pó',
        'Bebida Isotônica, sabores variados',
        'Biscoito, doce, recheado com chocolate',
        'Biscoito, doce, recheado com morango',
        'Biscoito, doce, wafer, recheado de chocolate',
        'Biscoito, doce, wafer, recheado de morango',
        'Bolo, mistura para',
        'Caldo de carne, tablete',
        'Caldo de galinha, tablete',
        'Cereais, mingau, milho, infantil',
        'Cereais, mistura para vitamina, trigo, cevada e aveia',
        'Cereal matinal, milho, açúcar',
        'Batata, frita, tipo chips, industrializada',
        'Chocolate, ao leite',
        'Chocolate, ao leite, com castanha do Pará',
        'Chocolate, ao leite, dietético',
        'Chocolate, meio amargo',
        'Creme de arroz, pó',
        'Creme de milho, pó',
        'Curau, milho verde, mistura para',
        'Farinha, láctea, de cereais',
        'Gelatina, sabores variados, pó',
        'Glicose de milho',
        'Maionese, tradicional com ovos',
        'Margarina, com óleo hidrogenado, com sal (65% de lipids)',
        'Margarina, com óleo hidrogenado, sem sal (80% de lipids)',
        'Mingau tradicional, pó',
        'Shoyu',
        'Tempero a base de sal',
        'Tomate, molho industrializado'
    )
);


-- 2. Deleção dos alimentos da TACO
DELETE FROM taco WHERE description IN(
        'Açaí, polpa, com xarope de guaraná e glucose',
        'Achocolatado, pó',
        'Bebida Isotônica, sabores variados',
        'Biscoito, doce, recheado com chocolate',
        'Biscoito, doce, recheado com morango',
        'Biscoito, doce, wafer, recheado de chocolate',
        'Biscoito, doce, wafer, recheado de morango',
        'Bolo, mistura para',
        'Caldo de carne, tablete',
        'Caldo de galinha, tablete',
        'Cereais, mingau, milho, infantil',
        'Cereais, mistura para vitamina, trigo, cevada e aveia',
        'Cereal matinal, milho, açúcar',
        'Batata, frita, tipo chips, industrializada',
        'Chocolate, ao leite',
        'Chocolate, ao leite, com castanha do Pará',
        'Chocolate, ao leite, dietético',
        'Chocolate, meio amargo',
        'Creme de arroz, pó',
        'Creme de milho, pó',
        'Curau, milho verde, mistura para',
        'Farinha, láctea, de cereais',
        'Gelatina, sabores variados, pó',
        'Glicose de milho',
        'Maionese, tradicional com ovos',
        'Margarina, com óleo hidrogenado, com sal (65% de lipids)',
        'Margarina, com óleo hidrogenado, sem sal (80% de lipids)',
        'Mingau tradicional, pó',
        'Shoyu',
        'Tempero a base de sal',
        'Tomate, molho industrializado'
);

COMMIT;