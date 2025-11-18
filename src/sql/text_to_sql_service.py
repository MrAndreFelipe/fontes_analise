# src/sql/text_to_sql_service.py
"""
Serviço de Text-to-SQL para Oracle 11g
- Gera SQL via LLM
- Valida e aplica LIMIT
- Executa no Oracle (read-only)
"""

import os
import logging
from typing import Dict, Any, Optional, List

from core.database_adapter import DatabaseConfig, DatabaseAdapterFactory, OracleAdapter
from core.connection_pool import DatabaseConnectionPool
from .schema_introspector import SchemaIntrospector
from .sql_validator import SQLValidator
from .text_to_sql_generator import TextToSQLGenerator

logger = logging.getLogger(__name__)

class TextToSQLService:
    def __init__(self, 
                 oracle_adapter: Optional[OracleAdapter] = None, 
                 oracle_config: Optional[Dict[str, Any]] = None,
                 oracle_pool: Optional[DatabaseConnectionPool] = None):
        """
        Initialize Text-to-SQL Service
        
        Args:
            oracle_adapter: Legacy OracleAdapter (deprecated)
            oracle_config: Oracle configuration dict
            oracle_pool: DatabaseConnectionPool instance (PRODUCTION-READY)
        """
        self.introspector = SchemaIntrospector()
        self.validator = SQLValidator()
        self.generator = TextToSQLGenerator()
        
        # Connection pool for production (preferred)
        self.oracle_pool = oracle_pool
        
        # Legacy adapter support (fallback)
        self.oracle_adapter = oracle_adapter or self._build_adapter_from_config(oracle_config)

    def _build_adapter_from_config(self, config: Optional[Dict[str, Any]]) -> Optional[OracleAdapter]:
        # Tenta do param, depois variáveis de ambiente
        cfg = config or self._read_env_oracle_config()
        if not cfg:
            logger.warning("Configuração Oracle não fornecida. Apenas geração de SQL estará disponível.")
            return None
        try:
            # Lógica igual ao database_adapter.py
            # Se tiver service_name, passa nos additional_params
            # Senão, usa SID no campo database
            service_name = cfg.get('service_name')
            sid = cfg.get('sid')
            
            logger.info(f"Oracle config: host={cfg.get('host')}, port={cfg.get('port')}, user={cfg.get('user')}")
            logger.info(f"Oracle config: service_name={service_name}, sid={sid}")
            
            if service_name:
                # Usa SERVICE_NAME
                logger.info(f"Usando ORACLE SERVICE_NAME: {service_name}")
                db_cfg = DatabaseConfig(
                    host=cfg.get('host', 'localhost'),
                    port=int(cfg.get('port', 1521)),
                    database='',  # Não usado quando há service_name
                    user=cfg.get('user', ''),
                    password=cfg.get('password', ''),
                    db_type='oracle',
                    additional_params={'service_name': service_name}
                )
            elif sid:
                # Usa SID (fallback)
                logger.info(f"Usando ORACLE SID: {sid}")
                db_cfg = DatabaseConfig(
                    host=cfg.get('host', 'localhost'),
                    port=int(cfg.get('port', 1521)),
                    database=sid,  # SID vai no campo database
                    user=cfg.get('user', ''),
                    password=cfg.get('password', ''),
                    db_type='oracle',
                    additional_params=None  # Sem additional_params, usa SID
                )
            else:
                logger.error("Nem ORACLE_SERVICE_NAME nem ORACLE_SID foram fornecidos")
                return None
            
            return DatabaseAdapterFactory.create_adapter(db_cfg)  # type: ignore
        except Exception as e:
            logger.error(f"Falha ao construir adaptador Oracle: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _read_env_oracle_config(self) -> Optional[Dict[str, Any]]:
        # Lê de variáveis de ambiente
        host = os.getenv('ORACLE_HOST')
        user = os.getenv('ORACLE_USER')
        password = os.getenv('ORACLE_PASSWORD')
        service_name = os.getenv('ORACLE_SERVICE_NAME')
        sid = os.getenv('ORACLE_SID')
        port = os.getenv('ORACLE_PORT', '1521')
        if not (host and user and password and (service_name or sid)):
            return None
        return {
            'host': host,
            'port': int(port),
            'user': user,
            'password': password,
            'service_name': service_name,
            'sid': sid,
        }

    def generate_and_execute(self, question: str, constraints: Optional[str] = None, conversation_history: Optional[List[Dict]] = None, limit: int = 10) -> Dict[str, Any]:
        """
        Fluxo completo: Pergunta -> SQL -> Validação -> Execução -> Resultado
        
        Args:
            question: Pergunta do usuario
            constraints: Restricoes adicionais
            conversation_history: Historico recente da conversa (lista de {user, bot})
            limit: Limite de resultados
        """
        schema_text = self.introspector.get_schema_for_llm()
        sql = self.generator.generate_sql(question, schema_text, constraints, conversation_history)
        
        # If LLM detected out-of-scope question
        if sql == 'OUT_OF_SCOPE':
            logger.warning(f"Question out of scope: '{question[:50]}...'")
            return {
                'success': False,
                'error': 'OUT_OF_SCOPE',
                'generated_sql': None,
                'need_fallback': False,  # Don't fallback, send error message
                'fallback_reason': 'out_of_scope'
            }
        
        # If LLM is unavailable, return None to force embedding fallback
        if sql is None:
            logger.warning("SQL generation returned None (LLM unavailable), forcing embedding fallback")
            return {
                'success': False,
                'error': 'LLM unavailable for Text-to-SQL',
                'generated_sql': None,
                'need_fallback': True,
                'fallback_reason': 'llm_unavailable'
            }
        
        # Log SQL generated by LLM (before validation)
        logger.info(f"SQL generated by LLM: {sql}")

        ok, safe_sql_or_msg = self.validator.sanitize_and_limit(sql, limit=limit)
        if not ok:
            logger.warning(f"SQL validation failed: {safe_sql_or_msg}")
            logger.warning(f"Invalid SQL was: {sql}")
            return {
                'success': False,
                'error': f'SQL inválido: {safe_sql_or_msg}',
                'generated_sql': sql,
                'need_fallback': True,
                'fallback_reason': 'invalid_sql'
            }

        final_sql = safe_sql_or_msg
        rows: List[Dict[str, Any]] = []
        error: Optional[str] = None

        # Check if Oracle is available (pool or adapter)
        if not self.oracle_pool and not self.oracle_adapter:
            logger.warning("Sem adaptador Oracle configurado. Retornando apenas SQL gerado.")
            return {
                'success': True,
                'generated_sql': final_sql,
                'rows': rows,
                'columns': [],
                'executed': False,
                'need_fallback': False
            }

        # Use connection pool if available (PRODUCTION)
        if self.oracle_pool and self.oracle_pool.oracle_pool:
            return self._execute_with_pool(final_sql)
        
        # Fallback to legacy adapter
        return self._execute_with_adapter(final_sql)
    
    def _execute_with_pool(self, sql: str) -> Dict[str, Any]:
        """Execute SQL using connection pool (PRODUCTION-READY)"""
        conn = None
        try:
            conn = self.oracle_pool.get_oracle_connection()
            cursor = conn.cursor()
            cursor.execute(sql)
            
            # Fetch results
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = []
            for row in cursor.fetchall():
                rows.append(dict(zip(columns, row)))
            
            cursor.close()
            
            return {
                'success': True,
                'generated_sql': sql,
                'rows': rows,
                'columns': columns,
                'executed': True,
                'need_fallback': len(rows) == 0,
                'fallback_reason': 'no_rows' if len(rows) == 0 else None
            }
        
        except Exception as e:
            logger.error(f"Erro ao executar SQL (pool): {e}")
            logger.error(f"Failed SQL was: {sql}")
            return {
                'success': False,
                'generated_sql': sql,
                'error': str(e),
                'rows': [],
                'need_fallback': True,
                'fallback_reason': 'execution_error'
            }
        
        finally:
            if conn:
                self.oracle_pool.return_oracle_connection(conn)
    
    def _execute_with_adapter(self, sql: str) -> Dict[str, Any]:
        """Execute SQL using legacy adapter (DEPRECATED)"""
        try:
            if not self.oracle_adapter.connection:
                self.oracle_adapter.connect()
            rows = self.oracle_adapter.execute_query(sql)
            columns = list(rows[0].keys()) if rows else []
            return {
                'success': True,
                'generated_sql': sql,
                'rows': rows,
                'columns': columns,
                'executed': True,
                'need_fallback': len(rows) == 0,
                'fallback_reason': 'no_rows' if len(rows) == 0 else None
            }
        except Exception as e:
            logger.error(f"Erro ao executar SQL (adapter): {e}")
            logger.error(f"Failed SQL was: {sql}")
            return {
                'success': False,
                'generated_sql': sql,
                'error': str(e),
                'rows': [],
                'need_fallback': True,
                'fallback_reason': 'execution_error'
            }
        finally:
            try:
                if self.oracle_adapter:
                    self.oracle_adapter.disconnect()
            except Exception:
                pass
