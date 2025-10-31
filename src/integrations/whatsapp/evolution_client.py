# src/integrations/whatsapp/evolution_client.py
"""
Evolution API Client
Handles communication with Evolution API for WhatsApp messaging
"""

import requests
import logging
from typing import Dict, Any, Optional, List
import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))
from core.retry_handler import retry_api_call

logger = logging.getLogger(__name__)

class EvolutionAPIClient:
    """Client for Evolution API to send/receive WhatsApp messages"""
    
    def __init__(self, api_url: str, api_key: str, instance_name: str):
        """
        Initialize Evolution API client
        
        Args:
            api_url: Base URL of Evolution API (e.g., http://10.1.200.22:8081)
            api_key: API key for authentication
            instance_name: Instance name (e.g., TCC_Andre_e_Jean)
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.instance_name = instance_name
        
        self.headers = {
            'apikey': self.api_key,
            'Content-Type': 'application/json'
        }
        
        logger.info(f"Evolution API Client initialized for instance: {instance_name}")
    
    @retry_api_call(max_retries=3)
    def send_text_message(self, phone_number: str, message: str) -> Dict[str, Any]:
        """
        Send text message via WhatsApp with markdown formatting support (COM RETRY)
        
        Args:
            phone_number: Recipient phone number (format: 5511999999999)
            message: Text message to send (supports WhatsApp markdown: *bold*, _italic_)
            
        Returns:
            API response dict
        """
        endpoint = f"{self.api_url}/message/sendText/{self.instance_name}"
        
        payload = {
            "number": phone_number,
            "text": message,
            "options": {
                "delay": 0,
                "presence": "composing"
            }
        }
        
        try:
            logger.info(f"Sending message to {phone_number}")
            response = requests.post(endpoint, json=payload, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Message sent successfully: {result.get('key', {}).get('id', 'unknown')}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending message: {e}")
            return {'error': str(e), 'success': False}
    
    @retry_api_call(max_retries=2)
    def get_instance_status(self) -> Dict[str, Any]:
        """
        Get instance connection status (COM RETRY)
        
        Returns:
            Status dict with connection info
        """
        endpoint = f"{self.api_url}/instance/connectionState/{self.instance_name}"
        
        try:
            response = requests.get(endpoint, headers=self.headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting instance status: {e}")
            return {'error': str(e), 'connected': False}
    
    @retry_api_call(max_retries=2)
    def set_webhook(self, webhook_url: str, events: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Configure webhook for receiving messages (COM RETRY)
        
        Args:
            webhook_url: Public URL to receive webhooks (e.g., https://abc.ngrok.io/webhook)
            events: List of events to subscribe (default: messages only)
            
        Returns:
            API response dict
        """
        if events is None:
            events = [
                'messages.upsert',
                'messages.update',
                'connection.update'
            ]
        
        endpoint = f"{self.api_url}/webhook/set/{self.instance_name}"
        
        payload = {
            "url": webhook_url,
            "webhook_by_events": True,
            "webhook_base64": False,
            "events": events
        }
        
        try:
            logger.info(f"Setting webhook: {webhook_url}")
            response = requests.post(endpoint, json=payload, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Webhook configured successfully")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error setting webhook: {e}")
            return {'error': str(e), 'success': False}
    
    def get_webhook_info(self) -> Dict[str, Any]:
        """
        Get current webhook configuration
        
        Returns:
            Webhook info dict
        """
        endpoint = f"{self.api_url}/webhook/find/{self.instance_name}"
        
        try:
            response = requests.get(endpoint, headers=self.headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting webhook info: {e}")
            return {'error': str(e)}
    
    def send_typing_indicator(self, phone_number: str, is_typing: bool = True) -> Dict[str, Any]:
        """
        Send typing indicator (optional feature)
        
        Args:
            phone_number: Recipient phone number
            is_typing: True to show typing, False to hide
            
        Returns:
            API response dict
        """
        endpoint = f"{self.api_url}/chat/sendPresence/{self.instance_name}"
        
        payload = {
            "number": phone_number,
            "presence": "composing" if is_typing else "paused"
        }
        
        try:
            response = requests.post(endpoint, json=payload, headers=self.headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.debug(f"Error sending typing indicator: {e}")
            return {'error': str(e)}
    
    def mark_message_as_read(self, message_key: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mark message as read
        
        Args:
            message_key: Message key dict from webhook payload
            
        Returns:
            API response dict
        """
        endpoint = f"{self.api_url}/chat/markMessageAsRead/{self.instance_name}"
        
        try:
            response = requests.post(endpoint, json=message_key, headers=self.headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.debug(f"Error marking message as read: {e}")
            return {'error': str(e)}
