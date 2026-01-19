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
                             QToolBar, QSpacerItem, QSizePolicy, QTabWidget)
from PyQt6.QtCore import (Qt, QAbstractTableModel, QModelIndex, QThread, pyqtSignal, 
                          QSize, QSettings, QSortFilterProxyModel, QRegularExpression)
from PyQt6.QtGui import QAction, QIcon, QColor, QBrush, QKeySequence, QShortcut

# Ensure core modules importable
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from core.parser import XliffParser
from core.abstractor import TagAbstractor
from core.logger import get_logger, setup_exception_hook
from ai.client import LLMClient

# Initialize logger for this module
logger = get_logger(__name__)

# --- Worker Threads ---

class TranslationWorker(QThread):
    progress = pyqtSignal(int, int) # current, total
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, units, client, source_lang="zh-CN", target_lang="en"):
        super().__init__()
        self.units = units
        self.client = client
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.is_running = True

    def run(self):
        to_translate = [u for u in self.units if u.state != 'locked']
        total = len(to_translate)
        batch_size = 10
        
        try:
            for i in range(0, total, batch_size):
                if not self.is_running: break
                
                chunk = to_translate[i:i+batch_size]
                payload = [{"id": u.id, "text": u.source_abstracted} for u in chunk]
                
                results = self.client.translate_batch(payload, self.source_lang, self.target_lang)
                
                res_map = {str(r["id"]): r["translation"] for r in results}
                for u in chunk:
                    if str(u.id) in res_map:
                        u.target_abstracted = res_map[str(u.id)]
                        u.state = "translated"
                
                self.progress.emit(min(i + batch_size, total), total)
                
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self.is_running = False

class RefineWorker(QThread):
    finished = pyqtSignal(str) # new_translation
    error = pyqtSignal(str)

    def __init__(self, client, source, current_target, instruction):
        super().__init__()
        self.client = client
        self.source = source
        self.current_target = current_target
        self.instruction = instruction

    def run(self):
        try:
            new_trans = self.client.refine_segment(self.source, self.current_target, self.instruction)
            self.finished.emit(new_trans)
        except Exception as e:
            self.error.emit(str(e))
            
class TestConnectionWorker(QThread):
    finished = pyqtSignal(bool, str)
    
    def __init__(self, client):
        super().__init__()
        self.client = client
        
    def run(self):
        try:
            success, msg = self.client.test_connection()
            self.finished.emit(success, msg)
        except Exception as e:
            self.finished.emit(False, str(e))

# --- Models ---

class XliffTableModel(QAbstractTableModel):
    def __init__(self, units=None):
        super().__init__()
        self.units = units or []
        self.headers = ["ID", "State", "Tags", "QA", "Source", "Target"]

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
            elif col == 4: return unit.source_abstracted
            elif col == 5: return unit.target_abstracted
            
        elif role == Qt.ItemDataRole.DecorationRole and col == 1:
            return None # We use DisplayRole for Emojis now

            
        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == 1: return f"Status: {unit.state}"

        return None

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def flags(self, index):
        if not index.isValid(): return Qt.ItemFlag.NoItemFlags
        
        flags = super().flags(index)
        unit = self.units[index.row()]
        
        if index.column() == 5:
            if unit.state != "locked":
                flags |= Qt.ItemFlag.ItemIsEditable
        
        return flags

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if index.isValid() and role == Qt.ItemDataRole.EditRole and index.column() == 5:
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
        
        # Models
        self.model = XliffTableModel()
        self.proxy_model = XliffFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        
        self.active_unit_index_map = -1 # Mapped index in source model
        
        # Workers
        self.trans_worker = None
        self.refine_worker = None
        self.test_worker = None
        
        self.setup_ui()
        self.load_settings()
        self.apply_styles()

    def setup_ui(self):
        # Central Widget is now a TabWidget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # --- Tab 1: Translate (Workbench) ---
        self.tab_translate = QWidget()
        self.setup_translate_tab()
        self.tabs.addTab(self.tab_translate, "Worktable")
        
        # --- Tab 2: Settings ---
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
        
        self.btn_trans = QPushButton("🚀 Translate All")
        self.btn_trans.clicked.connect(lambda: self.start_translation())
        top_bar.addWidget(self.btn_trans)

        self.btn_qa = QPushButton("🛡️ Run QA")
        self.btn_qa.clicked.connect(self.run_qa)
        top_bar.addWidget(self.btn_qa)
        
        top_bar.addSpacing(20)
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
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Tags (New)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # QA (New)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) # Source
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch) # Target
        
        layout.addWidget(self.table)

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
            
    def get_client(self):
        prov = self.combo_provider.currentText()
        key = self.txt_apikey.text()
        base = self.txt_base_url.text()
        model = self.txt_model.text()
        
        if not key:
            raise ValueError("API Key required")
            
        return LLMClient(api_key=key, base_url=base, model=model, provider="custom")

    def test_connection(self):
        try:
            client = self.get_client()
        except Exception as e:
            QMessageBox.warning(self, "Config Error", str(e))
            return
            
        self.btn_test_conn.setEnabled(False)
        self.btn_test_conn.setText("Testing...")
        self.test_worker = TestConnectionWorker(client)
        self.test_worker.finished.connect(lambda s, m: (
            self.btn_test_conn.setEnabled(True),
            self.btn_test_conn.setText("📡 Test Connection"),
            QMessageBox.information(self, "Result", m) if s else QMessageBox.critical(self, "Error", m)
        ))
        self.test_worker.start()

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open XLIFF", "", "XLIFF (*.xlf *.xliff)")
        if path:
            try:
                self.parser = XliffParser(path)
                self.parser.load()
                raw_units = self.parser.get_translation_units()
                self.units = []
                for u in raw_units:
                    res = self.abstractor.abstract(u.source_raw)
                    u.source_abstracted = res.abstracted_text
                    u.tags_map = res.tags_map
                    
                    if u.target_raw:
                        # Attempt to abstract target as well for visualization
                        # Note: This naively re-indexes tags. Complex re-ordering might mismatch IDs.
                        res_tgt = self.abstractor.abstract(u.target_raw)
                        u.target_abstracted = res_tgt.abstracted_text
                    
                    self.units.append(u)
                
                self.model.update_data(self.units)
                self.proxy_model.invalidate()
                self.update_stats()
            except Exception as e:
                logger.error(f"Failed to open file: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", str(e))

    def update_stats(self):
        total = len(self.units)
        done = sum(1 for u in self.units if u.target_abstracted)
        self.lbl_stats.setText(f"Total: {total} | Translated: {done}")

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
        
        self.trans_worker = TranslationWorker(target_units, client, self.combo_src.currentText(), self.combo_tgt.currentText())
        self.trans_worker.progress.connect(lambda c, t: self.progress.setValue(int(c/t*100)))
        self.trans_worker.finished.connect(self.on_trans_finished)
        self.trans_worker.error.connect(lambda e: QMessageBox.critical(self, "Error", e))
        self.trans_worker.start()

    def on_trans_finished(self):
        self.btn_trans.setEnabled(True)
        self.progress.setVisible(False)
        self.model.layoutChanged.emit() # Force refresh
        self.update_stats()
        QMessageBox.information(self, "Done", "Translation complete!")

    def on_selection_changed(self, selected, deselected):
        indexes = self.table.selectionModel().selectedRows()
        if len(indexes) == 1:
            # Get model index from proxy
            proxy_idx = indexes[0]
            source_idx = self.proxy_model.mapToSource(proxy_idx)
            self.active_unit_index_map = source_idx.row()
            
            unit = self.units[self.active_unit_index_map]
            
            self.dock_refine.setVisible(True)
            self.txt_source.setText(unit.source_abstracted)
            self.txt_target_edit.setPlainText(unit.target_abstracted or "")
            self.txt_diff.clear() # Clear specific Diff
            self.txt_prompt.clear()
        else:
            self.dock_refine.setVisible(False)
            self.active_unit_index_map = -1

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
        
    def run_qa(self):
        if not self.units: return
        
        # Use Python native re to avoid Qt Access Violations
        pattern = re.compile(r"\{\d+\}")
        error_count = 0
        warning_count = 0
        
        for unit in self.units:
            if unit.state == "locked": continue
            
            unit.errors = [] # Reset
            
            # 1. Tag Count Check
            source_tag_count = len(unit.tags_map)
            
            # Count target tags in abstract string
            # count matches of {n}
            matches = pattern.findall(unit.target_abstracted or "")
            target_tag_count = len(matches)
            
            unit.tag_stats = f"TAG: {target_tag_count}/{source_tag_count}"
            
            # 2. Logic
            if target_tag_count != source_tag_count:
                unit.qa_status = "error"
                unit.errors.append("Tag quantity mismatch")
                error_count += 1
            elif not unit.target_abstracted and unit.state in ["translated", "edited"]:
                unit.qa_status = "warning"
                unit.errors.append("Empty translation")
                warning_count += 1
            else:
                unit.qa_status = "ok"
                
        self.model.layoutChanged.emit() # Refresh UI (Icons)
        
        msg = f"QA Complete.\nErrors: {error_count}\nWarnings: {warning_count}"
        if error_count > 0:
            QMessageBox.warning(self, "QA Issues Found", msg + "\n\nPlease fix ERRORS before exporting.")
        else:
            QMessageBox.information(self, "QA Passed", msg)

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

if __name__ == "__main__":
    import faulthandler
    # Enable fault handler to catch hard crashes (segfaults)
    sys.stderr = open("logs/crash_dump.txt", "w", encoding="utf-8")
    faulthandler.enable(file=sys.stderr, all_threads=True)
    
    setup_exception_hook()  # Install global crash logger
    app = QApplication(sys.argv)
    qdarktheme.setup_theme()
    logger.info("Application starting...")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())