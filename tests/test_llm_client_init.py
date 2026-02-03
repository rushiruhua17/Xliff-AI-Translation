import unittest
from unittest.mock import patch


class _FakeOpenAI:
    def __init__(self, api_key=None, base_url=None):
        self.api_key = api_key
        self.base_url = base_url


class TestLLMClientInit(unittest.TestCase):
    def test_deepseek_provider_initializes_client(self):
        with patch("ai.client.OpenAI", _FakeOpenAI):
            from ai.client import LLMClient

            c = LLMClient(api_key="sk-test", base_url="https://api.deepseek.com/v1", model="deepseek-chat", provider="deepseek")
            self.assertIsNotNone(c.client)
            self.assertEqual(c.client.api_key, "sk-test")
            self.assertEqual(c.client.base_url, "https://api.deepseek.com/v1")

    def test_missing_base_url_does_not_initialize_client(self):
        with patch("ai.client.OpenAI", _FakeOpenAI):
            from ai.client import LLMClient

            c = LLMClient(api_key="sk-test", base_url=None, model="deepseek-chat", provider="deepseek")
            self.assertIsNone(c.client)

    def test_ollama_without_key_uses_placeholder(self):
        with patch("ai.client.OpenAI", _FakeOpenAI):
            from ai.client import LLMClient

            c = LLMClient(api_key=None, base_url="http://localhost:11434/v1", model="llama3", provider="ollama")
            self.assertIsNotNone(c.client)
            self.assertEqual(c.client.api_key, "ollama")


if __name__ == "__main__":
    unittest.main()

