from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QMenu, QToolButton
from PyQt6.QtGui import QAction
from PyQt6.QtCore import pyqtSignal
from qfluentwidgets import (CardWidget, StrongBodyLabel, CaptionLabel, ProgressBar, 
                            PrimaryPushButton, SearchLineEdit, RadioButton, SegmentedWidget,
                            ComboBox, ToolButton, FluentIcon as FIF, ToolTipFilter, ToolTipPosition,
                            PushButton)

class ModernQAPanel(QWidget):
    """
    Dashboard for QA Status & Batch Actions.
    Also hosts Search & Filter controls and Language Selection.
    """
    
    filter_changed = pyqtSignal(str) # "All", "Untranslated", etc.
    search_changed = pyqtSignal(str) # text
    request_profile_edit = pyqtSignal()
    request_batch_translation = pyqtSignal()
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
        
        self.combo_src = ComboBox()
        self.combo_src.setVisible(False)
        self.combo_tgt = ComboBox()
        self.combo_tgt.setVisible(False)
        
        # Search Bar
        self.search_bar = SearchLineEdit(self)
        self.search_bar.setPlaceholderText("Search source or target...")
        self.search_bar.setToolTip("Search text in source or target segments")
        self.search_bar.setFixedWidth(200)
        self.search_bar.textChanged.connect(self.search_changed)
        
        layout.addWidget(self.search_bar)

        self.lbl_translate_progress = CaptionLabel("", self)
        self.lbl_translate_progress.setVisible(False)
        layout.addWidget(self.lbl_translate_progress)

        self.translate_progress = ProgressBar(self)
        self.translate_progress.setFixedWidth(180)
        self.translate_progress.setFixedHeight(6)
        self.translate_progress.setVisible(False)
        layout.addWidget(self.translate_progress)
        
        layout.addStretch()
        
        # Actions
        self.btn_translate_all = PrimaryPushButton("Translate All", self)
        self.btn_translate_all.setIcon(FIF.LANGUAGE)
        self.btn_translate_all.setToolTip("Batch translate all untranslated segments")
        self.btn_translate_all.clicked.connect(self.request_batch_translation)
        layout.addWidget(self.btn_translate_all)

        self.btn_profile = ToolButton(FIF.PEOPLE, self)
        self.btn_profile.setToolTip("Edit Translation Profile (Tone, Audience, etc.)")
        self.btn_profile.clicked.connect(self.request_profile_edit)
        layout.addWidget(self.btn_profile)

        self.btn_repair = PushButton("Batch Repair", self)
        self.btn_repair.setIcon(FIF.EDIT)
        self.btn_repair.setToolTip("Automatically fix tag errors in all segments")
        layout.addWidget(self.btn_repair)
        
        # More Actions
        self.btn_more = ToolButton(FIF.MORE, self)
        self.btn_more.setToolTip("More Options")
        self.btn_more.installEventFilter(ToolTipFilter(self.btn_more, showDelay=50, position=ToolTipPosition.BOTTOM))
        
        # Menu
        self.menu_more = QMenu(self)
        
        action_sample = QAction("🎲 Draft Sample", self)
        action_sample.triggered.connect(self.request_sample)
        
        self.menu_more.addAction(action_sample)
        
        self.btn_more.setMenu(self.menu_more)
        self.btn_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        layout.addWidget(self.btn_more)

    def start_translation_progress(self, total: int):
        self.lbl_translate_progress.setText(f"Translating: 0/{total}")
        self.lbl_translate_progress.setVisible(True)
        self.translate_progress.setVisible(True)
        self.translate_progress.setValue(0)

    def update_translation_progress(self, current: int, total: int):
        if total <= 0:
            return
        pct = int((current / total) * 100)
        pct = max(0, min(100, pct))
        self.lbl_translate_progress.setText(f"Translating: {current}/{total}")
        self.translate_progress.setValue(pct)

    def finish_translation_progress(self, message: str = "Done"):
        self.lbl_translate_progress.setText(message)
        self.translate_progress.setValue(100)
