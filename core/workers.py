from PyQt6.QtCore import QThread, pyqtSignal
from typing import List, Dict
from core.xliff_obj import TranslationUnit

from core.prompt_builder import PromptBuilder
from core.profile import TranslationProfile
from core.prompts import SystemPrompts
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
            print(f"[TranslationWorker] Starting batch translation for {len(self.units)} units.")
            total = len(self.units)
            # Batch translate in chunks of 10 to provide progress updates
            batch_size = 10
            
            # Generate System Prompt ONCE based on Profile
            print("[TranslationWorker] Building system prompt...")
            system_instruction = PromptBuilder.build_system_message(
                self.profile, self.source_lang, self.target_lang
            )
            print(f"[TranslationWorker] System Prompt: {system_instruction[:100]}...")
            
            for i in range(0, total, batch_size):
                if not self.is_running:
                    print("[TranslationWorker] Worker stopped.")
                    break
                    
                batch = self.units[i:i + batch_size]
                print(f"[TranslationWorker] Processing batch {i} to {i+batch_size}")
                
                # Use PromptBuilder to format user message
                segments = [{"id": u.id, "source": u.source_abstracted} for u in batch]
                
                print(f"[TranslationWorker] Calling client.translate_batch with {len(segments)} segments")
                results = self.client.translate_batch(
                    segments, 
                    self.source_lang, 
                    self.target_lang,
                    system_prompt=system_instruction # Inject here
                )
                print(f"[TranslationWorker] Received {len(results)} results")
                
                # Map results back to units
                res_map = {str(res["id"]): res["translation"] for res in results}
                
                # Debug logging
                if not res_map and results:
                    print(f"[Worker] Warning: res_map empty but results exist. Keys: {[r.get('id') for r in results]}")

                # Emit results to main thread instead of modifying directly
                self.batch_finished.emit(res_map)
                
                self.progress.emit(min(i + batch_size, total), total)
            
            self.finished.emit()
            print("[TranslationWorker] Finished.")
        except Exception as e:
            print(f"[TranslationWorker] Error: {e}")
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
            from core.prompts import SystemPrompts
            client = LLMClient(**self.client_config)
            
            # 1. Construct analysis prompt (Focused on Brief fields)
            prompt = SystemPrompts.PROFILE_GEN_USER.format(text=self.sample_text[:3000])
            
            # 2. Call LLM (Using exposed chat property)
            response = client.chat.completions.create(
                model=client.model,
                messages=[
                    {"role": "system", "content": SystemPrompts.PROFILE_GEN_SYSTEM},
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
    finished = pyqtSignal(list) # Returns list of dicts: [{'id': 1, 'source': '...', 'translation': '...'}]
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
        
        # Store as dicts, not objects, to avoid thread safety issues
        self.sample_segments = [
            {"id": u.id, "source": u.source_abstracted} 
            for u in (first_n + random_m)
        ]
        
        self.client_config = client_config
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.profile = profile

    def run(self):
        try:
            if not self.sample_segments:
                self.finished.emit([])
                return

            from ai.client import LLMClient
            client = LLMClient(**self.client_config)

            system_instruction = PromptBuilder.build_system_message(
                self.profile, self.source_lang, self.target_lang
            )
            
            # Add explicit instruction that this is a SAMPLE draft
            system_instruction += "\n\nNOTE: This is a sample draft. Provide diverse options if context is ambiguous."

            results = client.translate_batch(
                self.sample_segments, 
                self.source_lang, 
                self.target_lang,
                system_prompt=system_instruction
            )
            
            # Results are already dicts: [{'id': ..., 'translation': ...}]
            # We might want to include source text for display
            final_output = []
            
            # Map results to source for completeness
            res_map = {str(r['id']): r['translation'] for r in results}
            
            for seg in self.sample_segments:
                seg_id = str(seg['id'])
                if seg_id in res_map:
                    final_output.append({
                        "id": seg['id'],
                        "source": seg['source'],
                        "translation": res_map[seg_id]
                    })
            
            self.finished.emit(final_output)
            
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
            
            system_prompt = SystemPrompts.REFINE_SYSTEM.replace("{token_str}", token_str)
            # Actually, REFINE_SYSTEM uses fixed text "Required Tokens: {token_str}" if I format it.
            # My SystemPrompts.REFINE_SYSTEM definition was static.
            # Let's fix SystemPrompts.REFINE_SYSTEM to be format-able or just append string.
            # In prompts.py I wrote: "CRITICAL: ...\nOutput ONLY..."
            # I didn't include {token_str} placeholder in the prompt file for REFINE_SYSTEM.
            # Let me re-read prompts.py content I wrote.
            # "CRITICAL: You must preserve all XLIFF tokens exactly as they appear in the source.\n"
            # "Output ONLY the refined translation text."
            # It seems I forgot to put the token list in the prompt text in prompts.py.
            # I should update the prompt logic here to inject it.
            
            full_system_prompt = SystemPrompts.REFINE_SYSTEM + f"\nRequired Tokens: {token_str}"
            
            user_prompt = SystemPrompts.REFINE_USER_TEMPLATE.format(
                source=source,
                target=target,
                instruction=instruction
            )
            
            # Use raw client chat completion
            # Assuming client.client is the OpenAI/Compatible client
            response = self.client.chat.completions.create(
                model=self.client.model,
                messages=[
                    {"role": "system", "content": full_system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            content = response.choices[0].message.content.strip()
            self.finished.emit(content)
            
        except Exception as e:
            self.error.emit(str(e))
