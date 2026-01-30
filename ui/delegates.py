from PyQt6.QtWidgets import QStyledItemDelegate
from PyQt6.QtGui import QTextDocument, QAbstractTextDocumentLayout, QPalette, QIcon, QPixmap, QPainter
from PyQt6.QtCore import Qt, QRectF

class RichTextDelegate(QStyledItemDelegate):
    """
    Renders HTML content in TableView cells.
    Used for highlighting tags (e.g. <span style='color:blue'>{1}</span>)
    """
    def paint(self, painter, option, index):
        option.widget.style().drawControl(
            option.widget.style().ControlElement.CE_ItemViewItem, option, painter)

        # Shift text slightly
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        text_rect = option.rect
        if icon:
            text_rect.setLeft(text_rect.left() + option.decorationSize.width() + 4)

        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text: return

        # Simple Tag Highlighting logic
        # Replace {n} with colored HTML
        # In a real app, this should be done in the Model or a Helper, 
        # but doing it here ensures view-only formatting.
        import re
        # Highlight {1}, {2} etc.
        html_text = re.sub(r'(\{\d+\})', r'<span style="color: #2196F3; font-weight: bold;">\1</span>', str(text))
        
        # Handle newlines
        html_text = html_text.replace("\n", "<br>")

        painter.save()
        painter.translate(text_rect.topLeft())
        
        doc = QTextDocument()
        doc.setHtml(html_text)
        doc.setTextWidth(text_rect.width())
        doc.setDefaultFont(option.font)
        
        # Color adjustment for selection
        if option.state & getattr(option.widget.style().StateFlag, 'State_Selected', 0):
             # If selected, maybe change text color? 
             # For now keep it simple, Fluent style handles selection background
             pass
             
        doc.drawContents(painter)
        painter.restore()

    def sizeHint(self, option, index):
        # We need to calculate height based on content
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text: return super().sizeHint(option, index)
        
        doc = QTextDocument()
        doc.setHtml(str(text))
        doc.setTextWidth(option.rect.width())
        return QSize(int(doc.idealWidth()), int(doc.size().height()))

from PyQt6.QtCore import QSize

class StatusDelegate(QStyledItemDelegate):
    """
    Renders status icons instead of Emoji text.
    """
    def paint(self, painter, option, index):
        # Background
        option.widget.style().drawControl(
            option.widget.style().ControlElement.CE_ItemViewItem, option, painter)
            
        status = index.data(Qt.ItemDataRole.DisplayRole) # Model returns emoji currently
        # We should probably map emoji back to status string or use unit.state if we had access
        # But for now, let's just render the text centered
        
        painter.save()
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, status)
        painter.restore()
