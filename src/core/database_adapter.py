# src/core/database_adapter.py
"""
Database Adapter - Sistema RAG Cativa Têxtil
Camada de abstração para diferentes bancos de dados (PostgreSQL e Oracle)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """Configuração genérica de banco de dados"""
    host: str
    port: int
    database: str
    user: str
    password: str
    db_type: str  # 'postgresql' ou 'oracle'
    schema: Optional[str] = None
    additional_params: Optional[Dict[str, Any]] = None

@dataclass
class SearchResult:
    """Resultado de busca genérico"""
    chunk_id: str
    content_text: str
    similarity: float
    entity: str
    nivel_lgpd: str
    metadata: Dict[str, Any]

class DatabaseAdapter(ABC):
    """Interface abstrata para adaptadores de banco de dados"""
    
    @abstractmethod
    def connect(self) -> bool:
        """Conecta ao banco de dados"""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Desconecta do banco de dados"""
        pass
    
    @abstractmethod
    def execute_query(self, query: str, params: Tuple = None) -> List[Dict[str, Any]]:
        """Executa uma query e retorna resultados"""
        pass
    
    @abstractmethod
    def search_exact_entities(self, entities: Dict[str, Any], excluded_ids: List[str] = None) -> List[SearchResult]:
        """Busca exata por entidades"""
        pass
    
    @abstractmethod
    def search_vector_similarity(self, embedding: List[float], similarity_threshold: float = 0.7, 
                                max_results: int = 10, excluded_ids: List[str] = None) -> List[SearchResult]:
        """Busca por similaridade vetorial"""
        pass
    
    @abstractmethod
    def get_chunks_summary(self) -> Dict[str, Any]:
        """Retorna estatísticas dos chunks"""
        pass
    
    @abstractmethod
    def insert_chunk(self, chunk_data: Dict[str, Any]) -> bool:
        """Insere um chunk no banco"""
        pass

class PostgreSQLAdapter(DatabaseAdapter):
    """Adaptador para PostgreSQL com PGVector"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection = None
        self._setup_queries()
    
    def _setup_queries(self):
        """Define queries específicas do PostgreSQL"""
        self.queries = {
            'exact_pedido': """
                SELECT 
                    chunk_id, content_text, entity, nivel_lgpd, attributes, periodo, source_file
                FROM chunks
                WHERE content_text ILIKE %s AND chunk_id NOT IN %s
                ORDER BY created_at DESC LIMIT %s
            """,
            'exact_region': """
                SELECT 
                    chunk_id, content_text, entity, nivel_lgpd, attributes, periodo, source_file
                FROM chunks
                WHERE (content_text ILIKE ANY(%s)) AND chunk_id NOT IN %s
                ORDER BY created_at DESC LIMIT %s
            """,
            'vector_similarity': """
                SELECT 
                    chunk_id, content_text, 1 - (embedding <=> %s::vector) as similarity,
                    entity, nivel_lgpd, attributes, periodo, source_file
                FROM chunks
                WHERE embedding IS NOT NULL 
                AND 1 - (embedding <=> %s::vector) >= %s
                AND chunk_id NOT IN %s
                ORDER BY embedding <=> %s::vector LIMIT %s
            """,
            'chunks_summary': """
                SELECT 
                    COUNT(*) as total_chunks,
                    COUNT(DISTINCT entity) as unique_entities,
                    COUNT(*) FILTER (WHERE nivel_lgpd = 'ALTO') as lgpd_alto,
                    COUNT(*) FILTER (WHERE nivel_lgpd = 'MÉDIO') as lgpd_medio,
                    COUNT(*) FILTER (WHERE nivel_lgpd = 'BAIXO') as lgpd_baixo
                FROM chunks
            """
        }
    
    def connect(self) -> bool:
        """Conecta ao PostgreSQL"""
        try:
            import psycopg2
            self.connection = psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password
            )
            logger.info("Conectado ao PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"Erro ao conectar PostgreSQL: {e}")
            return False
    
    def disconnect(self) -> None:
        """Desconecta do PostgreSQL"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def execute_query(self, query: str, params: Tuple = None) -> List[Dict[str, Any]]:
        """Executa query no PostgreSQL"""
        try:
            from psycopg2.extras import RealDictCursor
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erro ao executar query PostgreSQL: {e}")
            return []
    
    def search_exact_entities(self, entities: Dict[str, Any], excluded_ids: List[str] = None) -> List[SearchResult]:
        """Busca exata por entidades no PostgreSQL"""
        results = []
        excluded_tuple = tuple(excluded_ids) if excluded_ids else ('',)
        
        try:
            # Busca por pedidos
            if 'pedido' in entities:
                for pedido in entities['pedido']:
                    pattern = f'%{pedido}%'
                    rows = self.execute_query(self.queries['exact_pedido'], (pattern, excluded_tuple, 10))
                    for row in rows:
                        results.append(SearchResult(
                            chunk_id=row['chunk_id'],
                            content_text=row['content_text'],
                            similarity=1.0,
                            entity=row['entity'],
                            nivel_lgpd=row['nivel_lgpd'],
                            metadata={
                                'attributes': row['attributes'],
                                'periodo': row['periodo'],
                                'source_file': row['source_file'],
                                'match_type': 'exact_pedido'
                            }
                        ))
            
            # Busca por regiões
            if 'regiao' in entities:
                patterns = [f'%{region}%' for region in entities['regiao']]
                rows = self.execute_query(self.queries['exact_region'], (patterns, excluded_tuple, 15))
                for row in rows:
                    results.append(SearchResult(
                        chunk_id=row['chunk_id'],
                        content_text=row['content_text'],
                        similarity=0.95,
                        entity=row['entity'],
                        nivel_lgpd=row['nivel_lgpd'],
                        metadata={
                            'attributes': row['attributes'],
                            'periodo': row['periodo'],
                            'source_file': row['source_file'],
                            'match_type': 'exact_region'
                        }
                    ))
        
        except Exception as e:
            logger.error(f"Erro na busca exata PostgreSQL: {e}")
        
        return results
    
    def search_vector_similarity(self, embedding: List[float], similarity_threshold: float = 0.7,
                                max_results: int = 10, excluded_ids: List[str] = None) -> List[SearchResult]:
        """Busca por similaridade vetorial no PostgreSQL"""
        results = []
        excluded_tuple = tuple(excluded_ids) if excluded_ids else ('',)
        
        try:
            rows = self.execute_query(
                self.queries['vector_similarity'],
                (embedding, embedding, similarity_threshold, excluded_tuple, embedding, max_results)
            )
            
            for row in rows:
                results.append(SearchResult(
                    chunk_id=row['chunk_id'],
                    content_text=row['content_text'],
                    similarity=float(row['similarity']) if row['similarity'] else 0.0,
                    entity=row['entity'],
                    nivel_lgpd=row['nivel_lgpd'],
                    metadata={
                        'attributes': row['attributes'],
                        'periodo': row['periodo'],
                        'source_file': row['source_file'],
                        'match_type': 'vector_similarity'
                    }
                ))
        
        except Exception as e:
            logger.error(f"Erro na busca vetorial PostgreSQL: {e}")
        
        return results
    
    def get_chunks_summary(self) -> Dict[str, Any]:
        """Retorna estatísticas dos chunks no PostgreSQL"""
        try:
            rows = self.execute_query(self.queries['chunks_summary'])
            return rows[0] if rows else {}
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas PostgreSQL: {e}")
            return {}
    
    def insert_chunk(self, chunk_data: Dict[str, Any]) -> bool:
        """Insere chunk no PostgreSQL com campos LGPD"""
        try:
            import json
            import psycopg2.extras
            from datetime import datetime, timedelta
            
            # Calcula retention_until se não fornecido
            retention_until = chunk_data.get('retention_until')
            if not retention_until and chunk_data.get('data_origem'):
                # Importa helper para calcular retenção
                from security.lgpd_audit import map_entity_to_category
                from security.lgpd_audit import LGPDAuditLogger
                
                audit_logger = LGPDAuditLogger(self.connection)
                data_category = map_entity_to_category(chunk_data.get('entity', 'PEDIDO_VENDA'))
                retention_until = audit_logger.calculate_retention_date(
                    data_category,
                    chunk_data['data_origem']
                )
            
            query = """
                INSERT INTO chunks 
                (chunk_id, content_text, encrypted_content, entity, attributes, periodo, 
                 nivel_lgpd, hash_sha256, source_file, chunk_size, embedding_model, embedding,
                 retention_until, data_origem, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO NOTHING
            """
            
            # Converte dicionários para JSON se necessário
            attributes = chunk_data.get('attributes', {})
            if isinstance(attributes, dict):
                attributes = json.dumps(attributes)
            
            # Converte embedding para lista se necessário
            embedding = chunk_data.get('embedding')
            if embedding is not None:
                import numpy as np
                if isinstance(embedding, np.ndarray):
                    embedding = embedding.astype(float).tolist()
                elif not isinstance(embedding, list):
                    embedding = list(float(x) for x in embedding)
            
            params = (
                chunk_data['chunk_id'], 
                chunk_data['content_text'], 
                chunk_data.get('encrypted_content'),
                chunk_data['entity'], 
                attributes, 
                chunk_data.get('periodo'),
                chunk_data['nivel_lgpd'], 
                chunk_data['hash_sha256'], 
                chunk_data['source_file'],
                chunk_data['chunk_size'], 
                chunk_data.get('embedding_model'), 
                embedding,
                retention_until,
                chunk_data.get('data_origem'),
                chunk_data.get('is_active', True)
            )
            
            # Executa usando cursor específico para tratar arrays
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            cursor.close()
            self.connection.commit()
            return True
        
        except Exception as e:
            logger.error(f"Erro ao inserir chunk PostgreSQL: {e}")
            if self.connection:
                self.connection.rollback()
            return False

class OracleAdapter(DatabaseAdapter):
    """Adaptador para Oracle Database 11g com estratégia híbrida"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection = None
        self.cursor = None
        self._setup_oracle_queries()
        logger.info("OracleAdapter inicializado para Oracle 11g")
    
    def _setup_oracle_queries(self):
        """Define queries específicas do Oracle com estratégia híbrida"""
        self.queries = {
            # Busca estruturada direta (rápida)
            'exact_pedido': """
                SELECT NUMERO_PEDIDO, NOME_CLIENTE, VALOR_ITEM_LIQUIDO,
                       VALOR_ITEM_BRUTO, DESCRICAO_REGIAO, DATA_VENDA,
                       'ESTRUTURADA' AS TIPO_REGISTRO
                FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA 
                WHERE NUMERO_PEDIDO = :pedido
            """,
            
            'exact_cliente': """
                SELECT NUMERO_PEDIDO, NOME_CLIENTE, VALOR_ITEM_LIQUIDO,
                       VALOR_ITEM_BRUTO, DESCRICAO_REGIAO, DATA_VENDA
                FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA 
                WHERE UPPER(NOME_CLIENTE) LIKE UPPER(:cliente_pattern)
                AND ROWNUM <= 20
                ORDER BY DATA_VENDA DESC
            """,
            
            'exact_regiao': """
                SELECT * FROM (
                    SELECT NUMERO_PEDIDO, NOME_CLIENTE, VALOR_ITEM_LIQUIDO,
                           DESCRICAO_REGIAO, DESCRICAO_REGIONAL, DATA_VENDA
                    FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA 
                    WHERE (UPPER(DESCRICAO_REGIAO) LIKE UPPER(:regiao_pattern)
                           OR UPPER(DESCRICAO_REGIONAL) LIKE UPPER(:regiao_pattern))
                    ORDER BY 
                        CASE WHEN UPPER(DESCRICAO_REGIAO) = UPPER(:regiao_exact) THEN 1 ELSE 2 END,
                        DATA_VENDA DESC
                )
                WHERE ROWNUM <= 10
            """,
            
            'exact_valor_range': """
                SELECT NUMERO_PEDIDO, NOME_CLIENTE, VALOR_ITEM_LIQUIDO,
                       DESCRICAO_REGIAO, DATA_VENDA
                FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA 
                WHERE VALOR_ITEM_LIQUIDO BETWEEN :valor_min AND :valor_max
                AND ROWNUM <= 20
                ORDER BY VALOR_ITEM_LIQUIDO DESC
            """,
            
            # Dados textuais para embeddings
            'textual_data': """
                SELECT REGISTRO_ID, TEXTO_COMPLETO, NIVEL_LGPD,
                       DATA_VENDA, VALOR_ITEM_LIQUIDO, NOME_CLIENTE
                FROM INDUSTRIAL.VW_RAG_VENDAS_TEXTUAL
                WHERE DATA_VENDA >= :data_inicio
                AND ROWNUM <= :max_rows
                ORDER BY DATA_VENDA DESC
            """,
            
            # Resumos agregados para análises
            'resumos_periodo': """
                SELECT REGISTRO_ID, TEXTO_RESUMO, PERIODO,
                       FATURAMENTO_LIQUIDO, TOTAL_PEDIDOS
                FROM INDUSTRIAL.VW_RAG_RESUMOS_AGREGADOS
                WHERE PERIODO >= :periodo_inicio
                ORDER BY PERIODO DESC
            """,
            
            # Estatísticas gerais
            'vendas_summary': """
                SELECT COUNT(*) as total_pedidos,
                       COUNT(DISTINCT NOME_CLIENTE) as clientes_unicos,
                       SUM(VALOR_ITEM_LIQUIDO) as faturamento_total,
                       AVG(VALOR_ITEM_LIQUIDO) as ticket_medio,
                       MIN(DATA_VENDA) as data_inicio,
                       MAX(DATA_VENDA) as data_fim
                FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA
            """,
            
            # Top clientes
            'top_clientes': """
                SELECT NOME_CLIENTE, COUNT(*) as pedidos,
                       SUM(VALOR_ITEM_LIQUIDO) as faturamento_total
                FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA 
                WHERE DATA_VENDA >= :data_inicio
                GROUP BY NOME_CLIENTE
                ORDER BY SUM(VALOR_ITEM_LIQUIDO) DESC
                FETCH FIRST 10 ROWS ONLY
            """,
            
            # Maior valor por período
            'maior_valor_periodo': """
                SELECT * FROM (
                    SELECT NUMERO_PEDIDO, NOME_CLIENTE, VALOR_ITEM_LIQUIDO,
                           VALOR_ITEM_BRUTO, DESCRICAO_REGIAO, DATA_VENDA
                    FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA 
                    WHERE EXTRACT(MONTH FROM DATA_VENDA) = :mes
                    AND EXTRACT(YEAR FROM DATA_VENDA) = :ano
                    ORDER BY VALOR_ITEM_LIQUIDO DESC
                )
                WHERE ROWNUM <= 1
            """,
            
            # Menor valor por período
            'menor_valor_periodo': """
                SELECT * FROM (
                    SELECT NUMERO_PEDIDO, NOME_CLIENTE, VALOR_ITEM_LIQUIDO,
                           VALOR_ITEM_BRUTO, DESCRICAO_REGIAO, DATA_VENDA
                    FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA 
                    WHERE EXTRACT(MONTH FROM DATA_VENDA) = :mes
                    AND EXTRACT(YEAR FROM DATA_VENDA) = :ano
                    ORDER BY VALOR_ITEM_LIQUIDO ASC
                )
                WHERE ROWNUM <= 1
            """,
            
            # Pedidos por período
            'pedidos_periodo': """
                SELECT NUMERO_PEDIDO, NOME_CLIENTE, VALOR_ITEM_LIQUIDO,
                       VALOR_ITEM_BRUTO, DESCRICAO_REGIAO, DATA_VENDA
                FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA 
                WHERE EXTRACT(MONTH FROM DATA_VENDA) = :mes
                AND EXTRACT(YEAR FROM DATA_VENDA) = :ano
                ORDER BY DATA_VENDA DESC
            """,
            
            # Contas a Pagar - Dados textuais
            'cp_textual_data': """
                SELECT REGISTRO_ID, TEXTO_COMPLETO, NIVEL_LGPD,
                       DATA_VENCIMENTO, VALOR_TITULO, VALOR_SALDO,
                       NOME_FORNECEDOR, CNPJ_FORNECEDOR, TITULO,
                       DATA_EMISSAO, DESCRICAO_GRUPO, DESCRICAO_SUBGRUPO,
                       DESCRICAO_BANCO
                FROM INDUSTRIAL.VW_RAG_CONTAS_PAGAR_TEXTUAL
                WHERE DATA_VENCIMENTO >= :data_inicio
                AND ROWNUM <= :max_rows
                ORDER BY DATA_VENCIMENTO DESC
            """,
            
            # Contas a Pagar - Resumos agregados
            'cp_resumos_agregados': """
                SELECT REGISTRO_ID, TEXTO_RESUMO, PERIODO,
                       EMPRESA, VALOR_TOTAL, SALDO_TOTAL,
                       VALOR_MEDIO, TOTAL_TITULOS, TITULOS_PAGOS,
                       TITULOS_VENCIDOS
                FROM INDUSTRIAL.VW_RAG_CP_RESUMOS_AGREGADOS
                WHERE PERIODO >= :periodo_inicio
                ORDER BY PERIODO DESC
            """,
            
            # Contas a Receber - Dados textuais
            'cr_textual_data': """
                SELECT REGISTRO_ID, TEXTO_COMPLETO, NIVEL_LGPD,
                       DATA_VENCIMENTO, VALOR_DUPLICATA AS VALOR_TITULO,
                       SALDO, NOME_CLIENTE, CNPJ_CLIENTE,
                       NOME_REPRESENTANTE, FATURA, ORDEM,
                       DATA_EMISSAO, SITUACAO_DUPLICATA, OPERACAO,
                       DESCRICAO_BANCO
                FROM INDUSTRIAL.VW_RAG_CONTAS_RECEBER_TEXTUAL
                WHERE DATA_VENCIMENTO >= :data_inicio
                AND ROWNUM <= :max_rows
                ORDER BY DATA_VENCIMENTO DESC
            """,
            
            # Contas a Receber - Resumos agregados
            'cr_resumos_agregados': """
                SELECT REGISTRO_ID, TEXTO_RESUMO, PERIODO,
                       EMPRESA, VALOR_TOTAL, SALDO_TOTAL,
                       VALOR_MEDIO, TOTAL_DUPLICATAS, DUPLICATAS_RECEBIDAS,
                       DUPLICATAS_VENCIDAS
                FROM INDUSTRIAL.VW_RAG_CR_RESUMOS_AGREGADOS
                WHERE PERIODO >= :periodo_inicio
                ORDER BY PERIODO DESC
            """
        }
    
    def connect(self) -> bool:
        """Conecta ao Oracle 11g"""
        try:
            import cx_Oracle
            
            # Configura client Oracle se necessário
            # cx_Oracle.init_oracle_client(lib_dir="/path/to/oracle/client")
            
            # Cria DSN para conexão
            if self.config.additional_params and 'service_name' in self.config.additional_params:
                dsn = cx_Oracle.makedsn(
                    self.config.host, 
                    self.config.port, 
                    service_name=self.config.additional_params['service_name']
                )
            else:
                # Fallback para SID
                dsn = cx_Oracle.makedsn(
                    self.config.host, 
                    self.config.port, 
                    sid=self.config.database
                )
            
            # Conecta ao Oracle
            self.connection = cx_Oracle.connect(
                user=self.config.user,
                password=self.config.password,
                dsn=dsn,
                encoding="UTF-8"
            )
            
            # Configura cursor
            self.cursor = self.connection.cursor()
            
            # Testa conexão
            self.cursor.execute("SELECT 1 FROM DUAL")
            self.cursor.fetchone()
            
            logger.info("Conectado ao Oracle 11g com sucesso")
            logger.info(f"Host: {self.config.host}:{self.config.port}")
            logger.info(f"Database: {self.config.database}")
            
            return True
            
        except ImportError:
            logger.error("Módulo cx_Oracle não encontrado. Instale com: pip install cx-Oracle")
            return False
        except Exception as e:
            logger.error(f"Erro ao conectar ao Oracle: {e}")
            return False
    
    def disconnect(self) -> None:
        """Desconecta do Oracle"""
        try:
            if self.cursor:
                self.cursor.close()
                self.cursor = None
            
            if self.connection:
                self.connection.close()
                self.connection = None
            
            logger.info("Desconectado do Oracle")
        except Exception as e:
            logger.error(f"Erro ao desconectar do Oracle: {e}")
    
    def execute_query(self, query: str, params: Dict = None) -> List[Dict[str, Any]]:
        """Executa query no Oracle"""
        try:
            if not self.connection or not self.cursor:
                logger.error("Conexão Oracle não estabelecida")
                return []
            
            # Executa query com parâmetros nomeados
            self.cursor.execute(query, params or {})
            
            # Obtém nomes das colunas
            columns = [desc[0].lower() for desc in self.cursor.description]
            
            # Converte resultados para lista de dicionários
            rows = self.cursor.fetchall()
            results = []
            
            for row in rows:
                row_dict = {}
                for i, value in enumerate(row):
                    # Converte tipos Oracle para Python
                    if hasattr(value, 'read'):
                        # CLOB/BLOB
                        value = value.read()
                    elif str(type(value)) == "<class 'cx_Oracle.LOB'>":
                        value = value.read()
                    
                    row_dict[columns[i]] = value
                
                results.append(row_dict)
            
            return results
            
        except Exception as e:
            logger.error(f"Erro ao executar query Oracle: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            return []
    
    def search_exact_entities(self, entities: Dict[str, Any], excluded_ids: List[str] = None) -> List[SearchResult]:
        """Busca exata por entidades usando queries Oracle diretas"""
        results = []
        
        try:
            # Busca por pedidos
            if 'pedido' in entities:
                for pedido in entities['pedido']:
                    rows = self.execute_query(
                        self.queries['exact_pedido'], 
                        {'pedido': str(pedido)}
                    )
                    
                    for row in rows:
                        # Cria texto descritivo
                        content_text = (
                            f"Pedido {row['numero_pedido']}, "
                            f"Cliente: {row['nome_cliente']}, "
                            f"Valor: R$ {row['valor_item_liquido']:.2f}, "
                            f"Região: {row['descricao_regiao']}, "
                            f"Data: {row['data_venda']}"
                        )
                        
                        results.append(SearchResult(
                            chunk_id=f"oracle_pedido_{row['numero_pedido']}",
                            content_text=content_text,
                            similarity=1.0,  # Exact match
                            entity='PEDIDO_VENDA',
                            nivel_lgpd='MEDIO',
                            metadata={
                                'numero_pedido': row['numero_pedido'],
                                'nome_cliente': row['nome_cliente'],
                                'valor_liquido': float(row['valor_item_liquido']) if row['valor_item_liquido'] else 0,
                                'valor_bruto': float(row['valor_item_bruto']) if row['valor_item_bruto'] else 0,
                                'regiao': row['descricao_regiao'],
                                'data_venda': str(row['data_venda']),
                                'source': 'oracle_estruturada',
                                'match_type': 'exact_pedido'
                            }
                        ))
            
            # Busca por clientes
            if 'cliente' in entities:
                for cliente in entities['cliente']:
                    rows = self.execute_query(
                        self.queries['exact_cliente'],
                        {'cliente_pattern': f'%{cliente}%'}
                    )
                    
                    for row in rows:
                        content_text = (
                            f"Cliente {row['nome_cliente']}, "
                            f"Pedido {row['numero_pedido']}, "
                            f"Valor: R$ {row['valor_item_liquido']:.2f}, "
                            f"Região: {row['descricao_regiao']}"
                        )
                        
                        results.append(SearchResult(
                            chunk_id=f"oracle_cliente_{row['numero_pedido']}",
                            content_text=content_text,
                            similarity=0.95,
                            entity='CLIENTE',
                            nivel_lgpd='ALTO',
                            metadata={
                                'numero_pedido': row['numero_pedido'],
                                'nome_cliente': row['nome_cliente'],
                                'valor_liquido': float(row['valor_item_liquido']) if row['valor_item_liquido'] else 0,
                                'regiao': row['descricao_regiao'],
                                'data_venda': str(row['data_venda']),
                                'source': 'oracle_estruturada',
                                'match_type': 'exact_cliente'
                            }
                        ))
            
            # Busca por período (mês/ano) - NOVA FUNCIONALIDADE
            if 'mes' in entities and 'ano' in entities:
                mes = entities['mes'][0]  # Número do mês
                ano = int(entities['ano'][0])  # Ano
                
                # Detecta se é maior ou menor valor
                valor_type = entities.get('valor_type', ['maior'])[0]  # Default: maior
                
                if valor_type == 'menor':
                    query_key = 'menor_valor_periodo'
                    logger.info(f"Oracle: Buscando menor valor para {mes:02d}/{ano}")
                    tipo_busca = 'menor'
                else:
                    query_key = 'maior_valor_periodo'
                    logger.info(f"Oracle: Buscando maior valor para {mes:02d}/{ano}")
                    tipo_busca = 'maior'
                
                rows = self.execute_query(
                    self.queries[query_key],
                    {
                        'mes': mes,
                        'ano': ano
                    }
                )
                
                for row in rows:
                    content_text = (
                        f"{tipo_busca.capitalize()} valor em {mes:02d}/{ano}: Pedido {row['numero_pedido']}, "
                        f"Cliente: {row['nome_cliente']}, "
                        f"Valor: R$ {row['valor_item_liquido']:.2f}, "
                        f"Região: {row['descricao_regiao']}, "
                        f"Data: {row['data_venda']}"
                    )
                    
                    results.append(SearchResult(
                        chunk_id=f"oracle_{valor_type}_valor_{row['numero_pedido']}",
                        content_text=content_text,
                        similarity=1.0,  # Score máximo para consulta específica
                        entity=f'PEDIDO_{tipo_busca.upper()}_VALOR',
                        nivel_lgpd='MEDIO',
                        metadata={
                            'numero_pedido': row['numero_pedido'],
                            'nome_cliente': row['nome_cliente'],
                            'valor_liquido': float(row['valor_item_liquido']) if row['valor_item_liquido'] else 0,
                            'valor_bruto': float(row['valor_item_bruto']) if row['valor_item_bruto'] else 0,
                            'regiao': row['descricao_regiao'],
                            'data_venda': str(row['data_venda']),
                            'mes': mes,
                            'ano': ano,
                            'valor_type': valor_type,
                            'source': 'oracle_estruturada',
                            'match_type': f'exact_{valor_type}_valor_periodo'
                        }
                    ))
            
            # Busca por regiões - usa apenas a PRIMEIRA (prioritária)
            elif 'regiao' in entities:
                # A primeira região é sempre a prioritária (devido ao processamento no QueryProcessor)
                regiao_prioritaria = entities['regiao'][0]
                logger.info(f"Oracle: Usando região prioritária: {regiao_prioritaria}")
                rows = self.execute_query(
                    self.queries['exact_regiao'],
                    {
                        'regiao_pattern': f'%{regiao_prioritaria}%',
                        'regiao_exact': regiao_prioritaria.replace('%', '')
                    }
                )
                
                for row in rows:
                        content_text = (
                            f"Região {row['descricao_regiao']} - {row['descricao_regional']}, "
                            f"Pedido {row['numero_pedido']}, "
                            f"Cliente: {row['nome_cliente']}, "
                            f"Valor: R$ {row['valor_item_liquido']:.2f}"
                        )
                        
                        results.append(SearchResult(
                            chunk_id=f"oracle_regiao_{row['numero_pedido']}",
                            content_text=content_text,
                            similarity=0.90,
                            entity='REGIONAL',
                            nivel_lgpd='BAIXO',
                            metadata={
                                'numero_pedido': row['numero_pedido'],
                                'nome_cliente': row['nome_cliente'],
                                'valor_liquido': float(row['valor_item_liquido']) if row['valor_item_liquido'] else 0,
                                'regiao': row['descricao_regiao'],
                                'regional': row['descricao_regional'],
                                'data_venda': str(row['data_venda']),
                                'source': 'oracle_estruturada',
                                'match_type': 'exact_regiao'
                            }
                        ))
        
        except Exception as e:
            logger.error(f"Erro na busca exata Oracle: {e}")
        
        return results
    
    def search_vector_similarity(self, embedding: List[float], similarity_threshold: float = 0.7,
                                max_results: int = 10, excluded_ids: List[str] = None) -> List[SearchResult]:
        """Busca por similaridade usando dados textuais (Oracle 11g não tem vector search nativo)"""
        results = []
        
        try:
            # Para Oracle 11g, vamos buscar dados textuais e deixar o embedding para o PostgreSQL
            # Ou usar uma estratégia híbrida onde buscamos dados no Oracle e processamos embeddings
            from datetime import datetime, timedelta
            
            # Busca dados textuais dos últimos 6 meses
            data_inicio = datetime.now() - timedelta(days=180)
            
            rows = self.execute_query(
                self.queries['textual_data'],
                {
                    'data_inicio': data_inicio,
                    'max_rows': max_results * 2  # Busca mais para filtrar depois
                }
            )
            
            # Para cada resultado, cria um SearchResult
            for i, row in enumerate(rows[:max_results]):
                results.append(SearchResult(
                    chunk_id=f"oracle_textual_{row['registro_id']}",
                    content_text=row['texto_completo'],
                    similarity=0.75 - (i * 0.05),  # Simula similarity decrescente
                    entity='VENDA_TEXTUAL',
                    nivel_lgpd=row['nivel_lgpd'],
                    metadata={
                        'valor_liquido': float(row['valor_item_liquido']) if row['valor_item_liquido'] else 0,
                        'nome_cliente': row['nome_cliente'],
                        'data_venda': str(row['data_venda']),
                        'source': 'oracle_textual',
                        'match_type': 'textual_similarity'
                    }
                ))
        
        except Exception as e:
            logger.error(f"Erro na busca textual Oracle: {e}")
        
        return results
    
    def get_chunks_summary(self) -> Dict[str, Any]:
        """Retorna estatísticas dos dados de vendas Oracle"""
        try:
            # Estatísticas principais
            rows = self.execute_query(self.queries['vendas_summary'])
            
            if rows:
                stats = rows[0]
                return {
                    'total_chunks': int(stats['total_pedidos']) if stats['total_pedidos'] else 0,
                    'unique_entities': int(stats['clientes_unicos']) if stats['clientes_unicos'] else 0,
                    'faturamento_total': float(stats['faturamento_total']) if stats['faturamento_total'] else 0.0,
                    'ticket_medio': float(stats['ticket_medio']) if stats['ticket_medio'] else 0.0,
                    'data_inicio': str(stats['data_inicio']) if stats['data_inicio'] else '',
                    'data_fim': str(stats['data_fim']) if stats['data_fim'] else '',
                    'source': 'oracle',
                    'lgpd_alto': 0,  # Oracle não classifica por LGPD ainda
                    'lgpd_medio': int(stats['total_pedidos']) if stats['total_pedidos'] else 0,
                    'lgpd_baixo': 0
                }
            else:
                return {
                    'total_chunks': 0,
                    'unique_entities': 0,
                    'faturamento_total': 0.0,
                    'source': 'oracle',
                    'error': 'Nenhum dado encontrado'
                }
                
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas Oracle: {e}")
            return {
                'total_chunks': 0,
                'unique_entities': 0,
                'source': 'oracle',
                'error': str(e)
            }
    
    def insert_chunk(self, chunk_data: Dict[str, Any]) -> bool:
        """Oracle é read-only para o RAG - dados vêm das views"""
        logger.warning("Oracle é read-only. Dados vêm das views, não inserção manual.")
        return False
    
    def search_aggregated_data(self, periodo_inicio: str = None) -> List[SearchResult]:
        """Busca dados agregados para análises"""
        results = []
        
        try:
            if not periodo_inicio:
                from datetime import datetime, timedelta
                periodo_inicio = (datetime.now() - timedelta(days=365)).strftime('%Y-%m')
            
            rows = self.execute_query(
                self.queries['resumos_periodo'],
                {'periodo_inicio': periodo_inicio}
            )
            
            for row in rows:
                results.append(SearchResult(
                    chunk_id=f"oracle_agregado_{row['registro_id']}",
                    content_text=row['texto_resumo'],
                    similarity=0.85,
                    entity='RESUMO_AGREGADO',
                    nivel_lgpd='BAIXO',
                    metadata={
                        'periodo': row['periodo'],
                        'faturamento_liquido': float(row['faturamento_liquido']) if row['faturamento_liquido'] else 0,
                        'total_pedidos': int(row['total_pedidos']) if row['total_pedidos'] else 0,
                        'source': 'oracle_agregado',
                        'match_type': 'aggregated_summary'
                    }
                ))
        
        except Exception as e:
            logger.error(f"Erro na busca agregada Oracle: {e}")
        
        return results
    
    def test_connection(self) -> Dict[str, Any]:
        """Testa conexão e views Oracle"""
        test_results = {
            'connection': False,
            'views_available': {},
            'sample_data': {},
            'errors': []
        }
        
        try:
            # Testa conexão básica
            if self.connect():
                test_results['connection'] = True
                logger.info("Conexão Oracle OK")
                
                # Testa cada view
                views_to_test = {
                    'VW_RAG_VENDAS_ESTRUTURADA': 'SELECT COUNT(*) as count FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA WHERE ROWNUM <= 1',
                    'VW_RAG_VENDAS_TEXTUAL': 'SELECT COUNT(*) as count FROM INDUSTRIAL.VW_RAG_VENDAS_TEXTUAL WHERE ROWNUM <= 1',
                    'VW_RAG_RESUMOS_AGREGADOS': 'SELECT COUNT(*) as count FROM INDUSTRIAL.VW_RAG_RESUMOS_AGREGADOS WHERE ROWNUM <= 1'
                }
                
                for view_name, test_query in views_to_test.items():
                    try:
                        result = self.execute_query(test_query)
                        test_results['views_available'][view_name] = True
                        logger.info(f"View {view_name}: OK")
                    except Exception as e:
                        test_results['views_available'][view_name] = False
                        test_results['errors'].append(f"View {view_name}: {str(e)}")
                        logger.warning(f"View {view_name}: Erro - {e}")
                
                # Busca dados de exemplo
                try:
                    sample = self.execute_query(
                        "SELECT NUMERO_PEDIDO, NOME_CLIENTE, VALOR_ITEM_LIQUIDO FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA WHERE ROWNUM <= 3"
                    )
                    test_results['sample_data'] = sample
                except Exception as e:
                    test_results['errors'].append(f"Sample data: {str(e)}")
                
            else:
                test_results['errors'].append("Falha na conexão Oracle")
                
        except Exception as e:
            test_results['errors'].append(f"Erro geral: {str(e)}")
        
        finally:
            self.disconnect()
        
        return test_results

class DatabaseAdapterFactory:
    """Factory para criar adaptadores de banco de dados"""
    
    @staticmethod
    def create_adapter(config: DatabaseConfig) -> DatabaseAdapter:
        """Cria o adaptador apropriado baseado na configuração"""
        
        if config.db_type.lower() == 'postgresql':
            return PostgreSQLAdapter(config)
        elif config.db_type.lower() == 'oracle':
            return OracleAdapter(config)
        else:
            raise ValueError(f"Tipo de banco não suportado: {config.db_type}")
    
    @staticmethod
    def from_dict(config_dict: Dict[str, Any]) -> DatabaseAdapter:
        """Cria adaptador a partir de dicionário de configuração"""
        
        db_config = DatabaseConfig(
            host=config_dict['host'],
            port=config_dict['port'],
            database=config_dict['database'],
            user=config_dict['user'],
            password=config_dict['password'],
            db_type=config_dict.get('db_type', 'postgresql'),
            schema=config_dict.get('schema'),
            additional_params=config_dict.get('additional_params')
        )
        
        return DatabaseAdapterFactory.create_adapter(db_config)

# Exemplo de uso:
# config = DatabaseConfig(
#     host='localhost', port=5433, database='cativa_rag_db',
#     user='cativa_user', password='pass', db_type='postgresql'
# )
# adapter = DatabaseAdapterFactory.create_adapter(config)
# adapter.connect()
# results = adapter.search_exact_entities({'pedido': ['843562']})