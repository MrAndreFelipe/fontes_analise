# src/security/lgpd_audit.py
"""
Módulo de Auditoria LGPD
Implementa logs de acesso (Art. 37) e exclusões (Art. 18)
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import psycopg2

logger = logging.getLogger(__name__)


class LGPDAuditLogger:
    """
    Gerencia logs de auditoria para conformidade LGPD
    """
    
    def __init__(self, postgres_conn=None):
        """
        Initialize LGPD audit logger
        
        Args:
            postgres_conn: Conexão PostgreSQL ativa
        """
        self.conn = postgres_conn
    
    def log_access(self,
                   user_id: str,
                   user_name: Optional[str],
                   user_clearance: str,
                   query_text: str,
                   query_classification: str,
                   route_used: str,
                   chunks_accessed: Optional[List[str]] = None,
                   success: bool = True,
                   denied_reason: Optional[str] = None,
                   processing_time_ms: Optional[int] = None) -> bool:
        """
        Registra acesso a dados (LGPD Art. 37 - Auditoria)
        
        Args:
            user_id: ID do usuário (WhatsApp phone)
            user_name: Nome do usuário
            user_clearance: Nível de clearance (ALTO/MÉDIO/BAIXO)
            query_text: Texto da consulta
            query_classification: Classificação LGPD da query
            route_used: Rota usada (text_to_sql, embeddings, cache, error)
            chunks_accessed: Lista de chunk_ids acessados
            success: Se o acesso foi bem-sucedido
            denied_reason: Motivo se acesso foi negado
            processing_time_ms: Tempo de processamento em ms
        
        Returns:
            True se log foi registrado com sucesso
        """
        if not self.conn:
            logger.warning("PostgreSQL connection not available, skipping access log")
            return False
        
        try:
            cursor = self.conn.cursor()
            
            query = """
                INSERT INTO access_log 
                (user_id, user_name, user_clearance, query_text, query_classification,
                 route_used, chunks_accessed, success, denied_reason, processing_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            params = (
                user_id,
                user_name,
                user_clearance,
                query_text[:1000],  # Limita tamanho
                query_classification,
                route_used,
                chunks_accessed if chunks_accessed else [],
                success,
                denied_reason,
                processing_time_ms
            )
            
            cursor.execute(query, params)
            self.conn.commit()
            cursor.close()
            
            logger.debug(f"Access logged: user={user_id}, clearance={user_clearance}, "
                        f"classification={query_classification}, success={success}")
            return True
        
        except Exception as e:
            logger.error(f"Error logging access: {e}")
            if self.conn:
                self.conn.rollback()
            return False
    
    def log_deletion(self,
                    deletion_type: str,
                    affected_table: str,
                    records_deleted: int,
                    deletion_reason: str,
                    criteria_used: Optional[Dict] = None,
                    requested_by: Optional[str] = None,
                    approved_by: Optional[str] = None,
                    evidence_backup_location: Optional[str] = None) -> bool:
        """
        Registra exclusão de dados (LGPD Art. 18)
        
        Args:
            deletion_type: Tipo (retention_cleanup, erasure_request, manual, anonymization)
            affected_table: Tabela afetada
            records_deleted: Quantidade de registros deletados
            deletion_reason: Motivo da exclusão
            criteria_used: Critérios usados para deleção (JSON)
            requested_by: Quem solicitou
            approved_by: Quem aprovou
            evidence_backup_location: Local do backup (evidência)
        
        Returns:
            True se log foi registrado com sucesso
        """
        if not self.conn:
            logger.warning("PostgreSQL connection not available, skipping deletion log")
            return False
        
        try:
            import json
            cursor = self.conn.cursor()
            
            query = """
                INSERT INTO lgpd_deletion_log
                (deletion_type, affected_table, records_deleted, deletion_reason,
                 criteria_used, requested_by, approved_by, evidence_backup_location)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            
            criteria_json = json.dumps(criteria_used) if criteria_used else None
            
            params = (
                deletion_type,
                affected_table,
                records_deleted,
                deletion_reason,
                criteria_json,
                requested_by or 'system',
                approved_by,
                evidence_backup_location
            )
            
            cursor.execute(query, params)
            log_id = cursor.fetchone()[0]
            self.conn.commit()
            cursor.close()
            
            logger.info(f"Deletion logged (ID={log_id}): type={deletion_type}, "
                       f"table={affected_table}, records={records_deleted}")
            return True
        
        except Exception as e:
            logger.error(f"Error logging deletion: {e}")
            if self.conn:
                self.conn.rollback()
            return False
    
    def get_retention_days(self, data_category: str) -> int:
        """
        Consulta política de retenção para uma categoria
        
        Args:
            data_category: Categoria (vendas, contas_pagar, etc)
        
        Returns:
            Número de dias de retenção (default 1825 = 5 anos)
        """
        if not self.conn:
            logger.warning("PostgreSQL connection not available, using default retention")
            return 1825
        
        try:
            cursor = self.conn.cursor()
            
            query = """
                SELECT retention_days 
                FROM lgpd_retention_policy
                WHERE data_category = %s AND active = TRUE
            """
            
            cursor.execute(query, (data_category,))
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return result[0]
            else:
                logger.warning(f"No retention policy found for {data_category}, using default 1825 days")
                return 1825
        
        except Exception as e:
            logger.error(f"Error getting retention policy: {e}")
            return 1825
    
    def calculate_retention_date(self, data_category: str, data_origem: datetime) -> datetime:
        """
        Calcula data de expiração baseada na política de retenção
        
        Args:
            data_category: Categoria dos dados
            data_origem: Data de origem do registro
        
        Returns:
            Data de expiração (retention_until)
        """
        retention_days = self.get_retention_days(data_category)
        return data_origem + timedelta(days=retention_days)
    
    def cleanup_old_access_logs(self, days_to_keep: int = 180) -> int:
        """
        Remove logs de acesso antigos (padrão: 6 meses conforme LGPD Art. 37)
        
        Args:
            days_to_keep: Quantos dias manter
        
        Returns:
            Número de registros deletados
        """
        if not self.conn:
            return 0
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            cursor = self.conn.cursor()
            
            cursor.execute("""
                DELETE FROM access_log
                WHERE accessed_at < %s
                RETURNING id
            """, (cutoff_date,))
            
            deleted_ids = cursor.fetchall()
            deleted_count = len(deleted_ids)
            
            self.conn.commit()
            cursor.close()
            
            # Log da limpeza
            if deleted_count > 0:
                self.log_deletion(
                    deletion_type='retention_cleanup',
                    affected_table='access_log',
                    records_deleted=deleted_count,
                    deletion_reason=f'Limpeza automática - logs > {days_to_keep} dias',
                    criteria_used={'cutoff_date': cutoff_date.isoformat()},
                    requested_by='system'
                )
            
            logger.info(f"Cleaned up {deleted_count} old access logs (older than {days_to_keep} days)")
            return deleted_count
        
        except Exception as e:
            logger.error(f"Error cleaning up access logs: {e}")
            if self.conn:
                self.conn.rollback()
            return 0


# Helper functions for standalone use

def create_audit_logger(postgres_conn) -> LGPDAuditLogger:
    """Factory function to create audit logger"""
    return LGPDAuditLogger(postgres_conn)


def map_entity_to_category(entity: str) -> str:
    """
    Mapeia entity para data_category
    
    Args:
        entity: Nome da entidade (PEDIDO_VENDA, CONTA_PAGAR, etc)
    
    Returns:
        Categoria de dados para policy lookup
    """
    entity_map = {
        'PEDIDO_VENDA': 'vendas',
        'VENDA': 'vendas',
        'CONTA_PAGAR': 'contas_pagar',
        'CP_RESUMO_AGREGADO': 'contas_pagar',
        'CONTA_RECEBER': 'contas_receber',
        'CR_RESUMO_AGREGADO': 'contas_receber',
        'DUPLICATA': 'contas_receber'
    }
    
    return entity_map.get(entity, 'vendas')  # Default: vendas
