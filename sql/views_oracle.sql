

-- Dados estruturados para consultas SQL diretas e rápidas (pedidos, clientes, regiões, valores)
CREATE OR REPLACE VIEW VW_RAG_VENDAS_ESTRUTURADA AS
SELECT A.numero  AS numero_pedido,
       a.cgc_cli AS cnpj_cliente,
       a.cgc_rep AS cnpj_representante,
       CASE WHEN a.EMPRESA = '00011' THEN 'Cativa Pomerode' ELSE 'Cativa MS' END AS EMPRESA,
       b.nome AS nome_cliente,
       c.nome AS nome_representante,
       a.dt_digitacao AS data_venda,
       SUM(a.vl_item_liquido) AS valor_item_liquido,
       SUM(a.vl_item_bruto) AS vl_item_bruto,
       a.regiao AS codigo_regiao,
       d.descricao AS descricao_regiao,
       a.regional AS codigo_regional,
       e.regional AS descricao_regional,
       SUM(a.vl_item_bruto) - SUM(a.vl_item_liquido) AS desconto,
       EXTRACT(YEAR FROM a.dt_digitacao) AS ano_venda,
       EXTRACT(MONTH FROM a.dt_digitacao) AS mes_venda,
       TO_CHAR(a.dt_digitacao, 'YYYY-MM') AS periodo_mensal,
       TO_CHAR(a.dt_digitacao, 'Q') AS trimestre,
       'ESTRUTURADA' as tipo_registro 
FROM MAPA.CTV_PEDIDO_2 a,
     parceiro b,
     parceiro c,
     regiao   d,
     regional e
WHERE a.cgc_cli = b.cgc
  AND a.cgc_rep = c.cgc
  AND a.regiao = d.regiao
  AND a.regional = e.id
  AND a.dt_digitacao >= SYSDATE - 730
GROUP BY A.numero,
         a.cgc_cli,
         a.cgc_rep,
         CASE WHEN a.EMPRESA = '00011' THEN 'Cativa Pomerode' ELSE 'Cativa MS' END,
         b.nome,
         c.nome,
         a.dt_digitacao,
         a.regiao,
         d.descricao,
         a.regional,
         e.regional,
         EXTRACT(YEAR FROM a.dt_digitacao),
         EXTRACT(MONTH FROM a.dt_digitacao),
         TO_CHAR(a.dt_digitacao, 'YYYY-MM'),
         TO_CHAR(a.dt_digitacao, 'Q');