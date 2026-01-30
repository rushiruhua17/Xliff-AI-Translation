from PyQt6.QtWidgets import (QTableView, QHeaderView, QMenu, QMessageBox, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QAction, QCursor

# Reuse existing core logic
from core.xliff_model import XliffTableModel, XliffFilterProxyModel
from ui.delegates import RichTextDelegate, StatusDelegate

class ModernTranslationTable(QTableView):
    """
    Decoupled Translation Table Widget.
    Encapsulates Model, Proxy, Delegates, and Context Menu logic.
    """
    
    # Signals for external interaction (Loose Coupling)
    selection_changed = pyqtSignal(object) # Emits TranslationUnit object
    status_toggled = pyqtSignal(int) # Emits unit_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModernTranslationTable")
        
        # Internal Data Structures
        self.units = []
        self._model = XliffTableModel()
        self._proxy = XliffFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        
        self.setModel(self._proxy)
        
        # Style & Behavior
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.verticalHeader().setVisible(False)
        self.setSortingEnabled(True)
        self.setWordWrap(True)
        self.setShowGrid(False) # Modern look
        
        # Setup Columns & Delegates
        self.setup_columns()
        
        # Signals
        self.selectionModel().currentRowChanged.connect(self.on_row_changed)
        
        # Context Menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def setup_columns(self):
        # Set Delegates
        self.setItemDelegateForColumn(1, StatusDelegate(self))
        self.setItemDelegateForColumn(5, RichTextDelegate(self))
        self.setItemDelegateForColumn(6, RichTextDelegate(self))
        
        # Column Resizing
        h = self.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed) # ID
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed) # Status
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed) # Tags
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed) # QA
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive) # Details
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch) # Source
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch) # Target

        self.setColumnWidth(0, 50)
        self.setColumnWidth(1, 40)
        self.setColumnWidth(2, 40)
        self.setColumnWidth(3, 40)
        self.setColumnWidth(4, 150)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Re-calculate row heights when table width changes
        # Use a timer to debounce and avoid performance issues during drag
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.resizeRowsToContents)

    def load_data(self, units):
        """Public API to load data"""
        self.units = units
        self._model.update_data(units)
        # Resize rows to fit content
        # Force a layout update first to ensure column widths are valid
        self.resizeRowsToContents()

    def get_selected_unit(self):
        idx = self.currentIndex()
        if not idx.isValid(): return None
        
        src_idx = self._proxy.mapToSource(idx)
        return self.units[src_idx.row()]

    def on_row_changed(self, current, previous):
        if not current.isValid(): return
        
        src_idx = self._proxy.mapToSource(current)
        if src_idx.isValid():
            unit = self.units[src_idx.row()]
            self.selection_changed.emit(unit)

    def show_context_menu(self, pos: QPoint):
        idx = self.indexAt(pos)
        if not idx.isValid(): return
        
        src_idx = self._proxy.mapToSource(idx)
        unit = self.units[src_idx.row()]
        
        menu = QMenu(self)
        
        # Actions
        action_copy_src = QAction("📋 Copy Source to Target", self)
        action_copy_src.triggered.connect(lambda: self.copy_source_to_target(unit, src_idx))
        
        action_revert = QAction("↩️ Revert to Original", self)
        action_revert.triggered.connect(lambda: self.revert_segment(unit, src_idx))
        
        # Status Submenu
        menu_status = menu.addMenu("🏳️ Set Status")
        for status in ["translated", "needs_translation", "new", "locked"]:
            a = QAction(status.capitalize(), self)
            a.triggered.connect(lambda checked, s=status: self.set_status(unit, s, src_idx))
            menu_status.addAction(a)
            
        menu.addAction(action_copy_src)
        menu.addAction(action_revert)
        
        menu.exec(self.viewport().mapToGlobal(pos))

    def copy_source_to_target(self, unit, index):
        unit.target_abstracted = unit.source_abstracted
        unit.state = "translated"
        self.refresh_row(index)
        self.selection_changed.emit(unit) # Notify external

    def revert_segment(self, unit, index):
        # In a real app, we might want to store original target in unit
        # For now, just clear or set to source? 
        # desktop_app.py didn't implement true revert history yet, so let's just clear
        unit.target_abstracted = ""
        unit.state = "new"
        self.refresh_row(index)
        self.selection_changed.emit(unit)

    def set_status(self, unit, status, index):
        unit.state = status
        self.refresh_row(index)

    def refresh_row(self, src_index):
        # Notify model to refresh UI
        # We need the start and end index for this row in the SOURCE model
        r = src_index.row()
        idx_start = self._model.index(r, 0)
        idx_end = self._model.index(r, 6)
        self._model.dataChanged.emit(idx_start, idx_end, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
        
    def refresh_unit(self, unit):
        """Refreshes the row corresponding to the given unit"""
        # Linear search for now (can be optimized with a map)
        try:
            row = self.units.index(unit)
            idx = self._model.index(row, 0)
            self.refresh_row(idx)
        except ValueError:
            pass # Unit not found?
            
    def filter_status(self, status):
        self._proxy.set_status_filter(status)
        
    def filter_text(self, text):
        self._proxy.set_text_filter(text)
