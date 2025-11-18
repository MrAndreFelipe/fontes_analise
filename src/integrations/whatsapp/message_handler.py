# src/integrations/whatsapp/message_handler.py
"""
Message Handler
Processes incoming WhatsApp messages and generates responses using RAG Engine
"""

import logging
from typing import Dict, Any, Optional
import time
import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from .response_formatter import ResponseFormatter
from .authorization import WhatsAppAuthorization
from core.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

class MessageHandler:
    """Handles incoming WhatsApp messages and generates RAG responses"""
    
    def __init__(self, rag_engine, evolution_client, enable_typing_indicator: bool = True,
                 authorization: WhatsAppAuthorization = None, rate_limit_requests: int = 20,
                 rate_limit_window: int = 60):
        """
        Initialize message handler
        
        Args:
            rag_engine: RAGEngine instance for processing queries
            evolution_client: EvolutionAPIClient instance for sending responses
            enable_typing_indicator: Whether to show typing indicator
            authorization: WhatsAppAuthorization instance for user permissions
            rate_limit_requests: Maximum requests per time window
            rate_limit_window: Time window in seconds for rate limiting
        """
        self.rag_engine = rag_engine
        self.evolution_client = evolution_client
        self.enable_typing_indicator = enable_typing_indicator
        self.formatter = ResponseFormatter()
        
        # Initialize authorization system
        self.authorization = authorization or WhatsAppAuthorization()
        
        # Initialize rate limiter to prevent abuse
        self.rate_limiter = RateLimiter(
            max_requests=rate_limit_requests,
            time_window=rate_limit_window
        )
        
        # In-memory conversation history (MVP)
        self.user_sessions = {}  # {user_id: {'messages': [...], 'last_update': timestamp}}
        self.session_timeout = 1800  # 30 minutes
        self.max_messages_per_session = 5
        
        logger.info(f"MessageHandler initialized with {len(self.authorization.users)} authorized users")
        logger.info(f"Rate limiting: {rate_limit_requests} messages per {rate_limit_window} seconds")
        logger.info(f"Conversation history: enabled (in-memory, {self.session_timeout}s timeout)")
    
    def handle_webhook_payload(self, payload: Dict[str, Any]):
        """
        Process webhook payload from Evolution API
        
        Args:
            payload: Webhook payload dict
        """
        try:
            # Extract message data
            data = payload.get('data', {})
            
            # Skip if not a message event
            if not data:
                logger.debug("Empty data in payload, skipping")
                return
            
            # Get message info
            message_data = data.get('message', {}) or data.get('key', {})
            if not message_data:
                logger.debug("No message data found, skipping")
                return
            
            # Extract message content
            message_type = message_data.get('messageType')
            
            # Only process text messages for now
            if message_type != 'conversation' and 'conversation' not in str(message_data):
                logger.info(f"Skipping non-text message type: {message_type}")
                return
            
            # Get message text
            message_text = None
            if 'message' in message_data:
                msg_obj = message_data.get('message', {})
                message_text = msg_obj.get('conversation') or msg_obj.get('extendedTextMessage', {}).get('text')
            elif 'conversation' in message_data:
                message_text = message_data.get('conversation')
            
            if not message_text or not message_text.strip():
                logger.debug("Empty message text, skipping")
                return
            
            # Get sender info
            sender = data.get('key', {}).get('remoteJid', '')
            if not sender:
                sender = message_data.get('key', {}).get('remoteJid', '')
            
            # Skip messages from self (bot messages)
            if data.get('key', {}).get('fromMe', False):
                logger.debug("Skipping message from self")
                return
            
            logger.info(f"Processing message from {sender}: {message_text[:50]}...")
            
            # Check if user is authorized (in whatsapp_users.json)
            user_context = self.authorization.get_user_context(sender)

            if not user_context:
                return

            if not user_context.get('enabled', False):
                logger.warning(f"Unauthorized user {sender} attempted to message bot")
                
                unauthorized_message = (
                    "Desculpe, seu número não está autorizado para usar este bot.\n\n"
                    "Entre em contato com o administrador para solicitar acesso."
                )
                
                try:
                    self.evolution_client.send_text_message(sender, unauthorized_message)
                except Exception as e:
                    logger.error(f"Failed to send unauthorized message: {e}")
                
                return
            
            # Check rate limiting
            if not self.rate_limiter.is_allowed(sender):
                retry_after = self.rate_limiter.get_retry_after(sender)
                logger.warning(f"Rate limit exceeded for {sender} (retry after {retry_after}s)")
                
                rate_limit_message = (
                    "Limite de mensagens atingido.\n\n"
                    f"Por favor, aguarde {retry_after} segundos antes de enviar nova mensagem.\n\n"
                    "Este limite existe para garantir a qualidade do servico para todos os usuarios."
                )
                
                try:
                    self.evolution_client.send_text_message(sender, rate_limit_message)
                except Exception as e:
                    logger.error(f"Failed to send rate limit message: {e}")
                
                return
            
            # Mark as read
            message_key = data.get('key', {})
            if message_key:
                self.evolution_client.mark_message_as_read(message_key)
            
            # Show typing indicator
            if self.enable_typing_indicator:
                self.evolution_client.send_typing_indicator(sender, True)
            
            logger.info(f"User {sender} - Clearance: {user_context.get('lgpd_clearance')}, "
                       f"Name: {user_context.get('user_name')}, "
                       f"Admin: {user_context.get('is_admin')}")
            
            # Check if message is a greeting (avoid unnecessary RAG processing)
            if self._is_greeting(message_text):
                greeting_response = self._get_greeting_response()
                logger.info(f"Greeting detected, sending simple response")
                
                # Hide typing indicator
                if self.enable_typing_indicator:
                    self.evolution_client.send_typing_indicator(sender, False)
                
                # Send greeting response
                self.evolution_client.send_text_message(sender, greeting_response)
                return
            
            # Get recent conversation context
            recent_context = self._get_session_context(sender)
            
            # Process with RAG Engine (including conversation history)
            start_time = time.time()
            rag_response = self.rag_engine.process_query(
                message_text, 
                user_context=user_context,
                conversation_history=recent_context  # Pass conversation context
            )
            processing_time = time.time() - start_time
            
            logger.info(f"RAG processing completed in {processing_time:.2f}s")
            
            # Hide typing indicator
            if self.enable_typing_indicator:
                self.evolution_client.send_typing_indicator(sender, False)
            
            # Format response for WhatsApp
            formatted_response = self.formatter.format_response(rag_response)
            
            # Send response
            self.evolution_client.send_text_message(sender, formatted_response)
            
            # Save to conversation history
            self._save_to_session(sender, message_text, formatted_response)
            
            logger.info(f"Response sent to {sender}")
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Try to send error message to user
            try:
                sender = payload.get('data', {}).get('key', {}).get('remoteJid', '')
                if sender:
                    error_msg = "Ocorreu um erro ao processar sua mensagem. Por favor, tente novamente."
                    self.evolution_client.send_text_message(sender, error_msg)
            except:
                pass
    
    def _is_greeting(self, message: str) -> bool:
        """Detecta se a mensagem é apenas uma saudação"""
        message_lower = message.lower().strip()
        
        # Lista de saudações comuns
        greetings = [
            'oi', 'olá', 'ola', 'hello', 'hi',
            'bom dia', 'boa tarde', 'boa noite',
            'opa', 'e ai', 'e aí', 'eae', 'opa',
            'alo', 'alô', 'hey', 'ow'
        ]
        
        # Verifica se é uma saudação simples (sem outras palavras significativas)
        # Remove pontuação
        clean_message = message_lower.replace('!', '').replace('?', '').replace('.', '').replace(',', '').strip()
        
        # Saudação exata
        if clean_message in greetings:
            return True
        
        # Saudação com emoji ou pontuação extra (ex: "Olá!!", "Oi 👋")
        words = clean_message.split()
        if len(words) <= 2 and any(greeting in clean_message for greeting in greetings):
            return True
        
        return False
    
    def _get_greeting_response(self) -> str:
        """Retorna resposta de saudação amigável"""
        return (
            "Olá! 👋\n\n"
            "Sou o assistente virtual da Cativa Têxtil.\n\n"
            "Posso ajudar você com:\n"
            "• Consultas de pedidos\n"
            "• Informações de clientes\n"
            "• Dados de representantes\n"
            "• Relatórios por região\n"
            "• Análises de vendas\n\n"
            "Como posso ajudar?"
        )
    
    def _get_session_context(self, user_id: str) -> list:
        """Retorna histórico recente da conversa do usuário"""
        session = self.user_sessions.get(user_id)
        
        if not session:
            return []
        
        # Check if session expired (> 30 minutes)
        if time.time() - session['last_update'] > self.session_timeout:
            logger.info(f"Session expired for {user_id}, clearing history")
            del self.user_sessions[user_id]
            return []
        
        # Return last N messages
        return session['messages'][-self.max_messages_per_session:]
    
    def _save_to_session(self, user_id: str, message: str, response: str) -> None:
        """Salva mensagem no histórico da sessão do usuário"""
        
        # Create session if doesn't exist
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'messages': [],
                'last_update': time.time()
            }
            logger.info(f"New conversation session created for {user_id}")
        
        # Add message to history (store summary for efficiency)
        self.user_sessions[user_id]['messages'].append({
            'user': message,
            'bot': response[:300]  # Store first 300 chars of response
        })
        
        # Update last activity timestamp
        self.user_sessions[user_id]['last_update'] = time.time()
        
        # Limit to max messages (keep only recent ones)
        if len(self.user_sessions[user_id]['messages']) > self.max_messages_per_session:
            self.user_sessions[user_id]['messages'] = \
                self.user_sessions[user_id]['messages'][-self.max_messages_per_session:]
        
        logger.debug(f"Saved to session {user_id}: {len(self.user_sessions[user_id]['messages'])} messages")
        
        # Periodic cleanup of old sessions (1% chance per message)
        import random
        if random.randint(1, 100) == 1:
            self._cleanup_old_sessions()
    
    def _cleanup_old_sessions(self) -> None:
        """Remove sessões inativas (> timeout)"""
        current_time = time.time()
        expired_users = [
            user_id for user_id, session in self.user_sessions.items()
            if current_time - session['last_update'] > self.session_timeout
        ]
        
        for user_id in expired_users:
            del self.user_sessions[user_id]
        
        if expired_users:
            logger.info(f"Cleaned {len(expired_users)} expired conversation sessions")
