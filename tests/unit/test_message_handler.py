# tests/unit/test_message_handler.py
"""
Testes unitarios para MessageHandler
Valida processamento de webhooks, rate limiting, sessoes e tratamento de erros
"""

import pytest
from unittest.mock import MagicMock, patch, call
import time
from integrations.whatsapp.message_handler import MessageHandler


@pytest.fixture
def mock_rag_engine():
    """Mock do RAG Engine (fixture global)"""
    mock = MagicMock()
    mock.process_query = MagicMock(return_value=MagicMock(
        success=True,
        answer="Resposta mockada do RAG",
        confidence=0.85,
        sources=[],
        metadata={'route': 'text_to_sql'},
        processing_time=0.5,
        lgpd_compliant=True,
        requires_human_review=False
    ))
    return mock


@pytest.mark.unit
class TestMessageHandler:
    """Testes para MessageHandler"""
    
    @pytest.fixture
    def handler(self, mock_rag_engine, mock_evolution_client):
        """Instancia MessageHandler com mocks"""
        return MessageHandler(
            rag_engine=mock_rag_engine,
            evolution_client=mock_evolution_client,
            enable_typing_indicator=True,
            rate_limit_requests=5,
            rate_limit_window=60
        )
    
    # ============================================
    # TESTES - PROCESSAMENTO DE MENSAGENS
    # ============================================
    
    def test_handle_valid_text_message(self, handler, sample_webhook_payload):
        """Testa processamento de mensagem de texto valida"""
        handler.handle_webhook_payload(sample_webhook_payload)
        
        # Verifica que RAG foi chamado
        handler.rag_engine.process_query.assert_called_once()
        
        # Verifica que resposta foi enviada
        handler.evolution_client.send_text_message.assert_called_once()
    
    def test_handle_empty_message(self, handler):
        """Testa que mensagens vazias sao ignoradas"""
        payload = {
            'data': {
                'key': {'remoteJid': '5511999999999@s.whatsapp.net', 'fromMe': False},
                'message': {'messageType': 'conversation', 'conversation': ''}
            }
        }
        
        handler.handle_webhook_payload(payload)
        
        # Nao deve processar mensagem vazia
        handler.rag_engine.process_query.assert_not_called()
    
    def test_handle_message_from_self(self, handler):
        """Testa que mensagens do proprio bot sao ignoradas"""
        payload = {
            'data': {
                'key': {'remoteJid': '5511999999999@s.whatsapp.net', 'fromMe': True},
                'message': {'messageType': 'conversation', 'conversation': 'Test'}
            }
        }
        
        handler.handle_webhook_payload(payload)
        
        # Nao deve processar mensagens proprias
        handler.rag_engine.process_query.assert_not_called()
    
    def test_handle_non_text_message(self, handler):
        """Testa que mensagens nao-texto sao ignoradas"""
        payload = {
            'data': {
                'key': {'remoteJid': '5511999999999@s.whatsapp.net', 'fromMe': False},
                'message': {'messageType': 'image', 'image': {}}
            }
        }
        
        handler.handle_webhook_payload(payload)
        
        # Nao deve processar mensagens nao-texto
        handler.rag_engine.process_query.assert_not_called()
    
    def test_passes_user_context_to_rag(self, handler, sample_webhook_payload):
        """Testa que user context eh passado para RAG Engine"""
        handler.handle_webhook_payload(sample_webhook_payload)
        
        # Verifica que foi chamado com user_context
        call_args = handler.rag_engine.process_query.call_args
        assert 'user_context' in call_args.kwargs
        
        user_context = call_args.kwargs['user_context']
        assert 'lgpd_clearance' in user_context
        assert 'user_id' in user_context
    
    # ============================================
    # TESTES - INDICADOR DE DIGITACAO
    # ============================================
    
    def test_typing_indicator_enabled(self, handler, sample_webhook_payload):
        """Testa que indicador de digitacao eh enviado quando habilitado"""
        handler.handle_webhook_payload(sample_webhook_payload)
        
        # Verifica que typing indicator foi chamado (True e depois False)
        assert handler.evolution_client.send_typing_indicator.call_count >= 2
    
    def test_typing_indicator_disabled(self, mock_rag_engine, mock_evolution_client, sample_webhook_payload):
        """Testa que indicador de digitacao nao eh enviado quando desabilitado"""
        handler = MessageHandler(
            rag_engine=mock_rag_engine,
            evolution_client=mock_evolution_client,
            enable_typing_indicator=False
        )
        
        handler.handle_webhook_payload(sample_webhook_payload)
        
        # Nao deve chamar typing indicator
        handler.evolution_client.send_typing_indicator.assert_not_called()
    
    # ============================================
    # TESTES - RATE LIMITING
    # ============================================
    
    def test_rate_limit_blocks_excess_requests(self, handler, sample_webhook_payload):
        """Testa que rate limit bloqueia requisicoes em excesso"""
        # Envia 6 mensagens (limite eh 5)
        for i in range(6):
            handler.handle_webhook_payload(sample_webhook_payload)
        
        # Apenas 5 devem ser processadas
        assert handler.rag_engine.process_query.call_count == 5
    
    def test_rate_limit_per_user(self, handler):
        """Testa que rate limit eh por usuario"""
        payload_user1 = {
            'data': {
                'key': {'remoteJid': '5511111111111@s.whatsapp.net', 'fromMe': False},
                'message': {'messageType': 'conversation', 'conversation': 'Test'}
            }
        }
        
        payload_user2 = {
            'data': {
                'key': {'remoteJid': '5511222222222@s.whatsapp.net', 'fromMe': False},
                'message': {'messageType': 'conversation', 'conversation': 'Test'}
            }
        }
        
        # Usuario 1 envia 5 mensagens (limite)
        for i in range(5):
            handler.handle_webhook_payload(payload_user1)
        
        # Usuario 2 ainda pode enviar
        handler.handle_webhook_payload(payload_user2)
        
        # Ambos devem ter sido processados (5 + 1 = 6)
        assert handler.rag_engine.process_query.call_count == 6
    
    def test_rate_limit_message_sent(self, handler, sample_webhook_payload):
        """Testa que mensagem de rate limit eh enviada"""
        # Esgota limite
        for i in range(6):
            handler.handle_webhook_payload(sample_webhook_payload)
        
        # Verifica que mensagem de rate limit foi enviada
        calls = handler.evolution_client.send_text_message.call_args_list
        rate_limit_calls = [c for c in calls if 'Limite de mensagens' in str(c)]
        
        assert len(rate_limit_calls) > 0
    
    # ============================================
    # TESTES - SESSOES E HISTORICO
    # ============================================
    
    def test_session_creation(self, handler, sample_webhook_payload):
        """Testa criacao de sessao para novo usuario"""
        user_id = sample_webhook_payload['data']['key']['remoteJid']
        
        # Antes de processar, nao deve haver sessao
        assert user_id not in handler.user_sessions
        
        handler.handle_webhook_payload(sample_webhook_payload)
        
        # Apos processar, deve haver sessao
        assert user_id in handler.user_sessions
        assert 'messages' in handler.user_sessions[user_id]
    
    def test_session_stores_conversation(self, handler, sample_webhook_payload):
        """Testa que mensagens sao armazenadas na sessao"""
        handler.handle_webhook_payload(sample_webhook_payload)
        
        user_id = sample_webhook_payload['data']['key']['remoteJid']
        session = handler.user_sessions[user_id]
        
        assert len(session['messages']) == 1
        assert 'user' in session['messages'][0]
        assert 'bot' in session['messages'][0]
    
    def test_session_passes_history_to_rag(self, handler, sample_webhook_payload):
        """Testa que historico eh passado para RAG em mensagens subsequentes"""
        # Primeira mensagem
        handler.handle_webhook_payload(sample_webhook_payload)
        
        # Segunda mensagem
        sample_webhook_payload['data']['message']['conversation'] = 'E quanto foi ontem?'
        handler.handle_webhook_payload(sample_webhook_payload)
        
        # Segunda chamada deve incluir conversation_history
        call_args = handler.rag_engine.process_query.call_args_list[1]
        assert 'conversation_history' in call_args.kwargs
        
        history = call_args.kwargs['conversation_history']
        assert len(history) > 0
    
    def test_session_limits_history_size(self, handler, sample_webhook_payload):
        """Testa que historico eh limitado ao maximo configurado"""
        # Envia mais mensagens que o limite
        max_messages = handler.max_messages_per_session
        for i in range(max_messages + 5):
            sample_webhook_payload['data']['message']['conversation'] = f'Mensagem {i}'
            handler.handle_webhook_payload(sample_webhook_payload)
        
        user_id = sample_webhook_payload['data']['key']['remoteJid']
        session = handler.user_sessions[user_id]
        
        # Historico nao deve exceder o limite
        assert len(session['messages']) <= max_messages
    
    def test_session_expires_after_timeout(self, handler, sample_webhook_payload):
        """Testa que sessoes expiram apos timeout"""
        user_id = sample_webhook_payload['data']['key']['remoteJid']
        
        # Cria sessao
        handler.handle_webhook_payload(sample_webhook_payload)
        assert user_id in handler.user_sessions
        
        # Simula expiracao (modifica timestamp)
        handler.user_sessions[user_id]['last_update'] = time.time() - (handler.session_timeout + 100)
        
        # Tenta acessar sessao
        history = handler._get_session_context(user_id)
        
        # Deve retornar vazio e remover sessao
        assert len(history) == 0
        assert user_id not in handler.user_sessions
    
    # ============================================
    # TESTES - SAUDACOES
    # ============================================
    
    def test_greeting_detection_simple(self, handler):
        """Testa deteccao de saudacoes simples"""
        greetings = ['oi', 'olá', 'bom dia', 'boa tarde', 'boa noite', 'alo']
        
        for greeting in greetings:
            assert handler._is_greeting(greeting) is True
    
    def test_greeting_case_insensitive(self, handler):
        """Testa que deteccao de saudacao eh case-insensitive"""
        assert handler._is_greeting('Oi') is True
        assert handler._is_greeting('OI') is True
        assert handler._is_greeting('oI') is True
    
    def test_greeting_with_punctuation(self, handler):
        """Testa saudacoes com pontuacao"""
        assert handler._is_greeting('Oi!') is True
        assert handler._is_greeting('Ola!!!') is True
        assert handler._is_greeting('Bom dia?') is True
    
    def test_non_greeting_not_detected(self, handler):
        """Testa que queries normais nao sao detectadas como saudacoes"""
        assert handler._is_greeting('Quais foram as vendas de hoje?') is False
        assert handler._is_greeting('Mostre o pedido 123456') is False
    
    def test_greeting_response_not_processed_by_rag(self, handler):
        """Testa que saudacoes nao sao processadas pelo RAG"""
        payload = {
            'data': {
                'key': {'remoteJid': '5511999999999@s.whatsapp.net', 'fromMe': False},
                'message': {'messageType': 'conversation', 'conversation': 'Oi'}
            }
        }
        
        handler.handle_webhook_payload(payload)
        
        # Nao deve chamar RAG para saudacoes
        handler.rag_engine.process_query.assert_not_called()
        
        # Deve enviar resposta de saudacao
        handler.evolution_client.send_text_message.assert_called_once()
        
        # Verifica que resposta contem texto de boas-vindas
        call_args = handler.evolution_client.send_text_message.call_args[0]
        response_text = call_args[1]
        assert 'assist' in response_text.lower()
    
    # ============================================
    # TESTES - TRATAMENTO DE ERROS
    # ============================================
    
    def test_handles_rag_exception(self, handler, sample_webhook_payload):
        """Testa tratamento de excecao no RAG Engine"""
        # Configura RAG para lancar excecao
        handler.rag_engine.process_query.side_effect = Exception("RAG Error")
        
        # Nao deve lancar excecao
        handler.handle_webhook_payload(sample_webhook_payload)
        
        # Deve ter tentado enviar mensagem (mesmo que falhe)
        # Verifica que send_text_message foi chamado pelo menos uma vez
        assert handler.evolution_client.send_text_message.called
    
    def test_handles_evolution_api_exception(self, handler, sample_webhook_payload):
        """Testa tratamento de excecao na Evolution API"""
        # Configura Evolution para lancar excecao
        handler.evolution_client.send_text_message.side_effect = Exception("API Error")
        
        # Nao deve lancar excecao
        handler.handle_webhook_payload(sample_webhook_payload)
    
    def test_handles_malformed_payload(self, handler):
        """Testa tratamento de payload malformado"""
        malformed_payloads = [
            {},
            {'data': {}},
            {'data': {'key': {}}},
            {'data': {'message': {}}},
            None
        ]
        
        for payload in malformed_payloads:
            # Nao deve lancar excecao
            handler.handle_webhook_payload(payload)
            
            # Nao deve processar
            handler.rag_engine.process_query.assert_not_called()
    
    # ============================================
    # TESTES - MARK AS READ
    # ============================================
    
    def test_marks_message_as_read(self, handler, sample_webhook_payload):
        """Testa que mensagens sao marcadas como lidas"""
        handler.handle_webhook_payload(sample_webhook_payload)
        
        # Verifica que mark_as_read foi chamado
        handler.evolution_client.mark_message_as_read.assert_called_once()


@pytest.mark.unit
class TestMessageHandlerSessionCleanup:
    """Testes para limpeza de sessoes antigas"""
    
    @pytest.fixture
    def handler_with_cleanup(self, mock_rag_engine, mock_evolution_client):
        """Handler configurado para teste de cleanup"""
        handler = MessageHandler(
            rag_engine=mock_rag_engine,
            evolution_client=mock_evolution_client
        )
        # Timeout curto para testes
        handler.session_timeout = 5
        return handler
    
    def test_cleanup_removes_expired_sessions(self, handler_with_cleanup):
        """Testa que cleanup remove sessoes expiradas"""
        # Cria sessao expirada
        expired_user = '5511111111111@s.whatsapp.net'
        handler_with_cleanup.user_sessions[expired_user] = {
            'messages': [],
            'last_update': time.time() - 10  # Expirado
        }
        
        # Cria sessao ativa
        active_user = '5511222222222@s.whatsapp.net'
        handler_with_cleanup.user_sessions[active_user] = {
            'messages': [],
            'last_update': time.time()  # Ativo
        }
        
        # Executa cleanup
        handler_with_cleanup._cleanup_old_sessions()
        
        # Sessao expirada deve ser removida
        assert expired_user not in handler_with_cleanup.user_sessions
        
        # Sessao ativa deve permanecer
        assert active_user in handler_with_cleanup.user_sessions


@pytest.mark.unit
@pytest.mark.parametrize("message,is_greeting", [
    ("oi", True),
    ("Olá", True),
    ("Bom dia", True),
    ("Boa tarde!", True),
    ("E ai?", True),
    ("Quais vendas?", False),
    ("Mostre pedido 123", False),
    ("oi como vai tudo bem?", False),  # Muito longo para ser saudacao simples
])
class TestGreetingDetectionParametrizado:
    """Testes parametrizados para deteccao de saudacoes"""
    
    def test_greeting_detection_parametrizada(self, mock_rag_engine, mock_evolution_client, message, is_greeting):
        """Testa deteccao de saudacao parametrizada"""
        handler = MessageHandler(
            rag_engine=mock_rag_engine,
            evolution_client=mock_evolution_client
        )
        
        assert handler._is_greeting(message) == is_greeting
