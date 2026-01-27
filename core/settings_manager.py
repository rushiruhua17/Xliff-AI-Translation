import os
import json
import logging
import keyring
import base64
from typing import Dict, Optional, Any

# Configure logger
logger = logging.getLogger(__name__)

APP_NAME = "XLIFF_AI_Assistant"
CONFIG_FILE = "config.json"
FALLBACK_KEY_FILE = "secrets.json"

class KeyringManager:
    """
    Manages secure storage of API Keys using system keyring.
    Falls back to a local obfuscated file if keyring is unavailable.
    """
    
    def __init__(self):
        self.use_fallback = False
        try:
            # Check if keyring is working by trying to set/get a dummy value
            # Some environments (headless) might fail
            keyring.get_password("test_service", "test_user")
        except Exception as e:
            logger.warning(f"System keyring not available: {e}. Using local fallback.")
            self.use_fallback = True

    def set_secret(self, service: str, key: str, value: str):
        if not value:
            return # Don't save empty secrets
            
        if self.use_fallback:
            self._save_fallback(service, key, value)
        else:
            try:
                keyring.set_password(f"{APP_NAME}_{service}", key, value)
            except Exception as e:
                logger.error(f"Failed to save to keyring: {e}. Switching to fallback.")
                self.use_fallback = True
                self._save_fallback(service, key, value)

    def get_secret(self, service: str, key: str) -> Optional[str]:
        if self.use_fallback:
            return self._load_fallback(service, key)
        else:
            try:
                return keyring.get_password(f"{APP_NAME}_{service}", key)
            except Exception:
                # If keyring fails read, try fallback
                return self._load_fallback(service, key)

    def _save_fallback(self, service: str, key: str, value: str):
        """
        Simple obfuscation (NOT ENCRYPTION) for fallback.
        Better than plain text, but not secure against determined attackers.
        """
        data = self._read_fallback_file()
        if service not in data:
            data[service] = {}
        
        # Simple Base64 encoding to avoid clear text in file
        encoded = base64.b64encode(value.encode('utf-8')).decode('utf-8')
        data[service][key] = encoded
        
        try:
            with open(FALLBACK_KEY_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save fallback secrets: {e}")

    def _load_fallback(self, service: str, key: str) -> Optional[str]:
        data = self._read_fallback_file()
        encoded = data.get(service, {}).get(key)
        if encoded:
            try:
                return base64.b64decode(encoded).decode('utf-8')
            except Exception:
                return None
        return None

    def _read_fallback_file(self) -> Dict:
        if not os.path.exists(FALLBACK_KEY_FILE):
            return {}
        try:
            with open(FALLBACK_KEY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

class SettingsManager:
    """
    Manages application configuration (Providers, Models, UI prefs).
    Separates sensitive data (Keyring) from config (JSON).
    """
    def __init__(self):
        self.keyring = KeyringManager()
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
        
        # Default Config
        return {
            "default_provider": "deepseek",
            "providers": {
                "deepseek": {
                    "base_url": "https://api.deepseek.com/v1",
                    "models": ["deepseek-chat", "deepseek-coder"],
                    "default_model": "deepseek-chat"
                },
                "gemini": {
                    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                    "models": ["gemini-1.5-pro", "gemini-1.5-flash"],
                    "default_model": "gemini-1.5-pro"
                },
                "openai": {
                    "base_url": "https://api.openai.com/v1",
                    "models": ["gpt-4o", "gpt-3.5-turbo"],
                    "default_model": "gpt-3.5-turbo"
                }
            }
        }

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def get_api_key(self, provider_name: str) -> Optional[str]:
        return self.keyring.get_secret("providers", provider_name)

    def set_api_key(self, provider_name: str, key: str):
        self.keyring.set_secret("providers", provider_name, key)

    def get_provider_config(self, provider_name: str) -> Dict:
        return self.config.get("providers", {}).get(provider_name, {})

    def set_provider_config(self, provider_name: str, base_url: str, models: list):
        if "providers" not in self.config:
            self.config["providers"] = {}
        self.config["providers"][provider_name] = {
            "base_url": base_url,
            "models": models,
            "default_model": models[0] if models else ""
        }
        self.save_config()

    def get_active_provider(self) -> str:
        return self.config.get("default_provider", "deepseek")

    def set_active_provider(self, provider_name: str):
        self.config["default_provider"] = provider_name
        self.save_config()
