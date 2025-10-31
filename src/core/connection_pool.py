# src/core/connection_pool.py
"""
Connection Pool Manager - Sistema RAG Cativa Têxtil
Gerencia pools de conexão para PostgreSQL e Oracle para produção

Benefícios:
- Reutilização de conexões (performance)
- Limite de conexões simultâneas (evita esgotar recursos do banco)
- Gerenciamento automático de ciclo de vida
- Thread-safe
"""

import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager
from .retry_handler import retry_database

logger = logging.getLogger(__name__)


class DatabaseConnectionPool:
    """
    Gerenciador de pools de conexão para produção
    
    Suporta:
    - PostgreSQL (via psycopg2.pool)
    - Oracle (via cx_Oracle.SessionPool)
    """
    
    def __init__(self, 
                 postgres_config: Optional[Dict[str, Any]] = None,
                 oracle_config: Optional[Dict[str, Any]] = None,
                 min_connections: int = 2,
                 max_connections: int = 10):
        """
        Inicializa pools de conexão
        
        Args:
            postgres_config: Configuração PostgreSQL (host, port, database, user, password)
            oracle_config: Configuração Oracle (host, port, user, password, sid/service_name)
            min_connections: Número mínimo de conexões no pool
            max_connections: Número máximo de conexões no pool
        """
        self.postgres_pool = None
        self.oracle_pool = None
        self.min_connections = min_connections
        self.max_connections = max_connections
        
        # Inicializa PostgreSQL pool
        if postgres_config:
            self._init_postgres_pool(postgres_config)
        
        # Inicializa Oracle pool
        if oracle_config:
            self._init_oracle_pool(oracle_config)
    
    def _init_postgres_pool(self, config: Dict[str, Any]):
        """Inicializa pool de conexões PostgreSQL"""
        try:
            from psycopg2 import pool
            
            self.postgres_pool = pool.ThreadedConnectionPool(
                minconn=self.min_connections,
                maxconn=self.max_connections,
                host=config['host'],
                port=config['port'],
                database=config['database'],
                user=config['user'],
                password=config['password']
            )
            logger.info(f"PostgreSQL connection pool initialized (min={self.min_connections}, max={self.max_connections})")
        
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL pool: {e}")
            self.postgres_pool = None
    
    def _init_oracle_pool(self, config: Dict[str, Any]):
        """Inicializa pool de conexões Oracle"""
        try:
            import cx_Oracle
            
            # Determina DSN (service_name ou sid)
            service_name = config.get('service_name')
            sid = config.get('sid')
            
            if service_name:
                dsn = cx_Oracle.makedsn(
                    config['host'], 
                    config['port'], 
                    service_name=service_name
                )
                logger.info(f"Oracle DSN with SERVICE_NAME: {service_name}")
            elif sid:
                dsn = cx_Oracle.makedsn(
                    config['host'], 
                    config['port'], 
                    sid=sid
                )
                logger.info(f"Oracle DSN with SID: {sid}")
            else:
                logger.error("Oracle config must have 'service_name' or 'sid'")
                self.oracle_pool = None
                return
            
            self.oracle_pool = cx_Oracle.SessionPool(
                user=config['user'],
                password=config['password'],
                dsn=dsn,
                min=self.min_connections,
                max=self.max_connections,
                increment=1,
                threaded=True,
                getmode=cx_Oracle.SPOOL_ATTRVAL_NOWAIT
            )
            logger.info(f"Oracle connection pool initialized (min={self.min_connections}, max={self.max_connections})")
        
        except Exception as e:
            logger.error(f"Failed to initialize Oracle pool: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.oracle_pool = None
    
    # ===== PostgreSQL Methods =====
    
    @retry_database(max_retries=3)
    def get_postgres_connection(self):
        """
        Obtém conexão do pool PostgreSQL (COM RETRY)
        
        Returns:
            psycopg2.connection
        
        Raises:
            RuntimeError: Se pool não está inicializado
        """
        if not self.postgres_pool:
            raise RuntimeError("PostgreSQL pool not initialized")
        
        try:
            conn = self.postgres_pool.getconn()
            logger.debug("PostgreSQL connection acquired from pool")
            return conn
        except Exception as e:
            logger.error(f"Failed to get PostgreSQL connection: {e}")
            raise
    
    def return_postgres_connection(self, conn):
        """
        Retorna conexão ao pool PostgreSQL
        
        Args:
            conn: Conexão a ser retornada
        """
        if not self.postgres_pool:
            logger.warning("PostgreSQL pool not initialized, closing connection directly")
            if conn:
                conn.close()
            return
        
        try:
            self.postgres_pool.putconn(conn)
            logger.debug("PostgreSQL connection returned to pool")
        except Exception as e:
            logger.error(f"Failed to return PostgreSQL connection: {e}")
    
    @contextmanager
    def postgres_connection(self):
        """
        Context manager para conexões PostgreSQL
        
        Usage:
            with pool.postgres_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
        """
        conn = None
        try:
            conn = self.get_postgres_connection()
            yield conn
        finally:
            if conn:
                self.return_postgres_connection(conn)
    
    # ===== Oracle Methods =====
    
    @retry_database(max_retries=3)
    def get_oracle_connection(self):
        """
        Obtém conexão do pool Oracle (COM RETRY)
        
        Returns:
            cx_Oracle.connection
        
        Raises:
            RuntimeError: Se pool não está inicializado
        """
        if not self.oracle_pool:
            raise RuntimeError("Oracle pool not initialized")
        
        try:
            conn = self.oracle_pool.acquire()
            logger.debug("Oracle connection acquired from pool")
            return conn
        except Exception as e:
            logger.error(f"Failed to get Oracle connection: {e}")
            raise
    
    def return_oracle_connection(self, conn):
        """
        Retorna conexão ao pool Oracle
        
        Args:
            conn: Conexão a ser retornada
        """
        if not self.oracle_pool:
            logger.warning("Oracle pool not initialized, closing connection directly")
            if conn:
                conn.close()
            return
        
        try:
            self.oracle_pool.release(conn)
            logger.debug("Oracle connection returned to pool")
        except Exception as e:
            logger.error(f"Failed to return Oracle connection: {e}")
    
    @contextmanager
    def oracle_connection(self):
        """
        Context manager para conexões Oracle
        
        Usage:
            with pool.oracle_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM DUAL")
        """
        conn = None
        try:
            conn = self.get_oracle_connection()
            yield conn
        finally:
            if conn:
                self.return_oracle_connection(conn)
    
    # ===== Cleanup =====
    
    def close_all(self):
        """Fecha todos os pools de conexão"""
        logger.info("Closing all connection pools...")
        
        # Fecha PostgreSQL pool
        if self.postgres_pool:
            try:
                self.postgres_pool.closeall()
                logger.info("PostgreSQL pool closed")
            except Exception as e:
                logger.error(f"Error closing PostgreSQL pool: {e}")
        
        # Fecha Oracle pool
        if self.oracle_pool:
            try:
                self.oracle_pool.close()
                logger.info("Oracle pool closed")
            except Exception as e:
                logger.error(f"Error closing Oracle pool: {e}")
    
    def __del__(self):
        """Destrutor - garante que pools sejam fechados"""
        try:
            self.close_all()
        except:
            pass


# Testes básicos
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== Connection Pool Test ===\n")
    
    # Teste com configurações mock
    postgres_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'test_db',
        'user': 'test_user',
        'password': 'test_pass'
    }
    
    oracle_config = {
        'host': 'localhost',
        'port': 1521,
        'user': 'test_user',
        'password': 'test_pass',
        'sid': 'ORCL'
    }
    
    # Nota: Este teste não funcionará sem bancos reais configurados
    # É apenas para demonstrar a API
    
    try:
        pool = DatabaseConnectionPool(
            postgres_config=postgres_config,
            oracle_config=oracle_config,
            min_connections=1,
            max_connections=3
        )
        
        print("[OK] Pool inicializado")
        
        # Testa context manager (não executará sem DB real)
        # with pool.postgres_connection() as conn:
        #     cursor = conn.cursor()
        #     cursor.execute("SELECT 1")
        
        pool.close_all()
        print("[OK] Pool fechado com sucesso")
        
    except Exception as e:
        print(f"[FAILED] Erro (esperado sem DB real): {e}")
