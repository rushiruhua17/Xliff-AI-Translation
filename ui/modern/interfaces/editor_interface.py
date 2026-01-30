from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSplitter, QLabel, QFrame
from PyQt6.QtCore import Qt
from qfluentwidgets import BodyLabel

from ui.modern.widgets.translation_table import ModernTranslationTable
from ui.modern.widgets.ai_workbench import ModernWorkbench
from ui.modern.widgets.qa_panel import ModernQAPanel

class EditorInterface(QWidget):
    """
    Core Editor Interface:
    - Top: QA Panel & Translation Table (Grid)
    - Bottom: AI Workbench (Chat & Diff)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("EditorInterface")
        
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.v_layout.setSpacing(0)
        
        # QA Panel (Top Bar)
        self.qa_panel = ModernQAPanel(self)
        self.v_layout.addWidget(self.qa_panel)
        
        # Main Splitter
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(2)
        
        # 1. Top: Table Area
        self.table_container = QFrame()
        self.table_container.setStyleSheet("background: transparent;")
        table_layout = QVBoxLayout(self.table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        # Instantiate Modern Translation Table
        self.table = ModernTranslationTable(self.table_container)
        table_layout.addWidget(self.table)
        
        self.splitter.addWidget(self.table_container)
        
        # 2. Bottom: Workbench Area
        self.bench_container = QFrame()
        self.bench_container.setStyleSheet("background: #F9F9F9; border-top: 1px solid #E5E5E5;") 
        bench_layout = QVBoxLayout(self.bench_container)
        bench_layout.setContentsMargins(0, 0, 0, 0)
        
        # Instantiate Workbench
        self.workbench = ModernWorkbench(self.bench_container)
        bench_layout.addWidget(self.workbench)
        
        self.splitter.addWidget(self.bench_container)
        
        self.splitter.setSizes([600, 300])
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, True)
        
        self.v_layout.addWidget(self.splitter)
        
        # Wire Signals
        self.table.selection_changed.connect(self.workbench.set_context)
        
        # Connect QA Panel Filters to Table
        self.qa_panel.search_changed.connect(self.table.filter_text)
        self.qa_panel.filter_changed.connect(self.table.filter_status)
        
    def load_data(self, units):
        """Pass data to the table widget"""
        self.table.load_data(units)
