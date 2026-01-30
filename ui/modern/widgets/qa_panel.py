from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QMenu, QToolButton
from PyQt6.QtGui import QAction
from PyQt6.QtCore import pyqtSignal
from qfluentwidgets import (CardWidget, StrongBodyLabel, CaptionLabel, ProgressBar, 
                            PrimaryPushButton, SearchLineEdit, RadioButton, SegmentedWidget,
                            ComboBox, ToolButton, FluentIcon)

class ModernQAPanel(QWidget):
    """
    Dashboard for QA Status & Batch Actions.
    Also hosts Search & Filter controls and Language Selection.
    """
    
    filter_changed = pyqtSignal(str) # "All", "Untranslated", etc.
    search_changed = pyqtSignal(str) # text
    request_profile_edit = pyqtSignal()
    request_sample = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)
        
        # Stats Card
        self.stats_card = CardWidget(self)
        self.stats_card.setFixedSize(180, 50)
        c_layout = QVBoxLayout(self.stats_card)
        c_layout.setContentsMargins(10, 5, 10, 5)
        c_layout.setSpacing(2)
        
        self.lbl_stats = CaptionLabel("Errors: 0 | Warnings: 0", self.stats_card)
        self.progress = ProgressBar(self.stats_card)
        self.progress.setValue(100)
        self.progress.setFixedHeight(4)
        
        c_layout.addWidget(self.lbl_stats)
        c_layout.addWidget(self.progress)
        
        layout.addWidget(self.stats_card)
        
        # Language Selectors
        self.combo_src = ComboBox()
        self.combo_src.addItems(["en", "zh-CN", "ja", "de", "fr"])
        self.combo_src.setToolTip("Source Language")
        self.combo_src.setFixedWidth(80)
        
        self.combo_tgt = ComboBox()
        self.combo_tgt.addItems(["en", "zh-CN", "ja", "de", "fr"])
        self.combo_tgt.setToolTip("Target Language")
        self.combo_tgt.setFixedWidth(80)
        
        layout.addWidget(CaptionLabel("Src:", self))
        layout.addWidget(self.combo_src)
        layout.addWidget(CaptionLabel("Tgt:", self))
        layout.addWidget(self.combo_tgt)
        
        # Filter Segment
        self.seg_filter = SegmentedWidget(self)
        self.seg_filter.addItem("All", "All")
        self.seg_filter.addItem("Untranslated", "Untranslated")
        self.seg_filter.addItem("Translated", "Translated")
        self.seg_filter.addItem("Edited", "Edited")
        self.seg_filter.setCurrentItem("All")
        self.seg_filter.currentItemChanged.connect(lambda k: self.filter_changed.emit(k))
        
        layout.addWidget(self.seg_filter)
        
        # Search Bar
        self.search_bar = SearchLineEdit(self)
        self.search_bar.setPlaceholderText("Search source or target...")
        self.search_bar.setFixedWidth(200)
        self.search_bar.textChanged.connect(self.search_changed)
        
        layout.addWidget(self.search_bar)
        
        layout.addStretch()
        
        # Actions
        self.btn_repair = PrimaryPushButton("🔧 Batch Repair", self)
        layout.addWidget(self.btn_repair)
        
        # More Actions
        self.btn_more = ToolButton(FluentIcon.MORE, self)
        self.btn_more.setToolTip("More Actions")
        
        # Menu
        self.menu_more = QMenu(self)
        action_profile = QAction("📋 Edit Profile", self)
        action_profile.triggered.connect(self.request_profile_edit)
        
        action_sample = QAction("🎲 Draft Sample", self)
        action_sample.triggered.connect(self.request_sample)
        
        self.menu_more.addAction(action_profile)
        self.menu_more.addAction(action_sample)
        
        self.btn_more.setMenu(self.menu_more)
        self.btn_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        layout.addWidget(self.btn_more)
