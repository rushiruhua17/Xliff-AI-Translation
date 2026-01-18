import os
import time
import json
from typing import List, Dict, Any
import logging

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

class LLMClient:
    def __init__(self, api_key: str = None, base_url: str = None, model: str = "gpt-3.5-turbo", provider: str = "custom"):
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL")
        self.model = model
        self.provider = provider
        
        self.client = None
        if self.provider == "custom" and self.api_key:
            if OpenAI:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            else:
                logging.warning("OpenAI library not installed.")

    def translate_batch(self, segments: List[Dict[str, str]], source_lang: str, target_lang: str) -> List[Dict[str, str]]:
        if not self.client:
            # Fallback to mock if no client (or if key missing)
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] No API Key provided, using Mock mode.")
            return self._mock_translate(segments)

        prompt = self.create_prompt(segments, source_lang, target_lang)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional translator tool. Output strictly valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            data = json.loads(content)
            
            # Expecting data to be {"translations": [{"id": "...", "translation": "..."}]}
            # Or handle list response directly if LLM is nice
            if isinstance(data, list):
                return data
            elif "translations" in data:
                return data["translations"]
            else:
                # Try to parse list from values
                return list(data.values())[0] if data else []

        except Exception as e:
            print(f"LLM Error: {e}")
            # Fallback to mock or empty on error to not crash UI
            return self._mock_translate(segments)

    def _mock_translate(self, segments: List[Dict[str, str]]) -> List[Dict[str, str]]:
        results = []
        time.sleep(0.5)
        for seg in segments:
            txt = seg["text"]
            results.append({
                "id": seg["id"],
                "translation": f"[Mock] {txt}"
            })
        return results

    def refine_segment(self, source_text: str, current_target: str, instruction: str) -> str:
        """
        Refines a single translation based on user instruction.
        """
        if not self.client:
            time.sleep(1)
            return f"[Refined] {current_target}"
            
        prompt = (
            f"You are a professional translator tool. \n"
            f"Original Source: {source_text}\n"
            f"Current Translation: {current_target}\n"
            f"User Instruction: {instruction}\n\n"
            f"Please output ONLY the refined translation string. Preserve tags {{n}}."
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Output only the translation text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Refine Error: {e}")
            return current_target

    def create_prompt(self, segments: List[Dict[str, str]], source_lang: str, target_lang: str) -> str:
        instructions = (
            f"Translate the following segments from {source_lang} to {target_lang}.\n"
            "IMPORTANT RULES:\n"
            "1. Preserve all {n} tags exactly where they belong in the structure.\n"
            "2. Do not translate the tags themselves.\n"
            "3. Output MUST be valid JSON with key 'translations', which is a list of objects {\"id\": \"...\", \"translation\": \"...\"}.\n\n"
            "Input Segments:\n"
        )
        
        data_str = json.dumps(segments, ensure_ascii=False, indent=2)
        return instructions + data_str

    def test_connection(self) -> tuple[bool, str]:
        """
        Tests the connection to the LLM provider.
        Returns: (success, message)
        """
        if self.provider == "mock":
            return True, "Mock mode is always compliant."
            
        if not self.client:
            return False, "Client not initialized. Check API Key."

        try:
            # Try a lightweight call
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1
            )
            return True, f"Successfully connected to {self.model}!"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
