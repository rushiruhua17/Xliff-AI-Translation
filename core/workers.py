from PyQt6.QtCore import QThread, pyqtSignal
from typing import List, Dict
from core.xliff_obj import TranslationUnit

from core.prompt_builder import PromptBuilder
from core.profile import TranslationProfile
import json

class TranslationWorker(QThread):
    progress = pyqtSignal(int, int)  # current, total
    batch_finished = pyqtSignal(dict) # NEW: Emit {id_str: translation}
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, units: List[TranslationUnit], client, source_lang: str, target_lang: str, profile=None):
        super().__init__()
        self.units = units
        self.client = client
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.profile = profile # Receive profile object
        self.is_running = True

    def run(self):
        try:
            total = len(self.units)
            # Batch translate in chunks of 10 to provide progress updates
            batch_size = 10
            
            # Generate System Prompt ONCE based on Profile
            system_instruction = PromptBuilder.build_system_message(
                self.profile, self.source_lang, self.target_lang
            )
            
            for i in range(0, total, batch_size):
                if not self.is_running:
                    break
                    
                batch = self.units[i:i + batch_size]
                
                # Use PromptBuilder to format user message
                segments = [{"id": u.id, "source": u.source_abstracted} for u in batch]
                
                results = self.client.translate_batch(
                    segments, 
                    self.source_lang, 
                    self.target_lang,
                    system_prompt=system_instruction # Inject here
                )
                
                # Map results back to units
                res_map = {str(res["id"]): res["translation"] for res in results}
                
                # Debug logging
                if not res_map and results:
                    print(f"[Worker] Warning: res_map empty but results exist. Keys: {[r.get('id') for r in results]}")

                # Emit results to main thread instead of modifying directly
                self.batch_finished.emit(res_map)
                
                self.progress.emit(min(i + batch_size, total), total)
            
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self.is_running = False

class ProfileGeneratorWorker(QThread):
    finished = pyqtSignal(TranslationProfile) # Returns suggested profile
    error = pyqtSignal(str)

    def __init__(self, sample_text: str, client_config: dict):
        super().__init__()
        self.sample_text = sample_text
        self.client_config = client_config

    def run(self):
        try:
            from ai.client import LLMClient
            client = LLMClient(**self.client_config)
            
            # 1. Construct analysis prompt (Focused on Brief fields)
            prompt = (
                "Analyze the following text sample and suggest a comprehensive translation brief.\n"
                "Return strictly valid JSON matching this schema version 1.0:\n"
                "{\n"
                "  \"target_audience\": \"e.g. Expert Developers, End Users\",\n"
                "  \"tone\": \"neutral|formal|casual|friendly|authoritative\",\n"
                "  \"formality\": \"neutral|formal|informal\",\n"
                "  \"terminology_strictness\": \"strict|prefer|loose\",\n"
                "  \"unit_system\": \"SI|Imperial|Mixed\",\n"
                "  \"do_not_translate\": [\"list\", \"of\", \"terms\"],\n"
                "  \"style_guide_notes\": \"Summary of style and tone constraints\"\n"
                "}\n"
                "Do NOT guess client names or specific project types (e.g. 'Apple Manual'). Focus on style and linguistic properties.\n\n"
                f"Sample Text:\n{self.sample_text[:3000]}"
            )
            
            # 2. Call LLM (Using exposed chat property)
            response = client.chat.completions.create(
                model=client.model,
                messages=[
                    {"role": "system", "content": "You are a localization expert. Output ONLY valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # 3. Parse & Map
            content = response.choices[0].message.content
            data = json.loads(content)
            
            # 4. Construct Profile
            p = TranslationProfile()
            # No longer guessing project metadata
            p.brief.target_audience = data.get("target_audience", "")
            p.brief.tone = data.get("tone", "neutral")
            p.brief.formality = data.get("formality", "neutral")
            p.brief.style_guide_notes = data.get("style_guide_notes", "")
            
            # Map Advanced fields
            p.brief.terminology.strictness = data.get("terminology_strictness", "strict")
            p.brief.terminology.do_not_translate = data.get("do_not_translate", [])
            p.brief.formatting.unit_system = data.get("unit_system", "SI")
            
            self.finished.emit(p)
            
        except Exception as e:
            self.error.emit(str(e))

class SampleWorker(QThread):
    finished = pyqtSignal(list) # Returns list of sample translations
    error = pyqtSignal(str)

    def __init__(self, units: List[TranslationUnit], client_config: dict, source_lang: str, target_lang: str, profile=None, sample_size=5):
        super().__init__()
        # Filter for non-empty source
        active_units = [u for u in units if u.source_abstracted]
        
        # Sampling Strategy: First N + Random M (Prompt 6)
        n = 2  # First N
        m = 3  # Random M
        
        first_n = active_units[:n]
        remaining = active_units[n:]
        
        import random
        random_m = random.sample(remaining, min(m, len(remaining))) if remaining else []
        
        self.sample_units = first_n + random_m
        self.client_config = client_config
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.profile = profile

    def run(self):
        try:
            if not self.sample_units:
                self.finished.emit([])
                return

            from ai.client import LLMClient
            client = LLMClient(**self.client_config)

            system_instruction = PromptBuilder.build_system_message(
                self.profile, self.source_lang, self.target_lang
            )
            
            # Add explicit instruction that this is a SAMPLE draft
            system_instruction += "\n\nNOTE: This is a sample draft. Provide diverse options if context is ambiguous."

            segments = [{"id": u.id, "source": u.source_abstracted} for u in self.sample_units]
            
            results = client.translate_batch(
                segments, 
                self.source_lang, 
                self.target_lang,
                system_prompt=system_instruction
            )
            
            self.finished.emit(results)
            
        except Exception as e:
            self.error.emit(str(e))

class RefineWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, client, source_text: str, current_target: str, instruction: str):
        super().__init__()
        self.client = client
        self.source_text = source_text
        self.current_target = current_target
        self.instruction = instruction

    def run(self):
        try:
            new_text = self.client.refine_segment(self.source_text, self.current_target, self.instruction)
            self.finished.emit(new_text)
        except Exception as e:
            self.error.emit(str(e))

class TestConnectionWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, client):
        super().__init__()
        self.client = client

    def run(self):
        success, message = self.client.test_connection()
        self.finished.emit(success, message)

class WorkbenchWorker(QThread):
    finished = pyqtSignal(str) # AI response text
    error = pyqtSignal(str)

    def __init__(self, client, payload: dict):
        super().__init__()
        self.client = client
        self.payload = payload

    def run(self):
        try:
            # Construct Prompt
            # Payload: source, target, tokens, instruction
            source = self.payload.get("source", "")
            target = self.payload.get("target", "")
            tokens = self.payload.get("tokens", [])
            instruction = self.payload.get("instruction", "")
            
            token_str = ", ".join(tokens) if tokens else "None"
            
            system_prompt = (
                "You are a professional translator and editor. "
                "Your task is to refine the translation based on user instructions.\n"
                "CRITICAL: You must preserve all XLIFF tokens exactly as they appear in the source.\n"
                f"Required Tokens: {token_str}\n"
                "Output ONLY the refined translation text."
            )
            
            user_prompt = (
                f"Source: {source}\n"
                f"Current Translation: {target}\n"
                f"User Instruction: {instruction}\n\n"
                "Refined Translation:"
            )
            
            # Use raw client chat completion
            # Assuming client.client is the OpenAI/Compatible client
            response = self.client.client.chat.completions.create(
                model=self.client.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            content = response.choices[0].message.content.strip()
            self.finished.emit(content)
            
        except Exception as e:
            self.error.emit(str(e))
