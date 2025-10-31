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

-- Teste a view
-- SELECT * FROM INDUSTRIAL.VW_RAG_CR_RESUMOS_AGREGADOS WHERE ROWNUM <= 5;

-- ============================================================================
-- 5. VIEW: FLUXO DE CAIXA CONSOLIDADO (OPCIONAL - MUITO ÚTIL!)
-- ============================================================================

CREATE OR REPLACE VIEW INDUSTRIAL.VW_RAG_FLUXO_CAIXA_TEXTUAL AS
SELECT 
    'FC_' || EMPRESA || '_' || PERIODO AS REGISTRO_ID,
    
    'Fluxo de caixa ' || EMPRESA || ' em ' || TO_CHAR(TO_DATE(PERIODO, 'YYYY-MM'), 'MM/YYYY') || ': ' ||
    'Entradas (contas a receber) R$ ' || TO_CHAR(TOTAL_ENTRADAS, 'FM999G999G999D90') || ' em ' || QTD_ENTRADAS || ' duplicatas, ' ||
    'Saídas (contas a pagar) R$ ' || TO_CHAR(TOTAL_SAIDAS, 'FM999G999G999D90') || ' em ' || QTD_SAIDAS || ' títulos, ' ||
    'Saldo líquido R$ ' || TO_CHAR(SALDO_LIQUIDO, 'FM999G999G999D90') ||
    CASE 
        WHEN SALDO_LIQUIDO >= 0 THEN ' (positivo)'
        ELSE ' (negativo)'
    END AS TEXTO_COMPLETO,
    
    'MÉDIO' AS NIVEL_LGPD,
    
    TO_DATE(PERIODO || '-01', 'YYYY-MM-DD') AS DATA_REFERENCIA,
    PERIODO,
    EMPRESA,
    TOTAL_ENTRADAS,
    TOTAL_SAIDAS,
    SALDO_LIQUIDO,
    QTD_ENTRADAS,
    QTD_SAIDAS
FROM (
    SELECT 
        PERIODO,
        EMPRESA,
        SUM(CASE WHEN TIPO = 'CR' THEN VALOR ELSE 0 END) AS TOTAL_ENTRADAS,
        SUM(CASE WHEN TIPO = 'CP' THEN VALOR ELSE 0 END) AS TOTAL_SAIDAS,
        SUM(CASE WHEN TIPO = 'CR' THEN VALOR ELSE -VALOR END) AS SALDO_LIQUIDO,
        COUNT(CASE WHEN TIPO = 'CR' THEN 1 END) AS QTD_ENTRADAS,
        COUNT(CASE WHEN TIPO = 'CP' THEN 1 END) AS QTD_SAIDAS
    FROM (
        -- Contas a Receber (Entradas)
        SELECT 
            'CR' AS TIPO,
            TO_CHAR(DATA_VENCIMENTO, 'YYYY-MM') AS PERIODO,
            EMPRESA,
            VALOR_DUPLICATA AS VALOR
        FROM INDUSTRIAL.VW_RAG_CONTAS_RECEBER
        
        UNION ALL
        
        -- Contas a Pagar (Saídas)
        SELECT 
            'CP' AS TIPO,
            TO_CHAR(DATA_VENCIMENTO, 'YYYY-MM') AS PERIODO,
            EMPRESA,
            VALOR_TITULO AS VALOR
        FROM INDUSTRIAL.VW_RAG_CONTAS_APAGAR
    )
    GROUP BY PERIODO, EMPRESA
    
)
ORDER BY PERIODO DESC, EMPRESA;

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

-- 4. Distribuição por empresa
SELECT 'CP' AS TIPO, EMPRESA, COUNT(*) AS TOTAL 
FROM INDUSTRIAL.VW_RAG_CONTAS_PAGAR_TEXTUAL 
GROUP BY EMPRESA
UNION ALL
SELECT 'CR' AS TIPO, EMPRESA, COUNT(*) AS TOTAL 
FROM INDUSTRIAL.VW_RAG_CONTAS_RECEBER_TEXTUAL 
GROUP BY EMPRESA
ORDER BY TIPO, EMPRESA;

-- 5. Exemplos de textos completos
SELECT TEXTO_COMPLETO 
FROM INDUSTRIAL.VW_RAG_CONTAS_PAGAR_TEXTUAL 
WHERE ROWNUM <= 2;

SELECT TEXTO_COMPLETO 
FROM INDUSTRIAL.VW_RAG_CONTAS_RECEBER_TEXTUAL 
WHERE ROWNUM <= 2;

-- ============================================================================
-- EXEMPLOS DE PERGUNTAS QUE O SISTEMA PODERÁ RESPONDER
-- ============================================================================
-- 
-- CONTAS A PAGAR:
-- - "Quais contas a pagar da Cativa Têxtil vencem essa semana?"
-- - "Fornecedor X tem títulos em atraso?"
-- - "Total a pagar do grupo Despesas Gerais?"
-- - "Contas vencidas no banco Itaú?"
-- 
-- CONTAS A RECEBER:
-- - "Duplicatas em atraso do cliente Y?"
-- - "Representante Z tem títulos a receber?"
-- - "Total a receber da Cativa MS esse mês?"
-- - "Situação das duplicatas da fatura 123456?"
-- 
-- FLUXO DE CAIXA:
-- - "Fluxo de caixa da Cativa Têxtil em outubro?"
-- - "Comparar entradas e saídas do mês?"
-- - "Saldo líquido previsto para próximo mês?"
-- 
-- ============================================================================

-- ============================================================================
-- EXEMPLO DE TEXTO GERADO PARA CONTAS A PAGAR
-- ============================================================================
-- Conta a pagar título 12345 da empresa Cativa Têxtil para o fornecedor 
-- ACME FORNECEDORA LTDA (CNPJ 12.345.678/0001-90), valor de R$ 15.420,50, 
-- saldo de R$ 15.420,50, emissão em 01/10/2025, vencimento em 31/10/2025, 
-- a vencer em 13 dias, grupo: Matéria Prima, subgrupo: Tecidos, 
-- banco: BANCO ITAU SA
-- ============================================================================

-- ============================================================================
-- EXEMPLO DE TEXTO GERADO PARA CONTAS A RECEBER
-- ============================================================================
-- Conta a receber duplicata 987654/1 da empresa Cativa Têxtil do cliente 
-- CONFECCOES XYZ LTDA (CNPJ 98.765.432/0001-10), representante JOAO SILVA, 
-- operação de Saída, valor de R$ 8.342,90, saldo de R$ 8.342,90, 
-- emissão em 05/10/2025, vencimento em 05/11/2025, a vencer em 18 dias, 
-- situação: Em Aberto, banco: BANCO BRADESCO SA
-- ============================================================================
