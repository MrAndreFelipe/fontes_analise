-- sql/01_init_database.sql
-- Schema inicial do banco RAG Cativa Têxtil (VERSÃO CORRIGIDA)

-- Habilitar extensão PGVector
CREATE EXTENSION IF NOT EXISTS vector;

-- Verificar se extensão foi instalada
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE EXCEPTION 'Extensão vector não foi instalada corretamente';
    END IF;
END $$;

-- Tabela principal de chunks
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    content_text TEXT NOT NULL,
    encrypted_content BYTEA,
    entity TEXT NOT NULL,
    attributes JSONB NOT NULL DEFAULT '[]',
    periodo TEXT,
    nivel_lgpd TEXT NOT NULL CHECK (nivel_lgpd IN ('ALTO', 'MÉDIO', 'BAIXO')),
    hash_sha256 TEXT NOT NULL UNIQUE,
    source_file TEXT NOT NULL,
    chunk_size INTEGER NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Campos LGPD
    retention_until TIMESTAMP WITH TIME ZONE,
    data_origem TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    CONSTRAINT chunks_chunk_size_positive CHECK (chunk_size > 0),
    CONSTRAINT chunks_embedding_not_null CHECK (embedding IS NOT NULL)
);

-- Tabela de estatísticas de processamento
CREATE TABLE IF NOT EXISTS processing_stats (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    total_records INTEGER NOT NULL,
    chunks_created INTEGER NOT NULL,
    embeddings_generated INTEGER NOT NULL,
    processing_time_seconds NUMERIC(10,2) NOT NULL,
    throughput_records_per_second NUMERIC(8,2),
    lgpd_alto_count INTEGER DEFAULT 0,
    lgpd_medio_count INTEGER DEFAULT 0,
    lgpd_baixo_count INTEGER DEFAULT 0,
    memory_usage_mb NUMERIC(10,2),
    source_file TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    config_parameters JSONB,
    errors_found INTEGER DEFAULT 0,
    error_details JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de auditoria LGPD (classificação de chunks)
CREATE TABLE IF NOT EXISTS lgpd_audit (
    id SERIAL PRIMARY KEY,
    chunk_id TEXT NOT NULL REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    classification_level TEXT NOT NULL,
    confidence_score NUMERIC(3,2),
    detected_fields JSONB,
    encryption_applied BOOLEAN DEFAULT FALSE,
    retention_policy JSONB,
    access_restrictions JSONB,
    classified_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    classified_by TEXT DEFAULT 'system'
);

-- Tabela de log de acesso (LGPD Art. 37 - Auditoria)
CREATE TABLE IF NOT EXISTS access_log (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    user_name TEXT,
    user_clearance TEXT NOT NULL CHECK (user_clearance IN ('ALTO', 'MÉDIO', 'BAIXO')),
    query_text TEXT NOT NULL,
    query_classification TEXT NOT NULL,
    route_used TEXT NOT NULL CHECK (route_used IN ('text_to_sql', 'embeddings', 'cache', 'error')),
    chunks_accessed TEXT[],
    success BOOLEAN NOT NULL DEFAULT FALSE,
    denied_reason TEXT,
    processing_time_ms INTEGER,
    accessed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de log de exclusões LGPD (Art. 18)
CREATE TABLE IF NOT EXISTS lgpd_deletion_log (
    id SERIAL PRIMARY KEY,
    deletion_type TEXT NOT NULL CHECK (deletion_type IN ('retention_cleanup', 'erasure_request', 'manual', 'anonymization')),
    affected_table TEXT NOT NULL,
    records_deleted INTEGER NOT NULL,
    deletion_reason TEXT NOT NULL,
    criteria_used JSONB,
    requested_by TEXT,
    approved_by TEXT,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    evidence_backup_location TEXT
);

-- Tabela de política de retenção LGPD
CREATE TABLE IF NOT EXISTS lgpd_retention_policy (
    id SERIAL PRIMARY KEY,
    data_category TEXT NOT NULL UNIQUE,
    retention_days INTEGER NOT NULL CHECK (retention_days > 0),
    legal_basis TEXT NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    last_review_date DATE,
    next_review_date DATE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ÍNDICES (só criar após tabelas existirem)

-- Índice vetorial HNSW para similaridade de cosseno
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_cosine 
ON chunks USING hnsw (embedding vector_cosine_ops);

-- Índices para consultas por metadados
CREATE INDEX IF NOT EXISTS idx_chunks_nivel_lgpd ON chunks(nivel_lgpd);
CREATE INDEX IF NOT EXISTS idx_chunks_entity ON chunks(entity);
CREATE INDEX IF NOT EXISTS idx_chunks_source_file ON chunks(source_file);
CREATE INDEX IF NOT EXISTS idx_chunks_created_at ON chunks(created_at);
CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(hash_sha256);
CREATE INDEX IF NOT EXISTS idx_chunks_active ON chunks(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_chunks_retention ON chunks(retention_until) WHERE retention_until IS NOT NULL;

-- Índices para busca textual
CREATE INDEX IF NOT EXISTS idx_chunks_content_gin 
ON chunks USING gin(to_tsvector('portuguese', content_text));

-- Índices para auditoria LGPD
CREATE INDEX IF NOT EXISTS idx_lgpd_audit_chunk_id ON lgpd_audit(chunk_id);
CREATE INDEX IF NOT EXISTS idx_lgpd_audit_level ON lgpd_audit(classification_level);

-- Índices para access_log
CREATE INDEX IF NOT EXISTS idx_access_log_user ON access_log(user_id);
CREATE INDEX IF NOT EXISTS idx_access_log_date ON access_log(accessed_at);
CREATE INDEX IF NOT EXISTS idx_access_log_clearance ON access_log(user_clearance);

-- Índices para lgpd_deletion_log
CREATE INDEX IF NOT EXISTS idx_deletion_log_date ON lgpd_deletion_log(executed_at);
CREATE INDEX IF NOT EXISTS idx_deletion_log_type ON lgpd_deletion_log(deletion_type);

-- TRIGGER para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_chunks_updated_at 
BEFORE UPDATE ON chunks 
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- VIEWS (só criar após todas as tabelas e colunas existirem)

-- View para estatísticas rápidas
CREATE OR REPLACE VIEW chunks_summary AS
SELECT 
    COUNT(*) as total_chunks,
    COUNT(DISTINCT entity) as unique_entities,
    COUNT(DISTINCT source_file) as source_files,
    COUNT(*) FILTER (WHERE nivel_lgpd = 'ALTO') as lgpd_alto,
    COUNT(*) FILTER (WHERE nivel_lgpd = 'MÉDIO') as lgpd_medio, 
    COUNT(*) FILTER (WHERE nivel_lgpd = 'BAIXO') as lgpd_baixo,
    COALESCE(AVG(chunk_size)::INTEGER, 0) as avg_chunk_size,
    COALESCE(MIN(chunk_size), 0) as min_chunk_size,
    COALESCE(MAX(chunk_size), 0) as max_chunk_size,
    COUNT(*) FILTER (WHERE encrypted_content IS NOT NULL) as encrypted_chunks,
    MIN(created_at) as first_chunk_created,
    MAX(created_at) as last_chunk_created
FROM chunks;

-- View para análise de entidades
CREATE OR REPLACE VIEW entity_analysis AS
SELECT 
    entity,
    COUNT(*) as chunk_count,
    COALESCE(AVG(chunk_size)::INTEGER, 0) as avg_size,
    COUNT(*) FILTER (WHERE nivel_lgpd = 'ALTO') as alto_count,
    COUNT(*) FILTER (WHERE nivel_lgpd = 'MÉDIO') as medio_count,
    COUNT(*) FILTER (WHERE nivel_lgpd = 'BAIXO') as baixo_count,
    ROUND(
        COALESCE(COUNT(*) FILTER (WHERE encrypted_content IS NOT NULL), 0) * 100.0 / 
        NULLIF(COUNT(*), 0), 2
    ) as encryption_percentage
FROM chunks 
WHERE entity IS NOT NULL
GROUP BY entity 
ORDER BY chunk_count DESC;

-- Função para busca por similaridade
CREATE OR REPLACE FUNCTION search_similar_chunks(
    query_embedding vector(1536),
    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INTEGER DEFAULT 10,
    lgpd_filter TEXT DEFAULT NULL
)
RETURNS TABLE (
    chunk_id TEXT,
    content_text TEXT,
    similarity_score FLOAT,
    entity TEXT,
    nivel_lgpd TEXT,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.chunk_id,
        c.content_text,
        (1 - (c.embedding <=> query_embedding))::FLOAT as similarity_score,
        c.entity,
        c.nivel_lgpd,
        c.created_at
    FROM chunks c
    WHERE 
        (1 - (c.embedding <=> query_embedding)) >= similarity_threshold
        AND (lgpd_filter IS NULL OR c.nivel_lgpd = lgpd_filter)
    ORDER BY c.embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- Inserir dados iniciais de configuração
INSERT INTO processing_stats (
    session_id, total_records, chunks_created, embeddings_generated,
    processing_time_seconds, source_file, embedding_model
) VALUES (
    'initial_setup', 0, 0, 0, 0.0, 'setup', 'text-embedding-3-small'
) ON CONFLICT DO NOTHING;

-- Inserir políticas de retenção LGPD
INSERT INTO lgpd_retention_policy (data_category, retention_days, legal_basis, notes) VALUES
('vendas', 1825, 'Código Comercial Art. 1.196', '5 anos - Dados comerciais'),
('contas_pagar', 1825, 'Legislação Tributária (Lei 8.137/1990)', '5 anos - Obrigação fiscal'),
('contas_receber', 1825, 'Legislação Tributária', '5 anos - Obrigação fiscal'),
('access_logs', 180, 'LGPD Art. 37', '6 meses - Logs de auditoria'),
('user_sessions', 180, 'LGPD Art. 15', '6 meses - Sessões de usuários inativos')
ON CONFLICT (data_category) DO NOTHING;

-- Log de inicialização
DO $$
BEGIN
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Database RAG Cativa Têxtil inicializado com sucesso!';
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Extensão PGVector: %', 
        CASE WHEN EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector') 
             THEN 'INSTALADA' 
             ELSE 'NÃO ENCONTRADA' 
        END;
    RAISE NOTICE '';
    RAISE NOTICE 'Tabelas criadas:';
    RAISE NOTICE '  - chunks (com campos LGPD: retention_until, data_origem, is_active)';
    RAISE NOTICE '  - processing_stats';
    RAISE NOTICE '  - lgpd_audit';
    RAISE NOTICE '  - access_log (auditoria de acesso - Art. 37)';
    RAISE NOTICE '  - lgpd_deletion_log (log de exclusões - Art. 18)';
    RAISE NOTICE '  - lgpd_retention_policy (políticas de retenção)';
    RAISE NOTICE '';
    RAISE NOTICE 'Conformidade LGPD: ATIVA';
    RAISE NOTICE 'Retenção de dados: Vendas/CP/CR = 5 anos | Logs = 6 meses';
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Pronto para receber dados!';
END $$;
