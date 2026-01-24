import os
import time
import json
import re
from typing import List, Dict, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from core.logger import get_logger
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

    @property
    def chat(self):
        """Expose the underlying OpenAI chat attribute if available."""
        if self.client and hasattr(self.client, 'chat'):
            return self.client.chat
        raise AttributeError("Underlying LLM client does not support 'chat' attribute (check API Key/Connection)")

    def translate_batch(self, segments: List[Dict[str, str]], source_lang: str, target_lang: str, system_prompt: str = None) -> List[Dict[str, str]]:
        if not self.client:
            # Fallback to mock if no client (or if key missing)
            logger.warning("No API Key provided, using Mock mode.")
            return self._mock_translate(segments)

        # Use provided system_prompt OR fallback to default
        if system_prompt:
             user_content = json.dumps(segments, ensure_ascii=False, indent=2)
             system_content = system_prompt
        else:
             # Legacy/Default prompt builder logic (internal)
             prompt_full = self.create_prompt(segments, source_lang, target_lang)
             system_content = "You are a professional translator tool. Output strictly valid JSON."
             user_content = prompt_full
        
        try:
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            data = self._parse_json(content)
            
            # Expecting data to be {"translations": [{"id": "...", "translation": "..."}]}
            if isinstance(data, list):
                # If prompt builder asked for list, return list directly
                # Our PromptBuilder asks for list.
                # But legacy expects {"translations": ...}
                # We need to normalize.
                return data
            elif isinstance(data, dict) and "translations" in data:
                return data["translations"]
            elif isinstance(data, dict):
                # Try to parse list from values or check if it's keys
                # If prompt builder returns list of objects, but wrapped in dict?
                return list(data.values())[0] if data else []
            return []

        except Exception as e:
            logger.error(f"LLM Translation Error: {e}", exc_info=True)
            # Fallback to mock or empty on error to not crash UI
            return self._mock_translate(segments)

    def _parse_json(self, text: str) -> Any:
        """Robustly parse JSON from LLM response, handling markdown blocks."""
        text = text.strip()
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
            
        # Try regex extraction for markdown blocks or loose text
        match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        logger.error(f"Failed to parse JSON from: {text[:100]}...")
        return None

    def _mock_translate(self, segments: List[Dict[str, str]]) -> List[Dict[str, str]]:
        results = []
        time.sleep(0.5)
        for seg in segments:
            # Handle both 'text' (legacy) and 'source' (PromptBuilder) keys
            txt = seg.get("source") or seg.get("text") or ""
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
            logger.error(f"Refine Error: {e}", exc_info=True)
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
        prompt = f"""You are a XLIFF tag repair specialist. Your ONLY task is to fix missing or extra placeholder tokens.

**CRITICAL RULES**:
1. You MUST include ALL of these tokens EXACTLY ONCE: {required_str}
2. Do NOT add, remove, or modify any tokens beyond what's required.
3. Do NOT translate the text again - only adjust token positions.
4. Token format must be exactly {{n}} where n is a digit.

**Required Tokens**: {required_str}
**Source (for reference)**: {source_text}
**Current (Broken) Translation**: {broken_target}

Output ONLY the fixed translation. Nothing else."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a tag repair tool. Follow instructions precisely."},
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
