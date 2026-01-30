from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from qfluentwidgets import (SubtitleLabel, BodyLabel, CardWidget, IconWidget, 
                            PrimaryPushButton, SearchLineEdit, FluentIcon as FIF,
                            SingleDirectionScrollArea)

class HomeInterface(SingleDirectionScrollArea):
    """
    Home Interface: Recent files, Quick Actions, Project Overview.
    """
    open_file_clicked = pyqtSignal()
    recent_file_clicked = pyqtSignal(str) # New signal for recent files
    
    def __init__(self, parent=None):
        super().__init__(parent=parent, orient=Qt.Orientation.Vertical)
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setObjectName("HomeInterface")
        
        self.v_layout = QVBoxLayout(self.view)
        self.v_layout.setContentsMargins(36, 36, 36, 36)
        self.v_layout.setSpacing(20)
        
        self.init_header()
        self.init_quick_actions()
        self.init_recent_files()
        
        self.v_layout.addStretch()
        
        self.view.setStyleSheet("background: transparent;")

    def init_header(self):
        title = SubtitleLabel("Welcome to XLIFF AI Assistant", self)
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        self.v_layout.addWidget(title)
        
        desc = BodyLabel("Your intelligent companion for localization and translation tasks.", self)
        desc.setStyleSheet("color: #666666; font-size: 16px;")
        self.v_layout.addWidget(desc)

    def init_quick_actions(self):
        self.v_layout.addSpacing(10)
        self.v_layout.addWidget(BodyLabel("Quick Actions", self))
        
        layout = QHBoxLayout()
        layout.setSpacing(16)
        
        # Open File Action
        self.action_open = self.create_action_card(
            "Open File", 
            "Import .xliff to start translating", 
            FIF.FOLDER
        )
        self.action_open.clicked.connect(self.open_file_clicked)
        layout.addWidget(self.action_open)
        
        # New Project Action (Placeholder)
        self.action_new = self.create_action_card(
            "New Project", 
            "Create a new workspace from scratch", 
            FIF.ADD
        )
        layout.addWidget(self.action_new)
        
        layout.addStretch()
        self.v_layout.addLayout(layout)

    def create_action_card(self, title, desc, icon):
        card = CardWidget(self)
        card.setFixedSize(240, 100)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        
        h = QHBoxLayout(card)
        h.setContentsMargins(20, 10, 20, 10)
        
        icon_w = IconWidget(icon, card)
        icon_w.setFixedSize(36, 36)
        h.addWidget(icon_w)
        
        v = QVBoxLayout()
        v.setSpacing(0)
        lbl_title = BodyLabel(title, card)
        lbl_title.setStyleSheet("font-weight: bold; font-size: 15px;")
        v.addWidget(lbl_title)
        
        lbl_desc = BodyLabel(desc, card)
        lbl_desc.setStyleSheet("color: #888888; font-size: 12px;")
        lbl_desc.setWordWrap(True)
        v.addWidget(lbl_desc)
        
        h.addLayout(v)
        return card

    def init_recent_files(self):
        self.v_layout.addSpacing(20)
        self.v_layout.addWidget(BodyLabel("Recent Files", self))
        
        self.recent_layout = QVBoxLayout()
        self.recent_layout.setSpacing(10)
        
        # Load from config
        from core.config.app_config import AppConfig
        config = AppConfig()
        files = config.recent_files
        
        if not files:
            self.recent_layout.addWidget(BodyLabel("No recent files found.", self).setStyleSheet("color: gray;"))
        else:
            for path in files:
                import os
                name = os.path.basename(path)
                self.add_recent_item(name, path)
        
        self.v_layout.addLayout(self.recent_layout)

    def add_recent_item(self, name, path):
        # Create a simple clickable card or button
        from qfluentwidgets import PushButton
        btn = PushButton(f"{name}  ({path})", self)
        btn.setStyleSheet("text-align: left; padding-left: 10px;")
        btn.clicked.connect(lambda: self.open_recent_file(path))
        self.recent_layout.addWidget(btn)

    def open_recent_file(self, path):
        # We need to signal main window to open this file
        # But we only have open_file_clicked signal which takes no args
        # Let's verify if path exists first
        import os
        if os.path.exists(path):
            # Hack: emit signal, but we need a way to pass path
            # Or add a new signal
            self.recent_file_clicked.emit(path)
        else:
            # Show error?
            pass