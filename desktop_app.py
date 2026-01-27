import sys
import os
import time
import difflib
import re
import tempfile # For atomic save
import shutil # For atomic save
import qdarktheme # Modern theme
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTableView, QFileDialog, 
                             QHeaderView, QMessageBox, QLabel, QAbstractItemView,
                             QComboBox, QLineEdit, QGroupBox, QMenu, QDockWidget,
                             QTextEdit, QProgressBar, QSplitter, QFrame, QCheckBox,
                             QToolBar, QSpacerItem, QSizePolicy, QTabWidget, QDialog, QToolButton)
from PyQt6.QtCore import (Qt, QAbstractTableModel, QModelIndex, QThread, pyqtSignal, 
                          QSize, QSettings, QSortFilterProxyModel, QRegularExpression, QTimer, QEvent, QPersistentModelIndex)
from PyQt6.QtGui import QAction, QIcon, QColor, QBrush, QKeySequence, QShortcut

# Ensure core modules importable
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from core.parser import XliffParser
from core.abstractor import TagAbstractor
from core.logger import get_logger, setup_exception_hook
from core.qa import QAChecker
from core.repair import RepairWorker
from core.workers import TranslationWorker, RefineWorker, TestConnectionWorker, SampleWorker, WorkbenchWorker
from core.profile import TranslationProfile, TranslationProfileContainer, ProfileStatus
from core.autosave import Autosaver
from core.settings_manager import SettingsManager
from core.token_guard import TokenGuard
from ui.profile_wizard import ProfileWizardDialog, WizardResult
from ui.workbench_frame import AIWorkbenchFrame
from ui.settings_dialog import SettingsDialog
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
        self.setWindowTitle("XLIFF AI Assistant Pro v2.0 [*]") # Support dirty indicator
        self.resize(1400, 900)
        
        # Settings (UI State)
        self.settings = QSettings("Gemini", "XLIFF_AI_Assistant")
        # Settings Manager (Business Logic)
        self.settings_manager = SettingsManager()
        
        # State Flags
        self.is_dirty = False # Tracks unsaved changes for Close Prompt
        
        # Data
        self.parser = None
        self.units = []
        self.abstractor = TagAbstractor()
        
        # Autosave
        self.autosaver = None
        
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
        self.wb_worker = None
        
        self.setup_ui()
        self.load_settings()
        self.apply_styles()
        
        # Connect autosave to data changes (Universal Autosave)
        self.model.dataChanged.connect(lambda: self.perform_autosave())
        
        # Suggestion Bar (Hidden by default)
        self.suggestion_bar = QFrame()
        self.suggestion_bar.setObjectName("suggestionBar")
        self.suggestion_bar.setStyleSheet("""
            QFrame#suggestionBar {
                background-color: #FFF3CD;
                border-bottom: 1px solid #FFECB3;
                padding: 10px;
            }
            QLabel { color: #856404; font-weight: bold; }
        """)
        self.suggestion_bar.setVisible(False)
        
        # Post-init: Check for crash recovery
        QTimer.singleShot(100, self.check_crash_recovery)

    def check_crash_recovery(self):
        """Check if app was closed unexpectedly and prompt for recovery."""
        try:
            clean_shutdown = self.settings.value("clean_shutdown", True, type=bool)
            last_active = self.settings.value("last_active_file", "")
            last_opened = self.settings.value("last_opened_file", "")
            last_fingerprint = self.settings.value("last_file_fingerprint", "")
            
            logger.info(f"Startup Check: Clean={clean_shutdown}, LastActive={last_active}, LastOpened={last_opened}")
            
            # Reset clean shutdown flag immediately and SYNC to disk
            self.settings.setValue("clean_shutdown", False)
            self.settings.sync()
            
            # Priority 1: Crash Recovery
            if not clean_shutdown and last_active and os.path.exists(last_active):
                logger.info(f"Unexpected shutdown detected. Last active file: {last_active}")
                
                # Verify fingerprint to avoid loading corrupted/externally changed files blindly
                current_fingerprint = Autosaver.calculate_file_fingerprint(last_active)
                if current_fingerprint != last_fingerprint:
                    logger.warning("Last active file has changed externally. Skipping auto-resume.")
                    QMessageBox.warning(self, "Session Resume Skipped", 
                        f"The file '{os.path.basename(last_active)}' was modified externally after the crash.\n\nCrash recovery aborted to prevent data corruption.")
                    return

                # Check for autosave
                autosave_path = Autosaver._get_autosave_path(last_active)
                has_autosave = os.path.exists(autosave_path)
                
                if has_autosave:
                    # MERGED DIALOG: "Recover & Open", "Open Original", "Cancel"
                    box = QMessageBox(self)
                    box.setWindowTitle("Crash Recovery")
                    box.setText(f"Application closed unexpectedly while editing '{os.path.basename(last_active)}'.\n\nUnsaved progress found.")
                    box.setIcon(QMessageBox.Icon.Warning)
                    
                    btn_recover = box.addButton("Recover & Open", QMessageBox.ButtonRole.AcceptRole)
                    btn_open = box.addButton("Open Original", QMessageBox.ButtonRole.ActionRole)
                    btn_cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                    
                    box.exec()
                    
                    if box.clickedButton() == btn_recover:
                        self.load_file(last_active, auto_recover=True)
                    elif box.clickedButton() == btn_open:
                        self.load_file(last_active, auto_recover=False)
                    else:
                        pass # Cancel
                else:
                    # Simple "Resume" Prompt
                    reply = QMessageBox.question(self, "Resume Session", 
                        f"Application closed unexpectedly.\n\nReopen '{os.path.basename(last_active)}'?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        self.load_file(last_active, auto_recover=False)
            
            # Priority 2: Normal Resume (Open Last File)
            elif last_opened and os.path.exists(last_opened):
                # Only ask if we didn't just crash
                reply = QMessageBox.question(self, "Open Last File", 
                    f"Do you want to reopen '{os.path.basename(last_opened)}'?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.load_file(last_opened)

        except Exception as e:
            logger.error(f"Error in crash recovery check: {e}")

    def load_file(self, path, auto_recover=False):
        """
        Internal method to load a file.
        :param path: Absolute path to XLIFF file
        :param auto_recover: If True, automatically apply autosave without prompt
        """
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
            
            # Format headers
            for v in [self.table, self.view_qa]:
                h = v.horizontalHeader()
                h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) 
                h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) 
                h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) 
                h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) 
                h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) 
                h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch) 
                h.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch) 
            
            self.update_stats()
            
            # 3. Load Profile
            self.load_profile_for_file(path)
            
            # 4. Session Tracking
            self.settings.setValue("last_active_file", path) # For crash recovery
            self.settings.setValue("last_opened_file", path) # For normal resume
            self.settings.setValue("last_file_fingerprint", Autosaver.calculate_file_fingerprint(path))
            self.settings.sync() # Force persist immediately
            
            # 5. Autosave Init & Recovery
            self.init_autosave(path, auto_recover=auto_recover)
            
            # Reset dirty flag after load
            self.is_dirty = False 
            self.setWindowModified(False)
            
        except Exception as e:
            logger.error(f"Failed to load file: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", str(e))

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open XLIFF", "", "XLIFF (*.xlf *.xliff)")
        if path:
            self.load_file(path)

    def init_autosave(self, file_path, auto_recover=False):
        """Initialize autosaver and check for crash recovery"""
        self.autosaver = Autosaver(file_path)
        
        recovery_data = self.autosaver.check_recovery_available()
        if recovery_data:
            if auto_recover:
                # Apply silently
                self.apply_recovery(recovery_data)
                return

            ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(recovery_data['timestamp']))
            count = recovery_data.get('count', 0)
            
            reply = QMessageBox.question(
                self, "Crash Recovery", 
                f"Found unsaved progress from {ts}.\n\n"
                f"Recover {count} segments?\n\n"
                "(Yes to recover, No to discard)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.apply_recovery(recovery_data)
            else:
                # User chose to discard
                self.autosaver.cleanup()

    def setup_ui(self):
        # --- Main Layout Wrapper (Splitter) ---
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.main_splitter)
        
        # --- Left Pane: Main Application ---
        self.left_container = QWidget()
        central_layout = QVBoxLayout(self.left_container)
        central_layout.setContentsMargins(0,0,0,0)
        central_layout.setSpacing(0)
        
        self.tabs = QTabWidget() # Initialize Tabs
        self.main_splitter.addWidget(self.left_container)
        
        # --- Right Pane: AI Workbench ---
        self.workbench = AIWorkbenchFrame()
        self.main_splitter.addWidget(self.workbench)
        
        # Initial State
        self.workbench_visible = self.settings.value("workbench_visible", True, type=bool)
        self.workbench.setVisible(self.workbench_visible)
        
        # Connect Signals
        self.connect_workbench_signals()
        
        # Initialize Workbench Models
        self.update_workbench_config()
        
        # --- Brief Card (Phase 3) ---
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
        
        # Suggestion Bar (Created in init, added here)
        if hasattr(self, 'suggestion_bar'):
            central_layout.addWidget(self.suggestion_bar)
            
            # Setup Layout for Suggestion Bar
            sb_layout = QHBoxLayout(self.suggestion_bar)
            self.lbl_suggestion = QLabel("Suggestion Message")
            sb_layout.addWidget(self.lbl_suggestion)
            
            self.btn_suggestion_action = QPushButton("Action")
            self.btn_suggestion_action.setStyleSheet("background-color: #FFC107; color: black; border: none; padding: 5px 10px;")
            sb_layout.addWidget(self.btn_suggestion_action)
            
            sb_layout.addStretch()
            
            btn_dismiss = QPushButton("✕")
            btn_dismiss.setFixedSize(24, 24)
            btn_dismiss.setFlat(True)
            btn_dismiss.clicked.connect(lambda: self.suggestion_bar.setVisible(False))
            sb_layout.addWidget(btn_dismiss)
            
        central_layout.addWidget(self.tabs)
        
        # --- Tab 1: Translate (Workbench) ---
        self.tab_translate = QWidget()
        self.setup_translate_tab()
        self.tabs.addTab(self.tab_translate, "Worktable")
        
        # --- Tab 2: QA Focus ---
        self.tab_qa = QWidget()
        self.setup_qa_tab()
        self.tabs.addTab(self.tab_qa, "🛡️ QA Review")
        
        # Settings moved to Dialog

    def setup_translate_tab(self):
        layout = QVBoxLayout(self.tab_translate)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Top Bar: File Actions & Stats
        top_bar = QHBoxLayout()
        
        self.btn_open = QPushButton("📂 Open")
        self.btn_open.clicked.connect(self.open_file)
        top_bar.addWidget(self.btn_open)
        
        # Language Selectors
        top_bar.addWidget(QLabel("Src:"))
        self.combo_src = QComboBox()
        self.combo_src.addItems(["zh-CN", "en", "ja", "de", "fr"])
        top_bar.addWidget(self.combo_src)
        
        top_bar.addWidget(QLabel("Tgt:"))
        self.combo_tgt = QComboBox()
        self.combo_tgt.addItems(["en", "zh-CN", "ja", "de", "fr"])
        top_bar.addWidget(self.combo_tgt)
        
        # Save (Overwrite)
        self.btn_save_overwrite = QPushButton("💾 Save")
        self.btn_save_overwrite.setToolTip("Save changes to current file (Ctrl+S)")
        self.btn_save_overwrite.clicked.connect(self.save_current_file)
        top_bar.addWidget(self.btn_save_overwrite)
        
        self.btn_save = QPushButton("📤 Export") # Renamed from Save to Export
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
        # Theme Toggle (Icon only)
        self.btn_theme = QToolButton()
        self.btn_theme.setText("🌗") # Default text to ensure visibility
        self.btn_theme.setToolTip("Toggle Theme")
        self.btn_theme.clicked.connect(self.toggle_theme)
        # Icon size handled by style or system
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
        self.table.selectionModel().currentChanged.connect(self.on_current_row_changed)
        
        # Row Height Optimization
        self.table.setWordWrap(True)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.verticalHeader().setDefaultSectionSize(40) # Default compact height
        self.table.setMouseTracking(True) # Enable hover tracking
        self.table.entered.connect(self.on_table_hover)
        
        # Shortcuts
        QShortcut(QKeySequence("Ctrl+Up"), self.table, lambda: self.navigate_grid(-1))
        QShortcut(QKeySequence("Ctrl+Down"), self.table, lambda: self.navigate_grid(1))
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_current_file) # Save Shortcut
        
        # Table Headers
        h = self.table.horizontalHeader()
        h.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        h.customContextMenuRequested.connect(self.show_header_context_menu)
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        
        # Default Widths (Init)
        # We will load persisted widths in load_file or a separate method
        
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

    def open_settings_dialog(self):
        dlg = SettingsDialog(self)
        dlg.settings_changed.connect(self.on_settings_changed)
        dlg.exec()
        self.update_workbench_config()

    def update_workbench_config(self):
        """Update Workbench UI with latest settings (Models)"""
        try:
            # 1. Get Active Provider Models
            provider = self.settings_manager.get_active_provider()
            config = self.settings_manager.get_provider_config(provider)
            models = config.get("models", [])
            
            # 2. Update Combo
            self.workbench.model_combo.blockSignals(True)
            self.workbench.model_combo.clear()
            self.workbench.model_combo.addItems(models)
            
            # 3. Set Default
            default_model = config.get("default_model")
            if default_model:
                self.workbench.model_combo.setCurrentText(default_model)
            
            self.workbench.model_combo.blockSignals(False)
            
            # 4. Update Status Indicator (Visual check)
            api_key = self.settings_manager.get_api_key(provider)
            if api_key:
                self.workbench.status_indicator.set_status("green")
                self.workbench.status_indicator.setToolTip(f"Connected to {provider}")
            else:
                self.workbench.status_indicator.set_status("yellow")
                self.workbench.status_indicator.setToolTip("API Key Missing")
                
        except Exception as e:
            logger.error(f"Failed to update workbench config: {e}")

    def on_settings_changed(self):
        # Reload settings if needed (e.g. language defaults)
        self.load_settings()

    def toggle_theme(self):
        """Toggle between dark and light theme"""
        current_theme = self.settings.value("theme", "dark")
        new_theme = "light" if current_theme == "dark" else "dark"
        
        qdarktheme.setup_theme(new_theme)
        self.apply_styles(new_theme)
        
        self.settings.setValue("theme", new_theme)
        logger.info(f"Theme changed to {new_theme}")

    def load_settings(self):
        try:
            # Language Defaults
            self.combo_src.setCurrentText(self.settings.value("source_lang", "zh-CN"))
            self.combo_tgt.setCurrentText(self.settings.value("target_lang", "en"))
            
            # Geometry
            geo = self.settings.value("geometry")
            if geo: self.restoreGeometry(geo)
            
            # Theme
            theme = self.settings.value("theme", "dark")
            qdarktheme.setup_theme(theme)
            self.apply_styles(theme) 
            
        except Exception as e:
            print(f"Error loading settings: {e}")

    def apply_styles(self, theme="dark"):
        pass

    def get_client_config(self):
        # Retrieve active config from SettingsManager
        manager = self.settings_manager
        provider = manager.get_active_provider()
        config = manager.get_provider_config(provider)
        key = manager.get_api_key(provider)
        
        return {
            "api_key": key,
            "base_url": config.get("base_url"),
            "model": config.get("default_model") or (config.get("models")[0] if config.get("models") else ""),
            "provider": "custom"
        }

    def get_client(self):
        config = self.get_client_config()
        if not config["api_key"]:
            raise ValueError("API Key required. Please configure in Settings.")
            
        return LLMClient(**config)

    def test_connection(self):
        # Moved to SettingsDialog
        pass

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
                    if v == self.view_qa:
                        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
                        h.setStretchLastSection(True)
                    else:
                        # Main Table: Restore column state
                        self.restore_column_state()
                
                self.update_stats()
                
                # 3. Load Profile (Sidecar Logic)
                self.load_profile_for_file(path)
                
                # 4. Autosave Init & Recovery Check
                self.init_autosave(path)
                
            except Exception as e:
                logger.error(f"Failed to open file: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", str(e))

    def init_autosave(self, file_path):
        """Initialize autosaver and check for crash recovery"""
        self.autosaver = Autosaver(file_path)
        
        recovery_data = self.autosaver.check_recovery_available()
        if recovery_data:
            ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(recovery_data['timestamp']))
            count = recovery_data.get('count', 0)
            
            reply = QMessageBox.question(
                self, "Crash Recovery", 
                f"Found unsaved progress from {ts}.\n\n"
                f"Recover {count} segments?\n\n"
                "(Yes to recover, No to discard)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.apply_recovery(recovery_data)
            else:
                # User chose to discard
                self.autosaver.cleanup()

    def apply_recovery(self, data):
        """Apply patch from autosave to current model"""
        try:
            updates = data.get("units", {})
            applied_count = 0
            
            for u in self.units:
                if u.id in updates:
                    patch = updates[u.id]
                    u.target_abstracted = patch['target']
                    u.state = patch['state']
                    applied_count += 1
            
            self.model.layoutChanged.emit()
            self.update_stats()
            logger.info(f"Recovered {applied_count} segments from autosave.")
            QMessageBox.information(self, "Recovery Complete", f"Successfully restored {applied_count} segments.")
            
        except Exception as e:
            logger.error(f"Recovery failed: {e}")
            QMessageBox.critical(self, "Recovery Failed", str(e))

    def perform_autosave(self):
        """Trigger an atomic autosave of current progress"""
        if not self.is_dirty:
            self.is_dirty = True
            self.setWindowModified(True)
            
        if self.autosaver:
            # We save everything, let Autosaver filter inside
            # Run in main thread to ensure data consistency (it's fast JSON dump)
            self.autosaver.save_patch(self.units)

    def atomic_save_file(self, target_path):
        """
        Atomic save implementation: Write to temp -> Move to target
        Uses QSaveFile logic (simulated with tempfile+shutil for Pythonic simplicity/robustness)
        """
        try:
            # 1. Update targets in parser (memory)
            for u in self.units:
                if u.target_abstracted:
                    try:
                        u.target_raw = self.abstractor.reconstruct(u.target_abstracted, u.tags_map)
                    except Exception as e:
                        logger.warning(f"Tag reconstruction failed for unit {u.id}: {e}")
            
            # 2. Write to temp file first
            dir_name = os.path.dirname(target_path)
            with tempfile.NamedTemporaryFile(mode='w', dir=dir_name, delete=False, encoding='utf-8') as tf:
                # We use parser's save logic but redirect to temp file
                # Need to inspect parser.update_targets to see if it accepts a stream or path
                # Assuming it takes a path.
                temp_name = tf.name
            
            # Re-use parser's logic to write to the TEMP path
            self.parser.update_targets(self.units, temp_name)
            
            # 3. Atomic Move (Replace)
            if os.path.exists(target_path):
                os.remove(target_path) # Required on Windows before rename usually, or use replace
            
            os.replace(temp_name, target_path)
            
            return True
        except Exception as e:
            logger.error(f"Atomic save failed: {e}")
            if 'temp_name' in locals() and os.path.exists(temp_name):
                os.remove(temp_name)
            raise e

    def save_current_file(self):
        """Save changes to the current file (Ctrl+S)"""
        if not self.units or not self.parser or not self.parser.file_path:
            return
            
        try:
            # Atomic Write
            self.atomic_save_file(self.parser.file_path)
            
            # Success Handling
            self.is_dirty = False
            self.setWindowModified(False)
            if self.autosaver:
                self.autosaver.cleanup()
                
            # Update fingerprint
            self.settings.setValue("last_file_fingerprint", Autosaver.calculate_file_fingerprint(self.parser.file_path))
            self.settings.sync()
            
            QTimer.singleShot(0, lambda: QMessageBox.information(self, "Saved", f"Successfully saved to disk."))
            
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Could not save file:\n{e}")

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

    def calculate_source_fingerprint(self):
        """Calculate a hash of the abstract source content to detect file changes."""
        import hashlib
        content = "".join([u.source_abstracted for u in self.units if u.source_abstracted])
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def load_profile_for_file(self, xliff_path):
        """Loads profile from sidecar or creates a new one with Wizard"""
        # Sidecar path: file.xlf -> file.profile.json
        self.current_sidecar_path = f"{xliff_path}.profile.json"
        
        # Calculate current fingerprint
        current_fingerprint = self.calculate_source_fingerprint()
        
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
            
        # Decision Logic: To popup or not to popup
        status = self.current_profile.controls.status
        saved_fingerprint = self.current_profile.controls.source_fingerprint
        
        # 1. NEW Profile (No Sidecar) -> Auto Popup
        if status == ProfileStatus.NEW:
            self.launch_profile_wizard()
            
        # 2. CONFIRMED but Mismatch -> Suggestion Bar
        elif status == ProfileStatus.CONFIRMED:
            if saved_fingerprint and saved_fingerprint != current_fingerprint:
                self.show_suggestion(
                    "Source file has changed since last profile setup.",
                    "Review Profile",
                    self.launch_profile_wizard
                )
            else:
                self.suggestion_bar.setVisible(False)
                
        # 3. DRAFT (Skipped) -> Suggestion Bar
        elif status == ProfileStatus.DRAFT:
            self.show_suggestion(
                "Profile setup is incomplete (Draft).",
                "Resume Wizard",
                self.launch_profile_wizard
            )
            
        # Always update UI
        self.update_profile_status_ui()

    def show_suggestion(self, message, action_text, action_callback):
        self.lbl_suggestion.setText(message)
        self.btn_suggestion_action.setText(action_text)
        try:
            self.btn_suggestion_action.clicked.disconnect()
        except: pass
        self.btn_suggestion_action.clicked.connect(lambda: (self.suggestion_bar.setVisible(False), action_callback()))
        self.suggestion_bar.setVisible(True)

    def launch_profile_wizard(self):
        if not self.current_profile: return
        
        dlg = ProfileWizardDialog(self.current_profile, self)
        if dlg.exec():
            # Accepted
            self.current_profile = dlg.get_profile()
            self.current_profile.controls.status = ProfileStatus.CONFIRMED
            self.current_profile.controls.source_fingerprint = self.calculate_source_fingerprint()
            self.save_profile()
            logger.info("Profile configured and saved.")
            self.suggestion_bar.setVisible(False)
        else:
            if dlg.result_code == WizardResult.SKIPPED:
                logger.info("Profile setup skipped. Keeping profile as NEW.")
                self.current_profile.controls.status = ProfileStatus.NEW
                self.current_profile.controls.source_fingerprint = ""
                self.suggestion_bar.setVisible(False)
            else:
                # Cancelled - do nothing (keep current state)
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
        self.trans_worker.batch_finished.connect(self.on_batch_translation_result)
        self.trans_worker.finished.connect(self.on_trans_finished)
        self.trans_worker.error.connect(lambda e: QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Error", e)))
        self.trans_worker.start()

    def on_batch_translation_result(self, res_map: dict):
        """Handle batch translation results safely in Main Thread"""
        if not res_map: return
        
        # Using layoutAboutToBeChanged is safer for bulk updates
        # self.model.layoutAboutToBeChanged.emit() # Optional if just data change
        
        # Optimize: Map ID to unit once
        unit_map = {str(u.id): u for u in self.units}
        
        changed_indices = []
        
        for uid_str, text in res_map.items():
            if uid_str in unit_map:
                u = unit_map[uid_str]
                if u.target_abstracted != text:
                    u.target_abstracted = text
                    u.state = "translated"
                    changed_indices.append(u)

        if changed_indices:
            # Efficient refresh: Emit dataChanged for the whole range? 
            # Or just layoutChanged for simplicity since it's a batch
            self.model.layoutChanged.emit()
            self.perform_autosave()

    def on_trans_finished(self):
        try:
            # Safety: Stop any pending hover actions to prevent conflict with layoutChanged
            if hasattr(self, '_hover_timer'):
                self._hover_timer.stop()
                
            self.btn_trans.setEnabled(True)
            self.progress.setVisible(False)
            self.model.layoutChanged.emit() # Force refresh
            self.update_stats()
            
            # Delay the modal dialog to allow layout/rendering to stabilize (Prevent Access Violation)
            # 300ms gives Qt event loop enough time to process the heavy layoutChanged event
            QTimer.singleShot(300, lambda: QMessageBox.information(self, "Done", "Translation complete!"))
        except Exception as e:
            logger.error(f"Error in on_trans_finished: {e}")

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

    def on_current_row_changed(self, current, previous):
        """Handle row selection change: Expand current, collapse previous."""
        try:
            if previous.isValid():
                self.table.setRowHeight(previous.row(), 40) # Restore default
                
            if current.isValid():
                # Auto-expand
                # Safety Check: If selection has multiple rows, do NOT auto-expand the active one
                # This prevents thrashing when dragging to select multiple rows
                sel = self.table.selectionModel()
                if sel and len(sel.selectedRows()) > 1:
                    pass # Skip expansion during multi-select
                else:
                    self.table.resizeRowToContents(current.row())
                
                # Update Refine Dock
                proxy_idx = current
                source_idx = self.proxy_model.mapToSource(proxy_idx)
                if source_idx.isValid():
                    self.update_ui_for_unit(source_idx.row())
            else:
                self.active_unit_index_map = -1
        except Exception as e:
            # Swallow layout errors during rapid selection changes
            logger.debug(f"Row change error: {e}")

    def on_table_hover(self, index):
        """
        Handle mouse hover: Expand hovered row temporarily.
        Uses a debounce timer to prevent jitter/flickering when moving rapidly across rows.
        """
        try:
            # Initialize timer if needed
            if not hasattr(self, '_hover_timer'):
                self._hover_timer = QTimer(self)
                self._hover_timer.setSingleShot(True)
                self._hover_timer.timeout.connect(self._apply_hover_resize)

            row = index.row()
            current_row = self.table.currentIndex().row()
            
            # If we are already hovering this row (and it's processed), do nothing
            if hasattr(self, '_last_hover_row') and self._last_hover_row == row:
                return

            # Stop any pending resize for a different row
            self._hover_timer.stop()
            
            # Store target and start debounce
            # Fix: Use QPersistentModelIndex to prevent Access Violation if model resets
            self._hover_target_index = QPersistentModelIndex(index)
            self._hover_timer.start(100) # 100ms delay for smoothness
        except Exception:
            pass

    def _apply_hover_resize(self):
        """Execute the actual row resizing after debounce delay"""
        try:
            if not hasattr(self, '_hover_target_index') or not self._hover_target_index.isValid():
                return
                
            index = self._hover_target_index
            row = index.row()
            
            # Double check row validity (index.row() might be valid but out of bounds if rows removed)
            if row < 0 or row >= self.table.model().rowCount():
                return

            current_row = self.table.currentIndex().row()
            
            # Skip hover expand if multi-select is active (prevent crash/lag)
            if len(self.table.selectionModel().selectedRows()) > 1:
                return

            last_hover = getattr(self, '_last_hover_row', -1)
            
            # 1. Expand NEW row first (Stability: Ensure target exists before shifting others)
            if row != current_row:
                self.table.resizeRowToContents(row)
                # Enforce minimum height to prevent "collapsing" empty rows
                if self.table.rowHeight(row) < 40:
                    self.table.setRowHeight(row, 40)
                self._last_hover_row = row
            else:
                self._last_hover_row = -1
                
            # 2. Shrink OLD row (after new one is stable)
            if last_hover != -1 and last_hover != current_row and last_hover != row:
                self.table.setRowHeight(last_hover, 40)
        except Exception:
            pass

    def leaveEvent(self, event):
        """Restore hover row when leaving window/table area"""
        # Stop any pending hover action
        if hasattr(self, '_hover_timer'):
            self._hover_timer.stop()
            
        if hasattr(self, '_last_hover_row') and self._last_hover_row != -1:
            if self._last_hover_row != self.table.currentIndex().row():
                self.table.setRowHeight(self._last_hover_row, 40)
            self._last_hover_row = -1
        super().leaveEvent(event)

    def show_header_context_menu(self, pos):
        """Right-click on header to toggle columns."""
        menu = QMenu(self)
        header = self.table.horizontalHeader()
        
        for i in range(self.model.columnCount()):
            name = self.model.headerData(i, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
            action = QAction(name, self, checkable=True)
            action.setChecked(not header.isSectionHidden(i))
            action.triggered.connect(lambda checked, col=i: self.toggle_column(col, checked))
            menu.addAction(action)
            
        menu.exec(header.mapToGlobal(pos))

    def toggle_column(self, col, visible):
        if visible:
            self.table.showColumn(col)
        else:
            self.table.hideColumn(col)
        self.save_column_state()

    def save_column_state(self):
        header = self.table.horizontalHeader()
        state = header.saveState()
        self.settings.setValue("table_column_state", state)

    def restore_column_state(self):
        state = self.settings.value("table_column_state")
        if state:
            self.table.horizontalHeader().restoreState(state)
        else:
            # Default Layout
            self.table.setColumnWidth(0, 50) # ID
            self.table.setColumnWidth(1, 50) # State
            self.table.setColumnWidth(2, 80) # Tags
            self.table.setColumnWidth(3, 50) # QA
            self.table.setColumnHidden(2, True) # Hide Tags by default
            self.table.setColumnHidden(4, True) # Hide Details by default
            
            # Source/Target split remaining
            width = self.table.width() - 250
            self.table.setColumnWidth(5, int(width * 0.45))
            self.table.setColumnWidth(6, int(width * 0.45))

    def on_selection_changed(self, selected, deselected):
        # Deprecated: Replaced by on_current_row_changed
        pass

    def on_qa_selection_changed(self, selected, deselected):
        indexes = self.view_qa.selectionModel().selectedRows()
        if len(indexes) == 1:
            proxy_idx = indexes[0]
            source_idx = self.proxy_qa.mapToSource(proxy_idx)
            self.update_ui_for_unit(source_idx.row())

    def update_ui_for_unit(self, row):
        self.active_unit_index_map = row
        # Note: Workbench updates are now demand-driven via "Add Context" button
        # or we could auto-push here if desired. For now, we just track the active row.

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

    def show_context_menu(self, pos):
        # Stop hover timer to prevent conflicts with menu actions/model updates
        if hasattr(self, '_hover_timer'):
            self._hover_timer.stop()

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
            try:
                # Safety: Stop hover timer (Fix Access Violation during layout change)
                if hasattr(self, '_hover_timer'):
                    self._hover_timer.stop()

                # 1. Show Wait Cursor
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                
                # 2. Batch Update
                # Temporarily block signals if needed, but layoutChanged is enough
                changed_count = 0
                
                # Notify model about structure change to be safe
                self.model.layoutAboutToBeChanged.emit()
                
                for u in selected_units:
                    if u.state == "locked": continue
                    # Only change if not empty
                    if u.target_abstracted:
                        u.target_abstracted = ""
                        u.state = "needs_translation"
                        changed_count += 1
                
                if changed_count > 0:
                    # 3. Refresh UI
                    self.model.layoutChanged.emit()
                    self.update_stats()
                    
                    # 4. Autosave (CRITICAL)
                    self.perform_autosave()
                    logger.info(f"Cleared {changed_count} segments.")
                else:
                    # If no changes, still need to close layout transaction if we opened one? 
                    # layoutChanged usually pairs with layoutAboutToBeChanged
                    self.model.layoutChanged.emit()
                
            except Exception as e:
                logger.error(f"Error clearing targets: {e}")
                QMessageBox.critical(self, "Error", f"Failed to clear targets: {e}")
            finally:
                QApplication.restoreOverrideCursor()
        
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
        self.repair_worker.segment_repaired.connect(self.on_segment_repaired)
        self.repair_worker.finished.connect(self.on_repair_finished)
        self.repair_worker.error.connect(lambda e: QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Repair Error", e)))
        self.repair_worker.start()
    
    def on_segment_repaired(self, unit_id: int, new_target: str, new_state: str):
        """Handle individual segment repair result in Main Thread"""
        # Find unit by ID
        for u in self.units:
            if u.id == unit_id:
                u.target_abstracted = new_target
                u.state = new_state
                # We don't need to refresh UI for every single segment (too slow),
                # we wait for final layoutChanged or batch updates.
                break

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
            
            # Cleanup autosave on successful export
            if self.autosaver:
                self.autosaver.cleanup()
            
            # Remove "active file" on successful export/save? 
            # No, user might keep editing. 
            # But maybe we update the fingerprint because file changed?
            # Yes, file on disk changed, so fingerprint changed.
            self.settings.setValue("last_file_fingerprint", Autosaver.calculate_file_fingerprint(path))
                
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
        """Handle exit: Check for running tasks, unsaved changes and persist settings."""
        logger.info(f"Close event triggered. Dirty: {self.is_dirty}")
        
        # 1. Check for Running Workers (Priority over Dirty)
        running_tasks = []
        if self.trans_worker and self.trans_worker.isRunning():
            running_tasks.append("Translation")
        if self.repair_worker and self.repair_worker.isRunning():
            running_tasks.append("Batch Repair")
            
        if running_tasks:
            task_str = " and ".join(running_tasks)
            reply = QMessageBox.question(self, "Tasks in Progress", 
                f"{task_str} is currently running.\n\n"
                "Force Quit will abort these tasks.\n"
                "Are you sure you want to exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
                
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            else:
                # User chose to Force Quit
                # Stop workers if possible (cleaner exit)
                if self.trans_worker: self.trans_worker.stop()
                # Repair worker might not have stop(), but thread kill is implicit on app exit
                pass

        # 2. Check Dirty State
        if self.is_dirty:
            box = QMessageBox(self)
            box.setWindowTitle("Unsaved Changes")
            box.setText("You have unsaved changes. Do you want to save them?")
            box.setIcon(QMessageBox.Icon.Question)
            
            btn_save = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
            btn_dont_save = box.addButton("Don't Save (Keep Recovery)", QMessageBox.ButtonRole.DestructiveRole)
            btn_cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            
            box.exec()
            
            clicked = box.clickedButton()
            
            if clicked == btn_cancel:
                event.ignore()
                return
                
            elif clicked == btn_save:
                # Try to save
                try:
                    self.save_current_file()
                    # If save failed (exception caught inside but maybe we should check is_dirty?), 
                    # check if clean now
                    if self.is_dirty: # Still dirty implies save failed or cancelled
                        event.ignore()
                        return
                    # Save success -> Cleanup autosave handled in save_current_file
                except:
                    event.ignore()
                    return

            elif clicked == btn_dont_save:
                # Don't Save -> But Keep Recovery means DO NOT clean autosave
                # Just proceed to close. 
                pass
        
        # Save settings on exit
        self.settings.setValue("source_lang", self.combo_src.currentText())
        self.settings.setValue("target_lang", self.combo_tgt.currentText())
        # Provider settings are now managed by SettingsDialog/SettingsManager, 
        # so we don't need to manually save combo_provider etc. here.
        # self.settings.setValue("provider", self.combo_provider.currentText())
        # self.settings.setValue("api_key", self.txt_apikey.text())
        # self.settings.setValue("model", self.txt_model.text())
        # self.settings.setValue("base_url", self.txt_base_url.text())
        
        # Save Auto-Repair status if checkbox exists in main UI?
        # Actually it seems auto-repair checkbox was moved too or accessed differently.
        # Let's check if chk_auto_repair exists in MainWindow
        if hasattr(self, 'chk_auto_repair'):
            self.settings.setValue("auto_repair_enabled", self.chk_auto_repair.isChecked())
        
        # Save Diagnostic Mode
        if hasattr(self, 'chk_diagnostic'):
            self.settings.setValue("diagnostic_mode", self.chk_diagnostic.isChecked())
            
        self.settings.setValue("geometry", self.saveGeometry())
        
        # Mark clean shutdown
        self.settings.setValue("clean_shutdown", True)
        self.settings.sync() # Force write to disk
        
        # Parent close
        QMainWindow.closeEvent(self, event)

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

    # --- Workbench Integration ---

    def connect_workbench_signals(self):
        # Connect Workbench Actions
        self.workbench.settings_btn.clicked.connect(self.open_settings_dialog)
        self.workbench.request_context.connect(self.on_workbench_request_context)
        self.workbench.send_btn.clicked.connect(self.on_workbench_send)
        self.workbench.request_apply.connect(self.on_workbench_apply)

    def on_workbench_request_context(self):
        """Called when user clicks 'Add Context' in Workbench"""
        # 1. Check Selection (Support Multi-Select)
        # Use selectedRows(0) to ensure we get unique rows regardless of column selection
        proxy_indexes = self.table.selectionModel().selectedRows(0)
        
        if not proxy_indexes:
            QMessageBox.warning(self, "No Selection", "Please select segments in the table first.")
            return

        # 2. Map to Units & Sort visually
        proxy_indexes = sorted(proxy_indexes, key=lambda x: x.row())
        selected_units = []
        for p_idx in proxy_indexes:
            if not p_idx.isValid(): continue
            src_idx = self.proxy_model.mapToSource(p_idx)
            if not src_idx.isValid(): continue
            
            row = src_idx.row()
            if 0 <= row < len(self.units):
                selected_units.append(self.units[row])

        if not selected_units: return

        # 3. Single vs Multi Logic
        if len(selected_units) == 1:
            unit = selected_units[0]
            tokens = TokenGuard.extract_tokens(unit.source_abstracted)
            
            self.workbench.set_context(
                source=unit.source_abstracted,
                target=unit.target_abstracted or "",
                tokens=tokens
            )
            self.workbench.pending_unit_id = unit.id
            self.workbench.pending_unit_ids = None # Clear multi-list
            
        else:
            # Multi-segment mode
            combined_source = ""
            combined_target = ""
            ids = []
            
            for u in selected_units:
                combined_source += f"[ID:{u.id}] {u.source_abstracted}\n"
                combined_target += f"[ID:{u.id}] {u.target_abstracted or ''}\n"
                ids.append(u.id)
            
            self.workbench.set_context(
                source=combined_source.strip(),
                target=combined_target.strip(),
                tokens=[] # No token guard for batch yet
            )
            self.workbench.pending_unit_id = None
            self.workbench.pending_unit_ids = ids
            
            self.workbench.chat_display.append(f"<br><i>Batch Mode: {len(ids)} segments selected.</i>")

    def on_workbench_send(self):
        """Called when user clicks 'Send' in Workbench"""
        payload = self.workbench.get_prompt_payload()
        if not payload["source"]:
            QMessageBox.warning(self, "No Context", "Please add context first.")
            return

        # Inject Target Language Info
        target_lang = self.combo_tgt.currentText()
        payload["target_lang"] = target_lang

        # Inject Batch Instruction if needed
        if getattr(self.workbench, 'pending_unit_ids', None):
             # Prepend formatting requirement
             batch_instr = (
                 f"You are translating multiple segments into {target_lang}. "
                 "The input format is '[ID:x] Source Text'. "
                 "Please provide the translation in the exact same format: '[ID:x] Translated Text'. "
                 "Do not miss any segments. Keep IDs matching.\n\n"
             )
             payload["instruction"] = batch_instr + payload["instruction"]

        try:
            client = self.get_client()
        except Exception as e:
            QMessageBox.warning(self, "Config Error", str(e))
            return

        self.workbench.set_loading(True)
        
        self.wb_worker = WorkbenchWorker(client, payload)
        self.wb_worker.finished.connect(self.on_workbench_response)
        self.wb_worker.error.connect(lambda e: (
            self.workbench.set_loading(False),
            self.workbench.append_ai_response(f"<span style='color:red'>Error: {e}</span>")
        ))
        self.wb_worker.start()

    def on_workbench_response(self, response_text):
        self.workbench.set_loading(False)
        self.workbench.append_ai_response(response_text)
        
        # Update Diff View
        current_target = self.workbench.pending_target
        self.workbench.update_diff(current_target, response_text)
        self.workbench.pending_new_text = response_text
        
        # Check Mode
        if getattr(self.workbench, 'pending_unit_ids', None):
            # Batch Mode Validation
            self.workbench.apply_btn.setEnabled(True)
            self.workbench.apply_btn.setText("✅ Apply Batch")
            self.workbench.apply_btn.setToolTip("Apply translation to multiple segments")
            
        else:
            # Single Mode Token Validation
            # Fallback to pending_unit_id if active_unit_index_map is not reliable (user moved selection)
            unit = None
            if hasattr(self.workbench, 'pending_unit_id') and self.workbench.pending_unit_id:
                for u in self.units:
                    if u.id == self.workbench.pending_unit_id:
                        unit = u
                        break
            
            if unit:
                result = TokenGuard.validate(unit.source_abstracted, response_text, unit.tags_map)
                
                if result.valid:
                    self.workbench.apply_btn.setEnabled(True)
                    self.workbench.apply_btn.setText("✅ Apply to Editor")
                    self.workbench.apply_btn.setToolTip("Tokens Validated")
                else:
                    self.workbench.apply_btn.setEnabled(False)
                    self.workbench.apply_btn.setText("⛔ Blocked: Token Error")
                    self.workbench.apply_btn.setToolTip(result.message)
                    self.workbench.append_ai_response(f"<br><b>Token Guard:</b> <span style='color:red'>{result.message}</span>")

    def on_workbench_apply(self, new_text):
        """Called when user clicks 'Apply' in Workbench"""
        
        # Batch Apply
        ids = getattr(self.workbench, 'pending_unit_ids', None)
        if ids:
            # Parse [ID:x] format
            # Relaxed Regex: Allow spaces, case-insensitive ID, flexible separators
            # Matches: [ID:1], [id: 1], [ID : 1]
            pattern = re.compile(r'\[(?:ID|id)\s*:\s*(\d+)\]\s*(.*?)(?=\s*\[(?:ID|id)\s*:\s*\d+\]|\Z)', re.DOTALL | re.IGNORECASE)
            matches = pattern.findall(new_text)
            
            result_map = {int(m[0]): m[1].strip() for m in matches}
            
            # Validation: Check for missing segments
            missing_ids = [uid for uid in ids if uid not in result_map]
            
            # Special Handling: If regex failed completely but we have IDs, 
            # try a naive line-by-line fallback if lines count matches
            if len(result_map) == 0 and len(ids) > 0:
                 # Strategy A: Line-by-Line (for clean multiline output)
                 lines = [line.strip() for line in new_text.strip().split('\n') if line.strip()]
                 if len(lines) > len(ids) and lines[0].lower().startswith("ai:"):
                     lines = lines[1:]
                     
                 if len(lines) == len(ids):
                     # Fallback: Map strictly by order
                     for i, uid in enumerate(ids):
                         content = lines[i]
                         content = re.sub(r'^\[(?:ID|id)\s*:\s*\d+\]\s*', '', content, flags=re.IGNORECASE)
                         result_map[uid] = content
                     missing_ids = []
                 
                 # Strategy B: Delimiter Split (for single-line/wrapped output)
                 # If Strategy A failed, try splitting by the ID tag itself
                 else:
                     # Split by [ID:x] pattern
                     chunks = re.split(r'\[(?:ID|id)\s*:\s*\d+\]', new_text, flags=re.IGNORECASE)
                     # Filter empty start chunk
                     chunks = [c.strip() for c in chunks if c.strip()]
                     
                     if len(chunks) == len(ids):
                         for i, uid in enumerate(ids):
                             result_map[uid] = chunks[i]
                         missing_ids = [] # Clear missing since we recovered
            
            # Validation: Check for missing segments
            missing_ids = [uid for uid in ids if uid not in result_map]
            
            # Smart Remap: If counts match but IDs don't (AI hallucinated new IDs 1,2,3 instead of 48,49...),
            # force map by order.
            if missing_ids and len(result_map) == len(ids):
                logger.info("AI hallucinated IDs. Remapping by sequence order.")
                
                # Sort both by their respective order
                sorted_ai_ids = sorted(result_map.keys())
                # ids is already sorted by selection order in on_workbench_request_context? 
                # Actually ids comes from pending_unit_ids which was appended in loop order.
                
                new_map = {}
                for i, real_id in enumerate(ids):
                    hallucinated_id = sorted_ai_ids[i]
                    new_map[real_id] = result_map[hallucinated_id]
                
                result_map = new_map
                missing_ids = [] # Fixed!

            if missing_ids:
                msg = f"AI output incomplete. Selected {len(ids)} segments, but found {len(result_map)} in response.\n\nMissing IDs: {missing_ids}\n\nApply anyway?"
                reply = QMessageBox.question(self, "Incomplete Response", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    return

            changes = 0
            for uid in ids:
                if uid in result_map:
                    for unit in self.units:
                        if unit.id == uid:
                            if unit.target_abstracted != result_map[uid]:
                                unit.target_abstracted = result_map[uid]
                                unit.state = "edited"
                                changes += 1
                            break
            
            if changes > 0:
                self.model.layoutAboutToBeChanged.emit()
                self.model.layoutChanged.emit()
                self.update_stats()
                self.perform_autosave()
                QMessageBox.information(self, "Applied", f"Updated {changes} segments.")
                
                self.workbench.diff_view.clear()
                self.workbench.apply_btn.setEnabled(False)
                self.workbench.pending_unit_ids = None # Reset
            else:
                QMessageBox.warning(self, "No Changes", "No segments were updated. Check if AI maintained [ID:x] format.")
            
            return

        # Single Apply
        if self.active_unit_index_map < 0: return
        
        unit = self.units[self.active_unit_index_map]
        
        # Double check ID match (paranoid check)
        if hasattr(self.workbench, 'pending_unit_id') and self.workbench.pending_unit_id != unit.id:
            QMessageBox.warning(self, "Mismatch", "Selection changed! Please re-add context.")
            return

        if unit.target_abstracted != new_text:
            unit.target_abstracted = new_text
            unit.state = "edited"
            self.model.refresh_row(self.active_unit_index_map)
            self.update_stats()
            self.perform_autosave()
            
            # Update local workbench state to match new reality
            self.workbench.pending_target = new_text
            self.workbench.diff_view.clear()
            self.workbench.apply_btn.setEnabled(False) # Disable after apply
            
            QMessageBox.information(self, "Applied", "Translation updated successfully.")

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
