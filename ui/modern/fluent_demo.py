import sys
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel

# 引入 Fluent Widgets
from qfluentwidgets import (FluentWindow, NavigationItemPosition, FluentIcon as FIF,
                            NavigationInterface, SubtitleLabel, BodyLabel, 
                            CardWidget, IconWidget, PrimaryPushButton, 
                            TransparentPushButton, SearchLineEdit)

class HomeInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("HomeInterface")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = SubtitleLabel("Welcome back, User", self)
        layout.addWidget(title)
        
        desc = BodyLabel("Manage your translation projects and workspaces.", self)
        desc.setStyleSheet("color: #666666;")
        layout.addWidget(desc)
        layout.addSpacing(20)
        
        # Search Bar
        search = SearchLineEdit(self)
        search.setPlaceholderText("Search projects...")
        layout.addWidget(search)
        layout.addSpacing(20)
        
        # Recent Projects (Cards)
        layout.addWidget(BodyLabel("Recent Projects", self))
        
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(15)
        
        for name in ["Manual_v2.xliff", "Website_Strings.xml", "Marketing_2026.xliff"]:
            card = CardWidget(self)
            card.setFixedSize(200, 120)
            
            c_layout = QVBoxLayout(card)
            
            icon = IconWidget(FIF.DOCUMENT, card)
            icon.setFixedSize(32, 32)
            c_layout.addWidget(icon)
            
            c_layout.addWidget(BodyLabel(name, card))
            c_layout.addWidget(QLabel("Last edited: 2 mins ago", card))
            
            btn = PrimaryPushButton("Open", card)
            c_layout.addWidget(btn)
            
            cards_layout.addWidget(card)
            
        cards_layout.addStretch()
        layout.addLayout(cards_layout)
        layout.addStretch()

class ModernWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XLIFF AI Assistant (Fluent Design)")
        self.resize(1100, 750)
        
        # Enable Mica effect (Windows 11 only)
        self.windowEffect.setMicaEffect(self.winId())

        # Create sub-interfaces
        self.homeInterface = HomeInterface(self)
        self.editorInterface = QWidget() # Placeholder
        self.editorInterface.setObjectName("EditorInterface")
        
        self.chatInterface = QWidget() # Placeholder
        self.chatInterface.setObjectName("ChatInterface")

        self.initNavigation()

    def initNavigation(self):
        # Add items to sidebar
        self.addSubInterface(self.homeInterface, FIF.HOME, "Home")
        self.addSubInterface(self.editorInterface, FIF.EDIT, "Editor")
        self.addSubInterface(self.chatInterface, FIF.CHAT, "AI Assistant")
        
        self.navigationInterface.addSeparator()
        
        # Settings at bottom
        settingsInterface = QWidget()
        settingsInterface.setObjectName("SettingsInterface")
        self.addSubInterface(settingsInterface, FIF.SETTING, "Settings", NavigationItemPosition.BOTTOM)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernWindow()
    window.show()
    sys.exit(app.exec())
