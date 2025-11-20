# src/rag/rag_engine_v2.py
"""
Simplified RAG Engine - Clean Architecture
Single Responsibility: Orchestrate query processing through LGPD → Text-to-SQL → Embeddings

Architecture:
1. LGPD Classification & Permission Check
2. Text-to-SQL (Oracle) - Primary route
3. Embedding Search (PostgreSQL) - Fallback route
"""

import logging
import time
import hashlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

# Security & LGPD
from security.lgpd_query_classifier import (
    LGPDQueryClassifier,
    LGPDPermissionChecker,
    LGPDLevel,
    LGPDClassification
)
from security.lgpd_audit import LGPDAuditLogger
from security.encryption import AES256Encryptor

# Text-to-SQL
from sql.text_to_sql_service import TextToSQLService

# Embeddings (PostgreSQL fallback)
from data_processing.embeddings import EmbeddingGenerator
import psycopg2
from psycopg2.extras import RealDictCursor

# Connection Pool for production
from core.connection_pool import DatabaseConnectionPool
from monitoring import get_metrics_collector

logger = logging.getLogger(__name__)


@dataclass
class RAGResponse:
    """Immutable RAG response structure"""
    success: bool
    answer: str
    confidence: float
    sources: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    processing_time: float
    lgpd_compliant: bool
    requires_human_review: bool


@dataclass
class SearchResult:
    """Search result from embedding search"""
    chunk_id: str
    content: str
    similarity: float
    entity: str
    nivel_lgpd: str
    metadata: Dict[str, Any]


class RAGEngine:
    """
    Simplified RAG Engine
    
    Clean architecture with three main routes:
    1. LGPD Check (security)
    2. Text-to-SQL (primary - Oracle)
    3. Embeddings (fallback - PostgreSQL)
    """
    
    def __init__(self, 
                 oracle_config: Optional[Dict[str, Any]] = None,
                 postgres_config: Optional[Dict[str, Any]] = None,
                 use_openai: bool = True):
        """
        Initialize simplified RAG Engine
        
        Args:
            oracle_config: Oracle database config for Text-to-SQL
            postgres_config: PostgreSQL config for embedding fallback
            use_openai: Enable OpenAI for response formatting
        """
        # LGPD Components (new clean module)
        self.lgpd_classifier = LGPDQueryClassifier()
        self.permission_checker = LGPDPermissionChecker()
        
        # Encryptor para descriptografar chunks sensíveis
        try:
            self.encryptor = AES256Encryptor()
            logger.info("AES-256-GCM encryptor initialized for chunk decryption")
        except ValueError as e:
            logger.warning(f"Encryption unavailable: {e}")
            self.encryptor = None
        
        # Store oracle_config for later use
        self.oracle_config = oracle_config
        
        # Embedding Service (PostgreSQL) - Fallback route
        if not postgres_config:
            try:
                from core.config import Config
                pg = Config.postgres()
                postgres_config = {
                    'host': pg.host,
                    'port': pg.port,
                    'database': pg.database,
                    'user': pg.user,
                    'password': pg.password
                }
            except Exception as e:
                logger.warning(f"Could not load config from .env, using defaults: {e}")
                postgres_config = {
                    'host': 'localhost',
                    'port': 5432,
                    'database': 'cativa_rag_db',
                    'user': 'postgres',
                    'password': ''
                }
        self.postgres_config = postgres_config
        
        # Initialize connection pool (PRODUCTION-READY)
        # Supports both PostgreSQL (embeddings) and Oracle (Text-to-SQL)
        self.db_pool = DatabaseConnectionPool(
            postgres_config=postgres_config,
            oracle_config=oracle_config,
            min_connections=2,
            max_connections=10
        )
        
        # LGPD Audit Logger
        self.audit_logger = None
        if self.db_pool and self.db_pool.postgres_pool:
            try:
                from security.lgpd_audit import LGPDAuditLogger
                conn = self.db_pool.get_postgres_connection()
                self.audit_logger = LGPDAuditLogger(conn)
                self.db_pool.return_postgres_connection(conn)
                logger.info("LGPD Audit Logger initialized")
            except Exception as e:
                logger.warning(f"LGPD Audit Logger unavailable: {e}")
        
        # Text-to-SQL Service (Oracle) - Primary route
        # Pass the connection pool for production-ready connection management
        self.text_to_sql = None
        if oracle_config:
            try:
                self.text_to_sql = TextToSQLService(
                    oracle_config=oracle_config,
                    oracle_pool=self.db_pool  # Pass pool for production
                )
                logger.info("Text-to-SQL service initialized with connection pool")
            except Exception as e:
                logger.warning(f"Text-to-SQL unavailable: {e}")
        
        self.embedding_generator = EmbeddingGenerator()
        
        # OpenAI for response formatting
        self.use_openai = use_openai
        if use_openai:
            try:
                from ai.openai_client import OpenAIClient
                self.openai_client = OpenAIClient()
            except Exception as e:
                logger.warning(f"OpenAI unavailable: {e}")
                self.openai_client = None
        
        # Simple in-memory cache
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour
        
        # Metrics collector
        self.metrics_collector = get_metrics_collector()
        
        logger.info("RAG Engine initialized (simplified architecture)")
        logger.info(f"- LGPD: Enabled")
        logger.info(f"- Text-to-SQL: {'Enabled' if self.text_to_sql else 'Disabled'}")
        logger.info(f"- Embeddings: Enabled (fallback)")
        logger.info(f"- OpenAI: {'Enabled' if use_openai else 'Disabled'}")
    
    def process_query(self, 
                     query: str, 
                     user_context: Optional[Dict[str, Any]] = None,
                     conversation_history: Optional[List[Dict]] = None) -> RAGResponse:
        """
        Process query through simplified pipeline
        
        Flow:
        1. Check cache
        2. LGPD classification & permission check
        3. Try Text-to-SQL (Oracle)
        4. Fallback to embeddings (PostgreSQL)
        5. Return formatted response
        
        Args:
            query: User query in natural language
            user_context: User context with lgpd_clearance
            conversation_history: Recent conversation context (list of {user, bot} dicts)
            
        Returns:
            RAGResponse with answer and metadata
        """
        start_time = time.time()
        logger.info(f"Processing query: {query[:100]}...")
        
        try:
            # Step 1: Check cache
            cache_key = self._generate_cache_key(query, user_context)
            cached = self.cache.get(cache_key)
            if cached and (time.time() - cached['timestamp']) < self.cache_ttl:
                logger.info("Response from cache")
                return cached['response']
            
            # Step 2: LGPD Classification & Permission Check
            lgpd_classification = self.lgpd_classifier.classify(query)
            logger.info(f"LGPD Level: {lgpd_classification.level.value} (confidence: {lgpd_classification.confidence:.2f})")
            
            if not self.permission_checker.check_permission(lgpd_classification.level, user_context):
                denied_response = self._create_permission_denied_response(lgpd_classification, time.time() - start_time)
                # Log acesso negado
                self._log_access_denied(query, lgpd_classification, user_context)
                return denied_response
            
            # Step 3: Try Text-to-SQL (Oracle) - Primary route
            if self.text_to_sql:
                logger.info("Attempting Text-to-SQL route (Oracle)...")
                sql_response = self._try_text_to_sql(query, lgpd_classification, conversation_history)
                
                # Check if question is out of scope
                if sql_response and sql_response.metadata.get('out_of_scope'):
                    logger.info("Query out of scope, returning error message")
                    return sql_response  # Return error message, don't fallback
                
                if sql_response:
                    logger.info("Response generated via Text-to-SQL")
                    self._cache_response(cache_key, sql_response)
                    self._audit_query(query, lgpd_classification, sql_response, user_context)
                    # Log acesso LGPD
                    self._log_access_lgpd(query, lgpd_classification, sql_response, user_context, start_time)
                    # Record metrics
                    self._record_metrics(query, lgpd_classification, sql_response, user_context, start_time)
                    return sql_response
                logger.warning("Text-to-SQL returned no results")
            
            # Step 4: Fallback to Embeddings (PostgreSQL)
            logger.info("Attempting embeddings fallback (PostgreSQL)...")
            embedding_response = self._try_embedding_search(query, lgpd_classification, user_context, conversation_history)
            if embedding_response:
                logger.info("Response generated via embeddings")
                self._cache_response(cache_key, embedding_response)
                self._audit_query(query, lgpd_classification, embedding_response, user_context)
                # Log acesso LGPD
                self._log_access_lgpd(query, lgpd_classification, embedding_response, user_context, start_time)
                # Record metrics
                self._record_metrics(query, lgpd_classification, embedding_response, user_context, start_time)
                return embedding_response
            
            # Step 5: No results from any route
            logger.warning("No results from any route")
            return self._create_no_results_response(query, lgpd_classification, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            return RAGResponse(
                success=False,
                answer="Ocorreu um erro ao processar sua solicitação. Por favor, tente novamente.",
                confidence=0.0,
                sources=[],
                metadata={'error': str(e)},
                processing_time=time.time() - start_time,
                lgpd_compliant=True,
                requires_human_review=True
            )
    
    def _try_text_to_sql(self, query: str, lgpd: LGPDClassification, conversation_history: Optional[List[Dict]] = None) -> Optional[RAGResponse]:
        """
        Try Text-to-SQL route (Oracle)
        
        Args:
            query: Pergunta do usuario
            lgpd: Classificacao LGPD
            conversation_history: Historico recente da conversa
        
        Returns RAGResponse if successful, None otherwise
        """
        try:
            result = self.text_to_sql.generate_and_execute(query, conversation_history=conversation_history, limit=10)
            
            # Check if query is out of scope
            if result and result.get('error') == 'OUT_OF_SCOPE':
                return RAGResponse(
                    success=False,
                    answer=(
                        "Desculpe, essa pergunta está fora do meu escopo de atuação.\n\n"
                        "Sou especializado em dados empresariais da Cativa Têxtil:\n\n"
                        "📊 **Vendas e Pedidos**\n"
                        "   • Faturamento, valores, quantidades\n"
                        "   • Análises por período, região, cliente\n\n"
                        "👥 **Clientes e Representantes**\n"
                        "   • Consultas de nomes, regiões\n"
                        "   • Performance comercial\n\n"
                        "💰 **Financeiro**\n"
                        "   • Contas a pagar/receber\n"
                        "   • Títulos, vencimentos, saldos\n\n"
                        "Como posso ajudar com dados da empresa?"
                    ),
                    confidence=1.0,
                    sources=[],
                    metadata={
                        'route': 'text_to_sql',
                        'lgpd_level': lgpd.level.value,
                        'out_of_scope': True
                    },
                    processing_time=0.0,
                    lgpd_compliant=True,
                    requires_human_review=False
                )
            
            if not result or not result.get('success'):
                return None
            
            # Check if query returned any rows
            rows = result.get('rows', [])
            if not rows:
                logger.warning("Text-to-SQL executed successfully but returned 0 rows, triggering fallback")
                return None
            
            # Log SQL gerado (para debug/auditoria)
            logger.info(f"Generated SQL: {result.get('generated_sql', 'N/A')}")
            logger.info(f"SQL executed: {result.get('executed')}, rows returned: {len(rows)}")
            
            # Format response (will be formatted by WhatsApp formatter)
            answer = self._format_sql_result(result)
            
            return RAGResponse(
                success=True,
                answer=answer,
                confidence=0.85,  # High confidence for SQL results
                sources=[{'source': 'oracle_text_to_sql', 'sql': result.get('generated_sql', '')}],
                metadata={
                    'route': 'text_to_sql',
                    'lgpd_level': lgpd.level.value,
                    'rows_returned': len(result.get('rows', []))
                },
                processing_time=0.0,
                lgpd_compliant=True,
                requires_human_review=lgpd.level == LGPDLevel.ALTO
            )
            
        except Exception as e:
            logger.error(f"Text-to-SQL error: {e}")
            return None
    
    def _try_embedding_search(self, 
                             query: str, 
                             lgpd: LGPDClassification,
                             user_context: Optional[Dict] = None,
                             conversation_history: Optional[List[Dict]] = None) -> Optional[RAGResponse]:
        """
        Try embedding search fallback (PostgreSQL)
        
        Returns RAGResponse if successful, None otherwise
        """
        try:
            # Generate query embedding
            query_embedding = self.embedding_generator.generate_embedding(query)
            
            # Search similar chunks (usando connection pool)
            search_results = self._search_similar_chunks(query_embedding, max_results=10)
            
            if not search_results:
                return None
            
            # Format results into context
            context_chunks = [
                {
                    'content': r.content,
                    'similarity': r.similarity,
                    'entity': r.entity,
                    'lgpd': r.nivel_lgpd
                }
                for r in search_results[:5]
            ]
            
            # Generate answer (with OpenAI if available, including conversation history)
            answer = self._generate_answer_from_chunks(query, context_chunks, user_context, conversation_history)
            
            # Calculate confidence
            avg_similarity = sum(r.similarity for r in search_results[:3]) / min(3, len(search_results))
            confidence = avg_similarity * 0.7  # Conservative confidence
            
            return RAGResponse(
                success=True,
                answer=answer,
                confidence=confidence,
                sources=[{
                    'chunk_id': r.chunk_id,
                    'similarity': round(r.similarity, 3),
                    'entity': r.entity
                } for r in search_results[:3]],
                metadata={
                    'route': 'embeddings',
                    'lgpd_level': lgpd.level.value,
                    'chunks_used': len(search_results)
                },
                processing_time=0.0,
                lgpd_compliant=True,
                requires_human_review=confidence < 0.6 or lgpd.level == LGPDLevel.ALTO
            )
            
        except Exception as e:
            logger.error(f"Embedding search error: {e}")
            return None
    
    def _search_similar_chunks(self, query_embedding, max_results: int = 10) -> List[SearchResult]:
        """Search PostgreSQL for similar chunks using vector similarity"""
        conn = None
        try:
            # Get connection from pool
            conn = self.db_pool.get_postgres_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            sql = """
                SELECT 
                    chunk_id,
                    content_text,
                    encrypted_content,
                    1 - (embedding <=> %s::vector) as similarity,
                    entity,
                    nivel_lgpd,
                    attributes,
                    periodo,
                    source_file
                FROM chunks
                WHERE embedding IS NOT NULL
                AND 1 - (embedding <=> %s::vector) >= 0.2
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
            """
            
            embedding_list = query_embedding.tolist()
            cursor.execute(sql, (embedding_list, embedding_list, embedding_list, max_results))
            
            results = []
            for row in cursor.fetchall():
                # Descriptografa conteúdo se necessário
                content_text = self._decrypt_if_needed(row)
                
                results.append(SearchResult(
                    chunk_id=row['chunk_id'],
                    content=content_text,
                    similarity=float(row['similarity']),
                    entity=row['entity'],
                    nivel_lgpd=row['nivel_lgpd'],
                    metadata={
                        'attributes': row['attributes'],
                        'periodo': row['periodo'],
                        'source_file': row['source_file'],
                        'was_encrypted': row.get('encrypted_content') is not None
                    }
                ))
            
            logger.info(f"Found {len(results)} similar chunks")
            return results
            
        except Exception as e:
            logger.error(f"Error searching chunks: {e}")
            return []
        finally:
            # Return connection to pool
            if conn:
                self.db_pool.return_postgres_connection(conn)
    
    def _format_sql_result(self, result: Dict) -> str:
        """Format SQL result into text (will be further formatted by WhatsApp formatter)"""
        if not result.get('executed'):
            return f"SQL gerado (não executado):\n{result.get('generated_sql', '')}"
        
        rows = result.get('rows', [])
        cols = result.get('columns', [])
        
        if not rows or not cols:
            return "Nenhuma linha retornada para esta consulta."
        
        # Simple tabular format
        lines = ["Resultados (prévia):"]
        lines.append(' | '.join(cols))
        lines.append('-' * (len(' | '.join(cols))))
        
        for row in rows[:5]:
            lines.append(' | '.join(str(row.get(c, '')) for c in cols))
        
        if len(rows) > 5:
            lines.append(f"... {len(rows) - 5} linhas adicionais")
        
        return '\n'.join(lines)
    
    def _generate_answer_from_chunks(self, 
                                     query: str, 
                                     chunks: List[Dict],
                                     user_context: Optional[Dict] = None,
                                     conversation_history: Optional[List[Dict]] = None) -> str:
        """Generate answer from embedding chunks (with OpenAI if available)"""
        if self.use_openai and self.openai_client and hasattr(self.openai_client, 'api_key_configured'):
            try:
                result = self.openai_client.generate_chat_response(
                    query=query,
                    context_chunks=chunks,
                    user_context=user_context,
                    conversation_history=conversation_history  # NEW: Pass conversation context
                )
                return result['answer']
            except Exception as e:
                logger.warning(f"OpenAI failed, using fallback: {e}")
        
        # Simple fallback formatting
        return self._simple_chunk_formatting(chunks)
    
    def _simple_chunk_formatting(self, chunks: List[Dict]) -> str:
        """Simple formatting when OpenAI not available"""
        if not chunks:
            return "Não encontrei informações relevantes."
        
        lines = ["Informações encontradas:", ""]
        for i, chunk in enumerate(chunks[:3], 1):
            content = chunk['content'][:200]
            lines.append(f"{i}. {content}...")
            lines.append("")
        
        if len(chunks) > 3:
            lines.append(f"(+{len(chunks)-3} resultados adicionais)")
        
        return '\n'.join(lines)
    
    def _create_permission_denied_response(self, 
                                          lgpd: LGPDClassification, 
                                          processing_time: float) -> RAGResponse:
        """Create LGPD permission denied response"""
        message = self.permission_checker.get_required_clearance_message(lgpd.level)
        
        return RAGResponse(
            success=False,
            answer=(
                f"Desculpe, você não tem permissão para acessar dados de nível {lgpd.level.value}.\n\n"
                f"{message}\n\n"
                f"Para solicitar acesso, entre em contato com:\n"
                f"• Seu gestor\n"
                f"• Departamento de TI\n\n"
                f"Referência: Política de Segurança da Informação (LGPD)"
            ),
            confidence=1.0,
            sources=[],
            metadata={
                'reason': 'lgpd_permission_denied',
                'required_level': lgpd.level.value,
                'lgpd_confidence': lgpd.confidence
            },
            processing_time=processing_time,
            lgpd_compliant=True,
            requires_human_review=False
        )
    
    def _create_no_results_response(self, 
                                    query: str, 
                                    lgpd: LGPDClassification,
                                    processing_time: float) -> RAGResponse:
        """Create no results response"""
        return RAGResponse(
            success=True,
            answer=(
                "Não encontrei registros com esses critérios.\n\n"
                "Que tal tentar:\n"
                "• Verificar os parâmetros informados\n"
                "• Ampliar os critérios de busca\n"
                "• Confirmar se os dados existem no sistema"
            ),
            confidence=0.0,
            sources=[],
            metadata={
                'lgpd_level': lgpd.level.value,
                'no_results': True
            },
            processing_time=processing_time,
            lgpd_compliant=True,
            requires_human_review=False
        )
    
    def _generate_cache_key(self, query: str, user_context: Optional[Dict] = None) -> str:
        """Generate unique cache key"""
        key_parts = [query.lower().strip()]
        if user_context:
            key_parts.append(user_context.get('user_id', ''))
            key_parts.append(user_context.get('lgpd_clearance', ''))
        
        key_string = '|'.join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _cache_response(self, cache_key: str, response: RAGResponse):
        """Cache response"""
        self.cache[cache_key] = {
            'response': response,
            'timestamp': time.time()
        }
    
    def _audit_query(self, 
                    query: str, 
                    lgpd: LGPDClassification,
                    response: RAGResponse,
                    user_context: Optional[Dict] = None):
        """Audit query for LGPD compliance"""
        audit_data = {
            'query': query[:500],
            'lgpd_level': lgpd.level.value,
            'lgpd_confidence': lgpd.confidence,
            'route': response.metadata.get('route', 'unknown'),
            'success': response.success,
            'confidence': response.confidence,
            'user_id': user_context.get('user_id') if user_context else None,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Audit: LGPD={audit_data['lgpd_level']} Route={audit_data['route']} Success={audit_data['success']}")
    
    def clear_cache(self):
        """Clear response cache"""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def _log_access_lgpd(self, query: str, lgpd: LGPDClassification, 
                         response: RAGResponse, user_context: Optional[Dict], start_time: float):
        """Log de acesso LGPD (Art. 37)"""
        if not self.audit_logger:
            return
        
        try:
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Extrai chunks acessados dos sources
            chunks_accessed = []
            if response.sources:
                chunks_accessed = [s.get('chunk_id') for s in response.sources if s.get('chunk_id')]
            
            conn = self.db_pool.get_postgres_connection()
            audit_logger_temp = LGPDAuditLogger(conn)
            
            audit_logger_temp.log_access(
                user_id=user_context.get('user_id', 'unknown') if user_context else 'unknown',
                user_name=user_context.get('user_name') if user_context else None,
                user_clearance=user_context.get('lgpd_clearance', 'BAIXO') if user_context else 'BAIXO',
                query_text=query,
                query_classification=lgpd.level.value,
                route_used=response.metadata.get('route', 'unknown'),
                chunks_accessed=chunks_accessed,
                success=response.success,
                processing_time_ms=processing_time_ms
            )
            
            self.db_pool.return_postgres_connection(conn)
        except Exception as e:
            logger.error(f"Error logging access to LGPD audit: {e}")
    
    def _log_access_denied(self, query: str, lgpd: LGPDClassification, user_context: Optional[Dict]):
        """Log de acesso negado (LGPD)"""
        if not self.audit_logger:
            return
        
        try:
            conn = self.db_pool.get_postgres_connection()
            audit_logger_temp = LGPDAuditLogger(conn)
            
            audit_logger_temp.log_access(
                user_id=user_context.get('user_id', 'unknown') if user_context else 'unknown',
                user_name=user_context.get('user_name') if user_context else None,
                user_clearance=user_context.get('lgpd_clearance', 'BAIXO') if user_context else 'BAIXO',
                query_text=query,
                query_classification=lgpd.level.value,
                route_used='error',
                success=False,
                denied_reason=f"Insufficient clearance for {lgpd.level.value} data"
            )
            
            self.db_pool.return_postgres_connection(conn)
        except Exception as e:
            logger.error(f"Error logging denied access: {e}")
    
    def _decrypt_if_needed(self, chunk_row: Dict) -> str:
        """
        Descriptografa chunk se encrypted_content existir
        
        Args:
            chunk_row: Row do banco com content_text e encrypted_content
        
        Returns:
            Texto descriptografado ou content_text original
        
        Lógica:
        1. Se encrypted_content existe e não é None → Descriptografa
        2. Senão → Usa content_text diretamente
        """
        encrypted_content = chunk_row.get('encrypted_content')
        
        # Se não há conteúdo criptografado, retorna texto normal
        if not encrypted_content:
            return chunk_row.get('content_text', '')
        
        # Se encryptor não está disponível, retorna texto normal (fallback)
        if not self.encryptor:
            logger.warning(f"Chunk {chunk_row.get('chunk_id')} está criptografado mas encryptor indisponível")
            return chunk_row.get('content_text', '')
        
        # Descriptografa
        try:
            # encrypted_content já vem como bytes do PostgreSQL (BYTEA)
            if isinstance(encrypted_content, memoryview):
                encrypted_content = bytes(encrypted_content)
            
            decrypted_text = self.encryptor.decrypt(encrypted_content)
            logger.debug(f"Chunk {chunk_row.get('chunk_id')} descriptografado: {len(encrypted_content)} bytes → {len(decrypted_text)} chars")
            return decrypted_text
            
        except Exception as e:
            logger.error(f"Erro ao descriptografar chunk {chunk_row.get('chunk_id')}: {e}")
            # Fallback para texto não criptografado
            return chunk_row.get('content_text', '[ERRO: Conteúdo criptografado ilegível]')
    
    def _record_metrics(self, query: str, lgpd: LGPDClassification, 
                       response: RAGResponse, user_context: Optional[Dict], start_time: float):
        """Registra métricas da query processada"""
        try:
            latency_ms = (time.time() - start_time) * 1000
            
            self.metrics_collector.record_query(
                query_text=query[:100],  # Truncate for privacy
                lgpd_level=lgpd.level.value,
                route_used=response.metadata.get('route', 'unknown'),
                success=response.success,
                latency_ms=latency_ms,
                user_id=user_context.get('user_id') if user_context else None,
                error=None if response.success else response.metadata.get('error'),
                tokens_used=response.metadata.get('tokens_used')
            )
        except Exception as e:
            logger.error(f"Error recording metrics: {e}")
    
    def close(self):
        """Close database connections and connection pools"""
        if self.db_pool:
            self.db_pool.close_all()
            logger.info("Connection pools closed")
