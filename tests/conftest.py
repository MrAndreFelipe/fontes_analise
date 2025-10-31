# tests/conftest.py
"""
Pytest fixtures compartilhadas
Fornece mocks e configuracoes reutilizaveis para todos os testes
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock
import numpy as np

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


# ============================================
# FIXTURES - CONFIGURACOES
# ============================================

@pytest.fixture
def mock_oracle_config():
    """Configuracao Oracle mock para testes"""
    return {
        'host': 'localhost',
        'port': 1521,
        'user': 'test_user',
        'password': 'test_pass',
        'service_name': 'TESTDB'
    }


@pytest.fixture
def mock_postgres_config():
    """Configuracao PostgreSQL mock para testes"""
    return {
        'host': 'localhost',
        'port': 5432,
        'database': 'test_db',
        'user': 'test_user',
        'password': 'test_pass'
    }


@pytest.fixture
def mock_openai_config():
    """Configuracao OpenAI mock para testes"""
    return {
        'api_key': 'sk-test-key-mock',
        'model': 'gpt-4',
        'embedding_model': 'text-embedding-3-small'
    }


# ============================================
# FIXTURES - USER CONTEXT
# ============================================

@pytest.fixture
def user_context_baixo():
    """User context com clearance BAIXO"""
    return {
        'lgpd_clearance': 'BAIXO',
        'user_id': '5511999999999@s.whatsapp.net',
        'user_name': 'Test User Baixo',
        'department': 'Test',
        'is_admin': False,
        'enabled': True
    }


@pytest.fixture
def user_context_medio():
    """User context com clearance MEDIO"""
    return {
        'lgpd_clearance': 'MEDIO',
        'user_id': '5511888888888@s.whatsapp.net',
        'user_name': 'Test User Medio',
        'department': 'Vendas',
        'is_admin': False,
        'enabled': True
    }


@pytest.fixture
def user_context_alto():
    """User context com clearance ALTO"""
    return {
        'lgpd_clearance': 'ALTO',
        'user_id': '5511777777777@s.whatsapp.net',
        'user_name': 'Test User Alto',
        'department': 'TI',
        'is_admin': True,
        'enabled': True
    }


# ============================================
# FIXTURES - MOCKS DE SERVICOS
# ============================================

@pytest.fixture
def mock_openai_client():
    """Mock do OpenAI Client"""
    mock = MagicMock()
    mock.api_key_configured = True
    
    # Mock embedding generation
    def mock_embedding(*args, **kwargs):
        return np.random.rand(1536).astype(np.float32)
    
    mock.generate_embedding = mock_embedding
    
    # Mock chat completion
    mock.generate_chat_response = MagicMock(return_value={
        'success': True,
        'answer': 'Resposta mock do OpenAI',
        'model': 'gpt-4',
        'tokens_used': {'total': 100},
        'context_chunks_used': 3
    })
    
    return mock


@pytest.fixture
def mock_oracle_adapter():
    """Mock do Oracle Adapter"""
    mock = MagicMock()
    mock.connection = True
    mock.connect = MagicMock()
    mock.disconnect = MagicMock()
    mock.execute_query = MagicMock(return_value=[
        {'PEDIDO': '123456', 'VALOR': 1000.50},
        {'PEDIDO': '123457', 'VALOR': 2500.75}
    ])
    return mock


@pytest.fixture
def mock_postgres_connection():
    """Mock de conexao PostgreSQL"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    
    # Mock cursor com fetchall
    mock_cursor.fetchall = MagicMock(return_value=[
        {'chunk_id': 'chunk_1', 'content_text': 'Test content', 'similarity': 0.85},
        {'chunk_id': 'chunk_2', 'content_text': 'Another content', 'similarity': 0.75}
    ])
    
    mock_conn.cursor = MagicMock(return_value=mock_cursor)
    return mock_conn


@pytest.fixture
def mock_evolution_client():
    """Mock do Evolution API Client"""
    mock = MagicMock()
    mock.send_text_message = MagicMock(return_value={'success': True})
    mock.send_typing_indicator = MagicMock()
    mock.mark_message_as_read = MagicMock()
    mock.get_instance_status = MagicMock(return_value={'state': 'open'})
    return mock


# ============================================
# FIXTURES - DADOS DE TESTE
# ============================================

@pytest.fixture
def sample_sql_queries():
    """Queries SQL de exemplo para testes"""
    return {
        'valid_select': 'SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA WHERE ROWNUM <= 10',
        'invalid_drop': 'DROP TABLE VW_RAG_VENDAS_ESTRUTURADA',
        'invalid_update': 'UPDATE VW_RAG_VENDAS_ESTRUTURADA SET VALOR = 0',
        'invalid_multiple': 'SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA; DROP TABLE test;',
        'valid_with_limit': 'SELECT PEDIDO, VALOR FROM VW_RAG_VENDAS_ESTRUTURADA',
    }


@pytest.fixture
def sample_lgpd_queries():
    """Queries para testar classificacao LGPD"""
    return {
        'baixo': [
            'Qual o total de vendas hoje?',
            'Mostre o ranking de vendas por regiao',
            'Qual a media de vendas do mes?'
        ],
        'medio': [
            'Quais pedidos vencem hoje?',
            'Mostre o valor do pedido 123456',
            'Liste titulos a pagar vencidos'
        ],
        'alto': [
            'Quem comprou mais este mes?',
            'Mostre o nome do cliente do pedido 123456',
            'Liste clientes com CPF',
            'Qual o telefone do fornecedor X?'
        ]
    }


@pytest.fixture
def sample_webhook_payload():
    """Payload de webhook WhatsApp de exemplo"""
    return {
        'event': 'messages.upsert',
        'data': {
            'key': {
                'remoteJid': '5511999999999@s.whatsapp.net',
                'fromMe': False,
                'id': 'test_message_id'
            },
            'message': {
                'messageType': 'conversation',
                'conversation': 'Quais foram as vendas de hoje?'
            }
        }
    }


@pytest.fixture
def sample_embeddings():
    """Embeddings de exemplo para testes"""
    return {
        'query': np.random.rand(1536).astype(np.float32),
        'chunk1': np.random.rand(1536).astype(np.float32),
        'chunk2': np.random.rand(1536).astype(np.float32)
    }


# ============================================
# FIXTURES - CLEANUP
# ============================================

@pytest.fixture(autouse=True)
def reset_environment():
    """Reset automatico de variaveis de ambiente apos cada teste"""
    import os
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


# ============================================
# MARKERS CUSTOMIZADOS
# ============================================

def pytest_configure(config):
    """Configura markers customizados"""
    config.addinivalue_line(
        "markers", "unit: marca testes unitarios rapidos"
    )
    config.addinivalue_line(
        "markers", "integration: marca testes de integracao (mais lentos)"
    )
    config.addinivalue_line(
        "markers", "requires_db: marca testes que requerem banco de dados"
    )
    config.addinivalue_line(
        "markers", "requires_openai: marca testes que requerem OpenAI API"
    )
