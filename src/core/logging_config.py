# src/core/logging_config.py
"""
Logging Estruturado - Sistema RAG Cativa Têxtil
Configuração de logging para produção

Benefícios:
- Logs persistentes em arquivo (não perdidos ao reiniciar)
- Rotação automática (evita disco cheio)
- Formato JSON estruturado (fácil análise/parsing)
- Logs separados por nível (info.log, error.log)
- Context tracking (user_id, request_id, query)
"""

import logging
import logging.handlers
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class JSONFormatter(logging.Formatter):
    """
    Formata logs em JSON estruturado para produção
    
    Benefícios do formato JSON:
    - Fácil parsing por ferramentas de análise
    - Busca estruturada (ex: grep por user_id)
    - Integração com sistemas de monitoramento
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Formata log record como JSON"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Adiciona informações contextuais se existirem
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        
        if hasattr(record, 'query'):
            log_data['query'] = record.query[:500]  # Limita tamanho
        
        if hasattr(record, 'phone'):
            log_data['phone'] = record.phone
        
        if hasattr(record, 'processing_time'):
            log_data['processing_time'] = record.processing_time
        
        # Adiciona exception info se houver
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info)
            }
        
        return json.dumps(log_data, ensure_ascii=False)


class HumanReadableFormatter(logging.Formatter):
    """
    Formata logs de forma legível para console
    """
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def setup_production_logging(
    log_dir: Optional[Path] = None,
    app_name: str = 'rag_bot',
    log_level: str = 'INFO',
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    console_output: bool = True
):
    """
    Configura logging para produção
    
    Args:
        log_dir: Diretório para logs (None = pasta 'logs' na raiz do projeto)
        app_name: Nome da aplicação (usado no nome dos arquivos)
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: Tamanho máximo de cada arquivo de log (em bytes)
        backup_count: Número de backups a manter
        console_output: Se deve mostrar logs no console também
    
    Estrutura de arquivos criada:
        logs/
        ├── rag_bot_info.log      (INFO+)
        ├── rag_bot_info.log.1    (rotacionado)
        ├── rag_bot_error.log     (ERROR+)
        └── rag_bot_error.log.1   (rotacionado)
    
    Example:
        from core.logging_config import setup_production_logging
        
        setup_production_logging()
        logger = logging.getLogger(__name__)
        logger.info("Sistema iniciado")
    """
    # Determina diretório de logs
    if log_dir is None:
        # Usa pasta 'logs' na raiz do projeto
        project_root = Path(__file__).parent.parent.parent
        log_dir = project_root / 'logs'
    
    # Cria diretório se não existir
    log_dir.mkdir(exist_ok=True, parents=True)
    
    # Remove handlers existentes
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # ===== Handler 1: INFO+ para arquivo (rotacionado, JSON) =====
    info_file = log_dir / f'{app_name}_info.log'
    info_handler = logging.handlers.RotatingFileHandler(
        filename=info_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(JSONFormatter())
    
    # ===== Handler 2: ERROR+ para arquivo separado (rotacionado, JSON) =====
    error_file = log_dir / f'{app_name}_error.log'
    error_handler = logging.handlers.RotatingFileHandler(
        filename=error_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    
    # ===== Handler 3: Console (stdout) - formato humano =====
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(HumanReadableFormatter())
        root_logger.addHandler(console_handler)
    
    # Adiciona file handlers
    root_logger.addHandler(info_handler)
    root_logger.addHandler(error_handler)
    
    # Log de inicialização
    logging.info(f"Production logging initialized")
    logging.info(f"Log directory: {log_dir}")
    logging.info(f"Log level: {log_level}")
    logging.info(f"Max file size: {max_bytes / (1024 * 1024):.1f} MB")
    logging.info(f"Backup count: {backup_count}")


def get_logger_with_context(name: str, **context):
    """
    Cria logger com contexto adicional
    
    Args:
        name: Nome do logger
        **context: Contexto adicional (user_id, request_id, etc.)
    
    Returns:
        Logger com contexto
    
    Example:
        logger = get_logger_with_context(
            __name__,
            user_id="5511999999999",
            request_id="abc123"
        )
        logger.info("Processing query")
        # Log terá user_id e request_id automaticamente
    """
    logger = logging.getLogger(name)
    
    # Wrapper para adicionar contexto automaticamente
    class ContextLoggerAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            # Adiciona contexto ao log record
            extra = kwargs.get('extra', {})
            extra.update(self.extra)
            kwargs['extra'] = extra
            return msg, kwargs
    
    return ContextLoggerAdapter(logger, context)


# Helpers para logging estruturado

def log_query_processing(logger, query: str, user_id: str, processing_time: float, success: bool):
    """
    Log estruturado para processamento de query
    
    Args:
        logger: Logger instance
        query: Query processada
        user_id: ID do usuário
        processing_time: Tempo de processamento em segundos
        success: Se query foi bem-sucedida
    """
    logger.info(
        f"Query processed: success={success}",
        extra={
            'query': query,
            'user_id': user_id,
            'processing_time': processing_time,
            'success': success
        }
    )


def log_api_call(logger, api_name: str, endpoint: str, status_code: int, response_time: float):
    """
    Log estruturado para chamadas de API
    
    Args:
        logger: Logger instance
        api_name: Nome da API (ex: 'openai', 'evolution')
        endpoint: Endpoint chamado
        status_code: HTTP status code
        response_time: Tempo de resposta em segundos
    """
    logger.info(
        f"API call: {api_name} {endpoint}",
        extra={
            'api_name': api_name,
            'endpoint': endpoint,
            'status_code': status_code,
            'response_time': response_time
        }
    )


def log_error_with_context(logger, error: Exception, context: dict):
    """
    Log estruturado para erros com contexto
    
    Args:
        logger: Logger instance
        error: Exception ocorrida
        context: Contexto adicional do erro
    """
    logger.error(
        f"Error: {type(error).__name__}: {str(error)}",
        exc_info=True,
        extra=context
    )


# Teste básico
if __name__ == "__main__":
    print("=== Teste de Logging Estruturado ===\n")
    
    # Setup
    setup_production_logging(
        app_name='test_logging',
        log_level='INFO'
    )
    
    # Testa logs normais
    logger = logging.getLogger(__name__)
    logger.info("Teste de log INFO")
    logger.warning("Teste de log WARNING")
    logger.error("Teste de log ERROR")
    
    # Testa log com contexto
    context_logger = get_logger_with_context(
        __name__,
        user_id="5511999999999",
        request_id="req_123"
    )
    context_logger.info("Log com contexto automático")
    
    # Testa helper de query processing
    log_query_processing(
        logger,
        query="Quais vendas de hoje?",
        user_id="5511987654321",
        processing_time=1.23,
        success=True
    )
    
    # Testa log de erro
    try:
        raise ValueError("Erro de teste")
    except Exception as e:
        log_error_with_context(
            logger,
            e,
            {'query': 'teste', 'user_id': '123'}
        )
    
    print("\nSUCCESS: Logs gerados em logs/test_logging_info.log e logs/test_logging_error.log")
    print("Verifique os arquivos para ver formato JSON")
