import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QListWidget, QTextEdit, QSplitter, 
                             QLabel, QPushButton, QFrame)
from PyQt6.QtCore import Qt

class ModernSidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #2D2D2D; color: #CCCCCC;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Workspace Header
        header = QLabel(" WORKSPACES")
        header.setStyleSheet("padding: 10px; font-weight: bold; color: #888888;")
        layout.addWidget(header)
        
        # Workspace List
        self.list = QListWidget()
        self.list.setStyleSheet("border: none; background: transparent;")
        self.list.addItems(["Project Alpha", "Marketing Docs", "Technical Manuals"])
        layout.addWidget(self.list)
        
        # History Section
        header2 = QLabel(" RECENT FILES")
        header2.setStyleSheet("padding: 10px; font-weight: bold; color: #888888;")
        layout.addWidget(header2)
        
        self.history = QListWidget()
        self.history.setStyleSheet("border: none; background: transparent;")
        self.history.addItems(["user_guide.xliff", "strings.xml", "website_en.xliff"])
        layout.addWidget(self.history)
        
        # Bottom Settings
        btn_settings = QPushButton("⚙️ Settings")
        btn_settings.setStyleSheet("text-align: left; padding: 10px; border: none;")
        layout.addWidget(btn_settings)

class ModernWorkspace(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter: Top (Grid) / Bottom (Chat)
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 1. Translation Grid Mockup
        grid_container = QFrame()
        grid_container.setStyleSheet("background-color: #1E1E1E;")
        v = QVBoxLayout(grid_container)
        v.addWidget(QLabel("📝 Translation Editor (Grid View)"))
        # Placeholder for actual table
        table_mock = QTextEdit("Source | Target\nHello | 你好\nWorld | 世界")
        table_mock.setReadOnly(True)
        v.addWidget(table_mock)
        splitter.addWidget(grid_container)
        
        # 2. AI Chat Mockup
        chat_container = QFrame()
        chat_container.setStyleSheet("background-color: #252526;")
        v2 = QVBoxLayout(chat_container)
        v2.addWidget(QLabel("🤖 AI Assistant (Context Aware)"))
        chat_mock = QTextEdit("User: Translate this.\nAI: Sure! Here is the translation...")
        chat_mock.setReadOnly(True)
        v2.addWidget(chat_mock)
        
        input_area = QTextEdit()
        input_area.setPlaceholderText("Ask AI to refine translation...")
        input_area.setMaximumHeight(60)
        v2.addWidget(input_area)
        
        splitter.addWidget(chat_container)
        splitter.setSizes([600, 300]) # Initial ratio
        
        layout.addWidget(splitter)

class ModernMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XLIFF AI Assistant - Modern UI Prototype")
        self.resize(1200, 800)
        
        # Main Layout: Sidebar | Content
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.sidebar = ModernSidebar()
        self.workspace = ModernWorkspace()
        
        main_splitter.addWidget(self.sidebar)
        main_splitter.addWidget(self.workspace)
        
        # Set Sidebar width
        main_splitter.setSizes([250, 950])
        main_splitter.setCollapsible(0, False)
        
        self.setCentralWidget(main_splitter)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Apply a dark theme base
    app.setStyle("Fusion")
    
    window = ModernMainWindow()
    window.show()
    sys.exit(app.exec())
