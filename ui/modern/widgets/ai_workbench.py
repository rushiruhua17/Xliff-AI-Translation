from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
                             QLabel, QFrame, QSplitter)
from PyQt6.QtCore import Qt, pyqtSignal
from qfluentwidgets import (StrongBodyLabel, BodyLabel, PrimaryPushButton, 
                            PushButton, TextEdit, CardWidget)

class ModernWorkbench(QWidget):
    """
    AI Workbench Component.
    Features:
    - Chat Interface (History & Input)
    - Diff View (Source vs Target context)
    - Action Buttons (Translate, Refine, Apply)
    """
    
    # Signals
    request_translation = pyqtSignal(object) # unit
    request_refinement = pyqtSignal(object) # unit
    apply_changes = pyqtSignal(object, str) # unit, new_text
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModernWorkbench")
        self.current_unit = None
        
        self.init_ui()
        
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter: Left (Diff/Context) | Right (Chat)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- Left: Context & Actions ---
        left_container = QWidget()
        l_layout = QVBoxLayout(left_container)
        l_layout.setContentsMargins(10, 10, 10, 10)
        
        l_layout.addWidget(StrongBodyLabel("Context & Actions", self))
        
        # Source Box
        l_layout.addWidget(BodyLabel("Source:", self))
        self.txt_source = TextEdit()
        self.txt_source.setReadOnly(True)
        self.txt_source.setMaximumHeight(80)
        l_layout.addWidget(self.txt_source)
        
        # Target Box
        l_layout.addWidget(BodyLabel("Target (Editable):", self))
        self.txt_target = TextEdit()
        self.txt_target.setMaximumHeight(80)
        l_layout.addWidget(self.txt_target)
        
        # Actions
        btn_layout = QHBoxLayout()
        self.btn_trans = PrimaryPushButton("Translate")
        self.btn_trans.clicked.connect(self.on_translate)
        
        self.btn_refine = PushButton("Refine")
        self.btn_refine.clicked.connect(self.on_refine)
        
        self.btn_apply = PushButton("Apply to Table")
        self.btn_apply.clicked.connect(self.on_apply)
        
        btn_layout.addWidget(self.btn_trans)
        btn_layout.addWidget(self.btn_refine)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_apply)
        
        l_layout.addLayout(btn_layout)
        l_layout.addStretch()
        
        splitter.addWidget(left_container)
        
        # --- Right: AI Chat ---
        right_container = QWidget()
        r_layout = QVBoxLayout(right_container)
        r_layout.setContentsMargins(10, 10, 10, 10)
        
        r_layout.addWidget(StrongBodyLabel("AI Assistant", self))
        
        # Chat History
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet("border: 1px solid #E5E5E5; border-radius: 6px; background: #FFFFFF;")
        r_layout.addWidget(self.chat_history)
        
        # Chat Input (Simplified)
        input_layout = QHBoxLayout()
        self.chat_input = TextEdit()
        self.chat_input.setPlaceholderText("Ask AI about this segment...")
        self.chat_input.setMaximumHeight(50)
        
        btn_send = PrimaryPushButton("Send")
        # btn_send.clicked.connect(...)
        
        input_layout.addWidget(self.chat_input)
        input_layout.addWidget(btn_send)
        r_layout.addLayout(input_layout)
        
        splitter.addWidget(right_container)
        splitter.setSizes([400, 500])
        
        layout.addWidget(splitter)

    def set_context(self, unit):
        """Update view with selected unit data"""
        self.current_unit = unit
        if not unit:
            self.txt_source.clear()
            self.txt_target.clear()
            self.btn_trans.setEnabled(False)
            self.btn_refine.setEnabled(False)
            self.btn_apply.setEnabled(False)
            return
            
        self.txt_source.setText(unit.source_abstracted or "")
        self.txt_target.setText(unit.target_abstracted or "")
        
        self.btn_trans.setEnabled(True)
        self.btn_refine.setEnabled(True)
        self.btn_apply.setEnabled(True)
        
        # Clear chat or load history? For now clear
        # self.chat_history.clear() 
        # self.append_message("System", f"Context switched to ID: {unit.id}")

    def append_message(self, role, text):
        color = "blue" if role == "AI" else "green"
        self.chat_history.append(f"<b style='color:{color}'>{role}:</b> {text}<br>")

    def on_translate(self):
        if self.current_unit:
            self.request_translation.emit(self.current_unit)
            self.append_message("System", "Translating...")

    def on_refine(self):
        if self.current_unit:
            self.request_refinement.emit(self.current_unit)
            self.append_message("System", "Refining...")

    def on_apply(self):
        if self.current_unit:
            new_text = self.txt_target.toPlainText()
            self.apply_changes.emit(self.current_unit, new_text)
            self.append_message("System", "Translation applied to table.")
