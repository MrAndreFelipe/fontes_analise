# src/core/retry_handler.py
"""
Retry Handler - Sistema RAG Cativa Têxtil
Implementa retry logic com exponential backoff para produção

Benefícios:
- Tolera falhas transitórias (rede, APIs, banco de dados)
- Exponential backoff evita sobrecarregar serviços
- Configurável por tipo de operação
- Logging detalhado de tentativas
"""

import time
import logging
from functools import wraps
from typing import Callable, Any, Tuple, Type

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    retry_on_result: Callable[[Any], bool] = None
):
    """
    Decorator para retry com exponential backoff
    
    Args:
        max_retries: Número máximo de tentativas (além da primeira)
        initial_delay: Delay inicial em segundos
        backoff_factor: Fator de multiplicação do delay (ex: 2.0 = dobra a cada tentativa)
        exceptions: Tupla de exceções que devem causar retry
        retry_on_result: Função opcional que determina se resultado deve causar retry
    
    Example:
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def call_api():
            return requests.get("https://api.example.com")
    
    Delays seguem padrão exponencial:
        - Tentativa 1: imediata
        - Tentativa 2: após 1s
        - Tentativa 3: após 2s (1 * 2.0)
        - Tentativa 4: após 4s (2 * 2.0)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    
                    # Verifica se resultado deve causar retry
                    if retry_on_result and retry_on_result(result):
                        if attempt < max_retries:
                            logger.warning(
                                f"{func.__name__} returned retry-worthy result "
                                f"(attempt {attempt + 1}/{max_retries + 1}). "
                                f"Retrying in {delay}s..."
                            )
                            time.sleep(delay)
                            delay *= backoff_factor
                            continue
                    
                    # Sucesso
                    if attempt > 0:
                        logger.info(f"{func.__name__} succeeded after {attempt + 1} attempts")
                    
                    return result
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
            
            # Todas as tentativas falharam
            raise last_exception
        
        return wrapper
    return decorator


def retry_with_custom_strategy(
    should_retry: Callable[[Exception, int], bool],
    get_delay: Callable[[int], float],
    max_retries: int = 3
):
    """
    Decorator para retry com estratégia customizada
    
    Args:
        should_retry: Função (exception, attempt) -> bool que decide se deve tentar novamente
        get_delay: Função (attempt) -> float que retorna delay para próxima tentativa
        max_retries: Número máximo de tentativas
    
    Example:
        def my_retry_logic(exception, attempt):
            if isinstance(exception, TimeoutError):
                return attempt < 5  # Mais tentativas para timeout
            return attempt < 2
        
        def my_delay(attempt):
            return attempt * 1.5  # Delay linear
        
        @retry_with_custom_strategy(my_retry_logic, my_delay, max_retries=5)
        def risky_operation():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            last_exception = None
            
            while attempt <= max_retries:
                try:
                    result = func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(f"{func.__name__} succeeded after {attempt + 1} attempts")
                    
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    if attempt < max_retries and should_retry(e, attempt):
                        delay = get_delay(attempt)
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}): {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        attempt += 1
                    else:
                        logger.error(f"{func.__name__} failed: {e}")
                        break
            
            raise last_exception
        
        return wrapper
    return decorator


# Estratégias pré-definidas para casos comuns

def retry_database(max_retries: int = 3):
    """
    Retry para operações de banco de dados
    
    Trata:
    - Timeouts
    - Connection errors
    - Deadlocks
    """
    import psycopg2
    try:
        import cx_Oracle
        db_exceptions = (
            psycopg2.OperationalError,
            psycopg2.InterfaceError,
            cx_Oracle.DatabaseError,
            ConnectionError,
            TimeoutError
        )
    except ImportError:
        db_exceptions = (
            psycopg2.OperationalError,
            psycopg2.InterfaceError,
            ConnectionError,
            TimeoutError
        )
    
    return retry_with_backoff(
        max_retries=max_retries,
        initial_delay=0.5,
        backoff_factor=2.0,
        exceptions=db_exceptions
    )


def retry_api_call(max_retries: int = 3):
    """
    Retry para chamadas de API externa
    
    Trata:
    - Rate limits (429)
    - Server errors (5xx)
    - Network errors
    """
    try:
        import requests
        api_exceptions = (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            ConnectionError,
            TimeoutError
        )
    except ImportError:
        api_exceptions = (ConnectionError, TimeoutError)
    
    def should_retry_http(result):
        """Verifica se código HTTP indica retry"""
        if hasattr(result, 'status_code'):
            # Retry em 429 (rate limit) e 5xx (server errors)
            return result.status_code == 429 or result.status_code >= 500
        return False
    
    return retry_with_backoff(
        max_retries=max_retries,
        initial_delay=1.0,
        backoff_factor=2.0,
        exceptions=api_exceptions,
        retry_on_result=should_retry_http
    )


def retry_openai(max_retries: int = 3):
    """
    Retry para chamadas OpenAI API
    
    Trata:
    - Rate limits
    - API errors
    - Timeouts
    """
    try:
        from openai import (
            APIError,
            APIConnectionError,
            RateLimitError,
            APITimeoutError
        )
        openai_exceptions = (
            APIError,
            APIConnectionError,
            RateLimitError,
            APITimeoutError,
            TimeoutError,
            ConnectionError
        )
    except ImportError:
        openai_exceptions = (TimeoutError, ConnectionError, Exception)
    
    return retry_with_backoff(
        max_retries=max_retries,
        initial_delay=2.0,  # OpenAI precisa de delay maior
        backoff_factor=3.0,  # Backoff mais agressivo
        exceptions=openai_exceptions
    )


# Testes básicos
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== Retry Handler Tests ===\n")
    
    # Teste 1: Sucesso após 2 tentativas
    print("Teste 1: Sucesso após 2 tentativas")
    attempt_counter = [0]
    
    @retry_with_backoff(max_retries=3, initial_delay=0.1)
    def flaky_function():
        attempt_counter[0] += 1
        if attempt_counter[0] < 2:
            raise ConnectionError(f"Tentativa {attempt_counter[0]} falhou")
        return "Sucesso!"
    
    try:
        result = flaky_function()
        print(f"[OK] Resultado: {result}\n")
    except Exception as e:
        print(f"[FAILED] Falhou: {e}\n")
    
    # Teste 2: Falha após todas as tentativas
    print("Teste 2: Falha após todas as tentativas")
    
    @retry_with_backoff(max_retries=2, initial_delay=0.1)
    def always_fails():
        raise ValueError("Sempre falha")
    
    try:
        always_fails()
        print("[FAILED] Não deveria ter chegado aqui\n")
    except ValueError as e:
        print(f"[OK] Falhou como esperado: {e}\n")
    
    # Teste 3: Retry database
    print("Teste 3: Retry para banco de dados")
    
    @retry_database(max_retries=2)
    def db_operation():
        return "Conectado ao banco"
    
    try:
        result = db_operation()
        print(f"[OK] Resultado: {result}\n")
    except Exception as e:
        print(f"[FAILED] Falhou: {e}\n")
    
    print("SUCCESS: Testes concluídos")
