import unittest
from unittest.mock import patch


class _FakeQSettings:
    def __init__(self, *args, **kwargs):
        self._store = {}

    def value(self, key, default=None, type=None):
        if key not in self._store:
            return default
        v = self._store.get(key)
        if type is bool:
            return bool(v)
        if type is list:
            return v if isinstance(v, list) else default
        return v

    def setValue(self, key, value):
        self._store[key] = value

    def sync(self):
        return None


class TestTaskKeyAliases(unittest.TestCase):
    def test_profile_alias_resolves_profile_analysis(self):
        with patch("core.config.app_config.QSettings", _FakeQSettings):
            from core.config.app_config import AppConfig

            cfg = AppConfig()
            cfg.model_profiles = [
                {
                    "id": "DeepSeek_deepseek-chat",
                    "name": "DeepSeek - deepseek-chat",
                    "provider": "deepseek",
                    "api_key": "sk-test",
                    "base_url": "https://api.deepseek.com/",
                    "model": "deepseek-chat",
                }
            ]
            cfg.task_mappings = {"profile_analysis": "DeepSeek_deepseek-chat"}

            self.assertIsNotNone(cfg.get_profile_by_task("profile_analysis"))
            self.assertIsNotNone(cfg.get_profile_by_task("profile"))
            self.assertIsNotNone(cfg.get_profile_by_task("profile_detection"))

    def test_profile_alias_does_not_override_explicit_profile_mapping(self):
        with patch("core.config.app_config.QSettings", _FakeQSettings):
            from core.config.app_config import AppConfig

            cfg = AppConfig()
            cfg.model_profiles = [
                {"id": "A", "name": "A", "provider": "custom", "api_key": "", "base_url": "", "model": "m1"},
                {"id": "B", "name": "B", "provider": "custom", "api_key": "", "base_url": "", "model": "m2"},
            ]
            cfg.task_mappings = {"profile": "B", "profile_analysis": "A"}

            p = cfg.get_profile_by_task("profile")
            self.assertIsNotNone(p)
            self.assertEqual(p["id"], "B")


if __name__ == "__main__":
    unittest.main()

