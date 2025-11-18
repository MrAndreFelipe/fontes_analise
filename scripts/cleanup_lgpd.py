# scripts/cleanup_lgpd.py
"""
Script de Limpeza Automática LGPD
Execução: Mensal (1º dia do mês às 04:00)

Realiza:
1. Limpeza de chunks expirados (retention_until < NOW())
2. Limpeza de logs de acesso antigos (> 6 meses)
3. Log de todas as exclusões para conformidade LGPD
"""

import sys
from pathlib import Path

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

# Importações do projeto
from core.config import Config
from core.database_adapter import DatabaseAdapterFactory, DatabaseConfig
from security.lgpd_audit import LGPDAuditLogger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LGPDCleanupService:
    """
    Serviço de limpeza automática conforme políticas LGPD
    """
    
    def __init__(self):
        """Initialize cleanup service"""
        self.postgres_adapter = None
        self.audit_logger = None
        self.stats = {
            'chunks_deleted': 0,
            'access_logs_deleted': 0,
            'errors': []
        }
    
    def connect(self) -> bool:
        """Conecta ao PostgreSQL"""
        try:
            pg = Config.postgres()
            db_config = DatabaseConfig(
                host=pg.host,
                port=pg.port,
                database=pg.database,
                user=pg.user,
                password=pg.password,
                db_type='postgresql'
            )
            
            self.postgres_adapter = DatabaseAdapterFactory.create_adapter(db_config)
            self.postgres_adapter.connect()
            
            self.audit_logger = LGPDAuditLogger(self.postgres_adapter.connection)
            
            logger.info("Connected to PostgreSQL")
            return True
        
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL: {e}")
            return False
    
    def cleanup_expired_chunks(self) -> int:
        """
        Remove chunks expirados baseado em retention_until
        
        Returns:
            Número de chunks deletados
        """
        logger.info("=== Cleaning up expired chunks ===")
        
        try:
            # Busca chunks expirados
            query = """
                SELECT chunk_id, entity, nivel_lgpd, created_at, retention_until
                FROM chunks
                WHERE retention_until < NOW()
                AND is_active = TRUE
            """
            
            expired_chunks = self.postgres_adapter.execute_query(query)
            
            if not expired_chunks:
                logger.info("No expired chunks found")
                return 0
            
            logger.info(f"Found {len(expired_chunks)} expired chunks")
            
            # Soft delete (marca como inativo)
            delete_query = """
                UPDATE chunks
                SET is_active = FALSE,
                    deleted_at = NOW()
                WHERE retention_until < NOW()
                AND is_active = TRUE
                RETURNING chunk_id
            """
            
            deleted = self.postgres_adapter.execute_query(delete_query)
            deleted_count = len(deleted) if deleted else 0
            
            self.postgres_adapter.connection.commit()
            
            # Log LGPD
            if deleted_count > 0:
                self.audit_logger.log_deletion(
                    deletion_type='retention_cleanup',
                    affected_table='chunks',
                    records_deleted=deleted_count,
                    deletion_reason='Limpeza automática - expiração de retenção LGPD',
                    criteria_used={
                        'retention_until': 'less than NOW()',
                        'execution_date': datetime.now().isoformat()
                    },
                    requested_by='system',
                    approved_by='lgpd_retention_policy'
                )
            
            logger.info(f"Soft deleted {deleted_count} expired chunks")
            self.stats['chunks_deleted'] = deleted_count
            
            return deleted_count
        
        except Exception as e:
            logger.error(f"Error cleaning up expired chunks: {e}")
            self.stats['errors'].append(str(e))
            return 0
    
    def cleanup_old_access_logs(self, days_to_keep: int = 180) -> int:
        """
        Remove logs de acesso antigos (padrão: 6 meses conforme LGPD Art. 37)
        
        Args:
            days_to_keep: Dias a manter (default 180 = 6 meses)
        
        Returns:
            Número de logs deletados
        """
        logger.info(f"=== Cleaning up access logs older than {days_to_keep} days ===")
        
        try:
            deleted_count = self.audit_logger.cleanup_old_access_logs(days_to_keep)
            
            logger.info(f"Deleted {deleted_count} old access logs")
            self.stats['access_logs_deleted'] = deleted_count
            
            return deleted_count
        
        except Exception as e:
            logger.error(f"Error cleaning up access logs: {e}")
            self.stats['errors'].append(str(e))
            return 0
    
    def hard_delete_old_soft_deleted(self, days_to_keep: int = 90) -> int:
        """
        Remove permanentemente chunks que foram soft-deleted há mais de N dias
        (Permite recovery window)
        
        Args:
            days_to_keep: Dias de janela de recuperação
        
        Returns:
            Número de chunks permanentemente deletados
        """
        logger.info(f"=== Hard deleting chunks soft-deleted > {days_to_keep} days ago ===")
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            query = """
                DELETE FROM chunks
                WHERE is_active = FALSE
                AND deleted_at < %s
                RETURNING chunk_id
            """
            
            deleted = self.postgres_adapter.execute_query(query, (cutoff_date,))
            deleted_count = len(deleted) if deleted else 0
            
            self.postgres_adapter.connection.commit()
            
            # Log LGPD
            if deleted_count > 0:
                self.audit_logger.log_deletion(
                    deletion_type='manual',
                    affected_table='chunks',
                    records_deleted=deleted_count,
                    deletion_reason=f'Exclusão permanente - soft-deleted > {days_to_keep} dias',
                    criteria_used={
                        'is_active': False,
                        'deleted_at_before': cutoff_date.isoformat()
                    },
                    requested_by='system'
                )
            
            logger.info(f"Permanently deleted {deleted_count} soft-deleted chunks")
            
            return deleted_count
        
        except Exception as e:
            logger.error(f"Error hard deleting chunks: {e}")
            self.stats['errors'].append(str(e))
            return 0
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Retorna estatísticas da limpeza"""
        return {
            'chunks_deleted': self.stats['chunks_deleted'],
            'access_logs_deleted': self.stats['access_logs_deleted'],
            'total_records_cleaned': self.stats['chunks_deleted'] + self.stats['access_logs_deleted'],
            'errors': self.stats['errors'],
            'error_count': len(self.stats['errors'])
        }
    
    def disconnect(self):
        """Desconecta do PostgreSQL"""
        if self.postgres_adapter:
            self.postgres_adapter.disconnect()
            logger.info("Disconnected from PostgreSQL")


def main():
    """
    Execução principal do script
    """
    print("=" * 80)
    print("LGPD CLEANUP SERVICE - Limpeza Automática de Dados")
    print("=" * 80)
    print(f"Execution time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    service = LGPDCleanupService()
    
    try:
        # Conecta
        if not service.connect():
            print("ERROR: Failed to connect to database")
            return 1
        
        print()
        
        # 1. Limpa chunks expirados
        chunks_deleted = service.cleanup_expired_chunks()
        print()
        
        # 2. Limpa logs de acesso antigos (6 meses)
        logs_deleted = service.cleanup_old_access_logs(days_to_keep=180)
        print()
        
        # 3. Remove permanentemente soft-deleted antigos (90 dias de recovery)
        hard_deleted = service.hard_delete_old_soft_deleted(days_to_keep=90)
        print()
        
        # Estatísticas finais
        stats = service.get_stats_summary()
        
        print("=" * 80)
        print("CLEANUP SUMMARY")
        print("=" * 80)
        print(f"Chunks soft-deleted (expired): {stats['chunks_deleted']}")
        print(f"Chunks hard-deleted (old soft-deletes): {hard_deleted}")
        print(f"Access logs deleted: {stats['access_logs_deleted']}")
        print(f"Total records cleaned: {stats['total_records_cleaned'] + hard_deleted}")
        print(f"Errors: {stats['error_count']}")
        
        if stats['errors']:
            print("\nErrors encountered:")
            for error in stats['errors']:
                print(f"  - {error}")
        
        print("=" * 80)
        print("LGPD cleanup completed successfully")
        print("=" * 80)
        
        service.disconnect()
        return 0
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
