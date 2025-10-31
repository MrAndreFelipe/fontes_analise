# src/integrations/whatsapp/authorization.py
"""
WhatsApp User Authorization System
Manages user permissions and LGPD clearance levels
"""

import logging
import json
import os
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class WhatsAppAuthorization:
    """Manages WhatsApp user authorization and LGPD clearance levels"""
    
    # Default clearance level for unknown users
    DEFAULT_CLEARANCE = 'BAIXO'
    
    # Valid clearance levels
    VALID_LEVELS = ['BAIXO', 'MÉDIO', 'ALTO']
    
    def __init__(self, config_file: str = None, enable_database: bool = False):
        """
        Initialize authorization system
        
        Args:
            config_file: Path to JSON config file with user permissions
            enable_database: If True, use database for permissions (future)
        """
        self.config_file = config_file or os.path.join(
            os.path.dirname(__file__), 
            'whatsapp_users.json'
        )
        self.enable_database = enable_database
        self.users = {}
        self.admin_numbers = set()
        
        # Load permissions
        self._load_permissions()
        
        logger.info(f"WhatsAppAuthorization initialized with {len(self.users)} users")
    
    def _load_permissions(self):
        """Load user permissions from config file or database"""
        
        if self.enable_database:
            # Future: load from database
            logger.warning("Database mode not implemented yet, falling back to JSON")
        
        # Load from JSON file
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                self.users = data.get('users', {})
                self.admin_numbers = set(data.get('admins', []))
                
                logger.info(f"Loaded {len(self.users)} users from {self.config_file}")
                
                # Validate levels
                for phone, user_data in self.users.items():
                    level = user_data.get('clearance_level', self.DEFAULT_CLEARANCE)
                    if level not in self.VALID_LEVELS:
                        logger.warning(f"Invalid clearance level '{level}' for {phone}, using {self.DEFAULT_CLEARANCE}")
                        user_data['clearance_level'] = self.DEFAULT_CLEARANCE
                
            except Exception as e:
                logger.error(f"Error loading permissions from {self.config_file}: {e}")
                self._create_default_config()
        else:
            logger.warning(f"Config file not found: {self.config_file}")
            self._create_default_config()
    
    def _create_default_config(self):
        """Create default configuration file"""
        
        default_config = {
            "users": {
                "5511999999999@s.whatsapp.net": {
                    "name": "Admin User",
                    "clearance_level": "ALTO",
                    "department": "TI",
                    "enabled": True,
                    "notes": "Default admin user - replace with real numbers"
                }
            },
            "admins": [
                "5511999999999@s.whatsapp.net"
            ],
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "version": "1.0"
            }
        }
        
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Created default config at {self.config_file}")
            self.users = default_config['users']
            self.admin_numbers = set(default_config['admins'])
            
        except Exception as e:
            logger.error(f"Error creating default config: {e}")
    
    def get_user_context(self, phone_number: str) -> Dict:
        """
        Get user context for RAG Engine
        
        Args:
            phone_number: WhatsApp number (e.g., 5511999999999@s.whatsapp.net)
        
        Returns:
            Dict with user context including lgpd_clearance
        """
        
        # Normalize phone number format
        phone = self._normalize_phone(phone_number)
        
        # Get user data
        user_data = self.users.get(phone, {})
        
        # Check if user is enabled
        if not user_data.get('enabled', True):
            logger.warning(f"User {phone} is disabled")
            return {
                'lgpd_clearance': 'BAIXO',
                'user_id': phone,
                'enabled': False
            }
        
        # Get clearance level
        clearance = user_data.get('clearance_level', self.DEFAULT_CLEARANCE)
        
        # Build context
        context = {
            'lgpd_clearance': clearance,
            'user_id': phone,
            'user_name': user_data.get('name', 'Unknown'),
            'department': user_data.get('department', 'N/A'),
            'is_admin': phone in self.admin_numbers,
            'enabled': True
        }
        
        logger.debug(f"User context for {phone}: clearance={clearance}, admin={context['is_admin']}")
        
        return context
    
    def _normalize_phone(self, phone_number: str) -> str:
        """Normalize phone number format"""
        
        # Remove common variations
        phone = phone_number.strip()
        
        # Ensure it ends with @s.whatsapp.net
        if '@' not in phone:
            phone = f"{phone}@s.whatsapp.net"
        
        return phone
    
    def is_authorized(self, phone_number: str, required_level: str = 'BAIXO') -> bool:
        """
        Check if user is authorized for a specific clearance level
        
        Args:
            phone_number: WhatsApp number
            required_level: Required clearance level
        
        Returns:
            True if authorized
        """
        
        context = self.get_user_context(phone_number)
        
        if not context.get('enabled', False):
            return False
        
        user_level = context['lgpd_clearance']
        
        # Hierarchy
        level_hierarchy = {'BAIXO': 0, 'MÉDIO': 1, 'ALTO': 2}
        
        user_clearance = level_hierarchy.get(user_level, 0)
        required_clearance = level_hierarchy.get(required_level, 2)
        
        return user_clearance >= required_clearance
    
    def add_user(self, phone_number: str, name: str, clearance_level: str = 'BAIXO', 
                 department: str = 'N/A', is_admin: bool = False) -> bool:
        """
        Add or update user (admin function)
        
        Args:
            phone_number: WhatsApp number
            name: User name
            clearance_level: LGPD clearance level
            department: User department
            is_admin: If user is admin
        
        Returns:
            True if successful
        """
        
        if clearance_level not in self.VALID_LEVELS:
            logger.error(f"Invalid clearance level: {clearance_level}")
            return False
        
        phone = self._normalize_phone(phone_number)
        
        self.users[phone] = {
            'name': name,
            'clearance_level': clearance_level,
            'department': department,
            'enabled': True,
            'added_at': datetime.now().isoformat(),
            'notes': ''
        }
        
        if is_admin:
            self.admin_numbers.add(phone)
        
        # Save to file
        return self._save_permissions()
    
    def remove_user(self, phone_number: str) -> bool:
        """Remove user (admin function)"""
        
        phone = self._normalize_phone(phone_number)
        
        if phone in self.users:
            del self.users[phone]
            self.admin_numbers.discard(phone)
            return self._save_permissions()
        
        return False
    
    def disable_user(self, phone_number: str) -> bool:
        """Disable user without removing (admin function)"""
        
        phone = self._normalize_phone(phone_number)
        
        if phone in self.users:
            self.users[phone]['enabled'] = False
            return self._save_permissions()
        
        return False
    
    def enable_user(self, phone_number: str) -> bool:
        """Enable disabled user (admin function)"""
        
        phone = self._normalize_phone(phone_number)
        
        if phone in self.users:
            self.users[phone]['enabled'] = True
            return self._save_permissions()
        
        return False
    
    def _save_permissions(self) -> bool:
        """Save permissions to config file"""
        
        try:
            config = {
                'users': self.users,
                'admins': list(self.admin_numbers),
                'metadata': {
                    'updated_at': datetime.now().isoformat(),
                    'version': '1.0'
                }
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Permissions saved to {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving permissions: {e}")
            return False
    
    def list_users(self) -> List[Dict]:
        """List all users (admin function)"""
        
        users_list = []
        for phone, data in self.users.items():
            users_list.append({
                'phone': phone,
                'name': data.get('name', 'Unknown'),
                'clearance': data.get('clearance_level', self.DEFAULT_CLEARANCE),
                'department': data.get('department', 'N/A'),
                'enabled': data.get('enabled', True),
                'is_admin': phone in self.admin_numbers
            })
        
        return users_list
    
    def reload_permissions(self):
        """Reload permissions from file (useful for hot-reload)"""
        logger.info("Reloading permissions...")
        self._load_permissions()
