DO $$
DECLARE
    linhas_updated INTEGER := 0;
    linhas_deleted INTEGER := 0;
    v_rows INTEGER;
BEGIN
    -- --- COLE TODOS OS SEUS UPDATES AQUI DENTRO ---

    UPDATE per_capita SET nome_alimento = 'Azeitona, verde, conserva' 
    WHERE id = '5bf6ada2-d3c5-4fa2-ba6a-853e4902f7c2';

    UPDATE per_capita SET nome_alimento = 'Biscoito, salgado, cream cracker' 
    WHERE id = '31db24a1-f606-465d-aca9-9672018d3a85';

    UPDATE per_capita SET nome_alimento = 'Chocolate em pó' 
    WHERE id = '865123f8-9cdc-4e98-a385-ae3c1375ffee';

    UPDATE per_capita SET nome_alimento = 'Doce, de abóbora, cremoso' 
    WHERE id = '03e14119-77ad-4e43-9fd4-a51df1006925';

    UPDATE per_capita SET nome_alimento = 'Doce de frutas cristalizado' 
    WHERE id = '6e7867e6-2195-4852-9acf-ee0f346c5045';

    UPDATE per_capita SET nome_alimento = 'Ervilha, enlatada, drenada' 
    WHERE id = '24816131-640b-4189-b806-b510a754eeb1';

    UPDATE per_capita SET nome_alimento = 'Leite, de vaca, achocolatado' 
    WHERE id = 'e6f8c0cc-5240-472c-8777-1970a6004ba7';

    UPDATE per_capita SET nome_alimento = 'Linguiça, calabresa, fininha, crua' 
    WHERE id = '1368c95e-3451-4953-817e-f83f9289e179';

    UPDATE per_capita SET nome_alimento = 'Linguiça (suína, bovina, mista) crua' 
    WHERE id = '03e14119-77ad-4e43-9fd4-a51df1006925';

    UPDATE per_capita SET nome_alimento = 'Mamão, doce em calda, drenado' 
    WHERE id = '6c58e757-d3ef-4b74-9155-c540fa8e9a6c';

    UPDATE per_capita SET nome_alimento = 'Mamão verde, doce em calda, drenado' 
    WHERE id = '80dba58f-223b-4908-abbc-8b8d75064dec';

    UPDATE per_capita SET nome_alimento = 'Margarina, com óleo, sem sal' 
    WHERE id = 'cd315118-d851-4ba2-be3c-1b26ac9fb3d6';

    UPDATE per_capita SET nome_alimento = 'Milho, verde, enlatado, drenado' 
    WHERE id = 'ba03355a-7b17-4ce5-9bca-ee2c788e0a0c';

    UPDATE per_capita SET nome_alimento = 'Palmito, juçara, em conserva' 
    WHERE id = 'd0bcf06e-b2e4-4d74-b793-fff66137142e';

    UPDATE per_capita SET nome_alimento = 'Palmito, pupunha, em conserva' 
    WHERE id = 'd1483490-7f7a-4acd-9d1e-f6ba6f45dda9';

    UPDATE per_capita SET nome_alimento = 'Pé-de-moleque, amendoim' 
    WHERE id = 'e1f83e46-cc54-40d1-808f-34b545b2bb93';

    UPDATE per_capita SET nome_alimento = 'Peixe, água salgada, sardinha, conserva, c/ molho de tomate' 
    WHERE id = '0d27b0e6-0164-4a3b-9837-319902b49c28';

    UPDATE per_capita SET nome_alimento = 'Pêssego, enlatado, em calda' 
    WHERE id = '80dba58f-223b-4908-abbc-8b8d75064dec';

    UPDATE per_capita SET nome_alimento = 'Presunto, com capa de gordura' 
    WHERE id = '57ed3571-f498-43d6-9d66-9bc0291de440';

    UPDATE per_capita SET nome_alimento = 'Presunto, sem capa de gordura' 
    WHERE id = '9df507fa-b86f-46c4-80e5-81671dbfda10';

    UPDATE per_capita SET nome_alimento = 'Queijo, petit suisse, morango' 
    WHERE id = '2dc049fb-997a-4914-bd49-238e9e277915';

    UPDATE per_capita SET nome_alimento = 'Sardinha, conserva em óleo' 
    WHERE id = '82d8e94f-a120-4555-bc93-8a4a4c2db6f3';

    UPDATE per_capita SET nome_alimento = 'Seleta de legumes, enlatada' 
    WHERE id = '8fe987ac-9570-4fe8-ba4a-65f7be156100';

    UPDATE per_capita SET nome_alimento = 'Sorvete de qualquer sabor, industrializado' 
    WHERE id = '57681448-dfb6-44c1-9443-9fb30feefee5';

    UPDATE per_capita SET nome_alimento = 'Torrada, trigo, tradicional' 
    WHERE id = '152d7314-6eb4-410c-a3b6-b94e3c2fb8b2';

    DELETE FROM per_capita 
    WHERE id = 'a143b5cf-04af-4466-9647-239058273690'; -- doce, leite, cremoso 

    DELETE FROM per_capita 
    WHERE id = '2dd3ddd1-ba6d-41d2-b044-bfeea156f3c2'; -- feijão geral

    DELETE FROM per_capita 
    WHERE id = '9dd4d9d2-50ba-4b60-b2cc-61bc5524d2e7'; -- (média diferentes)

-- --- IMPRIME O RESULTADO NO CONSOLE ---
    RAISE NOTICE '=== RESUMO DA EXECUÇÃO ===';
    RAISE NOTICE 'Total de linhas atualizadas: %', linhas_updated;
    RAISE NOTICE 'Total de linhas deletadas: %', linhas_deleted;
    RAISE NOTICE 'Total geral de alterações: %', (linhas_updated + linhas_deleted);
END $$;