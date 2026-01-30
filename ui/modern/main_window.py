import sys
import os

# Add project root to sys.path to allow running this file directly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Also add current directory (xliff_ai_assistant) if running from root
current_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtWidgets import QApplication, QWidget, QMessageBox, QFileDialog
from PyQt6.QtGui import QShortcut, QKeySequence
from qfluentwidgets import (FluentWindow, NavigationItemPosition, FluentIcon as FIF,
                            SplashScreen, ToolTipFilter, ToolTipPosition)

# Core Logic
from core.parser import XliffParser
from core.abstractor import TagAbstractor
from core.autosave import Autosaver
from core.workers import TranslationWorker, RefineWorker, SampleWorker
from core.repair import RepairWorker
from core.services.qa_service import QAService
from core.config.app_config import AppConfig

# Import Interfaces
from ui.modern.interfaces.home_interface import HomeInterface
from ui.modern.interfaces.project_interface import ProjectInterface
from ui.modern.interfaces.editor_interface import EditorInterface
from ui.modern.interfaces.settings_interface import SettingsInterface
from ui.profile_wizard import ProfileWizardDialog

class ModernMainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XLIFF AI Assistant Pro")
        self.resize(1200, 800)
        
        # Set App Icon (Use Robot icon for AI theme)
        self.setWindowIcon(FIF.ROBOT.icon())
        
        # Enable Mica (Win11)
        self.windowEffect.setMicaEffect(self.winId())
        
        # 0. Show Splash Screen immediately
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(100, 100))
        # self.splashScreen.setTitleBarVisible(False) # Optional (Not supported in this version)
        
        # Show the splash screen. Since the main window is not shown yet, 
        # the splash screen will be visible. 
        # But wait, FluentWindow usually needs to be shown for Splash to be centered?
        # Actually, SplashScreen is a widget covering the window.
        # So we need to show the window first?
        # Let's follow standard pattern: show window, splash covers it.
        # But we are in __init__. We can't show window yet.
        # So we initialize splash here, and it will be shown when window.show() is called?
        # No, we need to explicitly show it if we want it to appear during heavy init.
        # However, we can't show a child widget if parent is hidden.
        # Strategy: Do heavy init AFTER window is shown, using QTimer.singleShot(0, self.lazy_init)
        
        # Logic Components (Fast Init)
        self.config = AppConfig()
        self.parser = None
        self.abstractor = TagAbstractor()
        self.current_file_path = None
        self.autosaver = None
        self.current_profile = None # TranslationProfile
        self.project_context = "" # Store context from ProjectInterface
        
        # Init Sub-Interfaces
        self.homeInterface = HomeInterface(self)
        self.projectInterface = ProjectInterface(self)
        self.editorInterface = EditorInterface(self)
        self.settingsInterface = SettingsInterface(self)
        
        self.init_navigation()
        self.configure_sidebar_tooltips() # Apply tooltip fix
        self.init_signals()
        self.init_shortcuts()
        
        # Workers (Lazy Init)
        self.trans_worker = None
        self.refine_worker = None
        self.qa_worker = None
        self.repair_worker = None
        self.sample_worker = None
        
        # Close Splash Screen after a delay (simulated loading)
        # In real app, close it when data is ready
        QTimer.singleShot(1500, self.splashScreen.finish)

    def init_navigation(self):
        self.addSubInterface(self.homeInterface, FIF.HOME, "Home")
        self.addSubInterface(self.projectInterface, FIF.FOLDER, "Project")
        self.addSubInterface(self.editorInterface, FIF.EDIT, "Editor")
        
        # Initially hide Editor until project is loaded? 
        # Or just keep it. FluentWindow manages stack.
        # Let's keep it visible but maybe disable interactions if no file?
        
        self.navigationInterface.addSeparator()
        
        # We use a trick for Settings: Add a dummy widget, but hijack the click
        self.addSubInterface(self.settingsInterface, FIF.SETTING, "Settings", NavigationItemPosition.BOTTOM)

    def configure_sidebar_tooltips(self):
        """
        Hack to apply ToolTipFilter to sidebar navigation items 
        to reduce the default hover delay.
        """
        # Iterate over all child widgets of navigation interface
        # NavigationItem is usually a QToolButton or similar
        from PyQt6.QtWidgets import QAbstractButton
        
        buttons = self.navigationInterface.findChildren(QAbstractButton)
        for btn in buttons:
            # Check if it has a tooltip or is a nav item
            # We install filter regardless to catch future tooltips
            btn.installEventFilter(ToolTipFilter(btn, showDelay=50, position=ToolTipPosition.RIGHT))

    def init_signals(self):
        # Home Actions
        self.homeInterface.open_file_clicked.connect(self.switch_to_project_tab)
        self.homeInterface.recent_file_clicked.connect(self.load_recent_file)
        
        # Project Actions
        self.projectInterface.start_project_clicked.connect(self.start_new_project)
        
        # Autosave Trigger (Listen to Model changes)
        self.editorInterface.table._model.dataChanged.connect(self.trigger_autosave)
        
        # Workbench Actions
        wb = self.editorInterface.workbench
        wb.request_translation.connect(self.start_translation)
        wb.request_refinement.connect(self.start_refinement)
        wb.apply_changes.connect(self.apply_workbench_changes)
        
        # QA Actions
        qa = self.editorInterface.qa_panel
        qa.btn_repair.clicked.connect(self.start_batch_repair)
        qa.request_profile_edit.connect(self.open_profile_wizard)
        qa.request_sample.connect(self.generate_sample)

    def switch_to_project_tab(self):
        self.switchTo(self.projectInterface)

    def load_recent_file(self, path):
        """Directly load a recent file, bypassing project wizard for now"""
        # In future, we might want to store project context with the recent file entry
        if self.load_file(path):
            self.switchTo(self.editorInterface)

    def start_new_project(self, path, settings):
        """Called when user starts a project from ProjectInterface"""
        self.project_context = settings.get("context", "")
        
        # Load File
        if self.load_file(path):
            # Apply Settings overrides
            src = settings.get("source_lang")
            tgt = settings.get("target_lang")
            
            # If Auto-Detect, we keep what parser found. Otherwise override.
            if src and src != "Auto-Detect":
                # Update parser or just UI? 
                # For now just UI display in QA panel (which we might hide later)
                # and internal state
                pass
                
            # Switch to Editor
            self.switchTo(self.editorInterface)
            
            # Inject Context into Workbench
            if self.project_context:
                self.editorInterface.workbench.append_message("System", f"<b>Project Context Loaded:</b><br>{self.project_context}")

    def open_profile_wizard(self):
        """Open the Profile Wizard Dialog"""
        # Ensure we have a profile object (create default if None)
        if not self.current_profile:
            from core.profile import TranslationProfile
            self.current_profile = TranslationProfile()
            
        wiz = ProfileWizardDialog(self.current_profile, self)
        if wiz.exec():
            self.current_profile = wiz.get_profile()
            QMessageBox.information(self, "Profile Updated", "Translation profile has been updated.")
            
    def generate_sample(self):
        """Run Sample Translation"""
        if not self.editorInterface.table.units:
            return
            
        qa = self.editorInterface.qa_panel
        src = qa.combo_src.currentText()
        tgt = qa.combo_tgt.currentText()
        
        try:
            client_config = self.get_client_config("translation")
            self.sample_worker = SampleWorker(
                self.editorInterface.table.units, 
                client_config, 
                src, 
                tgt, 
                self.current_profile
            )
            self.sample_worker.finished.connect(self.on_sample_ready)
            self.sample_worker.start()
            
            self.editorInterface.workbench.append_message("System", "Generating sample draft...")
            
        except Exception as e:
            QMessageBox.critical(self, "Sample Error", str(e))

    def get_client_config(self, task="translation"):
        # Helper to get raw config dict for workers that init their own client
        p = self.config.get_profile_by_task(task)
        if not p:
             raise ValueError(f"No model configured for task: {task}")
        return {
            "api_key": p.get("api_key"),
            "base_url": p.get("base_url"),
            "model": p.get("model"),
            "provider": p.get("provider", "custom")
        }

    def on_sample_ready(self, samples):
        # Display samples in Workbench or separate dialog
        # For now, append to chat
        wb = self.editorInterface.workbench
        wb.append_message("System", f"<b>Sample Draft Generated ({len(samples)} segments):</b>")
        for s in samples:
            wb.append_message("AI", f"<i>Source: {s['source']}</i><br><b>Target: {s['translation']}</b><br>---")

    def get_client(self, task="translation"):
        # Helper to get client from AppConfig
        # Need to migrate get_client_for_task logic from desktop_app.py or duplicate here
        # For now duplicating simply:
        p = self.config.get_profile_by_task(task)
        if not p:
             raise ValueError(f"No model configured for task: {task}")
        
        from ai.client import LLMClient
        return LLMClient(
            api_key=p.get("api_key"),
            base_url=p.get("base_url"),
            model=p.get("model"),
            provider=p.get("provider", "custom")
        )

    def start_translation(self, unit):
        try:
            client = self.get_client("translation")
            # Need context tokens? 
            # In a real app we'd get them from Profile or Analysis
            # For now passing empty tokens
            
            self.trans_worker = TranslationWorker([unit], client, {}, self.config.settings)
            self.trans_worker.segment_translated.connect(self.on_segment_translated)
            self.trans_worker.error.connect(lambda e: self.editorInterface.workbench.append_message("System", f"Error: {e}"))
            self.trans_worker.start()
        except Exception as e:
            QMessageBox.critical(self, "Config Error", str(e))

    def on_segment_translated(self, unit_id, target, state):
        # Find unit and update
        # Since we passed the unit object, we can update it directly?
        # But thread safety... TranslationWorker emits ID.
        # We need to find unit by ID
        # For single unit translation, we know it's the current one in workbench
        wb = self.editorInterface.workbench
        if wb.current_unit and wb.current_unit.id == unit_id:
            wb.txt_target.setText(target)
            wb.append_message("AI", f"Translation: {target}")

    def start_refinement(self, unit):
        try:
            client = self.get_client("translation") # Or specific refinement model
            self.refine_worker = RefineWorker(unit, client)
            self.refine_worker.refined.connect(self.on_segment_refined)
            self.refine_worker.start()
        except Exception as e:
            QMessageBox.critical(self, "Config Error", str(e))

    def on_segment_refined(self, new_text, explanation):
        wb = self.editorInterface.workbench
        wb.txt_target.setText(new_text)
        wb.append_message("AI", f"Refined: {new_text}<br><i>Reason: {explanation}</i>")

    def apply_workbench_changes(self, unit, new_text):
        # Update Table
        # We need to find the index in the model
        # This logic is encapsulated in Table?
        # Let's direct update unit and refresh table
        unit.target_abstracted = new_text
        unit.state = "edited"
        
        # Refresh UI
        # We need to notify the table to repaint this row
        # Iterate to find row? Or Table exposes refresh_unit(unit)?
        # For now, trigger full refresh or smart refresh
        # Let's add refresh_unit to ModernTranslationTable
        self.editorInterface.table.refresh_unit(unit)
        self.editorInterface.workbench.append_message("System", "Applied to table.")

    def start_batch_repair(self):
        # Logic similar to desktop_app.py batch_auto_repair
        pass # To be implemented fully, reusing RepairWorker

    def init_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_current_file)
        QShortcut(QKeySequence("Ctrl+O"), self, self.on_open_file)

    def on_open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open XLIFF", "", "XLIFF (*.xlf *.xliff)")
        if not path: return
        
        self.load_file(path)

    def load_file(self, path):
        try:
            # 1. Parse
            self.parser = XliffParser(path)
            self.parser.load()
            
            # Extract Languages
            src_lang, tgt_lang = self.parser.get_languages()
            # Update Info Label
            if src_lang or tgt_lang:
                s = src_lang if src_lang else "?"
                t = tgt_lang if tgt_lang else "?"
                self.editorInterface.qa_panel.lbl_langs.setText(f"Src: {s} -> Tgt: {t}")
                
                # Keep hidden combos synced for logic
                if src_lang: self.editorInterface.qa_panel.combo_src.setCurrentText(src_lang)
                if tgt_lang: self.editorInterface.qa_panel.combo_tgt.setCurrentText(tgt_lang)
            
            # 2. Abstract
            raw_units = self.parser.get_translation_units()
            units = []
            for u in raw_units:
                res = self.abstractor.abstract(u.source_raw)
                u.source_abstracted = res.abstracted_text
                u.tags_map = res.tags_map
                
                if u.target_raw:
                    res_tgt = self.abstractor.abstract(u.target_raw)
                    u.target_abstracted = res_tgt.abstracted_text
                
                units.append(u)
            
            # 3. Load into UI
            self.editorInterface.load_data(units)
            self.current_file_path = path
            self.setWindowTitle(f"XLIFF AI Assistant Pro - {path}")
            
            # 4. Init Autosave
            self.autosaver = Autosaver(path)
            
            # 5. Add to Recent Files
            self.config.add_recent_file(path)
            
            # 6. Run Initial QA
            self.run_qa_check()
            
            # 7. Return success
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load file:\n{str(e)}")
            return False

    def run_qa_check(self):
        """Runs QA checks on all units and updates UI"""
        if not self.editorInterface.table.units: return
        
        # Run QA synchronously (it's fast for local checks)
        QAService.check_batch(self.editorInterface.table.units)
        
        # Update UI Stats
        errors = len([u for u in self.editorInterface.table.units if u.qa_status == "error"])
        warnings = len([u for u in self.editorInterface.table.units if u.qa_status == "warning"])
        
        # Update QA Panel
        self.editorInterface.qa_panel.lbl_stats.setText(f"Errors: {errors} | Warnings: {warnings}")
        
        # Update Health Bar
        total = len(self.editorInterface.table.units)
        if total > 0:
            health = max(0, 100 - (errors * 5) - (warnings * 1))
            self.editorInterface.qa_panel.progress.setValue(health)
            
            # Color logic
            if errors > 0:
                self.editorInterface.qa_panel.progress.setStyleSheet("QProgressBar::chunk { background-color: #F44336; }")
            elif warnings > 0:
                self.editorInterface.qa_panel.progress.setStyleSheet("QProgressBar::chunk { background-color: #FFC107; }")
            else:
                self.editorInterface.qa_panel.progress.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")
        
        # Refresh Table View to show QA icons
        self.editorInterface.table.viewport().update()

    def save_current_file(self):
        if not self.current_file_path or not self.parser:
            return
            
        try:
            # 1. De-abstract (Inject tags back)
            for u in self.editorInterface.table.units:
                # Target
                if u.target_abstracted:
                    # Logic reuse: In real app, reuse TagAbstractor.deabstract
                    # For now, simple pass-through or implement basic logic
                    # We need access to tags_map
                    # TODO: Implement proper de-abstraction here or in parser
                    # u.target_raw = self.abstractor.deabstract(u.target_abstracted, u.tags_map)
                    
                    # Temporary: just save abstracted text if deabstractor not ready
                    # But desktop_app.py logic was:
                    # u.target_raw = self.abstractor.inject_tags(u.target_abstracted, u.tags_map)
                    u.target_raw = self.abstractor.inject_tags(u.target_abstracted, u.tags_map)
            
            # 2. Update Parser
            self.parser.update_units(self.editorInterface.table.units)
            
            # 3. Write to Disk
            self.parser.save()
            
            # 4. Clear Autosave
            if self.autosaver:
                self.autosaver.clear_autosave()
                
            QMessageBox.information(self, "Saved", "File saved successfully!")
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{str(e)}")

    def trigger_autosave(self):
        if self.autosaver:
            self.autosaver.save(self.editorInterface.table.units)

if __name__ == "__main__":
    # Setup Logging
    from core.logger import get_logger, setup_exception_hook
    setup_exception_hook()
    logger = get_logger("modern_ui")
    
    # Setup Crash Handler
    import faulthandler
    os.makedirs("logs", exist_ok=True)
    crash_file = open("logs/crash_dump.txt", "wb", buffering=0)
    faulthandler.enable(file=crash_file, all_threads=True)
    
    logger.info("Modern UI Application starting...")
    
    app = QApplication(sys.argv)
    
    # Global Tooltip Configuration
    # QToolTip.setShowDelay(0) is not available in PyQt6 directly.
    # We rely on ToolTipFilter for specific widgets.
    
    window = ModernMainWindow()
    window.show()
    
    # SplashScreen logic handled inside ModernMainWindow or here?
    # Since ModernMainWindow is a FluentWindow, we can do it inside __init__
    # or here. But we need to close it after initialization.
    # Let's keep the logic inside ModernMainWindow to encapsulate it.
    
    sys.exit(app.exec())
