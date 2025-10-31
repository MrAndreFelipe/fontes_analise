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

-- Tabela de auditoria LGPD
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

-- Índices para busca textual
CREATE INDEX IF NOT EXISTS idx_chunks_content_gin 
ON chunks USING gin(to_tsvector('portuguese', content_text));

-- Índices para auditoria LGPD
CREATE INDEX IF NOT EXISTS idx_lgpd_audit_chunk_id ON lgpd_audit(chunk_id);
CREATE INDEX IF NOT EXISTS idx_lgpd_audit_level ON lgpd_audit(classification_level);

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

-- Log de inicialização
DO $$
BEGIN
    RAISE NOTICE 'Database RAG Cativa Têxtil inicializado com sucesso!';
    RAISE NOTICE 'Extensão PGVector: %', 
        CASE WHEN EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector') 
             THEN 'INSTALADA' 
             ELSE 'NÃO ENCONTRADA' 
        END;
    RAISE NOTICE 'Tabelas criadas: chunks, processing_stats, lgpd_audit';
    RAISE NOTICE 'Pronto para receber dados!';
END $$;