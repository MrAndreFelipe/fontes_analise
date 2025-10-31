-- ============================================================================
-- VIEWS ORACLE PARA EMBEDDINGS - CONTAS A PAGAR E CONTAS A RECEBER
-- Sistema RAG Cativa Têxtil
-- ============================================================================
-- 
-- INSTRUÇÕES:
-- 1. Execute estas views no banco Oracle como usuário INDUSTRIAL
-- 2. Ajuste os nomes de tabelas conforme seu schema
-- 3. Adapte os campos conforme sua estrutura de dados
-- 4. Teste as views antes de rodar a sincronização
-- ============================================================================

-- ============================================================================
-- 1. VIEW: CONTAS A PAGAR - DADOS TEXTUAIS PARA EMBEDDINGS
-- ============================================================================

CREATE OR REPLACE VIEW INDUSTRIAL.VW_RAG_CONTAS_PAGAR_TEXTUAL AS
SELECT 
    -- ID único para controle de sincronização
    'CP_' || CP.NUMERO_TITULO || '_' || TO_CHAR(CP.DATA_VENCIMENTO, 'YYYYMMDD') AS REGISTRO_ID,
    
    -- Texto formatado para embedding
    'Conta a pagar título ' || CP.NUMERO_TITULO || 
    ' do fornecedor ' || CP.NOME_FORNECEDOR || 
    ' (CNPJ ' || CP.CNPJ_FORNECEDOR || ') ' ||
    'no valor de R$ ' || TO_CHAR(CP.VALOR_TITULO, 'FM999G999G999D90') || ', ' ||
    'vencimento em ' || TO_CHAR(CP.DATA_VENCIMENTO, 'DD/MM/YYYY') || 
    CASE 
        WHEN CP.DATA_PAGAMENTO IS NOT NULL THEN 
            ', pago em ' || TO_CHAR(CP.DATA_PAGAMENTO, 'DD/MM/YYYY') || 
            ' no valor de R$ ' || TO_CHAR(CP.VALOR_PAGO, 'FM999G999G999D90')
        WHEN CP.DATA_VENCIMENTO < TRUNC(SYSDATE) THEN 
            ', em atraso há ' || (TRUNC(SYSDATE) - CP.DATA_VENCIMENTO) || ' dias'
        ELSE 
            ', em aberto'
    END ||
    ', tipo: ' || CP.TIPO_TITULO || 
    ', categoria: ' || CP.CATEGORIA_DESPESA AS TEXTO_COMPLETO,
    
    -- Classificação LGPD baseada no valor e tipo
    CASE 
        WHEN CP.VALOR_TITULO > 50000 OR CP.CNPJ_FORNECEDOR LIKE '%CPF%' THEN 'ALTO'
        WHEN CP.VALOR_TITULO > 10000 THEN 'MÉDIO'
        ELSE 'BAIXO'
    END AS NIVEL_LGPD,
    
    -- Metadados para atributos do chunk
    CP.DATA_VENCIMENTO,
    CP.DATA_PAGAMENTO,
    CP.DATA_EMISSAO,
    CP.VALOR_TITULO,
    CP.VALOR_PAGO,
    CP.NOME_FORNECEDOR,
    CP.CNPJ_FORNECEDOR,
    CP.TIPO_TITULO,
    CP.CATEGORIA_DESPESA,
    CP.STATUS_TITULO,
    CP.NUMERO_NOTA_FISCAL,
    CP.OBSERVACOES
FROM INDUSTRIAL.TB_CONTAS_PAGAR CP  -- ← AJUSTE O NOME DA SUA TABELA
WHERE CP.DATA_EMISSAO >= ADD_MONTHS(TRUNC(SYSDATE), -24)  -- Últimos 2 anos
AND CP.STATUS_TITULO IN ('ABERTO', 'PAGO', 'VENCIDO', 'PARCIAL')
ORDER BY CP.DATA_VENCIMENTO DESC;

-- Teste a view
-- SELECT * FROM INDUSTRIAL.VW_RAG_CONTAS_PAGAR_TEXTUAL WHERE ROWNUM <= 5;

-- ============================================================================
-- 2. VIEW: CONTAS A RECEBER - DADOS TEXTUAIS PARA EMBEDDINGS
-- ============================================================================

CREATE OR REPLACE VIEW INDUSTRIAL.VW_RAG_CONTAS_RECEBER_TEXTUAL AS
SELECT 
    -- ID único para controle de sincronização
    'CR_' || CR.NUMERO_TITULO || '_' || TO_CHAR(CR.DATA_VENCIMENTO, 'YYYYMMDD') AS REGISTRO_ID,
    
    -- Texto formatado para embedding
    'Conta a receber título ' || CR.NUMERO_TITULO || 
    ' do cliente ' || CR.NOME_CLIENTE || 
    ' (CNPJ/CPF ' || CR.CNPJ_CPF_CLIENTE || ') ' ||
    'referente ao pedido ' || NVL(CR.NUMERO_PEDIDO, 'N/A') || ', ' ||
    'valor de R$ ' || TO_CHAR(CR.VALOR_TITULO, 'FM999G999G999D90') || ', ' ||
    'vencimento em ' || TO_CHAR(CR.DATA_VENCIMENTO, 'DD/MM/YYYY') || 
    CASE 
        WHEN CR.DATA_RECEBIMENTO IS NOT NULL THEN 
            ', recebido em ' || TO_CHAR(CR.DATA_RECEBIMENTO, 'DD/MM/YYYY') || 
            ' no valor de R$ ' || TO_CHAR(CR.VALOR_RECEBIDO, 'FM999G999G999D90')
        WHEN CR.DATA_VENCIMENTO < TRUNC(SYSDATE) THEN 
            ', em atraso há ' || (TRUNC(SYSDATE) - CR.DATA_VENCIMENTO) || ' dias'
        ELSE 
            ', em aberto'
    END ||
    ', tipo: ' || CR.TIPO_TITULO || 
    ', forma de pagamento: ' || CR.FORMA_PAGAMENTO AS TEXTO_COMPLETO,
    
    -- Classificação LGPD baseada no valor e dados do cliente
    CASE 
        WHEN CR.VALOR_TITULO > 50000 OR CR.CNPJ_CPF_CLIENTE LIKE '%CPF%' THEN 'ALTO'
        WHEN CR.VALOR_TITULO > 10000 THEN 'MÉDIO'
        ELSE 'BAIXO'
    END AS NIVEL_LGPD,
    
    -- Metadados para atributos do chunk
    CR.DATA_VENCIMENTO,
    CR.DATA_RECEBIMENTO,
    CR.DATA_EMISSAO,
    CR.VALOR_TITULO,
    CR.VALOR_RECEBIDO,
    CR.NOME_CLIENTE,
    CR.CNPJ_CPF_CLIENTE,
    CR.TIPO_TITULO,
    CR.FORMA_PAGAMENTO,
    CR.STATUS_TITULO,
    CR.NUMERO_PEDIDO,
    CR.NUMERO_NOTA_FISCAL,
    CR.NUMERO_PARCELA,
    CR.OBSERVACOES
FROM INDUSTRIAL.TB_CONTAS_RECEBER CR  -- ← AJUSTE O NOME DA SUA TABELA
WHERE CR.DATA_EMISSAO >= ADD_MONTHS(TRUNC(SYSDATE), -24)  -- Últimos 2 anos
AND CR.STATUS_TITULO IN ('ABERTO', 'RECEBIDO', 'VENCIDO', 'PARCIAL')
ORDER BY CR.DATA_VENCIMENTO DESC;

-- Teste a view
-- SELECT * FROM INDUSTRIAL.VW_RAG_CONTAS_RECEBER_TEXTUAL WHERE ROWNUM <= 5;

-- ============================================================================
-- 3. VIEW: CONTAS A PAGAR - RESUMOS AGREGADOS POR PERÍODO
-- ============================================================================

CREATE OR REPLACE VIEW INDUSTRIAL.VW_RAG_CP_RESUMOS_AGREGADOS AS
SELECT 
    'CP_AGR_' || TO_CHAR(DATA_VENCIMENTO, 'YYYY-MM') AS REGISTRO_ID,
    
    'Resumo contas a pagar de ' || TO_CHAR(DATA_VENCIMENTO, 'MM/YYYY') || ': ' ||
    'Total de ' || COUNT(*) || ' títulos, ' ||
    'valor total de R$ ' || TO_CHAR(SUM(VALOR_TITULO), 'FM999G999G999D90') || ', ' ||
    'valor médio de R$ ' || TO_CHAR(AVG(VALOR_TITULO), 'FM999G999D90') || ', ' ||
    COUNT(CASE WHEN DATA_PAGAMENTO IS NOT NULL THEN 1 END) || ' pagos (' || 
    ROUND((COUNT(CASE WHEN DATA_PAGAMENTO IS NOT NULL THEN 1 END) * 100.0) / COUNT(*), 1) || '%), ' ||
    COUNT(CASE WHEN DATA_VENCIMENTO < TRUNC(SYSDATE) AND DATA_PAGAMENTO IS NULL THEN 1 END) || ' em atraso' AS TEXTO_RESUMO,
    
    TO_CHAR(DATA_VENCIMENTO, 'YYYY-MM') AS PERIODO,
    SUM(VALOR_TITULO) AS VALOR_TOTAL,
    COUNT(*) AS TOTAL_TITULOS,
    COUNT(CASE WHEN DATA_PAGAMENTO IS NOT NULL THEN 1 END) AS TITULOS_PAGOS,
    COUNT(CASE WHEN DATA_VENCIMENTO < TRUNC(SYSDATE) AND DATA_PAGAMENTO IS NULL THEN 1 END) AS TITULOS_VENCIDOS
FROM INDUSTRIAL.TB_CONTAS_PAGAR
WHERE DATA_EMISSAO >= ADD_MONTHS(TRUNC(SYSDATE), -24)
GROUP BY TO_CHAR(DATA_VENCIMENTO, 'YYYY-MM')
ORDER BY TO_CHAR(DATA_VENCIMENTO, 'YYYY-MM') DESC;

-- Teste a view
-- SELECT * FROM INDUSTRIAL.VW_RAG_CP_RESUMOS_AGREGADOS WHERE ROWNUM <= 5;

-- ============================================================================
-- 4. VIEW: CONTAS A RECEBER - RESUMOS AGREGADOS POR PERÍODO
-- ============================================================================

CREATE OR REPLACE VIEW INDUSTRIAL.VW_RAG_CR_RESUMOS_AGREGADOS AS
SELECT 
    'CR_AGR_' || TO_CHAR(DATA_VENCIMENTO, 'YYYY-MM') AS REGISTRO_ID,
    
    'Resumo contas a receber de ' || TO_CHAR(DATA_VENCIMENTO, 'MM/YYYY') || ': ' ||
    'Total de ' || COUNT(*) || ' títulos, ' ||
    'valor total de R$ ' || TO_CHAR(SUM(VALOR_TITULO), 'FM999G999G999D90') || ', ' ||
    'valor médio de R$ ' || TO_CHAR(AVG(VALOR_TITULO), 'FM999G999D90') || ', ' ||
    COUNT(CASE WHEN DATA_RECEBIMENTO IS NOT NULL THEN 1 END) || ' recebidos (' || 
    ROUND((COUNT(CASE WHEN DATA_RECEBIMENTO IS NOT NULL THEN 1 END) * 100.0) / COUNT(*), 1) || '%), ' ||
    COUNT(CASE WHEN DATA_VENCIMENTO < TRUNC(SYSDATE) AND DATA_RECEBIMENTO IS NULL THEN 1 END) || ' em atraso' AS TEXTO_RESUMO,
    
    TO_CHAR(DATA_VENCIMENTO, 'YYYY-MM') AS PERIODO,
    SUM(VALOR_TITULO) AS VALOR_TOTAL,
    COUNT(*) AS TOTAL_TITULOS,
    COUNT(CASE WHEN DATA_RECEBIMENTO IS NOT NULL THEN 1 END) AS TITULOS_RECEBIDOS,
    COUNT(CASE WHEN DATA_VENCIMENTO < TRUNC(SYSDATE) AND DATA_RECEBIMENTO IS NULL THEN 1 END) AS TITULOS_VENCIDOS
FROM INDUSTRIAL.TB_CONTAS_RECEBER
WHERE DATA_EMISSAO >= ADD_MONTHS(TRUNC(SYSDATE), -24)
GROUP BY TO_CHAR(DATA_VENCIMENTO, 'YYYY-MM')
ORDER BY TO_CHAR(DATA_VENCIMENTO, 'YYYY-MM') DESC;

-- Teste a view
-- SELECT * FROM INDUSTRIAL.VW_RAG_CR_RESUMOS_AGREGADOS WHERE ROWNUM <= 5;

-- ============================================================================
-- 5. VIEW: FLUXO DE CAIXA CONSOLIDADO (OPCIONAL - MUITO ÚTIL!)
-- ============================================================================

CREATE OR REPLACE VIEW INDUSTRIAL.VW_RAG_FLUXO_CAIXA_TEXTUAL AS
SELECT 
    'FC_' || TO_CHAR(DATA_REFERENCIA, 'YYYY-MM') AS REGISTRO_ID,
    
    'Fluxo de caixa de ' || TO_CHAR(DATA_REFERENCIA, 'MM/YYYY') || ': ' ||
    'Entradas totais R$ ' || TO_CHAR(TOTAL_ENTRADAS, 'FM999G999G999D90') || ' em ' || QTD_ENTRADAS || ' títulos, ' ||
    'saídas totais R$ ' || TO_CHAR(TOTAL_SAIDAS, 'FM999G999G999D90') || ' em ' || QTD_SAIDAS || ' títulos, ' ||
    'saldo líquido R$ ' || TO_CHAR((TOTAL_ENTRADAS - TOTAL_SAIDAS), 'FM999G999G999D90') AS TEXTO_COMPLETO,
    
    'MÉDIO' AS NIVEL_LGPD,
    
    DATA_REFERENCIA,
    TOTAL_ENTRADAS,
    TOTAL_SAIDAS,
    (TOTAL_ENTRADAS - TOTAL_SAIDAS) AS SALDO_LIQUIDO,
    QTD_ENTRADAS,
    QTD_SAIDAS
FROM (
    SELECT 
        TO_DATE(TO_CHAR(DATA_VENCIMENTO, 'YYYY-MM') || '-01', 'YYYY-MM-DD') AS DATA_REFERENCIA,
        SUM(CASE WHEN TIPO = 'CR' THEN VALOR ELSE 0 END) AS TOTAL_ENTRADAS,
        SUM(CASE WHEN TIPO = 'CP' THEN VALOR ELSE 0 END) AS TOTAL_SAIDAS,
        COUNT(CASE WHEN TIPO = 'CR' THEN 1 END) AS QTD_ENTRADAS,
        COUNT(CASE WHEN TIPO = 'CP' THEN 1 END) AS QTD_SAIDAS
    FROM (
        SELECT 'CR' AS TIPO, DATA_VENCIMENTO, VALOR_TITULO AS VALOR
        FROM INDUSTRIAL.TB_CONTAS_RECEBER
        WHERE DATA_VENCIMENTO >= ADD_MONTHS(TRUNC(SYSDATE), -24)
        
        UNION ALL
        
        SELECT 'CP' AS TIPO, DATA_VENCIMENTO, VALOR_TITULO AS VALOR
        FROM INDUSTRIAL.TB_CONTAS_PAGAR
        WHERE DATA_VENCIMENTO >= ADD_MONTHS(TRUNC(SYSDATE), -24)
    )
    GROUP BY TO_DATE(TO_CHAR(DATA_VENCIMENTO, 'YYYY-MM') || '-01', 'YYYY-MM-DD')
)
ORDER BY DATA_REFERENCIA DESC;

-- Teste a view
-- SELECT * FROM INDUSTRIAL.VW_RAG_FLUXO_CAIXA_TEXTUAL WHERE ROWNUM <= 5;

-- ============================================================================
-- VALIDAÇÃO DAS VIEWS
-- ============================================================================

-- Execute estas queries para verificar se as views estão funcionando:

-- 1. Total de registros em cada view
SELECT 'CP_TEXTUAL' AS VIEW_NAME, COUNT(*) AS TOTAL FROM INDUSTRIAL.VW_RAG_CONTAS_PAGAR_TEXTUAL
UNION ALL
SELECT 'CR_TEXTUAL' AS VIEW_NAME, COUNT(*) AS TOTAL FROM INDUSTRIAL.VW_RAG_CONTAS_RECEBER_TEXTUAL
UNION ALL
SELECT 'CP_AGREGADO' AS VIEW_NAME, COUNT(*) AS TOTAL FROM INDUSTRIAL.VW_RAG_CP_RESUMOS_AGREGADOS
UNION ALL
SELECT 'CR_AGREGADO' AS VIEW_NAME, COUNT(*) AS TOTAL FROM INDUSTRIAL.VW_RAG_CR_RESUMOS_AGREGADOS
UNION ALL
SELECT 'FLUXO_CAIXA' AS VIEW_NAME, COUNT(*) AS TOTAL FROM INDUSTRIAL.VW_RAG_FLUXO_CAIXA_TEXTUAL;

-- 2. Exemplo de textos gerados (primeiras 3 linhas de cada)
SELECT 'CP' AS TIPO, SUBSTR(TEXTO_COMPLETO, 1, 150) AS PREVIEW 
FROM INDUSTRIAL.VW_RAG_CONTAS_PAGAR_TEXTUAL 
WHERE ROWNUM <= 3
UNION ALL
SELECT 'CR' AS TIPO, SUBSTR(TEXTO_COMPLETO, 1, 150) AS PREVIEW 
FROM INDUSTRIAL.VW_RAG_CONTAS_RECEBER_TEXTUAL 
WHERE ROWNUM <= 3;

-- 3. Distribuição por nível LGPD
SELECT 'CP' AS TIPO, NIVEL_LGPD, COUNT(*) AS TOTAL 
FROM INDUSTRIAL.VW_RAG_CONTAS_PAGAR_TEXTUAL 
GROUP BY NIVEL_LGPD
UNION ALL
SELECT 'CR' AS TIPO, NIVEL_LGPD, COUNT(*) AS TOTAL 
FROM INDUSTRIAL.VW_RAG_CONTAS_RECEBER_TEXTUAL 
GROUP BY NIVEL_LGPD
ORDER BY TIPO, NIVEL_LGPD;

-- ============================================================================
-- NOTAS IMPORTANTES
-- ============================================================================
-- 
-- 1. AJUSTE OS NOMES DAS TABELAS:
--    - TB_CONTAS_PAGAR → Nome real da sua tabela de contas a pagar
--    - TB_CONTAS_RECEBER → Nome real da sua tabela de contas a receber
--
-- 2. AJUSTE OS CAMPOS:
--    - Verifique se sua tabela possui todos os campos usados
--    - Adicione/remova campos conforme necessário
--    - Ajuste os cálculos se necessário
--
-- 3. CLASSIFICAÇÃO LGPD:
--    - Revise os critérios de classificação (valores, tipos)
--    - Ajuste conforme sua política de LGPD
--
-- 4. PERFORMANCE:
--    - As views filtram últimos 2 anos (ADD_MONTHS(..., -24))
--    - Ajuste este período conforme necessário
--    - Considere criar índices nas colunas DATA_EMISSAO e DATA_VENCIMENTO
--
-- 5. TESTES:
--    - Sempre teste as views antes de usar na sincronização
--    - Verifique se os textos estão bem formatados
--    - Confira se não há campos NULL quebrando as concatenações
--
-- ============================================================================
