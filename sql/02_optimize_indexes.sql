-- sql/02_optimize_indexes.sql
-- Otimizações adicionais de índices para melhor performance de busca

-- Índices compostos para buscas híbridas
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_entity_lgpd 
ON chunks(entity, nivel_lgpd);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_content_pattern 
ON chunks USING gin(content_text gin_trgm_ops);

-- Habilitar extensão pg_trgm se não estiver habilitada
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Índice para busca por números de pedido
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_pedido_pattern 
ON chunks USING gin(content_text gin_trgm_ops) 
WHERE content_text ~ '\d{6}';

-- Índice para atributos JSON
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_attributes_gin 
ON chunks USING gin(attributes);

-- Índices parciais para diferentes tipos de entidade
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_pedido_entity 
ON chunks(chunk_id, content_text, nivel_lgpd) 
WHERE entity = 'PEDIDO_VENDA';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_cliente_entity 
ON chunks(chunk_id, content_text, nivel_lgpd) 
WHERE entity = 'CLIENTE';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_regional_entity 
ON chunks(chunk_id, content_text, nivel_lgpd) 
WHERE entity = 'REGIONAL';

-- Função para busca otimizada de pedidos
CREATE OR REPLACE FUNCTION search_pedido_optimized(
    pedido_numero TEXT,
    lgpd_level TEXT DEFAULT NULL
)
RETURNS TABLE (
    chunk_id TEXT,
    content_text TEXT,
    similarity_score FLOAT,
    entity TEXT,
    nivel_lgpd TEXT,
    match_type TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.chunk_id,
        c.content_text,
        1.0::FLOAT as similarity_score,
        c.entity,
        c.nivel_lgpd,
        'exact_pedido'::TEXT as match_type
    FROM chunks c
    WHERE 
        c.content_text ILIKE '%' || pedido_numero || '%'
        AND (lgpd_level IS NULL OR c.nivel_lgpd = lgpd_level)
    ORDER BY 
        CASE WHEN c.content_text ILIKE '%NUMERO_PEDIDO,' || pedido_numero || '%' THEN 1 ELSE 2 END,
        c.created_at DESC
    LIMIT 10;
END;
$$ LANGUAGE plpgsql;

-- Função para busca otimizada de regiões
CREATE OR REPLACE FUNCTION search_regiao_optimized(
    regiao_termo TEXT,
    lgpd_level TEXT DEFAULT NULL
)
RETURNS TABLE (
    chunk_id TEXT,
    content_text TEXT,
    similarity_score FLOAT,
    entity TEXT,
    nivel_lgpd TEXT,
    match_type TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.chunk_id,
        c.content_text,
        0.95::FLOAT as similarity_score,
        c.entity,
        c.nivel_lgpd,
        'exact_regiao'::TEXT as match_type
    FROM chunks c
    WHERE 
        (c.content_text ILIKE '%' || regiao_termo || '%'
         OR c.content_text ILIKE '%DESCRICAO_REGIONAL%' || regiao_termo || '%'
         OR c.content_text ILIKE '%DESCRICAO_REGIAO%' || regiao_termo || '%')
        AND (lgpd_level IS NULL OR c.nivel_lgpd = lgpd_level)
    ORDER BY 
        CASE 
            WHEN c.content_text ILIKE '%DESCRICAO_REGIONAL,' || regiao_termo || '%' THEN 1 
            WHEN c.content_text ILIKE '%DESCRICAO_REGIAO,' || regiao_termo || '%' THEN 2
            ELSE 3 
        END,
        c.created_at DESC
    LIMIT 15;
END;
$$ LANGUAGE plpgsql;

-- View materializada para estatísticas por região
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_vendas_por_regiao AS
SELECT 
    regexp_replace(
        regexp_replace(content_text, '.*DESCRICAO_REGIONAL,([^,]+),.*', '\1'),
        '.*DESCRICAO_REGIAO,([^,]+),.*', '\1'
    ) as regiao,
    COUNT(*) as total_pedidos,
    entity,
    nivel_lgpd
FROM chunks 
WHERE content_text ~ 'DESCRICAO_REGIONAL|DESCRICAO_REGIAO'
GROUP BY regiao, entity, nivel_lgpd;

-- Índice na view materializada
CREATE INDEX IF NOT EXISTS idx_mv_vendas_regiao 
ON mv_vendas_por_regiao(regiao, entity);

-- Função para refresh da view materializada
CREATE OR REPLACE FUNCTION refresh_mv_vendas_por_regiao()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_vendas_por_regiao;
END;
$$ LANGUAGE plpgsql;

-- Estatísticas para o otimizador
ANALYZE chunks;

-- Log de otimização
DO $$
BEGIN
    RAISE NOTICE 'Otimizações de índice aplicadas com sucesso!';
    RAISE NOTICE 'Novos índices: compostos, trigram, parciais';
    RAISE NOTICE 'Funções adicionadas: search_pedido_optimized, search_regiao_optimized';
    RAISE NOTICE 'View materializada: mv_vendas_por_regiao';
END $$;