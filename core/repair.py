from PyQt6.QtCore import QThread, pyqtSignal
import re

class RepairWorker(QThread):
    progress = pyqtSignal(int, int)  # current, total
    segment_repaired = pyqtSignal(int, str, str) # NEW: Emit (id, target, state)
    finished = pyqtSignal(int, int)  # repaired_count, failed_count
    error = pyqtSignal(str)
    
    def __init__(self, units, client):
        super().__init__()
        self.units = units  # List of units with qa_status == "error"
        self.client = client
        self.is_running = True
    
    def run(self):
        repaired_count = 0
        failed_count = 0
        total = len(self.units)
        
        # Pattern for valid tokens {0}, {1}, etc.
        token_pattern = re.compile(r"\{\d+\}")
        
        try:
            for i, unit in enumerate(self.units):
                if not self.is_running: break
                
                # Extract required tokens from source
                required_tokens = token_pattern.findall(unit.source_abstracted or "")
                
                if not required_tokens:
                    failed_count += 1
                    continue
                
                # Call repair
                fixed_target = self.client.repair_segment(
                    source_text=unit.source_abstracted,
                    broken_target=unit.target_abstracted or "",
                    required_tokens=required_tokens
                )
                
                # Check change
                if fixed_target != unit.target_abstracted:
                    # Emit result instead of modifying directly
                    self.segment_repaired.emit(unit.id, fixed_target, "edited")
                    repaired_count += 1
                else:
                    failed_count += 1
                
                self.progress.emit(i + 1, total)
            
            self.finished.emit(repaired_count, failed_count)
            
        except Exception as e:
            self.error.emit(str(e))
            
    def stop(self):
        self.is_running = False
