# whatsapp_bot.py
"""
WhatsApp RAG Bot - Main Script
Integrates RAG Engine with WhatsApp via Evolution API
"""

import sys
import os
import logging
import signal
import time
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from integrations.whatsapp import EvolutionAPIClient, WebhookServer, MessageHandler
from rag.rag_engine import RAGEngine
from core.config import Config
from core.logging_config import setup_production_logging

# Configure production logging (estruturado com rotação)
setup_production_logging(
    app_name='whatsapp_rag_bot',
    log_level=os.getenv('LOG_LEVEL', 'INFO'),
    console_output=True
)
logger = logging.getLogger(__name__)

# Global reference for graceful shutdown
rag_engine_ref = None

def load_config():
    """Load configuration from centralized config module (.env file)"""
    # Carrega as configurações do .env
    evolution = Config.evolution()
    postgres = Config.postgres()
    oracle = Config.oracle()
    openai = Config.openai()
    
    return {
        # Evolution API (WhatsApp)
        'evolution_api_url': evolution.api_url,
        'evolution_api_key': evolution.api_key,
        'evolution_instance': evolution.instance_name,
        'webhook_host': evolution.webhook_host,
        'webhook_port': evolution.webhook_port,
        'webhook_public_url': evolution.webhook_public_url,
        
        # PostgreSQL (for embeddings fallback)
        'db_config': {
            'host': postgres.host,
            'port': postgres.port,
            'database': postgres.database,
            'user': postgres.user,
            'password': postgres.password
        },
        
        # Oracle (for Text-to-SQL primary route)
        'oracle_config': {
            'host': oracle.host,
            'port': oracle.port,
            'user': oracle.user,
            'password': oracle.password,
            'sid': oracle.sid or oracle.service_name,
        },
        
        # OpenAI (enabled if API key is configured)
        'use_openai': bool(openai.api_key)
    }

class GracefulShutdown:
    """Gerenciador de shutdown gracioso"""
    
    def __init__(self):
        self.shutdown_requested = False
        # Registra handlers para SIGINT (Ctrl+C) e SIGTERM
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        logger.info("Graceful shutdown handlers registered")
    
    def _handle_signal(self, signum, frame):
        """Handler para sinais de shutdown"""
        signal_name = 'SIGINT' if signum == signal.SIGINT else 'SIGTERM'
        logger.warning(f"Received {signal_name}, initiating graceful shutdown...")
        print(f"\n\n  {signal_name} recebido. Finalizando processamento...")
        self.shutdown_requested = True
    
    def should_shutdown(self):
        """Verifica se shutdown foi solicitado"""
        return self.shutdown_requested


def main():
    """Main function to start WhatsApp bot with graceful shutdown"""
    
    print("=" * 80)
    print("WHATSAPP RAG BOT - Sistema Cativa Textil")
    print("=" * 80)
    
    # Validate configuration before starting
    print("\nValidating system configuration...")
    if not Config.validate():
        print("\n" + "=" * 80)
        print("CONFIGURATION ERROR")
        print("=" * 80)
        print("\nThe system cannot start due to invalid configuration.")
        print("Please check the .env file and ensure all required variables are set.")
        print("\nRequired variables:")
        print("  - ORACLE_HOST, ORACLE_PORT, ORACLE_USER, ORACLE_PASSWORD")
        print("  - ORACLE_SERVICE_NAME or ORACLE_SID")
        print("  - PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD")
        print("  - OPENAI_API_KEY")
        print("  - EVOLUTION_API_URL, EVOLUTION_API_KEY, EVOLUTION_INSTANCE")
        print("\nExiting...\n")
        sys.exit(1)
    
    print("Configuration validated successfully.\n")
    
    # Load configuration
    logger.info("Loading configuration...")
    config = load_config()
    
    print(f"\nEvolution API URL: {config['evolution_api_url']}")
    print(f"Instance: {config['evolution_instance']}")
    print(f"Webhook Port: {config['webhook_port']}")
    print(f"OpenAI Enabled: {config['use_openai']}")
    
    # Initialize Evolution API client
    logger.info("Initializing Evolution API client...")
    evolution_client = EvolutionAPIClient(
        api_url=config['evolution_api_url'],
        api_key=config['evolution_api_key'],
        instance_name=config['evolution_instance']
    )
    
    # Check instance status
    logger.info("Checking instance connection status...")
    status = evolution_client.get_instance_status()
    if status.get('error'):
        logger.error(f"Failed to connect to Evolution API: {status['error']}")
        print("\nERRO: Nao foi possivel conectar a Evolution API.")
        print("Verifique se a API esta rodando e as credenciais estao corretas.")
        return
    
    print(f"\nInstance Status: {status.get('state', 'unknown')}")
    
    # Initialize RAG Engine
    logger.info("Initializing RAG Engine...")
    rag_engine = RAGEngine(
        postgres_config=config['db_config'],  # Corrigido: db_config → postgres_config
        oracle_config=config['oracle_config'],
        use_openai=config['use_openai']
    )
    
    # Database connection is handled internally by RAGEngine
    print("RAG Engine: Initialized")
    
    # Initialize Message Handler
    logger.info("Initializing Message Handler...")
    message_handler = MessageHandler(
        rag_engine=rag_engine,
        evolution_client=evolution_client,
        enable_typing_indicator=True
    )
    
    # Initialize Webhook Server
    logger.info("Initializing Webhook Server...")
    webhook_server = WebhookServer(
        host=config['webhook_host'],
        port=config['webhook_port']
    )
    
    # Set message handler
    webhook_server.set_message_handler(message_handler.handle_webhook_payload)
    
    # Configure webhook in Evolution API (if public URL provided)
    if config['webhook_public_url']:
        webhook_url = f"{config['webhook_public_url']}/webhook"
        logger.info(f"Configuring webhook: {webhook_url}")
        
        result = evolution_client.set_webhook(webhook_url)
        if result.get('error'):
            logger.warning(f"Failed to set webhook: {result['error']}")
            print(f"\nAVISO: Nao foi possivel configurar webhook automaticamente.")
            print(f"Configure manualmente via Evolution API: {webhook_url}")
        else:
            print(f"\nWebhook Configured: {webhook_url}")
    else:
        print("\nAVISO: WEBHOOK_PUBLIC_URL nao configurado.")
        print("Passos para configurar:")
        print("1. Execute: ngrok http 5000")
        print("2. Copie a URL publica (ex: https://abc123.ngrok.io)")
        print("3. Configure no Evolution API ou defina WEBHOOK_PUBLIC_URL")
    
    # Initialize graceful shutdown manager
    shutdown_manager = GracefulShutdown()
    
    print("\n" + "=" * 80)
    print("BOT INICIADO!")
    print("=" * 80)
    print("\nAguardando mensagens do WhatsApp...")
    print("Pressione Ctrl+C para encerrar")
    print()
    
    # Store RAG engine reference for cleanup
    global rag_engine_ref
    rag_engine_ref = rag_engine
    
    # Start webhook server in background thread using waitress (production WSGI)
    from threading import Thread
    from waitress import serve
    
    def run_waitress_server():
        """Run waitress WSGI server with production settings"""
        logger.info(f"Starting waitress WSGI server on {webhook_server.host}:{webhook_server.port}")
        serve(
            webhook_server.app,
            host=webhook_server.host,
            port=webhook_server.port,
            threads=4,
            channel_timeout=30,
            cleanup_interval=10,
            connection_limit=100,
            asyncore_use_poll=True
        )
    
    webhook_thread = Thread(
        target=run_waitress_server,
        daemon=False,
        name="WaitressWSGI"
    )
    webhook_thread.start()
    logger.info("Webhook server started in background thread (waitress WSGI)")
    
    # Main loop - aguarda shutdown signal
    try:
        while not shutdown_manager.should_shutdown():
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
    finally:
        # Graceful shutdown
        print("\n" + "=" * 80)
        print("FINALIZANDO SISTEMA...")
        print("=" * 80)
        
        logger.info("Starting shutdown sequence")
        
        # 1. Fecha connection pools
        if rag_engine:
            try:
                print("Fechando connection pools...")
                rag_engine.close()
                logger.info("Connection pools closed")
            except Exception as e:
                logger.error(f"Error closing connection pools: {e}")
        
        # 2. Aguarda thread do webhook (timeout 5s)
        if webhook_thread.is_alive():
            print("Aguardando webhook thread...")
            webhook_thread.join(timeout=5)
            if webhook_thread.is_alive():
                logger.warning("Webhook thread did not stop in time")
        
        print("Shutdown completo")
        logger.info("Shutdown completed")
        print("\nSistema encerrado com sucesso.\n")

if __name__ == "__main__":
    main()

