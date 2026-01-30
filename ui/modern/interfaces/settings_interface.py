from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget, 
                             QMessageBox, QLabel)
from PyQt6.QtCore import Qt, pyqtSignal
from qfluentwidgets import TitleLabel, PrimaryPushButton

from core.config.app_config import AppConfig
from ui.modern.settings.model_page import ModelSettingsPage

class SettingsInterface(QWidget):
    """
    Embedded Settings Page for ModernMainWindow.
    Replaces the old modal SettingsDialog.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsInterface")
        self.config = AppConfig()
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(TitleLabel("Settings", self))
        header_layout.addStretch()
        
        # Global Save Button (Optional, if we want explicit save)
        # In modern apps, changes might be instant, but for config safety we keep explicit save
        self.btn_save = PrimaryPushButton("Save All Changes", self)
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_save.setFixedWidth(150)
        header_layout.addWidget(self.btn_save)
        
        layout.addLayout(header_layout)
        
        # Content Tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Tab 1: Model Services
        self.model_page = ModelSettingsPage(self.config, self)
        self.tabs.addTab(self.model_page, "Model Services")
        
        # Tab 2: General (Placeholder)
        self.general_page = QWidget()
        self.init_general_page()
        self.tabs.addTab(self.general_page, "General")
        
    def init_general_page(self):
        layout = QVBoxLayout(self.general_page)
        layout.addWidget(QLabel("General application settings will appear here."))
        layout.addStretch()
        
    def save_settings(self):
        try:
            # 1. Save Model Page
            self.model_page.save_settings()
            
            # 2. Sync Config to Disk
            self.config.sync()
            
            # 3. Notify User
            QMessageBox.information(self, "Settings Saved", "Configuration has been updated successfully.")
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))
