# src/monitoring/metrics.py
"""
Sistema de metricas simples para observabilidade
Coleta metricas de latencia, sucesso/falha, distribuicao LGPD e custos

Abordagem pragmatica: armazena metricas em JSON local (sem dependencias pesadas)
"""

import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from threading import Lock
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class QueryMetric:
    """Metrica de uma query processada"""
    timestamp: str
    query_text: str
    lgpd_level: str
    route_used: str
    success: bool
    latency_ms: float
    user_id: Optional[str] = None
    error: Optional[str] = None
    tokens_used: Optional[int] = None


class MetricsCollector:
    """
    Coletor de metricas simples e eficiente
    Thread-safe, persiste em JSON
    """
    
    def __init__(self, metrics_file: Optional[Path] = None):
        """
        Inicializa coletor de metricas
        
        Args:
            metrics_file: Arquivo para persistir metricas (padrao: logs/metrics.json)
        """
        if metrics_file is None:
            metrics_file = Path(__file__).parent.parent.parent / 'logs' / 'metrics.json'
        
        self.metrics_file = metrics_file
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Metricas em memoria (agregadas)
        self.metrics = {
            'queries_total': 0,
            'queries_success': 0,
            'queries_failed': 0,
            'latency_sum_ms': 0.0,
            'routes': {},  # {route_name: count}
            'lgpd_levels': {},  # {level: count}
            'errors': {},  # {error_type: count}
            'tokens_total': 0,
            'last_reset': datetime.now().isoformat()
        }
        
        # Lock para thread-safety
        self._lock = Lock()
        
        # Carrega metricas existentes
        self._load_metrics()
        
        logger.info(f"MetricsCollector initialized (file: {self.metrics_file})")
    
    def record_query(self, 
                    query_text: str,
                    lgpd_level: str,
                    route_used: str,
                    success: bool,
                    latency_ms: float,
                    user_id: Optional[str] = None,
                    error: Optional[str] = None,
                    tokens_used: Optional[int] = None):
        """
        Registra metrica de uma query
        
        Args:
            query_text: Texto da query (truncado para logs)
            lgpd_level: Nivel LGPD (BAIXO/MEDIO/ALTO)
            route_used: Rota usada (text_to_sql/embeddings)
            success: Se query foi bem-sucedida
            latency_ms: Latencia em milissegundos
            user_id: ID do usuario (opcional)
            error: Mensagem de erro (se houver)
            tokens_used: Tokens usados (OpenAI)
        """
        with self._lock:
            # Atualiza contadores
            self.metrics['queries_total'] += 1
            
            if success:
                self.metrics['queries_success'] += 1
            else:
                self.metrics['queries_failed'] += 1
            
            # Latencia
            self.metrics['latency_sum_ms'] += latency_ms
            
            # Rotas
            if route_used not in self.metrics['routes']:
                self.metrics['routes'][route_used] = 0
            self.metrics['routes'][route_used] += 1
            
            # LGPD
            if lgpd_level not in self.metrics['lgpd_levels']:
                self.metrics['lgpd_levels'][lgpd_level] = 0
            self.metrics['lgpd_levels'][lgpd_level] += 1
            
            # Erros
            if error:
                error_type = error.split(':')[0] if ':' in error else error[:50]
                if error_type not in self.metrics['errors']:
                    self.metrics['errors'][error_type] = 0
                self.metrics['errors'][error_type] += 1
            
            # Tokens
            if tokens_used:
                self.metrics['tokens_total'] += tokens_used
        
        # Persiste periodicamente (a cada 10 queries)
        if self.metrics['queries_total'] % 10 == 0:
            self._persist_metrics()
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Retorna resumo das metricas
        
        Returns:
            Dict com metricas agregadas
        """
        with self._lock:
            total = self.metrics['queries_total']
            
            if total == 0:
                return {'message': 'Nenhuma query processada ainda'}
            
            avg_latency = self.metrics['latency_sum_ms'] / total
            success_rate = (self.metrics['queries_success'] / total) * 100
            
            return {
                'total_queries': total,
                'success_rate': f"{success_rate:.1f}%",
                'average_latency_ms': f"{avg_latency:.2f}",
                'routes': self.metrics['routes'],
                'lgpd_distribution': self.metrics['lgpd_levels'],
                'total_tokens_used': self.metrics['tokens_total'],
                'error_count': self.metrics['queries_failed'],
                'last_reset': self.metrics['last_reset']
            }
    
    def reset_metrics(self):
        """Reseta metricas (util para testes ou novo periodo)"""
        with self._lock:
            self.metrics = {
                'queries_total': 0,
                'queries_success': 0,
                'queries_failed': 0,
                'latency_sum_ms': 0.0,
                'routes': {},
                'lgpd_levels': {},
                'errors': {},
                'tokens_total': 0,
                'last_reset': datetime.now().isoformat()
            }
            self._persist_metrics()
        
        logger.info("Metrics reset")
    
    def _load_metrics(self):
        """Carrega metricas do arquivo"""
        try:
            if self.metrics_file.exists():
                with open(self.metrics_file, 'r') as f:
                    loaded = json.load(f)
                    self.metrics.update(loaded)
                logger.info(f"Loaded {self.metrics['queries_total']} metrics from file")
        except Exception as e:
            logger.warning(f"Could not load metrics file: {e}")
    
    def _persist_metrics(self):
        """Persiste metricas em arquivo"""
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(self.metrics, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist metrics: {e}")


# Instancia global (singleton)
_metrics_collector = None


def get_metrics_collector() -> MetricsCollector:
    """Retorna instancia global do coletor de metricas"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


# Decorador para medir latencia automaticamente
def track_latency(route_name: str):
    """
    Decorador para rastrear latencia de funcoes
    
    Usage:
        @track_latency('text_to_sql')
        def generate_sql(query):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                latency_ms = (time.time() - start_time) * 1000
                
                # Log latencia
                logger.debug(f"{route_name} completed in {latency_ms:.2f}ms")
                
                return result
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                logger.error(f"{route_name} failed after {latency_ms:.2f}ms: {e}")
                raise
        return wrapper
    return decorator


# Utilitario para exibir metricas
def print_metrics_summary():
    """Imprime resumo das metricas (util para debugging)"""
    collector = get_metrics_collector()
    summary = collector.get_summary()
    
    print("\n" + "=" * 60)
    print("METRICAS DO SISTEMA RAG")
    print("=" * 60)
    
    if 'message' in summary:
        print(summary['message'])
    else:
        print(f"\nTotal de Queries: {summary['total_queries']}")
        print(f"Taxa de Sucesso: {summary['success_rate']}")
        print(f"Latencia Media: {summary['average_latency_ms']}ms")
        print(f"Tokens Usados: {summary['total_tokens_used']}")
        
        print(f"\nDistribuicao por Rota:")
        for route, count in summary['routes'].items():
            print(f"  - {route}: {count}")
        
        print(f"\nDistribuicao LGPD:")
        for level, count in summary['lgpd_distribution'].items():
            print(f"  - {level}: {count}")
        
        print(f"\nErros: {summary['error_count']}")
        print(f"Ultimo Reset: {summary['last_reset']}")
    
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # Teste basico
    print("Testing MetricsCollector...")
    
    collector = MetricsCollector()
    
    # Simula algumas queries
    collector.record_query(
        query_text="Quais vendas hoje?",
        lgpd_level="BAIXO",
        route_used="text_to_sql",
        success=True,
        latency_ms=250.5,
        tokens_used=100
    )
    
    collector.record_query(
        query_text="Nome do cliente X",
        lgpd_level="ALTO",
        route_used="text_to_sql",
        success=True,
        latency_ms=180.2,
        tokens_used=150
    )
    
    collector.record_query(
        query_text="Pedidos vencidos",
        lgpd_level="MEDIO",
        route_used="embeddings",
        success=False,
        latency_ms=450.8,
        error="Database connection timeout"
    )
    
    # Exibe resumo
    print_metrics_summary()
