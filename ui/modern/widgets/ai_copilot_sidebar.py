from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, 
                             QTextEdit, QScrollArea, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from qfluentwidgets import (StrongBodyLabel, BodyLabel, PrimaryPushButton, 
                            PushButton, ToolButton, FluentIcon as FIF, 
                            CardWidget, SearchLineEdit, TextEdit)

class AICopilotSidebar(QWidget):
    """
    Right-side AI Copilot Sidebar.
    Features:
    - Context Info (Selection count)
    - Quick Actions (Translate, Refine, Fix Tags)
    - Command Input (Natural Language)
    - History/Log (Simplified)
    """
    
    # Signals
    request_action = pyqtSignal(str) # "translate", "refine", "fix_tags"
    request_command = pyqtSignal(str) # Custom text command
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # 1. Header
        h_header = QHBoxLayout()
        h_header.addWidget(StrongBodyLabel("✨ AI Copilot", self))
        h_header.addStretch()
        self.btn_self_test = ToolButton(FIF.MORE, self)
        self.btn_self_test.clicked.connect(lambda: self.request_action.emit("self_test"))
        h_header.addWidget(self.btn_self_test)
        self.btn_settings = ToolButton(FIF.SETTING, self)
        h_header.addWidget(self.btn_settings)
        layout.addLayout(h_header)
        
        # 2. Context Info
        self.context_card = CardWidget(self)
        self.context_card.setFixedHeight(60)
        c_layout = QHBoxLayout(self.context_card)
        c_layout.setContentsMargins(15, 10, 15, 10)
        
        self.lbl_selection = BodyLabel("No selection", self.context_card)
        c_layout.addWidget(self.lbl_selection)
        
        layout.addWidget(self.context_card)
        
        # 3. Quick Actions Grid
        self.action_container = QWidget()
        g_layout = QVBoxLayout(self.action_container)
        g_layout.setContentsMargins(0, 0, 0, 0)
        g_layout.setSpacing(10)
        
        # Row 1
        r1 = QHBoxLayout()
        self.btn_translate = PushButton("Translate", self)
        self.btn_translate.setIcon(FIF.LANGUAGE)
        self.btn_translate.clicked.connect(lambda: self.request_action.emit("translate"))
        
        self.btn_refine = PushButton("Refine", self)
        self.btn_refine.setIcon(FIF.EDIT)
        self.btn_refine.clicked.connect(lambda: self.request_action.emit("refine"))
        
        r1.addWidget(self.btn_translate)
        r1.addWidget(self.btn_refine)
        g_layout.addLayout(r1)
        
        # Row 2
        r2 = QHBoxLayout()
        self.btn_fix = PushButton("Fix Tags", self)
        self.btn_fix.setIcon(FIF.TAG)
        self.btn_fix.clicked.connect(lambda: self.request_action.emit("fix_tags"))
        
        self.btn_formalize = PushButton("Formalize", self)
        self.btn_formalize.setIcon(FIF.ACCEPT) # Mock icon
        self.btn_formalize.clicked.connect(lambda: self.request_action.emit("formalize"))
        
        r2.addWidget(self.btn_fix)
        r2.addWidget(self.btn_formalize)
        g_layout.addLayout(r2)
        
        layout.addWidget(self.action_container)
        
        # 4. Command Input
        layout.addWidget(StrongBodyLabel("Instruction", self))
        
        self.txt_input = TextEdit(self)
        self.txt_input.setPlaceholderText("e.g. 'Make it punchy', 'Use shorter words'...")
        self.txt_input.setFixedHeight(80)
        layout.addWidget(self.txt_input)
        
        self.btn_send = PrimaryPushButton("Generate Patch", self)
        self.btn_send.setIcon(FIF.SEND)
        self.btn_send.clicked.connect(self.on_send)
        layout.addWidget(self.btn_send)
        
        # 5. Tips / Status
        self.lbl_tip = BodyLabel("Tip: Select multiple segments to batch process.", self)
        self.lbl_tip.setTextColor("#808080", "#808080") # Gray
        self.lbl_tip.setWordWrap(True)
        layout.addWidget(self.lbl_tip)
        
        # 6. Mini Log (Scrollable)
        self.log_area = TextEdit(self)
        self.log_area.setReadOnly(True)
        self.log_area.setPlaceholderText("AI Logs...")
        self.log_area.setFixedHeight(100)
        layout.addWidget(self.log_area)
        
        layout.addStretch()
        
    def update_context(self, count):
        if count == 0:
            self.lbl_selection.setText("No selection")
            self.set_actions_enabled(False)
        elif count == 1:
            self.lbl_selection.setText("1 segment selected")
            self.set_actions_enabled(True)
        else:
            self.lbl_selection.setText(f"{count} segments selected")
            self.set_actions_enabled(True)
            
    def set_actions_enabled(self, enabled):
        self.action_container.setEnabled(enabled)
        self.btn_send.setEnabled(enabled)
        self.txt_input.setEnabled(enabled)

    def on_send(self):
        text = self.txt_input.toPlainText().strip()
        if text:
            self.request_command.emit(text)
            self.txt_input.clear()

    def append_message(self, role, text):
        """Append log message to the mini log area"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f"[{timestamp}] <b>{role}:</b> {text}")
        # Auto scroll
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())
        
        # Update tip if system message
        if role == "System":
            self.lbl_tip.setText(text.replace("<br>", " "))
