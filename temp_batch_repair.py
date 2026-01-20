    def get_repair_client(self):
        """Create a secondary LLM client for repair tasks (uses Repair Model config)"""
        if not self.chk_auto_repair.isChecked():
            raise ValueError("Auto-Repair is not enabled in Settings")
        
        # Use repair config if provided, otherwise fallback to main config
        repair_key = self.txt_repair_apikey.text() or self.txt_apikey.text()
        repair_model = self.txt_repair_model.text() or "deepseek-chat"
        repair_url = self.txt_repair_base_url.text() or "https://api.deepseek.com"
        
        if not repair_key:
            raise ValueError("Repair API Key required (or main API Key)")
        
        return LLMClient(api_key=repair_key, base_url=repair_url, model=repair_model, provider="custom")
    
    def batch_auto_repair(self):
        """Batch repair all units with qa_status == 'error'"""
        if not self.units:
            QMessageBox.warning(self, "No File", "Please open a file first.")
            return
        
        # Check if Auto-Repair is enabled
        if not self.chk_auto_repair.isChecked():
            QMessageBox.information(self, "Auto-Repair Disabled", 
                "Auto-Repair is currently disabled.\n\nPlease enable it in Settings Tab and configure a Repair Model.")
            return
        
        # Filter error units
        error_units = [u for u in self.units if u.qa_status == "error"]
        
        if not error_units:
            QMessageBox.information(self, "No Errors", "No error segments found. Run QA first!")
            return
        
        # Confirm action
        reply = QMessageBox.question(self, "Batch Auto-Repair", 
            f"Found {len(error_units)} segments with errors.\n\nAttempt to auto-repair all using AI?\n\n(This will use your Repair Model API)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            repair_client = self.get_repair_client()
        except Exception as e:
            QMessageBox.critical(self, "Config Error", str(e))
            return
        
        # Start repair worker
        self.btn_batch_repair.setEnabled(False)
        self.btn_batch_repair.setText("Repairing...")
        self.progress.setVisible(True)
        self.progress.setValue(0)
        
        self.repair_worker = RepairWorker(error_units, repair_client)
        self.repair_worker.progress.connect(lambda c, t: self.progress.setValue(int(c/t*100)))
        self.repair_worker.finished.connect(self.on_repair_finished)
        self.repair_worker.error.connect(lambda e: QMessageBox.critical(self, "Repair Error", e))
        self.repair_worker.start()
    
    def on_repair_finished(self, repaired_count, failed_count):
        """Called when batch repair completes"""
        self.btn_batch_repair.setEnabled(True)
        self.btn_batch_repair.setText("🔧 Batch Auto-Repair")
        self.progress.setVisible(False)
        
        # Refresh UI
        self.model.layoutChanged.emit()
        self.update_stats()
        
        # Re-run QA to verify fixes
        QTimer.singleShot(500, self.run_qa)
        
        # Show summary
        msg = f"Repair Complete!\n\nRepaired: {repaired_count}\nFailed: {failed_count}\n\nRe-running QA to verify..."
        QTimer.singleShot(100, lambda: QMessageBox.information(self, "Batch Repair Done", msg))
