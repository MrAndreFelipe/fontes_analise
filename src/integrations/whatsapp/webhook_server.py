# src/integrations/whatsapp/webhook_server.py
"""
Webhook Server using Flask
Receives messages from Evolution API and processes them
"""

from flask import Flask, request, jsonify
import logging
from typing import Callable, Dict, Any
import traceback

logger = logging.getLogger(__name__)

class WebhookServer:
    """Flask server to handle WhatsApp webhooks"""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 5000):
        """
        Initialize webhook server
        
        Args:
            host: Host to bind (0.0.0.0 for all interfaces)
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.message_handler = None
        
        # Disable Flask request logging to reduce noise
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.WARNING)
        
        self._setup_routes()
        logger.info(f"Webhook server initialized on {host}:{port}")
    
    def set_message_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """
        Set the message handler callback
        
        Args:
            handler: Function to call when message is received
        """
        self.message_handler = handler
        logger.info("Message handler configured")
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/webhook', methods=['POST'])
        def webhook():
            """Main webhook endpoint"""
            try:
                # Get JSON payload
                payload = request.get_json()
                
                if not payload:
                    logger.warning("Received empty payload")
                    return jsonify({'status': 'error', 'message': 'Empty payload'}), 400
                
                # Log received event
                event_type = payload.get('event', 'unknown')
                logger.info(f"Webhook received: {event_type}")
                logger.debug(f"Full payload: {payload}")
                
                # Process message if handler is set
                if self.message_handler and event_type == 'messages.upsert':
                    try:
                        self.message_handler(payload)
                    except Exception as e:
                        logger.error(f"Error in message handler: {e}")
                        logger.error(traceback.format_exc())
                
                # Always return success to Evolution API
                return jsonify({'status': 'success'}), 200
                
            except Exception as e:
                logger.error(f"Error processing webhook: {e}")
                logger.error(traceback.format_exc())
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.route('/health', methods=['GET'])
        def health():
            """Health check endpoint"""
            return jsonify({
                'status': 'healthy',
                'service': 'whatsapp-webhook',
                'handler_configured': self.message_handler is not None
            }), 200
        
        @self.app.route('/', methods=['GET'])
        def root():
            """Root endpoint"""
            return jsonify({
                'service': 'WhatsApp RAG Bot',
                'status': 'running',
                'endpoints': {
                    'webhook': '/webhook (POST)',
                    'health': '/health (GET)'
                }
            }), 200
    
    def run(self, debug: bool = False):
        """
        Start the Flask server
        
        Args:
            debug: Enable Flask debug mode
        """
        logger.info(f"Starting webhook server on http://{self.host}:{self.port}")
        logger.info("Waiting for messages from Evolution API...")
        
        self.app.run(
            host=self.host,
            port=self.port,
            debug=debug,
            use_reloader=False  # Disable reloader to prevent double initialization
        )
