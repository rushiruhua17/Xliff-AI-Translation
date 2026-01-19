    def run_qa(self):
        if not self.units: return
        
        pattern = QRegularExpression(r"\{\d+\}")
        error_count = 0
        warning_count = 0
        
        for unit in self.units:
            if unit.state == "locked": continue
            
            unit.errors = [] # Reset
            
            # 1. Tag Count Check
            source_tag_count = len(unit.tags_map)
            
            # Count target tags in abstract string
            match = pattern.globalMatch(unit.target_abstracted or "")
            target_tag_count = 0
            while match.hasNext():
                match.next()
                target_tag_count += 1
            
            unit.tag_stats = f"TAG: {target_tag_count}/{source_tag_count}"
            
            # 2. Logic
            if target_tag_count != source_tag_count:
                unit.qa_status = "error"
                unit.errors.append("Tag quantity mismatch")
                error_count += 1
            elif not unit.target_abstracted and unit.state in ["translated", "edited"]:
                unit.qa_status = "warning"
                unit.errors.append("Empty translation")
                warning_count += 1
            else:
                unit.qa_status = "ok"
                
        self.model.layoutChanged.emit() # Refresh UI (Icons)
        
        msg = f"QA Complete.\nErrors: {error_count}\nWarnings: {warning_count}"
        if error_count > 0:
            QMessageBox.warning(self, "QA Issues Found", msg + "\n\nPlease fix ERRORS before exporting.")
        else:
            QMessageBox.information(self, "QA Passed", msg)

    def save_file(self):
        if not self.units: return
        
        # Auto-run QA check before save
        self.run_qa()
        
        # Check for blockers
        errors = [u for u in self.units if u.qa_status == "error"]
        if errors:
            QMessageBox.critical(self, "Export Blocked", f"Found {len(errors)} Critical Errors (Tag Mismatch).\n\nYou must fix them to ensure valid XLIFF output.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export XLIFF", "", "XLIFF Files (*.xlf *.xliff);;All Files (*)")
        if path:
            for u in self.units:
                if u.target_abstracted:
                    try:
                        u.target_raw = self.abstractor.reconstruct(u.target_abstracted, u.tags_map)
                    except Exception as e:
                        logger.warning(f"Tag reconstruction failed for unit {u.id}: {e}")
            self.parser.update_targets(self.units, path)
            logger.info(f"File exported to: {path}")
            QMessageBox.information(self, "Saved", f"Exported to {path}")
