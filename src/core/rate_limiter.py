# src/core/rate_limiter.py
"""
Rate Limiter - Sistema RAG Cativa Textil
Token bucket algorithm para controle de rate limiting por usuario

Implementa rate limiting robusto para prevenir abuse de recursos:
- Token bucket algorithm (industry standard)
- Thread-safe
- Configuravel por usuario
- Memoria eficiente
"""

import time
import logging
from collections import defaultdict
from threading import Lock
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter baseado em token bucket algorithm
    
    Token bucket permite burst traffic controlado enquanto mantem
    rate medio. Mais flexivel que simple counter.
    
    Attributes:
        max_tokens: Numero maximo de tokens (requests) permitidos
        refill_rate: Taxa de reabastecimento (tokens por segundo)
        time_window: Janela de tempo em segundos para rate limiting
    """
    
    def __init__(self, max_requests: int = 20, time_window: int = 60):
        """
        Inicializa rate limiter
        
        Args:
            max_requests: Maximo de requests permitidos na janela
            time_window: Janela de tempo em segundos
        
        Example:
            limiter = RateLimiter(max_requests=20, time_window=60)
            # Permite 20 requests por minuto
        """
        self.max_tokens = max_requests
        self.time_window = time_window
        self.refill_rate = max_requests / time_window
        
        # Armazena estado por identificador (user_id)
        # Format: {identifier: (tokens_disponiveis, ultimo_timestamp)}
        self.buckets: Dict[str, Tuple[float, float]] = defaultdict(
            lambda: (self.max_tokens, time.time())
        )
        
        # Lock para thread safety
        self.lock = Lock()
        
        # Metricas
        self.total_requests = 0
        self.blocked_requests = 0
        
        logger.info(
            f"RateLimiter initialized: {max_requests} requests per {time_window}s "
            f"(refill rate: {self.refill_rate:.2f} tokens/s)"
        )
    
    def is_allowed(self, identifier: str) -> bool:
        """
        Verifica se request e permitido para o identificador
        
        Token bucket algorithm:
        1. Calcula tokens a adicionar desde ultimo acesso
        2. Atualiza bucket com novos tokens (max: max_tokens)
        3. Se bucket >= 1.0, consome 1 token e permite
        4. Se bucket < 1.0, nega request
        
        Args:
            identifier: Identificador unico (user_id, phone, IP)
        
        Returns:
            True se request permitido, False se rate limit excedido
        """
        with self.lock:
            self.total_requests += 1
            current_time = time.time()
            
            # Obtem estado atual do bucket
            tokens, last_time = self.buckets[identifier]
            
            # Calcula tokens a adicionar desde ultimo acesso
            time_passed = current_time - last_time
            tokens_to_add = time_passed * self.refill_rate
            
            # Atualiza tokens (max: max_tokens)
            tokens = min(self.max_tokens, tokens + tokens_to_add)
            
            # Verifica se tem tokens disponiveis
            if tokens >= 1.0:
                # Consome 1 token e permite request
                tokens -= 1.0
                self.buckets[identifier] = (tokens, current_time)
                
                logger.debug(
                    f"Request allowed for {identifier} "
                    f"(tokens remaining: {tokens:.2f})"
                )
                return True
            else:
                # Rate limit excedido
                self.buckets[identifier] = (tokens, current_time)
                self.blocked_requests += 1
                
                logger.warning(
                    f"Rate limit exceeded for {identifier} "
                    f"(tokens: {tokens:.2f}, needs: 1.0)"
                )
                return False
    
    def get_retry_after(self, identifier: str) -> int:
        """
        Calcula tempo em segundos ate proximo request permitido
        
        Args:
            identifier: Identificador do usuario
        
        Returns:
            Segundos ate proximo request (0 se ja pode fazer request)
        """
        with self.lock:
            tokens, last_time = self.buckets[identifier]
            current_time = time.time()
            
            # Calcula tokens atuais
            time_passed = current_time - last_time
            tokens_to_add = time_passed * self.refill_rate
            tokens = min(self.max_tokens, tokens + tokens_to_add)
            
            if tokens >= 1.0:
                return 0
            
            # Calcula tempo necessario para ter 1 token
            tokens_needed = 1.0 - tokens
            seconds_needed = tokens_needed / self.refill_rate
            
            return int(seconds_needed) + 1
    
    def reset(self, identifier: str):
        """
        Reseta rate limit para um identificador especifico
        
        Args:
            identifier: Identificador a resetar
        """
        with self.lock:
            if identifier in self.buckets:
                del self.buckets[identifier]
                logger.info(f"Rate limit reset for {identifier}")
    
    def reset_all(self):
        """Reseta rate limit para todos os identificadores"""
        with self.lock:
            self.buckets.clear()
            logger.info("Rate limit reset for all identifiers")
    
    def get_stats(self) -> Dict:
        """
        Retorna estatisticas do rate limiter
        
        Returns:
            Dict com metricas de uso
        """
        with self.lock:
            total = self.total_requests
            blocked = self.blocked_requests
            allowed = total - blocked
            block_rate = (blocked / total * 100) if total > 0 else 0
            
            return {
                'total_requests': total,
                'allowed_requests': allowed,
                'blocked_requests': blocked,
                'block_rate_percent': round(block_rate, 2),
                'active_users': len(self.buckets)
            }
    
    def cleanup_old_entries(self, max_age_seconds: int = 3600):
        """
        Remove entradas antigas para economizar memoria
        
        Args:
            max_age_seconds: Idade maxima de entradas em segundos
        """
        with self.lock:
            current_time = time.time()
            old_count = len(self.buckets)
            
            # Remove entradas mais antigas que max_age
            self.buckets = defaultdict(
                lambda: (self.max_tokens, time.time()),
                {
                    k: v for k, v in self.buckets.items()
                    if current_time - v[1] < max_age_seconds
                }
            )
            
            removed = old_count - len(self.buckets)
            if removed > 0:
                logger.info(f"Cleaned up {removed} old rate limit entries")


# Testes basicos
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== Rate Limiter Tests ===\n")
    
    # Test 1: Basic rate limiting
    print("Test 1: Basic rate limiting (5 requests per 10 seconds)")
    limiter = RateLimiter(max_requests=5, time_window=10)
    
    user_id = "test_user"
    
    # Deve permitir 5 requests
    for i in range(5):
        allowed = limiter.is_allowed(user_id)
        print(f"  Request {i+1}: {'Allowed' if allowed else 'Blocked'}")
    
    # 6a request deve ser bloqueada
    allowed = limiter.is_allowed(user_id)
    print(f"  Request 6: {'Allowed' if allowed else 'Blocked'}")
    
    if not allowed:
        retry_after = limiter.get_retry_after(user_id)
        print(f"  Retry after: {retry_after} seconds")
    
    print()
    
    # Test 2: Statistics
    print("Test 2: Statistics")
    stats = limiter.get_stats()
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Allowed: {stats['allowed_requests']}")
    print(f"  Blocked: {stats['blocked_requests']}")
    print(f"  Block rate: {stats['block_rate_percent']}%")
    print(f"  Active users: {stats['active_users']}")
    print()
    
    # Test 3: Refill over time
    print("Test 3: Token refill (waiting 2 seconds)")
    time.sleep(2)
    allowed = limiter.is_allowed(user_id)
    print(f"  Request after 2s: {'Allowed' if allowed else 'Blocked'}")
    print()
    
    print("All tests completed")
