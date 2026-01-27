from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QPushButton, QTextEdit, QSplitter, 
                             QFrame, QSizePolicy, QToolButton)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QPainter, QAction, QIcon
import difflib

class StatusIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self._status = "gray" # gray, green, yellow, red

    def set_status(self, status: str):
        self._status = status
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        color_map = {
            "green": QColor("#28a745"),
            "yellow": QColor("#ffc107"),
            "red": QColor("#dc3545"),
            "gray": QColor("#6c757d")
        }
        color = color_map.get(self._status, QColor("gray"))
        
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 12, 12)

class AIWorkbenchFrame(QWidget):
    request_apply = pyqtSignal(str) # Signal to apply translation (text)
    request_context = pyqtSignal()  # Signal to request context from main app

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # --- Header ---
        header_layout = QHBoxLayout()
        
        self.model_combo = QComboBox()
        self.model_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        self.status_indicator = StatusIndicator()
        self.status_indicator.setToolTip("Connection Status")
        
        self.settings_btn = QToolButton()
        self.settings_btn.setText("⚙") # Use icon in real app
        self.settings_btn.setToolTip("Open Settings")
        
        header_layout.addWidget(QLabel("Model:"))
        header_layout.addWidget(self.model_combo)
        header_layout.addWidget(self.status_indicator)
        header_layout.addWidget(self.settings_btn)
        
        layout.addLayout(header_layout)

        # --- Chat Area ---
        chat_group = QVBoxLayout()
        chat_group.addWidget(QLabel("Chat / Context:"))
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText("AI responses will appear here...")
        
        self.add_context_btn = QPushButton("Add Context from Editor")
        self.add_context_btn.clicked.connect(self.request_context.emit)
        
        self.chat_input = QTextEdit()
        self.chat_input.setMaximumHeight(80)
        self.chat_input.setPlaceholderText("Type instructions (e.g. 'Make it formal')...")
        
        self.send_btn = QPushButton("Send / Translate")
        
        chat_group.addWidget(self.chat_display)
        chat_group.addWidget(self.add_context_btn)
        chat_group.addWidget(self.chat_input)
        chat_group.addWidget(self.send_btn)
        
        # Use a splitter for Chat vs Diff to allow resizing
        # But per requirements, keep it simple first.
        layout.addLayout(chat_group, stretch=2)

        # --- Diff Area ---
        layout.addWidget(QLabel("Diff View:"))
        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setPlaceholderText("Diff will appear here...")
        self.diff_view.setMaximumHeight(150)
        layout.addWidget(self.diff_view)

        # --- Footer ---
        self.apply_btn = QPushButton("Apply to Editor")
        self.apply_btn.setEnabled(False) # Blocked by default
        self.apply_btn.clicked.connect(self.on_apply)
        
        layout.addWidget(self.apply_btn)

    def update_diff(self, old_text: str, new_text: str):
        diff = difflib.unified_diff(
            old_text.splitlines(), 
            new_text.splitlines(), 
            lineterm=""
        )
        self.diff_view.setPlainText("\n".join(diff))
        
    def on_apply(self):
        # Emit signal with the current diff content (new text)
        # We need to extract the "New" text from the diff or store it separately
        # Better: Store the pending_new_text when update_diff is called
        if hasattr(self, 'pending_new_text'):
            self.request_apply.emit(self.pending_new_text)

    def set_context(self, source: str, target: str, tokens: list):
        """Called by Main App to populate context"""
        self.chat_display.append(f"<b>[Context Loaded]</b><br>Source: {source}<br>Target: {target}")
        self.pending_source = source
        self.pending_target = target
        self.pending_tokens = tokens
        self.diff_view.clear()
        self.apply_btn.setEnabled(False)

    def get_prompt_payload(self) -> dict:
        return {
            "source": getattr(self, 'pending_source', ""),
            "target": getattr(self, 'pending_target', ""),
            "tokens": getattr(self, 'pending_tokens', []),
            "instruction": self.chat_input.toPlainText()
        }

    def append_ai_response(self, text: str):
        self.chat_display.append(f"<br><b>AI:</b> {text}")
        
    def set_loading(self, loading: bool):
        self.send_btn.setEnabled(not loading)
        self.send_btn.setText("Thinking..." if loading else "Send / Translate")
