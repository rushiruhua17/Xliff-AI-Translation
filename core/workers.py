from PyQt6.QtCore import QThread, pyqtSignal

class TranslationWorker(QThread):
    progress = pyqtSignal(int, int) # current, total
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, units, client, source_lang="zh-CN", target_lang="en"):
        super().__init__()
        self.units = units
        self.client = client
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.is_running = True

    def run(self):
        to_translate = [u for u in self.units if u.state != 'locked']
        total = len(to_translate)
        batch_size = 10
        
        try:
            for i in range(0, total, batch_size):
                if not self.is_running: break
                
                chunk = to_translate[i:i+batch_size]
                payload = [{"id": u.id, "text": u.source_abstracted} for u in chunk]
                
                results = self.client.translate_batch(payload, self.source_lang, self.target_lang)
                
                res_map = {str(r["id"]): r["translation"] for r in results}
                for u in chunk:
                    if str(u.id) in res_map:
                        u.target_abstracted = res_map[str(u.id)]
                        u.state = "translated"
                
                self.progress.emit(min(i + batch_size, total), total)
                
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self.is_running = False

class RefineWorker(QThread):
    finished = pyqtSignal(str) # new_translation
    error = pyqtSignal(str)

    def __init__(self, client, source, current_target, instruction):
        super().__init__()
        self.client = client
        self.source = source
        self.current_target = current_target
        self.instruction = instruction

    def run(self):
        try:
            new_trans = self.client.refine_segment(self.source, self.current_target, self.instruction)
            self.finished.emit(new_trans)
        except Exception as e:
            self.error.emit(str(e))
            
class TestConnectionWorker(QThread):
    finished = pyqtSignal(bool, str)
    
    def __init__(self, client):
        super().__init__()
        self.client = client
        
    def run(self):
        try:
            success, msg = self.client.test_connection()
            self.finished.emit(success, msg)
        except Exception as e:
            self.finished.emit(False, str(e))
