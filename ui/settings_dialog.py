from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QComboBox, QPushButton, QTabWidget, 
                             QWidget, QMessageBox, QFormLayout, QGroupBox, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal
from core.settings_manager import SettingsManager
from core.workers import TestConnectionWorker
from ai.client import LLMClient

class SettingsDialog(QDialog):
    settings_changed = pyqtSignal() # Signal to notify main app of updates

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self.settings_manager = SettingsManager()
        self.test_worker = None # Keep reference
        
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Tab 1: LLM Providers
        self.provider_tab = QWidget()
        self.init_provider_tab()
        self.tabs.addTab(self.provider_tab, "LLM Providers")
        
        # Tab 2: General (Placeholder for now)
        # self.general_tab = QWidget()
        # self.tabs.addTab(self.general_tab, "General")
        
        # Bottom Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def init_provider_tab(self):
        layout = QVBoxLayout(self.provider_tab)
        
        # Provider Selector
        sel_layout = QHBoxLayout()
        sel_layout.addWidget(QLabel("Active Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.currentIndexChanged.connect(self.on_provider_changed)
        sel_layout.addWidget(self.provider_combo)
        layout.addLayout(sel_layout)
        
        # Config Group
        self.config_group = QGroupBox("Provider Configuration")
        form_layout = QFormLayout(self.config_group)
        
        self.base_url_edit = QLineEdit()
        self.model_edit = QLineEdit() # Comma separated
        self.model_edit.setPlaceholderText("gpt-4o, gpt-3.5-turbo")
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("Enter API Key")
        
        form_layout.addRow("Base URL:", self.base_url_edit)
        form_layout.addRow("Models (CSV):", self.model_edit)
        form_layout.addRow("API Key:", self.api_key_edit)
        
        layout.addWidget(self.config_group)
        
        # Test Connection
        test_layout = QHBoxLayout()
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self.test_connection)
        test_layout.addStretch()
        test_layout.addWidget(self.test_btn)
        layout.addLayout(test_layout)
        
        layout.addStretch()

    def load_settings(self):
        config = self.settings_manager.config
        providers = config.get("providers", {}).keys()
        
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()
        self.provider_combo.addItems(providers)
        
        current = self.settings_manager.get_active_provider()
        idx = self.provider_combo.findText(current)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        self.provider_combo.blockSignals(False)
        
        self.on_provider_changed()

    def on_provider_changed(self):
        provider = self.provider_combo.currentText()
        if not provider:
            return
            
        config = self.settings_manager.get_provider_config(provider)
        self.base_url_edit.setText(config.get("base_url", ""))
        self.model_edit.setText(", ".join(config.get("models", [])))
        
        # Load Key
        key = self.settings_manager.get_api_key(provider)
        self.api_key_edit.setText(key if key else "")

    def save_settings(self):
        provider = self.provider_combo.currentText()
        if not provider:
            return

        # 1. Save Config
        base_url = self.base_url_edit.text().strip()
        models = [m.strip() for m in self.model_edit.text().split(",") if m.strip()]
        
        self.settings_manager.set_provider_config(provider, base_url, models)
        self.settings_manager.set_active_provider(provider)
        
        # 2. Save Key
        key = self.api_key_edit.text().strip()
        self.settings_manager.set_api_key(provider, key)
        
        self.settings_changed.emit()
        self.accept()

    def test_connection(self):
        # 1. Gather current values from UI (not saved config)
        provider = self.provider_combo.currentText()
        base_url = self.base_url_edit.text().strip()
        key = self.api_key_edit.text().strip()
        model_csv = self.model_edit.text().strip()
        
        # Parse first model as default for testing
        models = [m.strip() for m in model_csv.split(",") if m.strip()]
        default_model = models[0] if models else "gpt-3.5-turbo"
        
        if not key:
             QMessageBox.warning(self, "Test Failed", "Please enter an API Key first.")
             return
             
        # 2. Disable UI
        self.test_btn.setEnabled(False)
        self.test_btn.setText("Testing...")
        
        # 3. Create Temp Client
        try:
            # We construct a client explicitly with these params
            client = LLMClient(
                api_key=key,
                base_url=base_url,
                model=default_model,
                provider="custom" # Force custom to use OpenAI lib logic
            )
            
            # 4. Run Worker
            self.test_worker = TestConnectionWorker(client)
            self.test_worker.finished.connect(self.on_test_finished)
            self.test_worker.start()
            
        except Exception as e:
            self.on_test_finished(False, str(e))

    def on_test_finished(self, success, message):
        self.test_btn.setEnabled(True)
        self.test_btn.setText("Test Connection")
        
        if success:
            QMessageBox.information(self, "Connection Successful", message)
        else:
            QMessageBox.critical(self, "Connection Failed", f"Could not connect:\n{message}")
