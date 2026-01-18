import sys
import os
import time
import qdarktheme # Modern theme
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTableView, QFileDialog, 
                             QHeaderView, QMessageBox, QLabel, QAbstractItemView,
                             QComboBox, QLineEdit, QGroupBox, QMenu, QDockWidget,
                             QTextEdit, QProgressBar, QSplitter, QFrame)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QAction, QIcon, QColor, QBrush

# Ensure core modules importable
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from core.parser import XliffParser
from core.abstractor import TagAbstractor
from ai.client import LLMClient

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
        self.headers = ["ID", "State", "Source", "Target"]

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
                # Text representation of state
                return "" 
            elif col == 2: return unit.source_abstracted
            elif col == 3: return unit.target_abstracted
            
        elif role == Qt.ItemDataRole.DecorationRole and col == 1:
            # Icons/Colors for State
            if unit.state == "locked": return "🔒"
            elif unit.state == "translated": return "✅"
            elif unit.state == "edited": return "✏️"
            return "⚪"
            
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
        
        # Target editable only if not locked
        if index.column() == 3:
            if unit.state != "locked":
                flags |= Qt.ItemFlag.ItemIsEditable
        
        return flags

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if index.isValid() and role == Qt.ItemDataRole.EditRole and index.column() == 3:
            unit = self.units[index.row()]
            if unit.state == "locked": return False
            
            if unit.target_abstracted != value:
                unit.target_abstracted = value
                unit.state = "edited"
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                # Also notify state column changed
                idx_state = self.index(index.row(), 1)
                self.dataChanged.emit(idx_state, idx_state, [Qt.ItemDataRole.DecorationRole])
                return True
        return False

    def update_data(self, units):
        self.beginResetModel()
        self.units = units
        self.endResetModel()
        
    def refresh_row(self, row_idx):
        idx_start = self.index(row_idx, 0)
        idx_end = self.index(row_idx, 3)
        self.dataChanged.emit(idx_start, idx_end, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.DecorationRole])

# --- Main Window ---

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XLIFF AI Assistant Pro")
        self.resize(1400, 900)
        
        # Data
        self.parser = None
        self.units = []
        self.abstractor = TagAbstractor()
        self.current_file = None
        self.active_unit_index = -1
        
        # Workers
        self.trans_worker = None
        self.refine_worker = None
        self.test_worker = None
        
        self.setup_ui()
        self.apply_styles()

    def setup_ui(self):
        # Central Widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- Sidebar ---
        sidebar = QFrame()
        sidebar.setFixedWidth(280)
        sidebar.setObjectName("sidebar") # For styling
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        lbl_title = QLabel("XLIFF\nAssistant")
        lbl_title.setObjectName("appTitle")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_layout.addWidget(lbl_title)
        side_layout.addSpacing(10)
        
        # Language Config
        grp_lang = QGroupBox("Language")
        l_lang = QVBoxLayout()
        l_lang.addWidget(QLabel("Source:"))
        self.combo_src = QComboBox()
        self.combo_src.addItems(["en", "zh-CN", "fr", "de", "ja", "ko"])
        self.combo_src.setCurrentText("zh-CN") # Default
        l_lang.addWidget(self.combo_src)
        
        l_lang.addWidget(QLabel("Target:"))
        self.combo_tgt = QComboBox()
        self.combo_tgt.addItems(["en", "zh-CN", "fr", "de", "ja", "ko"])
        self.combo_tgt.setCurrentText("en") # Default
        l_lang.addWidget(self.combo_tgt)
        grp_lang.setLayout(l_lang)
        side_layout.addWidget(grp_lang)

        # AI Config
        grp_ai = QGroupBox("AI Configuration")
        l_ai = QVBoxLayout()
        
        self.combo_provider = QComboBox()
        self.combo_provider.addItems(["SiliconFlow", "OpenAI", "DeepSeek", "Mock"])
        l_ai.addWidget(QLabel("Provider:"))
        l_ai.addWidget(self.combo_provider)
        
        self.txt_apikey = QLineEdit()
        self.txt_apikey.setPlaceholderText("sk-...")
        self.txt_apikey.setEchoMode(QLineEdit.EchoMode.Password)
        l_ai.addWidget(QLabel("API Key:"))
        l_ai.addWidget(self.txt_apikey)
        
        self.txt_model = QLineEdit("deepseek-ai/DeepSeek-V2.5")
        l_ai.addWidget(QLabel("Model:"))
        l_ai.addWidget(self.txt_model)
        
        self.btn_test_conn = QPushButton("📡 Test Connection")
        self.btn_test_conn.clicked.connect(self.test_connection)
        l_ai.addWidget(self.btn_test_conn)
        
        grp_ai.setLayout(l_ai)
        side_layout.addWidget(grp_ai)
        
        side_layout.addStretch()
        
        # Action Buttons
        self.btn_open = QPushButton("📂 Open File")
        self.btn_open.clicked.connect(self.open_file)
        side_layout.addWidget(self.btn_open)
        
        self.btn_trans = QPushButton("🚀 Start Translation")
        self.btn_trans.clicked.connect(self.start_translation)
        self.btn_trans.setObjectName("btnPrimary")
        side_layout.addWidget(self.btn_trans)
        
        self.btn_save = QPushButton("💾 Export Result")
        self.btn_save.clicked.connect(self.save_file)
        side_layout.addWidget(self.btn_save)
        
        main_layout.addWidget(sidebar)
        
        # --- Content Area ---
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        # Top Bar (Stats)
        self.lbl_stats = QLabel("No file loaded.")
        content_layout.addWidget(self.lbl_stats)
        
        # Progress Bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        content_layout.addWidget(self.progress)
        
        # Table
        self.table = QTableView()
        self.model = XliffTableModel()
        self.table.setModel(self.model)
        
        # Table Config
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # ID
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # State
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) # Source
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch) # Target
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.selectionModel().selectionChanged.connect(self.on_selection_changed)
        
        content_layout.addWidget(self.table)
        
        main_layout.addWidget(content)
        
        # --- Refinement Dock (Bottom) ---
        self.dock_refine = QDockWidget("✨ AI Refinement Workbench", self)
        self.dock_refine.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        
        dock_widget = QWidget()
        dock_layout = QHBoxLayout(dock_widget)
        
        # Source (Readonly)
        v1 = QVBoxLayout()
        v1.addWidget(QLabel("Source:"))
        self.txt_source = QTextEdit()
        self.txt_source.setReadOnly(True)
        self.txt_source.setMaximumHeight(100)
        v1.addWidget(self.txt_source)
        dock_layout.addLayout(v1, 1)
        
        # Prompt & Action
        v2 = QVBoxLayout()
        v2.addWidget(QLabel("Custom Instruction:"))
        
        # Shortcuts
        h_shortcuts = QHBoxLayout()
        btn_s1 = QPushButton("Formal")
        btn_s1.clicked.connect(lambda: self.txt_prompt.setText("Make it more formal"))
        h_shortcuts.addWidget(btn_s1)
        
        btn_s2 = QPushButton("Concise")
        btn_s2.clicked.connect(lambda: self.txt_prompt.setText("Make it concise"))
        h_shortcuts.addWidget(btn_s2)
        
        btn_s3 = QPushButton("Fix Grammar")
        btn_s3.clicked.connect(lambda: self.txt_prompt.setText("Fix grammar errors"))
        h_shortcuts.addWidget(btn_s3)
        v2.addLayout(h_shortcuts)
        
        self.txt_prompt = QLineEdit()
        self.txt_prompt.setPlaceholderText("e.g. 'Use specific terminology'")
        v2.addWidget(self.txt_prompt)
        
        self.btn_refine = QPushButton("✨ Refine Segment")
        self.btn_refine.clicked.connect(self.refine_current_segment)
        v2.addWidget(self.btn_refine)
        v2.addStretch()
        dock_layout.addLayout(v2, 1)
        
        # Target (Result Preview/Edit)
        v3 = QVBoxLayout()
        v3.addWidget(QLabel("Translation:"))
        self.txt_target = QTextEdit()
        self.txt_target.setMaximumHeight(100)
        v3.addWidget(self.txt_target)
        dock_layout.addLayout(v3, 1)
        
        self.dock_refine.setWidget(dock_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_refine)
        self.dock_refine.setVisible(False) # Hide initially

    def apply_styles(self):
        # Custom tweaks on top of qdarktheme
        self.setStyleSheet("""
            QLabel#appTitle { font-size: 24px; font-weight: bold; color: #60CDFF; margin-bottom: 20px; }
            QPushButton { padding: 6px; border-radius: 4px; }
            QPushButton#btnPrimary { background-color: #007AFF; color: white; font-weight: bold; padding: 10px; }
            QPushButton#btnPrimary:hover { background-color: #0062CC; }
            QFrame#sidebar { background-color: #202124; border-right: 1px solid #3C4043; }
        """)

    # --- Logic ---

    def get_client(self):
        prov = self.combo_provider.currentText()
        key = self.txt_apikey.text()
        model = self.txt_model.text()
        
        prov_map = {"SiliconFlow": "custom", "OpenAI": "custom", "DeepSeek": "custom", "Mock": "mock"}
        base_urls = {
            "SiliconFlow": "https://api.siliconflow.cn/v1",
            "OpenAI": "https://api.openai.com/v1",
            "DeepSeek": "https://api.deepseek.com"
        }
        
        if not key and prov != "Mock":
            raise ValueError("API Key required")
            
        return LLMClient(api_key=key, base_url=base_urls.get(prov), model=model, provider=prov_map[prov])

    def test_connection(self):
        try:
            client = self.get_client()
        except Exception as e:
            QMessageBox.warning(self, "Config Error", str(e))
            return
            
        self.btn_test_conn.setEnabled(False)
        self.btn_test_conn.setText("Testing...")
        
        self.test_worker = TestConnectionWorker(client)
        self.test_worker.finished.connect(self.on_test_finished)
        self.test_worker.start()
        
    def on_test_finished(self, success, msg):
        self.btn_test_conn.setEnabled(True)
        self.btn_test_conn.setText("📡 Test Connection")
        if success:
            QMessageBox.information(self, "Success", msg)
        else:
            QMessageBox.critical(self, "Failed", msg)

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
                    self.units.append(u)
                
                self.model.update_data(self.units)
                self.update_stats()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def update_stats(self):
        total = len(self.units)
        done = sum(1 for u in self.units if u.target_abstracted)
        locked = sum(1 for u in self.units if u.state == 'locked')
        self.lbl_stats.setText(f"Total: {total} | Translated: {done} | Locked: {locked}")

    def start_translation(self):
        if not self.units: return
        try:
            client = self.get_client()
        except Exception as e:
            QMessageBox.warning(self, "Config Error", str(e))
            return
            
        self.btn_trans.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        
        src_lang = self.combo_src.currentText()
        tgt_lang = self.combo_tgt.currentText()
        
        self.trans_worker = TranslationWorker(self.units, client, src_lang, tgt_lang)
        self.trans_worker.progress.connect(lambda c, t: self.progress.setValue(int(c/t*100)))
        self.trans_worker.finished.connect(self.on_trans_finished)
        self.trans_worker.error.connect(lambda e: QMessageBox.critical(self, "Error", e))
        self.trans_worker.start()

    def on_trans_finished(self):
        self.btn_trans.setEnabled(True)
        self.progress.setVisible(False)
        self.model.layoutChanged.emit() # Refresh table
        self.update_stats()
        QMessageBox.information(self, "Done", "Batch translation complete!")

    def on_selection_changed(self, selected, deselected):
        indexes = self.table.selectionModel().selectedRows()
        if len(indexes) == 1:
            self.active_unit_index = indexes[0].row()
            unit = self.units[self.active_unit_index]
            
            self.dock_refine.setVisible(True)
            self.txt_source.setText(unit.source_abstracted)
            self.txt_target.setText(unit.target_abstracted or "")
            self.txt_prompt.clear()
        else:
            self.dock_refine.setVisible(False)
            self.active_unit_index = -1

    def refine_current_segment(self):
        if self.active_unit_index < 0: return
        
        unit = self.units[self.active_unit_index]
        instruction = self.txt_prompt.text()
        if not instruction: 
            QMessageBox.warning(self, "Info", "Please enter an instruction")
            return
            
        try:
            client = self.get_client()
        except Exception as e:
            QMessageBox.warning(self, "Config Error", str(e))
            return
            
        self.btn_refine.setEnabled(False)
        self.btn_refine.setText("Refining...")
        
        self.refine_worker = RefineWorker(client, unit.source_abstracted, unit.target_abstracted, instruction)
        self.refine_worker.finished.connect(self.on_refine_finished)
        self.refine_worker.start()

    def on_refine_finished(self, new_text):
        if self.active_unit_index >= 0:
            unit = self.units[self.active_unit_index]
            unit.target_abstracted = new_text
            unit.state = "edited"
            self.model.refresh_row(self.active_unit_index)
            self.txt_target.setText(new_text)
            self.update_stats()
            
        self.btn_refine.setEnabled(True)
        self.btn_refine.setText("✨ Refine Segment")

    def show_context_menu(self, pos):
        menu = QMenu()
        act_lock = menu.addAction("🔒 Lock Selected")
        act_unlock = menu.addAction("🔓 Unlock Selected")
        menu.addSeparator()
        act_copy = menu.addAction("📄 Copy Source")
        
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        
        indexes = self.table.selectionModel().selectedRows()
        rows = [i.row() for i in indexes]
        
        if action == act_lock:
            for r in rows:
                self.units[r].state = "locked"
                self.model.refresh_row(r)
        elif action == act_unlock:
            for r in rows:
                u = self.units[r]
                u.state = "edited" if u.target_abstracted else "needs_translation"
                self.model.refresh_row(r)
        elif action == act_copy:
            if rows:
                clip = QApplication.clipboard()
                clip.setText(self.units[rows[0]].source_abstracted)
                
        self.update_stats()

    def save_file(self):
        if not self.units or not self.parser: return
        path, _ = QFileDialog.getSaveFileName(self, "Export", "", "XLIFF (*.xlf)")
        if path:
            # Reconstruct
            for u in self.units:
                if u.target_abstracted:
                    try:
                        u.target_raw = self.abstractor.reconstruct(u.target_abstracted, u.tags_map)
                    except: pass
            self.parser.update_targets(self.units, path)
            QMessageBox.information(self, "Saved", f"File exported to {path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    qdarktheme.setup_theme() # Auto dark/light mode
    
    w = MainWindow()
    w.show()
    sys.exit(app.exec())