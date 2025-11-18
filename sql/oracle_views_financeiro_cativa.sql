-- ============================================================================
-- VIEWS ORACLE PARA EMBEDDINGS - ADAPTADAS PARA ESTRUTURA CATIVA
-- Sistema RAG Cativa Têxtil
-- ============================================================================
-- 
-- Estas views usam as views existentes como base:
-- - INDUSTRIAL.VW_RAG_CONTAS_APAGAR (Contas a Pagar)
-- - INDUSTRIAL.VW_RAG_CONTAS_RECEBER (Contas a Receber)
-- ============================================================================

-- ============================================================================
-- 1. VIEW: CONTAS A PAGAR - DADOS TEXTUAIS PARA EMBEDDINGS
-- ============================================================================

CREATE OR REPLACE VIEW INDUSTRIAL.VW_RAG_CONTAS_PAGAR_TEXTUAL AS
SELECT 
    -- ID único para controle de sincronização
    'CP_' || CHAVE_CONTAS_APAGAR || '_' || TO_CHAR(DATA_VENCIMENTO, 'YYYYMMDD') AS REGISTRO_ID,
    
    -- Texto formatado para embedding
    'Conta a pagar título ' || TITULO || 
    ' da empresa ' || EMPRESA || 
    ' para o fornecedor ' || NOME_FORNECEDOR || 
    ' (CNPJ ' || CNPJ_FORNECEDOR || '), ' ||
    'valor de R$ ' || TO_CHAR(VALOR_TITULO, 'FM999G999G999D90') || ', ' ||
    'saldo de R$ ' || TO_CHAR(VALOR_SALDO, 'FM999G999G999D90') || ', ' ||
    'emissão em ' || TO_CHAR(DATA_EMISSAO, 'DD/MM/YYYY') || ', ' ||
    'vencimento em ' || TO_CHAR(DATA_VENCIMENTO, 'DD/MM/YYYY') || 
    CASE 
        WHEN DATA_VENCIMENTO < TRUNC(SYSDATE) AND VALOR_SALDO > 0 THEN 
            ', em atraso há ' || (TRUNC(SYSDATE) - DATA_VENCIMENTO) || ' dias'
        WHEN VALOR_SALDO = 0 THEN 
            ', título pago'
        WHEN DATA_VENCIMENTO >= TRUNC(SYSDATE) THEN 
            ', a vencer em ' || (DATA_VENCIMENTO - TRUNC(SYSDATE)) || ' dias'
        ELSE 
            ', em aberto'
    END ||
    ', grupo: ' || DESCRICAO_GRUPO || 
    ', subgrupo: ' || DESCRICAO_SUBGRUPO ||
    ', banco: ' || DESCRICAO_BANCO AS TEXTO_COMPLETO,
    
    -- Classificação LGPD baseada no valor e tipo
    CASE 
        WHEN VALOR_TITULO > 50000 THEN 'ALTO'
        WHEN VALOR_TITULO > 10000 THEN 'MÉDIO'
        ELSE 'BAIXO'
    END AS NIVEL_LGPD,
    
    -- Metadados para atributos do chunk
    EMPRESA,
    CHAVE_CONTAS_APAGAR,
    TITULO,
    CNPJ_FORNECEDOR,
    NOME_FORNECEDOR,
    DATA_EMISSAO,
    DATA_VENCIMENTO,
    VALOR_TITULO,
    VALOR_SALDO,
    GRUPO,
    DESCRICAO_GRUPO,
    SUBGRUPO,
    DESCRICAO_SUBGRUPO,
    BANCO,
    DESCRICAO_BANCO
FROM INDUSTRIAL.VW_RAG_CONTAS_APAGAR
WHERE VALOR_SALDO IS NOT NULL  -- Apenas títulos com saldo definido
ORDER BY DATA_VENCIMENTO DESC;

-- Teste a view
-- SELECT * FROM INDUSTRIAL.VW_RAG_CONTAS_PAGAR_TEXTUAL WHERE ROWNUM <= 5;

-- ============================================================================
-- 2. VIEW: CONTAS A RECEBER - DADOS TEXTUAIS PARA EMBEDDINGS
-- ============================================================================

CREATE OR REPLACE VIEW INDUSTRIAL.VW_RAG_CONTAS_RECEBER_TEXTUAL AS
SELECT 
    -- ID único para controle de sincronização
    'CR_' || CHAVE_DUPLICATA || '_' || TO_CHAR(DATA_VENCIMENTO, 'YYYYMMDD') AS REGISTRO_ID,
    
    -- Texto formatado para embedding
    'Conta a receber duplicata ' || FATURA || '/' || ORDEM || 
    ' da empresa ' || EMPRESA ||
    ' do cliente ' || NOME_CLIENTE || 
    ' (CNPJ ' || CNPJ_CLIENTE || '), ' ||
    'representante ' || NOME_REPRESENTANTE || ', ' ||
    'operação de ' || OPERACAO || ', ' ||
    'valor de R$ ' || TO_CHAR(VALOR_DUPLICATA, 'FM999G999G999D90') || ', ' ||
    'saldo de R$ ' || TO_CHAR(SALDO, 'FM999G999G999D90') || ', ' ||
    'emissão em ' || TO_CHAR(DATA_EMISSAO, 'DD/MM/YYYY') || ', ' ||
    'vencimento em ' || TO_CHAR(DATA_VENCIMENTO, 'DD/MM/YYYY') || 
    CASE 
        WHEN DATA_VENCIMENTO < TRUNC(SYSDATE) AND SALDO > 0 THEN 
            ', em atraso há ' || (TRUNC(SYSDATE) - DATA_VENCIMENTO) || ' dias'
        WHEN SALDO = 0 THEN 
            ', duplicata recebida'
        WHEN DATA_VENCIMENTO >= TRUNC(SYSDATE) THEN 
            ', a vencer em ' || (DATA_VENCIMENTO - TRUNC(SYSDATE)) || ' dias'
        ELSE 
            ', em aberto'
    END ||
    ', situação: ' || SITUACAO_DUPLICATA ||
    ', banco: ' || DESCRICAO_BANCO ||
    CASE 
        WHEN CHAVE_AP IS NOT NULL THEN ', vinculada ao AP ' || CHAVE_AP
        ELSE ''
    END AS TEXTO_COMPLETO,
    
    -- Classificação LGPD baseada no valor
    CASE 
        WHEN VALOR_DUPLICATA > 50000 THEN 'ALTO'
        WHEN VALOR_DUPLICATA > 10000 THEN 'MÉDIO'
        ELSE 'BAIXO'
    END AS NIVEL_LGPD,
    
    -- Metadados para atributos do chunk
    EMPRESA,
    CHAVE_DUPLICATA,
    CHAVE_AP,
    FATURA,
    ORDEM,
    CHAVE_FATURA,
    CNPJ_CLIENTE,
    NOME_CLIENTE,
    OPERACAO,
    CNPJ_REPRESENTANTE,
    NOME_REPRESENTANTE,
    BANCO,
    DESCRICAO_BANCO,
    COMICAO_1,
    COMICAO_2,
    DATA_DIGITACAO,
    DATA_VENCIMENTO,
    DATA_EMISSAO,
    VALOR_DUPLICATA,
    SITUACAO_DUPLICATA,
    SALDO
FROM INDUSTRIAL.VW_RAG_CONTAS_RECEBER
WHERE SALDO IS NOT NULL  -- Apenas duplicatas com saldo definido
ORDER BY DATA_VENCIMENTO DESC;

-- Teste a view
-- SELECT * FROM INDUSTRIAL.VW_RAG_CONTAS_RECEBER_TEXTUAL WHERE ROWNUM <= 5;

-- ============================================================================
-- 3. VIEW: CONTAS A PAGAR - RESUMOS AGREGADOS POR PERÍODO E EMPRESA
-- ============================================================================

CREATE OR REPLACE VIEW INDUSTRIAL.VW_RAG_CP_RESUMOS_AGREGADOS AS
SELECT 
    'CP_AGR_' || EMPRESA || '_' || PERIODO AS REGISTRO_ID,
    
    'Resumo contas a pagar ' || EMPRESA || ' em ' || TO_CHAR(TO_DATE(PERIODO, 'YYYY-MM'), 'MM/YYYY') || ': ' ||
    'Total de ' || TOTAL_TITULOS || ' títulos, ' ||
    'valor total de R$ ' || TO_CHAR(VALOR_TOTAL, 'FM999G999G999D90') || ', ' ||
    'saldo total de R$ ' || TO_CHAR(SALDO_TOTAL, 'FM999G999G999D90') || ', ' ||
    'valor médio de R$ ' || TO_CHAR(VALOR_MEDIO, 'FM999G999D90') || ', ' ||
    TITULOS_PAGOS || ' títulos pagos (' || 
    ROUND((TITULOS_PAGOS * 100.0) / TOTAL_TITULOS, 1) || '%), ' ||
    TITULOS_VENCIDOS || ' títulos vencidos' AS TEXTO_RESUMO,
    
    PERIODO,
    EMPRESA,
    VALOR_TOTAL,
    SALDO_TOTAL,
    VALOR_MEDIO,
    TOTAL_TITULOS,
    TITULOS_PAGOS,
    TITULOS_VENCIDOS
FROM (
    SELECT 
        TO_CHAR(DATA_VENCIMENTO, 'YYYY-MM') AS PERIODO,
        EMPRESA,
        SUM(VALOR_TITULO) AS VALOR_TOTAL,
        SUM(VALOR_SALDO) AS SALDO_TOTAL,
        AVG(VALOR_TITULO) AS VALOR_MEDIO,
        COUNT(*) AS TOTAL_TITULOS,
        COUNT(CASE WHEN VALOR_SALDO = 0 THEN 1 END) AS TITULOS_PAGOS,
        COUNT(CASE WHEN DATA_VENCIMENTO < TRUNC(SYSDATE) AND VALOR_SALDO > 0 THEN 1 END) AS TITULOS_VENCIDOS
    FROM INDUSTRIAL.VW_RAG_CONTAS_APAGAR
    GROUP BY TO_CHAR(DATA_VENCIMENTO, 'YYYY-MM'), EMPRESA
)
ORDER BY PERIODO DESC, EMPRESA;

-- Teste a view
-- SELECT * FROM INDUSTRIAL.VW_RAG_CP_RESUMOS_AGREGADOS WHERE ROWNUM <= 5;

-- ============================================================================
-- 4. VIEW: CONTAS A RECEBER - RESUMOS AGREGADOS POR PERÍODO E EMPRESA
-- ============================================================================

CREATE OR REPLACE VIEW INDUSTRIAL.VW_RAG_CR_RESUMOS_AGREGADOS AS
SELECT 
    'CR_AGR_' || EMPRESA || '_' || PERIODO AS REGISTRO_ID,
    
    'Resumo contas a receber ' || EMPRESA || ' em ' || TO_CHAR(TO_DATE(PERIODO, 'YYYY-MM'), 'MM/YYYY') || ': ' ||
    'Total de ' || TOTAL_DUPLICATAS || ' duplicatas, ' ||
    'valor total de R$ ' || TO_CHAR(VALOR_TOTAL, 'FM999G999G999D90') || ', ' ||
    'saldo total de R$ ' || TO_CHAR(SALDO_TOTAL, 'FM999G999G999D90') || ', ' ||
    'valor médio de R$ ' || TO_CHAR(VALOR_MEDIO, 'FM999G999D90') || ', ' ||
    DUPLICATAS_RECEBIDAS || ' duplicatas recebidas (' || 
    ROUND((DUPLICATAS_RECEBIDAS * 100.0) / TOTAL_DUPLICATAS, 1) || '%), ' ||
    DUPLICATAS_VENCIDAS || ' duplicatas vencidas' AS TEXTO_RESUMO,
    
    PERIODO,
    EMPRESA,
    VALOR_TOTAL,
    SALDO_TOTAL,
    VALOR_MEDIO,
    TOTAL_DUPLICATAS,
    DUPLICATAS_RECEBIDAS,
    DUPLICATAS_VENCIDAS
FROM (
    SELECT 
        TO_CHAR(DATA_VENCIMENTO, 'YYYY-MM') AS PERIODO,
        EMPRESA,
        SUM(VALOR_DUPLICATA) AS VALOR_TOTAL,
        SUM(SALDO) AS SALDO_TOTAL,
        AVG(VALOR_DUPLICATA) AS VALOR_MEDIO,
        COUNT(*) AS TOTAL_DUPLICATAS,
        COUNT(CASE WHEN SALDO = 0 THEN 1 END) AS DUPLICATAS_RECEBIDAS,
        COUNT(CASE WHEN DATA_VENCIMENTO < TRUNC(SYSDATE) AND SALDO > 0 THEN 1 END) AS DUPLICATAS_VENCIDAS
    FROM INDUSTRIAL.VW_RAG_CONTAS_RECEBER
    GROUP BY TO_CHAR(DATA_VENCIMENTO, 'YYYY-MM'), EMPRESA
)
ORDER BY PERIODO DESC, EMPRESA;

