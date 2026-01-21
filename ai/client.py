import os
import time
import json
from typing import List, Dict, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from core.logger import get_logger
from ai.prompts import (
    TRANSLATION_SYSTEM_PROMPT, 
    TRANSLATION_USER_PROMPT_TEMPLATE,
    REFINE_SYSTEM_PROMPT,
    REFINE_USER_PROMPT_TEMPLATE,
    REPAIR_SYSTEM_PROMPT,
    REPAIR_USER_PROMPT_TEMPLATE
)

logger = get_logger(__name__)

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
                logger.warning("OpenAI library not installed.")

    def translate_batch(self, segments: List[Dict[str, str]], source_lang: str, target_lang: str) -> List[Dict[str, str]]:
        if not self.client:
            # Fallback to mock if no client (or if key missing)
            logger.warning("No API Key provided, using Mock mode.")
            return self._mock_translate(segments)

        prompt = self.create_prompt(segments, source_lang, target_lang)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
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
            logger.error(f"LLM Translation Error: {e}", exc_info=True)
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
            
        prompt = REFINE_USER_PROMPT_TEMPLATE.format(
            source_text=source_text,
            current_target=current_target,
            instruction=instruction
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": REFINE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Refine Error: {e}", exc_info=True)
            return current_target

    def create_prompt(self, segments: List[Dict[str, str]], source_lang: str, target_lang: str) -> str:
        data_str = json.dumps(segments, ensure_ascii=False, indent=2)
        return TRANSLATION_USER_PROMPT_TEMPLATE.format(
            source_lang=source_lang,
            target_lang=target_lang,
            data_str=data_str
        )

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
    
    def repair_segment(self, source_text: str, broken_target: str, required_tokens: list) -> str:
        """
        Repairs a broken translation by fixing missing/extra tokens.
        Uses a specialized prompt that enforces strict token preservation.
        
        Args:
            source_text: Original source with correct tokens
            broken_target: Current target with token errors
            required_tokens: List of tokens that MUST appear (e.g. ["{0}", "{1}"])
        
        Returns:
            Fixed translation string
        """
        if not self.client:
            logger.warning("No API client for repair, returning original")
            return broken_target
        
        # Construct strict repair prompt
        required_str = ", ".join(required_tokens)
        prompt = REPAIR_USER_PROMPT_TEMPLATE.format(
            required_str=required_str,
            source_text=source_text,
            broken_target=broken_target
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Very low temperature for deterministic fixes
                max_tokens=500
            )
            fixed = response.choices[0].message.content.strip()
            
            # Remove any markdown code blocks if LLM added them
            if fixed.startswith("```"):
                lines = fixed.split("\n")
                fixed = "\n".join(lines[1:-1]) if len(lines) > 2 else fixed
            
            logger.info(f"Repair attempt: '{broken_target}' -> '{fixed}'")
            return fixed
            
        except Exception as e:
            logger.error(f"Repair Error: {e}", exc_info=True)
            return broken_target  # Return original if repair fails
