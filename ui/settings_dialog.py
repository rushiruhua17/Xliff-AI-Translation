from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget, 
                             QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from core.config.app_config import AppConfig
from ui.modern.settings.model_page import ModelSettingsPage

class SettingsDialog(QDialog):
    settings_changed = pyqtSignal() # Signal to notify main app of updates

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(900)
        self.setMinimumHeight(600)
        
        self.config = AppConfig()
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Tab 1: Model Services (New Modern UI)
        self.model_page = ModelSettingsPage(self.config, self)
        self.tabs.addTab(self.model_page, "Model Services")
        
        # Tab 2: General (Placeholder for now)
        # self.general_tab = QWidget()
        # self.tabs.addTab(self.general_tab, "General")
        
        # Bottom Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save & Close")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def save_settings(self):
        # 1. Save Model Page
        self.model_page.save_settings()
        
        # 2. Sync Config to Disk
        self.config.sync()
        
        self.settings_changed.emit()
        self.accept()
