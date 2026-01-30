from PyQt6.QtCore import QAbstractTableModel, Qt, QSortFilterProxyModel
from PyQt6.QtGui import QBrush, QColor

class XliffTableModel(QAbstractTableModel):
    def __init__(self, units=None):
        super().__init__()
        self.units = units or []
        self.headers = ["ID", "State", "Tags", "QA", "Details", "Source", "Target"]

    def rowCount(self, parent=None):
        return len(self.units)

    def columnCount(self, parent=None):
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
