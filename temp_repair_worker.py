class RepairWorker(QThread):
    progress = pyqtSignal(int, int)  # current, total
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
        
        try:
            for i, unit in enumerate(self.units):
                if not self.is_running: break
                
                # Extract required tokens from source
                import re
                pattern = re.compile(r"\{\d+\}")
                required_tokens = pattern.findall(unit.source_abstracted or "")
                
                if not required_tokens:
                    failed_count += 1
                    continue
                
                # Call repair
                fixed_target = self.client.repair_segment(
                    source_text=unit.source_abstracted,
                    broken_target=unit.target_abstracted or "",
                    required_tokens=required_tokens
                )
                
                # Update unit
                if fixed_target != unit.target_abstracted:
                    unit.target_abstracted = fixed_target
                    unit.state = "edited"
                    repaired_count += 1
                else:
                    failed_count += 1
                
                self.progress.emit(i + 1, total)
            
            self.finished.emit(repaired_count, failed_count)
            
        except Exception as e:
            self.error.emit(str(e))
