#!/usr/bin/env python3
"""
Configuration Manager - Quản lý cấu hình bot trực tiếp
"""

import os
import json
import logging
from typing import Dict, Any, Optional

class ConfigManager:
    """Quản lý cấu hình bot"""
    
    def __init__(self):
        self.config_file = "bot_config.json"
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load cấu hình từ file"""
        default_config = {
            "nextcloud": {
                "url": "https://your-nextcloud-domain.com",
                "username": "bot_user",
                "password": "your_app_password",
                "room_id": "your_room_id"
            },
            "openrouter": {
                "api_keys": ["your_openrouter_api_key"],
                "current_key_index": 0
            },
            "n8n": {
                "webhook_url": "https://your-n8n-domain.com/webhook/nextcloud-bot"
            },
            "database": {
                "spreadsheet_id": "your_google_sheet_id",
                "service_account_file": "credentials.json"
            },
            "web": {
                "port": 5000,
                "admin_users": ["admin"],
                "admin_password": "admin123"
            }
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # Merge với default config
                    return self._merge_config(default_config, loaded_config)
            except Exception as e:
                logging.error(f"Error loading config: {e}")
                return default_config
        else:
            # Tạo file config mới
            self.save_config(default_config)
            return default_config
    
    def _merge_config(self, default: Dict, loaded: Dict) -> Dict:
        """Merge config với default values"""
        result = default.copy()
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key].update(value)
            else:
                result[key] = value
        return result
    
    def save_config(self, config: Optional[Dict] = None):
        """Lưu cấu hình vào file"""
        if config is None:
            config = self.config
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logging.info(f"Config saved to {self.config_file}")
        except Exception as e:
            logging.error(f"Error saving config: {e}")
    
    def get_config(self, section: str = None) -> Any:
        """Lấy cấu hình"""
        if section:
            return self.config.get(section, {})
        return self.config
    
    def update_config(self, section: str, updates: Dict[str, Any]) -> bool:
        """Cập nhật cấu hình"""
        try:
            if section not in self.config:
                self.config[section] = {}
            
            self.config[section].update(updates)
            self.save_config()
            
            # Reload modules nếu cần
            self._reload_modules(section)
            
            logging.info(f"Config updated for section: {section}")
            return True
        except Exception as e:
            logging.error(f"Error updating config: {e}")
            return False
    
    def _reload_modules(self, section: str):
        """Reload modules sau khi cập nhật config"""
        try:
            if section == "nextcloud":
                self._update_nextcloud_config()
            elif section == "openrouter":
                self._update_openrouter_config()
            elif section == "n8n":
                self._update_n8n_config()
        except Exception as e:
            logging.error(f"Error reloading modules: {e}")
    
    def _update_nextcloud_config(self):
        """Cập nhật config Nextcloud trong runtime"""
        try:
            import config
            nc_config = self.config.get("nextcloud", {})
            
            # Cập nhật variables
            config.NEXTCLOUD_URL = nc_config.get("url", config.NEXTCLOUD_URL)
            config.USERNAME = nc_config.get("username", config.USERNAME)
            config.APP_PASSWORD = nc_config.get("password", config.APP_PASSWORD)
            config.ROOM_ID = nc_config.get("room_id", config.ROOM_ID)
            
            logging.info("Nextcloud config updated in runtime")
        except Exception as e:
            logging.error(f"Error updating Nextcloud config: {e}")
    
    def _update_openrouter_config(self):
        """Cập nhật config OpenRouter trong runtime"""
        try:
            import send_nextcloud_message
            or_config = self.config.get("openrouter", {})
            
            # Cập nhật API keys
            send_nextcloud_message.OPENROUTER_API_KEYS = or_config.get("api_keys", send_nextcloud_message.OPENROUTER_API_KEYS)
            send_nextcloud_message.current_api_key_index = or_config.get("current_key_index", 0)
            
            logging.info("OpenRouter config updated in runtime")
        except Exception as e:
            logging.error(f"Error updating OpenRouter config: {e}")
    
    def _update_n8n_config(self):
        """Cập nhật config n8n trong runtime"""
        try:
            import send_nextcloud_message
            n8n_config = self.config.get("n8n", {})
            
            # Cập nhật webhook URL
            send_nextcloud_message.N8N_WEBHOOK_URL = n8n_config.get("webhook_url", send_nextcloud_message.N8N_WEBHOOK_URL)
            
            logging.info("n8n config updated in runtime")
        except Exception as e:
            logging.error(f"Error updating n8n config: {e}")
    
    def test_connection(self, connection_type: str) -> Dict[str, Any]:
        """Test kết nối với cấu hình hiện tại"""
        try:
            if connection_type == "nextcloud":
                return self._test_nextcloud()
            elif connection_type == "openrouter":
                return self._test_openrouter()
            elif connection_type == "n8n":
                return self._test_n8n()
            elif connection_type == "database":
                return self._test_database()
            else:
                return {"success": False, "message": "Unknown connection type"}
        except Exception as e:
            return {"success": False, "message": f"Test error: {e}"}
    
    def _test_nextcloud(self) -> Dict[str, Any]:
        """Test Nextcloud connection"""
        try:
            import requests
            from requests.auth import HTTPBasicAuth
            import config

            if not hasattr(config, 'NEXTCLOUD_URL') or not config.NEXTCLOUD_URL:
                return {"success": False, "message": "Nextcloud chưa được cấu hình"}

            # Test basic connection
            test_url = f"{config.NEXTCLOUD_URL}/ocs/v1.php/cloud/capabilities"
            headers = {'OCS-APIRequest': 'true', 'Accept': 'application/json'}

            response = requests.get(
                test_url,
                headers=headers,
                auth=HTTPBasicAuth(config.USERNAME, config.APP_PASSWORD),
                timeout=10
            )

            if response.status_code == 200:
                return {"success": True, "message": "Kết nối Nextcloud thành công"}
            else:
                return {"success": False, "message": f"Nextcloud connection failed: HTTP {response.status_code}"}

        except Exception as e:
            return {"success": False, "message": f"Nextcloud test error: {e}"}
    
    def _test_openrouter(self) -> Dict[str, Any]:
        """Test OpenRouter API"""
        try:
            import requests
            
            or_config = self.config.get("openrouter", {})
            api_keys = or_config.get("api_keys", [])
            
            if not api_keys or not api_keys[0]:
                return {"success": False, "message": "No API key configured"}
            
            api_key = api_keys[0]
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                models = response.json()
                return {
                    "success": True,
                    "message": f"OpenRouter API working - {len(models.get('data', []))} models available"
                }
            else:
                return {"success": False, "message": f"API error: {response.status_code}"}
                
        except Exception as e:
            return {"success": False, "message": f"OpenRouter test error: {e}"}
    
    def _test_n8n(self) -> Dict[str, Any]:
        """Test n8n webhook"""
        try:
            import requests
            
            n8n_config = self.config.get("n8n", {})
            webhook_url = n8n_config.get("webhook_url")
            
            if not webhook_url:
                return {"success": False, "message": "No webhook URL configured"}
            
            test_payload = {"test": True, "source": "config_manager"}
            response = requests.post(webhook_url, json=test_payload, timeout=10)
            
            if response.status_code in [200, 201, 202]:
                return {"success": True, "message": "n8n webhook working"}
            else:
                return {"success": False, "message": f"Webhook error: {response.status_code}"}
                
        except Exception as e:
            return {"success": False, "message": f"n8n test error: {e}"}
    
    def _test_database(self) -> Dict[str, Any]:
        """Test database connection"""
        try:
            from database import BotDatabase
            
            db = BotDatabase()
            if hasattr(db, 'service') and db.service:
                return {"success": True, "message": "Google Sheets database connected"}
            else:
                return {"success": True, "message": "Fallback database active"}
                
        except Exception as e:
            return {"success": False, "message": f"Database test error: {e}"}

# Global instance
config_manager = ConfigManager()
