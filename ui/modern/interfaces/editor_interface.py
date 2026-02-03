from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QFrame
from PyQt6.QtCore import Qt
from qfluentwidgets import BodyLabel

from ui.modern.widgets.translation_table import ModernTranslationTable
from ui.modern.widgets.ai_copilot_sidebar import AICopilotSidebar
from ui.modern.widgets.qa_panel import ModernQAPanel

class EditorInterface(QWidget):
    """
    Core Editor Interface:
    - Left: QA Panel & Translation Table (Vertical)
    - Right: AI Copilot Sidebar
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("EditorInterface")
        
        self.h_layout = QHBoxLayout(self)
        self.h_layout.setContentsMargins(0, 0, 0, 0)
        self.h_layout.setSpacing(0)
        
        # Main Splitter (Horizontal)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        
        # 1. Left Area: QA Panel + Table
        self.left_container = QWidget()
        left_layout = QVBoxLayout(self.left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # QA Panel
        self.qa_panel = ModernQAPanel(self)
        left_layout.addWidget(self.qa_panel)
        
        # Table
        self.table_container = QFrame()
        self.table_container.setStyleSheet("background: transparent;")
        table_layout = QVBoxLayout(self.table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        self.table = ModernTranslationTable(self.table_container)
        table_layout.addWidget(self.table)
        
        left_layout.addWidget(self.table_container)
        
        self.splitter.addWidget(self.left_container)
        
        # 2. Right Area: AI Copilot Sidebar
        self.right_container = QWidget()
        self.right_container.setMinimumWidth(320)
        self.right_container.setStyleSheet("background: #F9F9F9; border-left: 1px solid #E5E5E5;")
        right_layout = QVBoxLayout(self.right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.sidebar = AICopilotSidebar(self.right_container)
        right_layout.addWidget(self.sidebar)
        
        self.splitter.addWidget(self.right_container)
        
        # Set Splitter Ratios (70% Left, 30% Right)
        self.splitter.setStretchFactor(0, 7)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setCollapsible(1, True)
        
        self.h_layout.addWidget(self.splitter)
        
        # Wire Signals
        self.table.selection_changed.connect(self.on_selection_changed)
        
        # Workbench (Legacy reference for compatibility)
        # We map sidebar to workbench property to minimize breakage in main_window.py
        # But main_window expects 'workbench.request_translation' etc.
        # We need to bridge signals or update main_window.
        # Let's alias sidebar as workbench for now, but Sidebar has different signals.
        self.workbench = self.sidebar 
        
        # Connect QA Panel Filters to Table
        self.qa_panel.search_changed.connect(self.table.filter_text)
        
    def on_selection_changed(self, unit):
        # Update Sidebar Context
        # TODO: Support multi-selection count
        self.sidebar.update_context(1 if unit else 0)

    def load_data(self, units):
        """Pass data to the table widget"""
        self.table.load_data(units)
