import sys
import os
import time
import difflib
import re # Native regex for stability
import qdarktheme # Modern theme
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTableView, QFileDialog, 
                             QHeaderView, QMessageBox, QLabel, QAbstractItemView,
                             QComboBox, QLineEdit, QGroupBox, QMenu, QDockWidget,
                             QTextEdit, QProgressBar, QSplitter, QFrame, QCheckBox,
                             QToolBar, QSpacerItem, QSizePolicy, QTabWidget, QDialog)
from PyQt6.QtCore import (Qt, QAbstractTableModel, QModelIndex, QThread, pyqtSignal, 
                          QSize, QSettings, QSortFilterProxyModel, QRegularExpression, QTimer)
from PyQt6.QtGui import QAction, QIcon, QColor, QBrush, QKeySequence, QShortcut

# Ensure core modules importable
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from core.parser import XliffParser
from core.abstractor import TagAbstractor
from core.logger import get_logger, setup_exception_hook
from core.qa import QAChecker
from core.repair import RepairWorker
from core.workers import TranslationWorker, RefineWorker, TestConnectionWorker, SampleWorker
from core.profile import TranslationProfile, TranslationProfileContainer, ProfileStatus
from ui.profile_wizard import ProfileWizardDialog, WizardResult
from ai.client import LLMClient
import json # Added missing import

# Initialize logger for this module
logger = get_logger(__name__)

# --- Worker Threads moved to core.workers ---
# Imported above

# --- Models ---

class QAFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDynamicSortFilter(True)
    
    def filterAcceptsRow(self, source_row, source_parent):
        # Access the source model
        source_model = self.sourceModel()
        if not source_model: return True
        
        # Get the 'QA' column data (column 3 is just display text, we need the stored unit object ideally)
        # But our model stores units in a list. Let's access the unit directly.
        unit = source_model.units[source_row]
        
        # Keep row if status is NOT 'ok' (i.e., 'error' or 'warning')
        return unit.qa_status != "ok"

class XliffTableModel(QAbstractTableModel):
    def __init__(self, units=None):
        super().__init__()
        self.units = units or []
        self.headers = ["ID", "State", "Tags", "QA", "Details", "Source", "Target"]

    def rowCount(self, parent=QModelIndex()):
        return len(self.units)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.units)):
            return None
        
        unit = self.units[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if col == 0: return unit.id
            elif col == 1: 
                # Return State Emoji as TEXT
                if unit.state == "locked": return "🔒"
                elif unit.state == "translated": return "✅"
                elif unit.state == "edited": return "✏️"
                elif unit.state == "needs_translation": return "⚪"
                return "⚪"
            elif col == 2: return unit.tag_stats
            elif col == 3:
                # QA Status
                if unit.qa_status == "error": return "⛔"
                elif unit.qa_status == "warning": return "⚠️"
                else: return "✅"
            elif col == 4:
                # Details column: show first error message
                if unit.errors:
                    return unit.errors[0]  # Show first error
                return ""
            elif col == 5: return unit.source_abstracted
            elif col == 6: return unit.target_abstracted
            
        elif role == Qt.ItemDataRole.DecorationRole and col == 1:
            return None # We use DisplayRole for Emojis now

            
        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == 1: return f"Status: {unit.state}"
            elif col == 3:  # QA column
                if unit.errors:
                    return "\n".join(unit.errors)  # Show all errors in tooltip
                return "No issues"
            elif col == 4:  # Details column
                if unit.errors:
                    return "\n".join(unit.errors)
                return ""
                
        elif role == Qt.ItemDataRole.BackgroundRole:
            # Highlight error rows in light red
            if unit.qa_status == "error":
                return QBrush(QColor(255, 200, 200))  # Light red for errors
            elif unit.qa_status == "warning":
                return QBrush(QColor(255, 255, 200))  # Light yellow for warnings

        return None

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def flags(self, index):
        if not index.isValid(): return Qt.ItemFlag.NoItemFlags
        
        flags = super().flags(index)
        unit = self.units[index.row()]
        
        if index.column() == 6:
            if unit.state != "locked":
                flags |= Qt.ItemFlag.ItemIsEditable
        
        return flags

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if index.isValid() and role == Qt.ItemDataRole.EditRole and index.column() == 6:
            unit = self.units[index.row()]
            if unit.state == "locked": return False
            
            if unit.target_abstracted != value:
                unit.target_abstracted = value
                unit.state = "edited"
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                # Notify state column changed
                idx_state = self.index(index.row(), 1)
                self.dataChanged.emit(idx_state, idx_state, [Qt.ItemDataRole.DecorationRole])
                return True
        return False

    def update_data(self, units):
        self.beginResetModel()
        self.units = units
        self.endResetModel()
        
    def refresh_row(self, row_idx):
        # We need to map actual data index to model index. 
        # But here row_idx is absolute index.
        idx_start = self.index(row_idx, 0)
        idx_end = self.index(row_idx, 3)
        self.dataChanged.emit(idx_start, idx_end, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.DecorationRole])

        
class XliffFilterProxyModel(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.status_filter = "All"
        self.text_filter = ""
    
    def lessThan(self, left, right):
        # Numeric sorting for ID column (0)
        if left.column() == 0 and right.column() == 0:
            try:
                l_id = int(self.sourceModel().data(left))
                r_id = int(self.sourceModel().data(right))
                return l_id < r_id
            except:
                pass # Fallback to string sort
        return super().lessThan(left, right)

    def set_status_filter(self, status):
        self.status_filter = status
        self.invalidateFilter()
        
    def set_text_filter(self, text):
        self.text_filter = text.lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        unit = model.units[source_row]
        
        if self.status_filter != "All":
            if self.status_filter == "Translated" and unit.state != "translated": return False
            if self.status_filter == "Edited" and unit.state != "edited": return False
            if self.status_filter == "Locked" and unit.state != "locked": return False
            if self.status_filter == "Untranslated" and unit.state not in ["new", "needs_translation", None, ""]: 
                if unit.target_abstracted: return False

        if self.text_filter:
            s_text = (unit.source_abstracted or "").lower()
            t_text = (unit.target_abstracted or "").lower()
            if self.text_filter not in s_text and self.text_filter not in t_text:
                return False
                
        return True

# --- Main Window ---

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XLIFF AI Assistant Pro v2.0")
        self.resize(1400, 900)
        
        # Settings
        self.settings = QSettings("Gemini", "XLIFF_AI_Assistant")
        
        # Data
        self.parser = None
        self.units = []
        self.abstractor = TagAbstractor()
        
        # Profile Management
        self.current_profile = None # TranslationProfile
        self.current_sidecar_path = None
        
        # Models
        self.model = XliffTableModel()
        self.proxy_model = XliffFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        
        self.proxy_qa = QAFilterProxyModel()
        self.proxy_qa.setSourceModel(self.model)
        
        self.active_unit_index_map = -1 # Mapped index in source model
        
        # Workers
        self.trans_worker = None
        self.refine_worker = None
        self.test_worker = None
        self.repair_worker = None
        
        self.setup_ui()
        self.load_settings()
        self.apply_styles()

    def setup_ui(self):
        # Central Widget is now a TabWidget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # --- Translation Brief Card (Phase 3) ---
        # A simple, always-visible card above the tabs or inside the main layout
        # But QMainWindow central widget is occupied by tabs. 
        # We can use a layout wrapper for central widget: VBox(BriefCard, Tabs)
        
        central_container = QWidget()
        central_layout = QVBoxLayout(central_container)
        central_layout.setContentsMargins(0,0,0,0)
        central_layout.setSpacing(0)
        
        # Brief Card
        self.brief_card = QFrame()
        self.brief_card.setObjectName("briefCard")
        self.brief_card.setStyleSheet("""
            QFrame#briefCard {
                background-color: #2D2F31;
                border-bottom: 1px solid #3C4043;
                padding: 10px;
            }
            QLabel { color: #BDC1C6; }
            QLabel#briefTitle { font-weight: bold; color: #E8EAED; }
        """)
        self.brief_card.setVisible(False) # Hidden until profile loaded
        
        bc_layout = QHBoxLayout(self.brief_card)
        
        # Info
        v_info = QVBoxLayout()
        self.lbl_brief_title = QLabel("Translation Brief")
        self.lbl_brief_title.setObjectName("briefTitle")
        self.lbl_brief_details = QLabel("No Profile")
        v_info.addWidget(self.lbl_brief_title)
        v_info.addWidget(self.lbl_brief_details)
        bc_layout.addLayout(v_info)
        
        bc_layout.addStretch()
        
        # Edit Button
        self.btn_edit_brief = QPushButton("✏️ Edit Brief")
        self.btn_edit_brief.setFixedSize(100, 30)
        self.btn_edit_brief.clicked.connect(self.launch_profile_wizard)
        bc_layout.addWidget(self.btn_edit_brief)
        
        central_layout.addWidget(self.brief_card)
        central_layout.addWidget(self.tabs)
        
        self.setCentralWidget(central_container)
        
        # --- Tab 1: Translate (Workbench) ---
        self.tab_translate = QWidget()
        self.setup_translate_tab()
        self.tabs.addTab(self.tab_translate, "Worktable")
        
        # --- Tab 2: QA Focus ---
        self.tab_qa = QWidget()
        self.setup_qa_tab()
        self.tabs.addTab(self.tab_qa, "🛡️ QA Review")
        
        # --- Tab 3: Settings ---
        self.tab_settings = QWidget()
        self.setup_settings_tab()
        self.tabs.addTab(self.tab_settings, "Settings")

        # --- Refinement Dock (Right Drawer) ---
        self.dock_refine = QDockWidget("✨ Workbench", self)
        self.dock_refine.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        
        dock_widget = QWidget()
        dock_layout = QVBoxLayout(dock_widget)
        
        # Left: Source & Prompt
        v_left = QVBoxLayout()
        
        h_src = QHBoxLayout()
        h_src.addWidget(QLabel("Source Segment:"))
        h_src.addStretch()
        btn_copy_src = QPushButton("📋")
        btn_copy_src.setFixedSize(24, 24)
        btn_copy_src.setToolTip("Copy Source")
        btn_copy_src.clicked.connect(lambda: QApplication.clipboard().setText(self.txt_source.toPlainText()))
        h_src.addWidget(btn_copy_src)
        v_left.addLayout(h_src)
        
        self.txt_source = QTextEdit()
        self.txt_source.setReadOnly(True)
        self.txt_source.setMinimumHeight(60)
        v_left.addWidget(self.txt_source)
        
        v_left.addWidget(QLabel("Instruction:"))
        h_actions = QHBoxLayout()
        self.txt_prompt = QLineEdit()
        self.txt_prompt.setPlaceholderText("e.g. 'Fix grammar', 'Make concise'")
        self.txt_prompt.returnPressed.connect(self.refine_current_segment) # Enter to trigger
        h_actions.addWidget(self.txt_prompt)
        
        self.btn_refine = QPushButton("✨ Refine")
        self.btn_refine.clicked.connect(self.refine_current_segment)
        h_actions.addWidget(self.btn_refine)
        v_left.addLayout(h_actions)
        
        # Shortcuts
        h_quick = QHBoxLayout()
        for label, prompt in [("Formal", "Make it formal"), ("Concise", "Make it concise"), ("Fix Grammar", "Fix grammar errors")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, p=prompt: (self.txt_prompt.setText(p), self.refine_current_segment()))
            h_quick.addWidget(btn)
        h_quick.addStretch()
        v_left.addLayout(h_quick)
        
        dock_layout.addLayout(v_left, 1)

        # Right: Target & Diff
        v_right = QVBoxLayout()
        v_right.addWidget(QLabel("Translation (Preview/Diff):"))
        
        # Splitter for Diff and Edit to allow resizing
        splitter_right = QSplitter(Qt.Orientation.Vertical)
        
        self.txt_diff = QTextEdit()
        self.txt_diff.setReadOnly(True)
        self.txt_diff.setMinimumHeight(40)
        self.txt_diff.setPlaceholderText("Diff view will appear here...")
        splitter_right.addWidget(self.txt_diff)
        
        self.txt_target_edit = QTextEdit() # Editable
        self.txt_target_edit.setMinimumHeight(60)
        splitter_right.addWidget(self.txt_target_edit)
        
        # Set initial sizes
        splitter_right.setSizes([60, 100])
        
        v_right.addWidget(splitter_right)
        
        h_confirm = QHBoxLayout()
        h_confirm.addStretch()
        self.btn_apply = QPushButton("✅ Apply & Next (Ctrl+Enter)")
        self.btn_apply.clicked.connect(self.apply_refinement)
        self.btn_apply.setObjectName("btnPrimary")
        QShortcut(QKeySequence("Ctrl+Return"), self, self.apply_refinement)
        
        h_confirm.addWidget(self.btn_apply)
        v_right.addLayout(h_confirm)
        
        dock_layout.addLayout(v_right, 1)
        
        self.dock_refine.setWidget(dock_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_refine)
        self.dock_refine.setVisible(False)

    def setup_translate_tab(self):
        layout = QVBoxLayout(self.tab_translate)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Top Bar: File Actions & Stats
        top_bar = QHBoxLayout()
        
        self.btn_open = QPushButton("📂 Open")
        self.btn_open.clicked.connect(self.open_file)
        top_bar.addWidget(self.btn_open)
        
        self.btn_save = QPushButton("💾 Export")
        self.btn_save.clicked.connect(self.save_file)
        top_bar.addWidget(self.btn_save)
        
        # Profile Status Indicator (Phase 3.5)
        self.lbl_profile_status = QLabel("Status: New")
        self.lbl_profile_status.setObjectName("profileStatus")
        self.lbl_profile_status.setStyleSheet("""
            QLabel#profileStatus {
                background-color: #3C4043;
                color: #BDC1C6;
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        self.lbl_profile_status.setToolTip("Project Profile Status")
        top_bar.addWidget(self.lbl_profile_status)
        
        # Sampling Button (Phase 6)
        self.btn_sample = QPushButton("🎲 Draft Sample")
        self.btn_sample.setToolTip("Generate a 5-segment sample to verify style")
        self.btn_sample.clicked.connect(self.generate_sample_draft)
        top_bar.addWidget(self.btn_sample)
        
        self.btn_trans = QPushButton("🚀 Translate All")
        self.btn_trans.clicked.connect(lambda: self.start_translation())
        top_bar.addWidget(self.btn_trans)

        self.btn_qa = QPushButton("🛡️ Run QA")
        self.btn_qa.clicked.connect(self.run_qa)
        top_bar.addWidget(self.btn_qa)
        
        self.btn_batch_repair = QPushButton("🔧 Batch Auto-Repair")
        self.btn_batch_repair.clicked.connect(self.batch_auto_repair)
        top_bar.addWidget(self.btn_batch_repair)
        
        top_bar.addSpacing(20)
        self.health_bar = QProgressBar()
        self.health_bar.setFixedWidth(150)
        self.health_bar.setTextVisible(True)
        self.health_bar.setFormat("Health: %p%")
        self.health_bar.setToolTip("Export Readiness (segments without critical errors)")
        self.health_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #3C4043; border-radius: 4px; text-align: center; }
            QProgressBar::chunk { background-color: #4CAF50; }
        """)
        top_bar.addWidget(self.health_bar)
        
        top_bar.addSpacing(10)
        self.lbl_stats = QLabel("No file loaded")
        top_bar.addWidget(self.lbl_stats)
        
        top_bar.addStretch()
        
        # Theme Toggle (Small)
        self.btn_theme = QPushButton("🌓")
        self.btn_theme.setFixedSize(30, 30)
        self.btn_theme.clicked.connect(self.toggle_theme)
        top_bar.addWidget(self.btn_theme)
        
        layout.addLayout(top_bar)
        
        # Toolbar: Filter & Actions
        toolbar = QHBoxLayout()
        
        # Search
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Search source/target...")
        self.txt_search.textChanged.connect(self.on_search_changed)
        toolbar.addWidget(self.txt_search, 1)
        
        # Filters
        self.btn_grp_filter = []
        for name in ["All", "Untranslated", "Translated", "Edited", "Locked"]:
            btn = QPushButton(name)
            btn.setCheckable(True)
            if name == "All": btn.setChecked(True)
            btn.clicked.connect(lambda checked, n=name: self.on_filter_btn_clicked(n))
            toolbar.addWidget(btn)
            self.btn_grp_filter.append(btn)
            
        layout.addLayout(toolbar)
        
        # Progress Bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Table
        self.table = QTableView()
        self.table.setModel(self.proxy_model) 
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.selectionModel().selectionChanged.connect(self.on_selection_changed)
        
        # Shortcuts
        QShortcut(QKeySequence("Ctrl+Up"), self.table, lambda: self.navigate_grid(-1))
        QShortcut(QKeySequence("Ctrl+Down"), self.table, lambda: self.navigate_grid(1))
        
        # Table Headers
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # ID
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # State
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Tags
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # QA
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) # Details (Errors)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch) # Source
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch) # Target
        
        layout.addWidget(self.table)

    def setup_qa_tab(self):
        layout = QVBoxLayout(self.tab_qa)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # --- Readiness Panel ---
        self.panel_readiness = QFrame()
        self.panel_readiness.setObjectName("readinessPanel")
        self.panel_readiness.setFrameShape(QFrame.Shape.StyledPanel)
        r_layout = QHBoxLayout(self.panel_readiness)
        
        self.lbl_readiness_status = QLabel("<b>Status:</b> Not Checked")
        self.lbl_readiness_stats = QLabel("Errors: 0 | Warnings: 0")
        self.progress_health = QProgressBar()
        self.progress_health.setRange(0, 100)
        self.progress_health.setValue(100)
        self.progress_health.setTextVisible(True)
        self.progress_health.setFormat("Health: %p%")
        self.progress_health.setFixedWidth(150)
        
        r_layout.addWidget(self.lbl_readiness_status)
        r_layout.addStretch()
        r_layout.addWidget(self.lbl_readiness_stats)
        r_layout.addSpacing(20)
        r_layout.addWidget(self.progress_health)
        
        layout.addWidget(self.panel_readiness)
        
        # QA Toolbar
        qa_bar = QHBoxLayout()
        qa_bar.addWidget(QLabel("<b>🛡️ QA Issues Filter</b>"))
        qa_bar.addWidget(QLabel("(Showing only errors & warnings)"))
        qa_bar.addStretch()
        
        # Button to re-apply filter manualy if needed (usually auto)
        btn_refresh = QPushButton("🔄 Refresh Filter")
        btn_refresh.clicked.connect(lambda: self.proxy_qa.invalidate())
        qa_bar.addWidget(btn_refresh)
        
        layout.addLayout(qa_bar)
        
        # QA Table Viewer
        self.view_qa = QTableView()
        self.view_qa.setModel(self.proxy_qa)
        self.view_qa.setAlternatingRowColors(True)
        self.view_qa.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view_qa.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view_qa.setSortingEnabled(True)
        
        # Context Menu & Double Click
        self.view_qa.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view_qa.customContextMenuRequested.connect(self.on_qa_context_menu)
        self.view_qa.doubleClicked.connect(self.on_qa_double_click)
        
        layout.addWidget(self.view_qa)
        
        # Connect selection
        self.view_qa.selectionModel().selectionChanged.connect(self.on_qa_selection_changed)
        
        # Headers formatting (initial, will be updated in open_file)
        h = self.view_qa.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setStretchLastSection(True)

    def setup_settings_tab(self):
        layout = QVBoxLayout(self.tab_settings)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # LLM Config Group
        grp_llm = QGroupBox("AI Configuration")
        form_layout = QVBoxLayout()
        
        # Provider
        h_prov = QHBoxLayout()
        h_prov.addWidget(QLabel("Provider:"))
        self.combo_provider = QComboBox()
        self.combo_provider.addItems(["SiliconFlow", "OpenAI", "DeepSeek"])
        self.combo_provider.currentTextChanged.connect(self.on_provider_changed)
        h_prov.addWidget(self.combo_provider)
        form_layout.addLayout(h_prov)
        
        # API Key
        h_key = QHBoxLayout()
        h_key.addWidget(QLabel("API Key:"))
        self.txt_apikey = QLineEdit()
        self.txt_apikey.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_apikey.setPlaceholderText("sk-...")
        h_key.addWidget(self.txt_apikey)
        form_layout.addLayout(h_key)
        
        # Base URL
        h_url = QHBoxLayout()
        h_url.addWidget(QLabel("Base URL:"))
        self.txt_base_url = QLineEdit()
        self.txt_base_url.setPlaceholderText("https://api.openai.com/v1")
        h_url.addWidget(self.txt_base_url)
        form_layout.addLayout(h_url)
        
        # Model
        h_model = QHBoxLayout()
        h_model.addWidget(QLabel("Model:"))
        self.txt_model = QLineEdit()
        self.txt_model.setPlaceholderText("gpt-3.5-turbo")
        h_model.addWidget(self.txt_model)
        form_layout.addLayout(h_model)
        
        # Test Connection HTML Warning
        self.btn_test_conn = QPushButton("📡 Test Connection")
        self.btn_test_conn.clicked.connect(self.test_connection)
        form_layout.addWidget(self.btn_test_conn)

        grp_llm.setLayout(form_layout)
        layout.addWidget(grp_llm)
        
        # Language Config
        grp_lang = QGroupBox("Language Defaults")
        l_layout = QHBoxLayout()
        self.combo_src = QComboBox()
        self.combo_src.addItems(["zh-CN", "en", "ja", "de", "fr"])
        self.combo_tgt = QComboBox()
        self.combo_tgt.addItems(["en", "zh-CN", "ja", "de", "fr"])
        l_layout.addWidget(QLabel("Source:"))
        l_layout.addWidget(self.combo_src)
        l_layout.addWidget(QLabel("Target:"))
        l_layout.addWidget(self.combo_tgt)
        grp_lang.setLayout(l_layout)
        layout.addWidget(grp_lang)
        
        # Auto-Repair Config (Optional Feature)
        grp_repair = QGroupBox("Auto-Repair (Optional)")
        repair_layout = QVBoxLayout()
        
        # Enable Toggle
        self.chk_auto_repair = QCheckBox("Enable Auto-Repair")
        self.chk_auto_repair.setToolTip("Use a secondary AI model to automatically fix tag errors")
        repair_layout.addWidget(self.chk_auto_repair)
        
        # Repair Model
        h_repair_model = QHBoxLayout()
        h_repair_model.addWidget(QLabel("Repair Model:"))
        self.txt_repair_model = QLineEdit()
        self.txt_repair_model.setPlaceholderText("deepseek-chat")
        h_repair_model.addWidget(self.txt_repair_model)
        repair_layout.addLayout(h_repair_model)
        
        # Repair API Key
        h_repair_key = QHBoxLayout()
        h_repair_key.addWidget(QLabel("Repair API Key:"))
        self.txt_repair_apikey = QLineEdit()
        self.txt_repair_apikey.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_repair_apikey.setPlaceholderText("sk-... (Optional, uses main key if empty)")
        h_repair_key.addWidget(self.txt_repair_apikey)
        repair_layout.addLayout(h_repair_key)
        
        # Repair Base URL
        h_repair_url = QHBoxLayout()
        h_repair_url.addWidget(QLabel("Repair Base URL:"))
        self.txt_repair_base_url = QLineEdit()
        self.txt_repair_base_url.setPlaceholderText("https://api.deepseek.com")
        h_repair_url.addWidget(self.txt_repair_base_url)
        repair_layout.addLayout(h_repair_url)
        
        grp_repair.setLayout(repair_layout)
        layout.addWidget(grp_repair)
        
        # System & Debug Group
        grp_system = QGroupBox("System & Debug")
        sys_layout = QVBoxLayout()
        self.chk_diagnostic = QCheckBox("Enable Diagnostic Mode (Requires Restart)")
        self.chk_diagnostic.setToolTip("Enables verbose logging (QT_DEBUG_PLUGINS) for debugging crashes")
        sys_layout.addWidget(self.chk_diagnostic)
        grp_system.setLayout(sys_layout)
        layout.addWidget(grp_system)

        layout.addStretch()

    def toggle_theme(self):
        # Toggle between 'auto' (usually dark on this OS) and 'light'
        current = self.settings.value("theme", "dark")
        new_theme = "light" if current == "dark" else "dark"
        qdarktheme.setup_theme(new_theme)
        self.settings.setValue("theme", new_theme)
        self.apply_styles(new_theme) # Re-apply styles with new theme colors

    def apply_styles(self, theme="dark"):
        # Custom tweaks based on theme
        
        if theme == "dark":
            bg_sidebar = "#202124"
            bg_filter = "#2D2F31"
            border_col = "#3C4043"
            text_col = "#E8EAED"
            primary_col = "#007AFF"
            title_col = "#60CDFF"
        else:
            bg_sidebar = "#F1F3F4" # Light gray
            bg_filter = "#FFFFFF"
            border_col = "#DADCE0"
            text_col = "#202124"
            primary_col = "#1A73E8"
            title_col = "#1967D2"

        self.setStyleSheet(f"""
            QLabel#appTitle {{ font-size: 24px; font-weight: bold; color: {title_col}; margin-bottom: 20px; }}
            QPushButton {{ padding: 6px; border-radius: 4px; }}
            QPushButton#btnPrimary {{ background-color: {primary_col}; color: white; font-weight: bold; padding: 10px; }}
            QPushButton#btnPrimary:hover {{ opacity: 0.9; }}
            QFrame#sidebar {{ background-color: {bg_sidebar}; border-right: 1px solid {border_col}; }}
            QFrame#filterBar {{ background-color: {bg_filter}; border-bottom: 1px solid {border_col}; border-radius: 4px; }}
            QTextEdit {{ font-family: Consolas, monospace; font-size: 13px; }}
        """)
        
        # Update button text
        self.btn_theme.setText("🌞 Light Mode" if theme == "dark" else "🌙 Dark Mode")

    # --- Settings persistence ---
    def load_settings(self):
        try:
            self.combo_src.setCurrentText(self.settings.value("source_lang", "zh-CN"))
            self.combo_tgt.setCurrentText(self.settings.value("target_lang", "en"))
            self.combo_provider.setCurrentText(self.settings.value("provider", "SiliconFlow"))
            self.txt_apikey.setText(self.settings.value("api_key", ""))
            self.txt_model.setText(self.settings.value("model", ""))
            self.txt_base_url.setText(self.settings.value("base_url", ""))
            
            # Auto-Repair config
            self.chk_auto_repair.setChecked(self.settings.value("auto_repair_enabled", False, type=bool))
            self.txt_repair_model.setText(self.settings.value("repair_model", "deepseek-chat"))
            self.txt_repair_apikey.setText(self.settings.value("repair_api_key", ""))
            self.txt_repair_base_url.setText(self.settings.value("repair_base_url", "https://api.deepseek.com"))
            
            # Diagnostic mode
            self.chk_diagnostic.setChecked(self.settings.value("diagnostic_mode", False, type=bool))
            
            # Geometry
            geo = self.settings.value("geometry")
            if geo: self.restoreGeometry(geo)
            
            # Theme
            theme = self.settings.value("theme", "dark")
            qdarktheme.setup_theme(theme)
            self.apply_styles(theme) # Apply correct custom styles
            
            # Trigger provider update logic to set defaults if empty
            self.on_provider_changed(self.combo_provider.currentText())
            
        except Exception as e:
            print(f"Error loading settings: {e}")
            
    # Remove Provider Logic for Mock if necessary
    def on_provider_changed(self, text):
        presets = {
            "SiliconFlow": ("https://api.siliconflow.cn/v1", "deepseek-ai/DeepSeek-V2.5"),
            "OpenAI": ("https://api.openai.com/v1", "gpt-4o"),
            "DeepSeek": ("https://api.deepseek.com", "deepseek-chat"),
        }
        
        url, model = presets.get(text, ("", ""))
        if url and not self.txt_base_url.text():
            self.txt_base_url.setText(url)
        if model and not self.txt_model.text():
            self.txt_model.setText(model)
            
    def get_client_config(self):
        return {
            "api_key": self.txt_apikey.text(),
            "base_url": self.txt_base_url.text(),
            "model": self.txt_model.text(),
            "provider": "custom"
        }

    def get_client(self):
        config = self.get_client_config()
        if not config["api_key"]:
            raise ValueError("API Key required")
            
        return LLMClient(**config)

    def test_connection(self):
        try:
            client = self.get_client()
        except Exception as e:
            QMessageBox.warning(self, "Config Error", str(e))
            return
            
        self.btn_test_conn.setEnabled(False)
        self.btn_test_conn.setText("Testing...")
        self.test_worker = TestConnectionWorker(client)
        self.test_worker.finished.connect(lambda s, m: QTimer.singleShot(0, lambda: (
            self.btn_test_conn.setEnabled(True),
            self.btn_test_conn.setText("📡 Test Connection"),
            QMessageBox.information(self, "Result", m) if s else QMessageBox.critical(self, "Error", m)
        )))
        self.test_worker.start()

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open XLIFF", "", "XLIFF (*.xlf *.xliff)")
        if path:
            try:
                # 1. Load Data
                self.parser = XliffParser(path)
                self.parser.load()
                raw_units = self.parser.get_translation_units()
                self.units = []
                for u in raw_units:
                    res = self.abstractor.abstract(u.source_raw)
                    u.source_abstracted = res.abstracted_text
                    u.tags_map = res.tags_map
                    
                    if u.target_raw:
                        res_tgt = self.abstractor.abstract(u.target_raw)
                        u.target_abstracted = res_tgt.abstracted_text
                    
                    self.units.append(u)
                
                # 2. Update UI
                self.model.update_data(self.units)
                self.proxy_model.invalidate()
                self.proxy_qa.invalidate()
                self.view_qa.setModel(self.proxy_qa)
                
                # Format headers for both tables
                for v in [self.table, self.view_qa]:
                    h = v.horizontalHeader()
                    h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # ID
                    h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # State
                    h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Tags
                    h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # QA
                    h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) # Details
                    h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch) # Source
                    h.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch) # Target
                
                self.update_stats()
                
                # 3. Load Profile (Sidecar Logic)
                self.load_profile_for_file(path)
                
            except Exception as e:
                logger.error(f"Failed to open file: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", str(e))

    def update_profile_status_ui(self):
        if not self.current_profile:
            self.lbl_profile_status.setText("Status: None")
            self.brief_card.setVisible(False)
            return
            
        status = self.current_profile.controls.status
        text = f"Profile: {status.value.title()}"
        
        # Color Coding
        if status == ProfileStatus.CONFIRMED:
            col = "#4CAF50" # Green
            bg = "#1E3A23"
        elif status == ProfileStatus.DRAFT:
            col = "#FFD740" # Yellow
            bg = "#3A341E"
        elif status == ProfileStatus.NEW:
            col = "#60CDFF" # Blue
            bg = "#1E2A3A"
        else:
            col = "#BDC1C6"
            bg = "#3C4043"
            
        self.lbl_profile_status.setText(text)
        self.lbl_profile_status.setStyleSheet(f"""
            QLabel#profileStatus {{
                background-color: {bg};
                color: {col};
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: bold;
                border: 1px solid {col};
            }}
        """)
        
        # Update Brief Card (Prompt 7)
        self.brief_card.setVisible(True)
        brief = self.current_profile.brief
        meta = self.current_profile.project_metadata
        
        details = []
        # Line 1: Label & Audience
        label = meta.label or "None"
        audience = brief.target_audience or "General"
        details.append(f"<b>Label:</b> {label} | <b>Audience:</b> {audience}")
        
        # Line 2: Tone, Formality & Locale
        tone = brief.tone or "neutral"
        formality = brief.formality or "neutral"
        locale = brief.locale_variant or "Default"
        details.append(f"<b>Tone:</b> {tone} | <b>Formality:</b> {formality} | <b>Locale:</b> {locale}")
        
        self.lbl_brief_details.setText("<br>".join(details))

    def load_profile_for_file(self, xliff_path):
        """Loads profile from sidecar or creates a new one with Wizard"""
        # Sidecar path: file.xlf -> file.profile.json
        self.current_sidecar_path = f"{xliff_path}.profile.json"
        
        if os.path.exists(self.current_sidecar_path):
            try:
                with open(self.current_sidecar_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    container = TranslationProfileContainer.from_dict(data)
                    self.current_profile = container.profile
                    logger.info(f"Loaded existing profile from {self.current_sidecar_path}")
            except Exception as e:
                logger.error(f"Failed to load sidecar profile: {e}")
                # Fallback to new
                self.current_profile = TranslationProfile()
        else:
            # Create new default
            self.current_profile = TranslationProfile()
            
        # Check Status
        if self.current_profile.controls.status == ProfileStatus.NEW:
            # Launch Wizard
            self.launch_profile_wizard()
        
        # Always update UI
        self.update_profile_status_ui()

    def launch_profile_wizard(self):
        if not self.current_profile: return
        
        dlg = ProfileWizardDialog(self.current_profile, self)
        if dlg.exec():
            # Accepted
            self.current_profile = dlg.get_profile()
            self.current_profile.controls.status = ProfileStatus.CONFIRMED
            self.save_profile()
            logger.info("Profile configured and saved.")
        else:
            if dlg.result_code == WizardResult.SKIPPED:
                # User skipped - keep as NEW or DRAFT but don't save to disk yet
                logger.info("Profile setup skipped.")
                # Optional: Set status to DRAFT so we don't annoy user immediately again?
                # Or keep NEW so it asks again next time.
                self.lbl_profile_status.setText("Profile: Temporary (Default)")
                pass
            else:
                # Cancelled - do nothing (or close file?)
                pass
        
        self.update_profile_status_ui()

    def save_profile(self):
        if not self.current_profile or not self.current_sidecar_path: return
        try:
            container = TranslationProfileContainer(profile=self.current_profile)
            with open(self.current_sidecar_path, 'w', encoding='utf-8') as f:
                json.dump(container.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save profile: {e}")


    def update_stats(self):
        if not self.units:
            self.lbl_stats.setText("No file loaded")
            return
            
        total = len(self.units)
        done = sum(1 for u in self.units if u.target_abstracted)
        errors = sum(1 for u in self.units if u.qa_status == "error")
        warnings = sum(1 for u in self.units if u.qa_status == "warning")
        
        # RICH stats display
        stats_html = f"<b>Total:</b> {total} | <b>Done:</b> {done}"
        if errors > 0:
            stats_html += f" | <span style='color:#FF5252;'><b>🚨 {errors} Errors</b></span>"
        elif total > 0:
            stats_html += " | <span style='color:#4CAF50;'>✅ All Clean</span>"
            
        if warnings > 0:
            stats_html += f" | <span style='color:#FFD740;'><b>⚠️ {warnings} Warnings</b></span>"
            
        self.lbl_stats.setText(stats_html)
        
        # Update Health Bar
        error_free_count = total - errors
        health_pct = int(error_free_count / total * 100) if total > 0 else 0
        self.health_bar.setValue(health_pct)
        
        # Colorize health bar if low
        if errors > 0:
            self.health_bar.setStyleSheet("QProgressBar::chunk { background-color: #FF5252; }")
        else:
            self.health_bar.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")

    def on_search_changed(self, text):
        self.proxy_model.set_text_filter(text)
        
    def on_filter_btn_clicked(self, name):
        # Uncheck others
        for btn in self.btn_grp_filter:
            if btn.text() != name: btn.setChecked(False)
        self.proxy_model.set_status_filter(name)

    def start_translation(self, target_units=None):
        # target_units: list of units to translate. If None, translate all (except locked).
        if target_units is None:
            target_units = self.units
            
        if not target_units: return
        
        try:
            client = self.get_client()
        except Exception as e:
            QMessageBox.warning(self, "Config Error", str(e))
            return
            
        self.btn_trans.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        
        self.trans_worker = TranslationWorker(
            target_units, 
            client, 
            self.combo_src.currentText(), 
            self.combo_tgt.currentText(),
            profile=self.current_profile # Pass Profile
        )
        self.trans_worker.progress.connect(lambda c, t: self.progress.setValue(int(c/t*100)))
        self.trans_worker.finished.connect(self.on_trans_finished)
        self.trans_worker.error.connect(lambda e: QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Error", e)))
        self.trans_worker.start()

    def on_trans_finished(self):
        self.btn_trans.setEnabled(True)
        self.progress.setVisible(False)
        self.model.layoutChanged.emit() # Force refresh
        self.update_stats()
        QTimer.singleShot(0, lambda: QMessageBox.information(self, "Done", "Translation complete!"))

    def generate_sample_draft(self):
        """Phase 6: Generate a small sample draft for user verification"""
        if not self.units: return
        
        try:
            config = self.get_client_config()
            if not config["api_key"]:
                raise ValueError("API Key required")
        except Exception as e:
            QMessageBox.warning(self, "Config Error", str(e))
            return
            
        self.btn_sample.setEnabled(False)
        self.btn_sample.setText("Sampling...")
        
        # Launch Worker
        self.sample_worker = SampleWorker(
            self.units, config, 
            self.combo_src.currentText(), 
            self.combo_tgt.currentText(),
            profile=self.current_profile
        )
        self.sample_worker.finished.connect(self.on_sample_finished)
        self.sample_worker.error.connect(lambda e: (
            self.btn_sample.setEnabled(True),
            self.btn_sample.setText("🎲 Draft Sample"),
            QMessageBox.critical(self, "Sample Error", e)
        ))
        self.sample_worker.start()

    def on_sample_finished(self, results):
        self.btn_sample.setEnabled(True)
        self.btn_sample.setText("🎲 Draft Sample")
        
        if not results or not isinstance(results, list):
            QMessageBox.information(self, "Info", "No translatable segments found for sampling or empty result.")
            return
            
        # Format results for display
        text_preview = ""
        for res in results:
            text_preview += f"[ID {res['id']}] {res['translation']}\n\n"
            
        # Show Preview Dialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Sample Draft Preview")
        dlg.resize(600, 400)
        v = QVBoxLayout(dlg)
        
        lbl = QLabel("Here is a sample translation based on your current profile settings.\nIf this looks good, proceed to 'Translate All'.")
        v.addWidget(lbl)
        
        txt = QTextEdit()
        txt.setPlainText(text_preview)
        txt.setReadOnly(True)
        v.addWidget(txt)
        
        btns = QHBoxLayout()
        btn_ok = QPushButton("Looks Good")
        btn_ok.clicked.connect(dlg.accept)
        btn_refine = QPushButton("Adjust Profile...")
        btn_refine.clicked.connect(lambda: (dlg.reject(), self.launch_profile_wizard()))
        
        btns.addStretch()
        btns.addWidget(btn_refine)
        btns.addWidget(btn_ok)
        v.addLayout(btns)
        
        dlg.exec()

    def on_selection_changed(self, selected, deselected):
        indexes = self.table.selectionModel().selectedRows()
        if len(indexes) == 1:
            proxy_idx = indexes[0]
            source_idx = self.proxy_model.mapToSource(proxy_idx)
            self.update_ui_for_unit(source_idx.row())
        else:
            self.dock_refine.setVisible(False)
            self.active_unit_index_map = -1

    def on_qa_selection_changed(self, selected, deselected):
        indexes = self.view_qa.selectionModel().selectedRows()
        if len(indexes) == 1:
            proxy_idx = indexes[0]
            source_idx = self.proxy_qa.mapToSource(proxy_idx)
            self.update_ui_for_unit(source_idx.row())

    def update_ui_for_unit(self, row):
        self.active_unit_index_map = row
        unit = self.units[self.active_unit_index_map]
        
        self.dock_refine.setVisible(True)
        self.txt_source.setText(unit.source_abstracted)
        self.txt_target_edit.setPlainText(unit.target_abstracted or "")
        self.txt_diff.clear()
        self.txt_prompt.clear()

    def grid_navigate(self, delta):
        # Implementation for Ctrl+Up/Down
        pass 

    def navigate_grid(self, delta):
        idx = self.table.currentIndex()
        if idx.isValid():
            new_row = idx.row() + delta
            if 0 <= new_row < self.proxy_model.rowCount():
                new_idx = self.proxy_model.index(new_row, 0)
                self.table.setCurrentIndex(new_idx)
                self.table.selectRow(new_row)

    def refine_current_segment(self):
        if self.active_unit_index_map < 0: return
        
        unit = self.units[self.active_unit_index_map]
        instruction = self.txt_prompt.text()
        if not instruction: return
            
        try:
            client = self.get_client()
        except: return
            
        self.btn_refine.setEnabled(False)
        self.btn_refine.setText("Refining...")
        
        # We refine based on abstract source and CURRENT EDIT state in box
        current_val = self.txt_target_edit.toPlainText()
        
        self.refine_worker = RefineWorker(client, unit.source_abstracted, current_val, instruction)
        self.refine_worker.finished.connect(self.on_refine_finished)
        self.refine_worker.start()

    def on_refine_finished(self, new_text):
        old_text = self.txt_target_edit.toPlainText()
        
        # Show diff
        # d = difflib.HtmlDiff(wrapcolumn=40)
        
        # Update Edit box
        self.txt_target_edit.setPlainText(new_text)
        
        # Render simple Diff string (Red/Green)
        diff_html = self.generate_diff_html(old_text, new_text)
        self.txt_diff.setHtml(diff_html)
        
        self.btn_refine.setEnabled(True)
        self.btn_refine.setText("✨ Refine")
        self.txt_prompt.clear()

    def generate_diff_html(self, old, new):
        # Simple word-based diff
        seq = difflib.SequenceMatcher(None, old, new)
        html = []
        for tag, i1, i2, j1, j2 in seq.get_opcodes():
            if tag == 'replace':
                html.append(f"<span style='background-color:#ffcccc; text-decoration:line-through'>{old[i1:i2]}</span>")
                html.append(f"<span style='background-color:#ccffcc'>{new[j1:j2]}</span>")
            elif tag == 'delete':
                html.append(f"<span style='background-color:#ffcccc; text-decoration:line-through'>{old[i1:i2]}</span>")
            elif tag == 'insert':
                html.append(f"<span style='background-color:#ccffcc'>{new[j1:j2]}</span>")
            elif tag == 'equal':
                html.append(old[i1:i2])
        return "".join(html).replace("\n", "<br>")

    def apply_refinement(self):
        # Save text from edit box to model
        if self.active_unit_index_map < 0: return
        
        new_text = self.txt_target_edit.toPlainText()
        unit = self.units[self.active_unit_index_map]
        
        if unit.target_abstracted != new_text:
            unit.target_abstracted = new_text
            unit.state = "edited"
            self.model.refresh_row(self.active_unit_index_map)
            self.update_stats()
            
        # Move next
        self.navigate_grid(1)

    def show_context_menu(self, pos):
        # Get selected proxied indexes
        proxy_indexes = self.table.selectionModel().selectedRows()
        if not proxy_indexes: return
        
        # Map to source indexes
        # We need actual Unit objects for actions
        selected_units = []
        for p_idx in proxy_indexes:
            src_idx = self.proxy_model.mapToSource(p_idx)
            selected_units.append(self.units[src_idx.row()]) # Store reference

        menu = QMenu()
        
        # Translate Action
        action_translate = menu.addAction(f"🚀 Translate Selected ({len(selected_units)})")
        
        menu.addSeparator()
        
        # Lock Action
        action_lock = menu.addAction("🔒 Lock Selected")
        action_unlock = menu.addAction("🔓 Unlock Selected")
        
        menu.addSeparator()
        action_copy = menu.addAction("📄 Copy Source")
        action_clear = menu.addAction("🧹 Clear Target")
        
        # Execute
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        
        if action == action_translate:
            self.start_translation(target_units=selected_units)
            
        elif action == action_lock:
            for u in selected_units:
                u.state = "locked"
            self.model.layoutChanged.emit() # Refresh UI
            self.update_stats()
            
        elif action == action_unlock:
            for u in selected_units:
                u.state = "edited" if u.target_abstracted else "needs_translation"
            self.model.layoutChanged.emit()
            self.update_stats()
            
        elif action == action_copy:
            if selected_units:
                clip = QApplication.clipboard()
                # Copy first or all? Usually first seems safer for clipboard
                text = selected_units[0].source_abstracted
                clip.setText(text)

        elif action == action_clear:
            for u in selected_units:
                if u.state == "locked": continue
                u.target_abstracted = ""
                u.state = "needs_translation"
            self.model.layoutChanged.emit()
            self.update_stats()
        
    def run_qa(self, silent=False):
        if not self.units: return
        
        checker = QAChecker()
        error_count = 0
        warning_count = 0
        
        for unit in self.units:
            if unit.state == "locked": continue
            
            result = checker.check_unit(
                unit.source_abstracted, 
                unit.target_abstracted, 
                unit.state
            )
            
            unit.qa_status = result.status
            unit.tag_stats = result.tag_stats
            unit.qa_details = result.qa_details
            unit.errors = [issue.message for issue in result.issues]
            
            if result.status == "error":
                error_count += 1
            elif result.status == "warning":
                warning_count += 1
                
        self.model.layoutChanged.emit() # Refresh UI (Icons)
        
        # Update Readiness Panel
        if hasattr(self, 'update_readiness_panel'):
            self.update_readiness_panel(error_count, warning_count)
        
        if silent:
            return

        # CRITICAL: Defer QMessageBox to avoid Access Violation
        msg = f"QA Complete.\nErrors: {error_count}\nWarnings: {warning_count}"
        if error_count > 0:
            QTimer.singleShot(100, lambda: QMessageBox.warning(self, "QA Issues Found", msg + "\n\nPlease fix ERRORS before exporting."))
        else:
            QTimer.singleShot(100, lambda: QMessageBox.information(self, "QA Passed", msg))

    def get_repair_client(self):
        """Create a secondary LLM client for repair tasks (uses Repair Model config)"""
        if not self.chk_auto_repair.isChecked():
            raise ValueError("Auto-Repair is not enabled in Settings")
        
        # Use repair config if provided, otherwise fallback to main config
        repair_key = self.txt_repair_apikey.text() or self.txt_apikey.text()
        repair_model = self.txt_repair_model.text() or "deepseek-chat"
        repair_url = self.txt_repair_base_url.text() or "https://api.deepseek.com"
        
        if not repair_key:
            raise ValueError("Repair API Key required (or main API Key)")
        
        return LLMClient(api_key=repair_key, base_url=repair_url, model=repair_model, provider="custom")
    
    def batch_auto_repair(self):
        """Batch repair all units with qa_status == 'error'"""
        if not self.units:
            QMessageBox.warning(self, "No File", "Please open a file first.")
            return
        
        # Check if Auto-Repair is enabled
        if not self.chk_auto_repair.isChecked():
            QMessageBox.information(self, "Auto-Repair Disabled", 
                "Auto-Repair is currently disabled.\n\nPlease enable it in Settings Tab and configure a Repair Model.")
            return
        
        # Filter error units
        error_units = [u for u in self.units if u.qa_status == "error"]
        
        if not error_units:
            QMessageBox.information(self, "No Errors", "No error segments found. Run QA first!")
            return
        
        # Confirm action
        reply = QMessageBox.question(self, "Batch Auto-Repair", 
            f"Found {len(error_units)} segments with errors.\n\nAttempt to auto-repair all using AI?\n\n(This will use your Repair Model API)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            repair_client = self.get_repair_client()
        except Exception as e:
            QMessageBox.critical(self, "Config Error", str(e))
            return
        
        # Start repair worker
        self.btn_batch_repair.setEnabled(False)
        self.btn_batch_repair.setText("Repairing...")
        self.progress.setVisible(True)
        self.progress.setValue(0)
        
        self.repair_worker = RepairWorker(error_units, repair_client)
        self.repair_worker.progress.connect(lambda c, t: self.progress.setValue(int(c/t*100)))
        self.repair_worker.finished.connect(self.on_repair_finished)
        self.repair_worker.error.connect(lambda e: QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Repair Error", e)))
        self.repair_worker.start()
    
    def on_repair_finished(self, repaired_count, failed_count):
        """Called when batch repair completes"""
        self.btn_batch_repair.setEnabled(True)
        self.btn_batch_repair.setText("🔧 Batch Auto-Repair")
        self.progress.setVisible(False)
        
        # Refresh UI
        self.model.layoutChanged.emit()
        self.update_stats()
        
        # Re-run QA to verify fixes
        QTimer.singleShot(500, self.run_qa)
        
        # Show summary
        msg = f"Repair Complete!\n\nRepaired: {repaired_count}\nFailed: {failed_count}\n\nRe-running QA to verify..."
        QTimer.singleShot(100, lambda: QMessageBox.information(self, "Batch Repair Done", msg))

    def save_file(self):
        if not self.units: return
        
        # Auto-run QA check before save
        self.run_qa()
        
        # Check for blockers
        errors = [u for u in self.units if u.qa_status == "error"]
        if errors:
            QMessageBox.critical(self, "Export Blocked", f"Found {len(errors)} Critical Errors (Tag Mismatch).\n\nYou must fix them to ensure valid XLIFF output.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export XLIFF", "", "XLIFF Files (*.xlf *.xliff);;All Files (*)")
        if path:
            for u in self.units:
                if u.target_abstracted:
                    try:
                        u.target_raw = self.abstractor.reconstruct(u.target_abstracted, u.tags_map)
                    except Exception as e:
                        logger.warning(f"Tag reconstruction failed for unit {u.id}: {e}")
            self.parser.update_targets(self.units, path)
            logger.info(f"File exported to: {path}")
            QMessageBox.information(self, "Saved", f"Exported to {path}")

    def update_readiness_panel(self, errors, warnings):
        """Update the QA dashboard/panel"""
        if not hasattr(self, 'panel_readiness'): return
        
        self.lbl_readiness_stats.setText(f"Errors: {errors} | Warnings: {warnings}")
        
        # Calculate health
        total_active = len([u for u in self.units if u.state != "locked"])
        if total_active > 0:
            health = max(0, 100 - (errors * 5) - (warnings * 1)) # Simple penalty
        else:
            health = 100
            
        self.progress_health.setValue(health)
        
        # Color coding
        if health == 100 and errors == 0:
            self.progress_health.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }") # Green
            self.lbl_readiness_status.setText("<b>Status:</b> <span style='color:#4CAF50'>Ready to Export</span>")
        elif errors > 0:
            self.progress_health.setStyleSheet("QProgressBar::chunk { background-color: #F44336; }") # Red
            self.lbl_readiness_status.setText("<b>Status:</b> <span style='color:#F44336'>Blocked (Fix Errors)</span>")
        else:
            self.progress_health.setStyleSheet("QProgressBar::chunk { background-color: #FFC107; }") # Orange
            self.lbl_readiness_status.setText("<b>Status:</b> <span style='color:#FFC107'>Warnings Present</span>")

    def on_qa_context_menu(self, pos):
        """Show context menu for QA table"""
        index = self.view_qa.indexAt(pos)
        if not index.isValid(): return
        
        menu = QMenu(self)
        action_jump = QAction("✏️ Quick Edit (Jump)", self)
        action_repair = QAction("🔧 Repair Segment", self)
        
        action_jump.triggered.connect(lambda checked, idx=index: self.on_qa_double_click(idx))
        action_repair.triggered.connect(lambda checked, idx=index: self.repair_single_unit(idx))
        
        menu.addAction(action_jump)
        menu.addAction(action_repair)
        
        menu.exec(self.view_qa.viewport().mapToGlobal(pos))

    def repair_single_unit(self, index):
        source_index = self.proxy_qa.mapToSource(index)
        unit = self.model.units[source_index.row()]
        
        if unit.qa_status != "error":
             QMessageBox.information(self, "Info", "This segment does not have QA errors.")
             return

        reply = QMessageBox.question(self, "Repair Segment", "Attempt to repair this segment using AI?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes: return

        try:
            client = self.get_repair_client()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
            
        self.repair_worker = RepairWorker([unit], client)
        self.repair_worker.finished.connect(lambda r, f: self.on_single_repair_finished(r, f))
        self.repair_worker.error.connect(lambda e: QTimer.singleShot(0, lambda: QMessageBox.warning(self, "Repair Failed", e)))
        self.repair_worker.start()

    def on_single_repair_finished(self, repaired, failed):
        if repaired > 0:
            QTimer.singleShot(0, lambda: QMessageBox.information(self, "Success", "Segment repaired successfully."))
            # Defer QA check to next event loop to prevent Access Violation
            # and avoid double layout updates (run_qa handles update)
            QTimer.singleShot(0, lambda: self.run_qa(silent=True))
        else:
            QTimer.singleShot(0, lambda: QMessageBox.warning(self, "Failed", "AI could not repair the segment."))

    def on_qa_double_click(self, index):
        """Handle double click on QA table"""
        # Get the source model index
        source_index = self.proxy_qa.mapToSource(index)
        row = source_index.row()
        
        # Switch to Translate tab
        self.tabs.setCurrentIndex(0) # Index 0 is Worktable
        
        # Select the row in main table
        self.jump_to_unit(row)

    def closeEvent(self, event):
        """Save settings on exit"""
        self.settings.setValue("source_lang", self.combo_src.currentText())
        self.settings.setValue("target_lang", self.combo_tgt.currentText())
        self.settings.setValue("provider", self.combo_provider.currentText())
        self.settings.setValue("api_key", self.txt_apikey.text())
        self.settings.setValue("model", self.txt_model.text())
        self.settings.setValue("base_url", self.txt_base_url.text())
        self.settings.setValue("auto_repair_enabled", self.chk_auto_repair.isChecked())
        self.settings.setValue("repair_model", self.txt_repair_model.text())
        self.settings.setValue("repair_api_key", self.txt_repair_apikey.text())
        self.settings.setValue("repair_base_url", self.txt_repair_base_url.text())
        self.settings.setValue("diagnostic_mode", self.chk_diagnostic.isChecked())
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    def jump_to_unit(self, row_index):
        """Scroll to and select the unit in the main table"""
        idx = self.model.index(row_index, 0)
        # Map through proxy if main table uses proxy
        if hasattr(self, 'proxy_model'):
             proxy_idx = self.proxy_model.mapFromSource(idx)
             if proxy_idx.isValid():
                self.table.selectRow(proxy_idx.row())
                self.table.scrollTo(proxy_idx)
             else:
                 # It might be filtered out in the main view
                 self.proxy_model.set_status_filter("All") # Reset filter to find it
                 self.proxy_model.set_text_filter("")
                 proxy_idx = self.proxy_model.mapFromSource(idx)
                 if proxy_idx.isValid():
                     self.table.selectRow(proxy_idx.row())
                     self.table.scrollTo(proxy_idx)

if __name__ == "__main__":
    import faulthandler
    
    # 1. Ensure logs directory exists BEFORE any redirection
    os.makedirs("logs", exist_ok=True)
    
    # 2. Enable fault handler to catch hard crashes (segfaults)
    # Use unbuffered binary mode for crash dump to ensure immediate write on crash
    crash_file = open("logs/crash_dump.txt", "wb", buffering=0)
    faulthandler.enable(file=crash_file, all_threads=True)
    
    # 3. Setup global exception hook for Python-level uncaught errors
    setup_exception_hook()
    
    # 4. Diagnostic environment variables (can be toggled via settings)
    settings = QSettings("Gemini", "XLIFF_AI_Assistant")
    if settings.value("diagnostic_mode", False, type=bool):
        os.environ["QT_DEBUG_PLUGINS"] = "1"
        # Filter out extremely spammy categories
        os.environ["QT_LOGGING_RULES"] = "*.debug=true;qt.text.emojisegmenter=false;qt.text.layout=false;qt.qpa.events=false"
        logger.info("Diagnostic mode enabled: QT_DEBUG_PLUGINS=1")
    
    app = QApplication(sys.argv)
    qdarktheme.setup_theme()
    logger.info("Application starting...")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())