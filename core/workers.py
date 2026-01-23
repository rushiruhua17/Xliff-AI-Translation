from PyQt6.QtCore import QThread, pyqtSignal
from typing import List, Dict
from core.xliff_obj import TranslationUnit

class TranslationWorker(QThread):
    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, units: List[TranslationUnit], client, source_lang: str, target_lang: str):
        super().__init__()
        self.units = units
        self.client = client
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.is_running = True

    def run(self):
        try:
            total = len(self.units)
            # Batch translate in chunks of 10 to provide progress updates
            batch_size = 10
            
            for i in range(0, total, batch_size):
                if not self.is_running:
                    break
                    
                batch = self.units[i:i + batch_size]
                segments = [{"id": u.id, "text": u.source_abstracted} for u in batch]
                
                results = self.client.translate_batch(segments, self.source_lang, self.target_lang)
                
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
