from PyQt6.QtCore import QThread, pyqtSignal
from typing import List, Dict
from core.xliff_obj import TranslationUnit

from core.prompt_builder import PromptBuilder
from core.profile import TranslationProfile
import json

class TranslationWorker(QThread):
    progress = pyqtSignal(int, int)  # current, total
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
                # Note: We pass pre-built prompts to client if client supports it, 
                # OR we modify client to accept 'system_instruction'.
                # Assuming client.translate_batch can take system_prompt override or we just pass segments
                # and let client handle it?
                # Actually, client.translate_batch usually takes raw segments. 
                # Let's check client.py. If client.py uses hardcoded prompt, we need to change that too.
                # For now, let's assume we pass the system_instruction to translate_batch if it supports it.
                # If not, we might need to modify client.py.
                
                # Let's look at client.py first.
                # Since I cannot see client.py in this turn, I will assume I need to pass it.
                # But wait, I am the one writing the code.
                # I will modify client.translate_batch to accept system_prompt.
                
                results = self.client.translate_batch(
                    segments, 
                    self.source_lang, 
                    self.target_lang,
                    system_prompt=system_instruction # Inject here
                )
                
                # Map results back to units
                res_map = {str(res["id"]): res["translation"] for res in results}
                for u in batch:
                    if u.id in res_map:
                        u.target_abstracted = res_map[u.id]
                        u.state = "translated"
                
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
            
            # 1. Construct analysis prompt (Comprehensive for schema v1.0)
            prompt = (
                "Analyze the following text sample and suggest a comprehensive translation profile.\n"
                "Return strictly valid JSON matching this schema version 1.0:\n"
                "{\n"
                "  \"project_type\": \"e.g. Technical Manual, Legal Policy\",\n"
                "  \"target_audience\": \"e.g. Expert Developers, End Users\",\n"
                "  \"tone\": \"neutral|formal|casual|friendly|authoritative\",\n"
                "  \"formality\": \"neutral|formal|informal\",\n"
                "  \"terminology_strictness\": \"strict|prefer|loose\",\n"
                "  \"unit_system\": \"SI|Imperial|Mixed\",\n"
                "  \"do_not_translate\": [\"list\", \"of\", \"terms\"],\n"
                "  \"style_guide_notes\": \"Summary of style and tone constraints\"\n"
                "}\n\n"
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
            p.project_metadata.project_type = data.get("project_type", "")
            p.project_metadata.target_audience = data.get("target_audience", "")
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
