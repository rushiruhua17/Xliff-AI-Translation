from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QFrame, 
                             QMessageBox, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal
from qfluentwidgets import (SubtitleLabel, BodyLabel, PrimaryPushButton, LineEdit, 
                            CardWidget, EditableComboBox, StrongBodyLabel, FluentIcon as FIF,
                            TextEdit, ToolTipFilter, ToolTipPosition, SingleDirectionScrollArea)

class ProjectInterface(SingleDirectionScrollArea):
    """
    Project Interface:
    - Import File
    - Project Settings (Source/Target Lang, Context)
    """
    start_project_clicked = pyqtSignal(str, dict) # Path, Settings
    
    def __init__(self, parent=None):
        super().__init__(parent=parent, orient=Qt.Orientation.Vertical)
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setObjectName("ProjectInterface")
        
        self.v_layout = QVBoxLayout(self.view)
        self.v_layout.setContentsMargins(36, 36, 36, 36)
        self.v_layout.setSpacing(20)
        
        self.view.setStyleSheet("background: transparent;")
        
        self.init_header()
        self.init_file_selection()
        self.init_project_settings()
        self.init_actions()
        
        self.v_layout.addStretch()
        
        self.selected_file_path = None

    def init_header(self):
        title = SubtitleLabel("Create New Project", self)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.v_layout.addWidget(title)
        
        desc = BodyLabel("Import your translation file and configure project settings.", self)
        desc.setStyleSheet("color: #666666; font-size: 14px;")
        self.v_layout.addWidget(desc)

    def init_file_selection(self):
        self.v_layout.addSpacing(10)
        
        card = CardWidget(self.view)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        
        layout.addWidget(StrongBodyLabel("1. Import File", card))
        
        # File Input Row
        h_layout = QHBoxLayout()
        self.path_edit = LineEdit()
        self.path_edit.setPlaceholderText("Select .xliff or .xlf file...")
        self.path_edit.setReadOnly(True)
        h_layout.addWidget(self.path_edit)
        
        self.btn_browse = PrimaryPushButton("Browse", card)
        self.btn_browse.setIcon(FIF.FOLDER)
        self.btn_browse.setToolTip("Select translation file")
        self.btn_browse.installEventFilter(ToolTipFilter(self.btn_browse, showDelay=50, position=ToolTipPosition.BOTTOM))
        self.btn_browse.clicked.connect(self.browse_file)
        h_layout.addWidget(self.btn_browse)
        
        layout.addLayout(h_layout)
        self.v_layout.addWidget(card)

    def init_project_settings(self):
        self.v_layout.addSpacing(10)
        
        card = CardWidget(self.view)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        
        layout.addWidget(StrongBodyLabel("2. Project Settings", card))
        layout.addSpacing(10)
        
        # Languages Row
        lang_layout = QHBoxLayout()
        
        # Source Lang
        v_src = QVBoxLayout()
        v_src.addWidget(BodyLabel("Source Language"))
        self.combo_src = EditableComboBox()
        self.combo_src.addItems(["Auto-Detect", "en", "zh-CN", "ja", "ko", "fr", "de", "es"])
        # self.combo_src.setEditable(True) # EditableComboBox is editable by default
        v_src.addWidget(self.combo_src)
        lang_layout.addLayout(v_src)
        
        # Target Lang
        v_tgt = QVBoxLayout()
        v_tgt.addWidget(BodyLabel("Target Language"))
        self.combo_tgt = EditableComboBox()
        self.combo_tgt.addItems(["en", "zh-CN", "ja", "ko", "fr", "de", "es"])
        # self.combo_tgt.setEditable(True)
        v_tgt.addWidget(self.combo_tgt)
        lang_layout.addLayout(v_tgt)
        
        layout.addLayout(lang_layout)
        layout.addSpacing(15)
        
        # Context / Prompts
        layout.addWidget(BodyLabel("Project Context / Instructions (Optional)"))
        self.txt_context = TextEdit()
        self.txt_context.setPlaceholderText("Enter context about this project (e.g., 'Technical manual for a drone', 'Casual game dialog'). This will be used to guide the AI translation.")
        self.txt_context.setFixedHeight(100)
        layout.addWidget(self.txt_context)
        
        self.v_layout.addWidget(card)

    def init_actions(self):
        self.v_layout.addSpacing(20)
        
        h_layout = QHBoxLayout()
        h_layout.addStretch()
        
        self.btn_start = PrimaryPushButton("Start Translation", self.view)
        self.btn_start.setIcon(FIF.PLAY)
        self.btn_start.setFixedWidth(200)
        self.btn_start.setToolTip("Initialize project and open editor")
        self.btn_start.installEventFilter(ToolTipFilter(self.btn_start, showDelay=50, position=ToolTipPosition.BOTTOM))
        self.btn_start.clicked.connect(self.on_start_clicked)
        self.btn_start.setEnabled(False) # Disabled until file selected
        
        h_layout.addWidget(self.btn_start)
        self.v_layout.addLayout(h_layout)

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open XLIFF", "", "XLIFF (*.xlf *.xliff)")
        if path:
            self.selected_file_path = path
            self.path_edit.setText(path)
            self.btn_start.setEnabled(True)
            
            # Try to auto-detect languages (Mock logic for now, real logic happens in parser)
            # In a real app, we might parse headers here to pre-fill combos
            pass

    def on_start_clicked(self):
        if not self.selected_file_path:
            return
            
        settings = {
            "source_lang": self.combo_src.currentText(),
            "target_lang": self.combo_tgt.currentText(),
            "context": self.txt_context.toPlainText()
        }
        
        self.start_project_clicked.emit(self.selected_file_path, settings)
