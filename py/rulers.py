from PyQt6.QtWidgets import QWidget, QGridLayout
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QCursor
from PyQt6.QtCore import Qt, QPoint, pyqtSignal

RULER_SIZE = 25

class Ruler(QWidget):
    guide_dragged = pyqtSignal(int)

    def __init__(self, orientation, parent=None):
        super().__init__(parent)
        self.orientation = orientation
        self.mouse_pos = QPoint(0, 0)
        self.is_dragging_guide = False
        self.drag_pos = 0
        self.setMouseTracking(True)
        self.setMinimumSize(RULER_SIZE, RULER_SIZE)

    def set_mouse_pos(self, pos):
        self.mouse_pos = pos
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging_guide = True
            self.drag_pos = self.mouse_pos.y() if self.orientation == Qt.Orientation.Vertical else self.mouse_pos.x()
            self.update()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        if self.orientation == Qt.Orientation.Horizontal:
            self.setCursor(Qt.CursorShape.SplitVCursor)
            self.drag_pos = pos.x()
        else:
            self.setCursor(Qt.CursorShape.SplitHCursor)
            self.drag_pos = pos.y()

        if self.is_dragging_guide:
            self.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging_guide:
            self.is_dragging_guide = False
            self.guide_dragged.emit(self.drag_pos)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(240, 240, 240))
        painter.setPen(QPen(QColor(120, 120, 120), 1))
        font = QFont("Arial", 8)
        painter.setFont(font)

        if self.orientation == Qt.Orientation.Horizontal:
            start, end = self.rect().left(), self.rect().right()
            for i in range(start, end, 10):
                if i % 100 == 0: painter.drawLine(i, 0, i, 10); painter.drawText(i + 2, 15, str(i))
                elif i % 50 == 0: painter.drawLine(i, 0, i, 7)
                else: painter.drawLine(i, 0, i, 4)
            painter.setPen(QPen(QColor(0, 150, 255), 1))
            painter.drawLine(self.mouse_pos.x(), 0, self.mouse_pos.x(), self.height())
            if self.is_dragging_guide:
                painter.setPen(QPen(QColor(255, 0, 0), 1, Qt.PenStyle.DashLine))
                painter.drawLine(self.drag_pos, 0, self.drag_pos, self.height())
        else:
            start, end = self.rect().top(), self.rect().bottom()
            for i in range(start, end, 10):
                if i % 100 == 0: painter.drawLine(0, i, 10, i); painter.drawText(12, i + 10, str(i))
                elif i % 50 == 0: painter.drawLine(0, i, 7, i)
                else: painter.drawLine(0, i, 4, i)
            painter.setPen(QPen(QColor(0, 150, 255), 1))
            painter.drawLine(0, self.mouse_pos.y(), self.width(), self.mouse_pos.y())
            if self.is_dragging_guide:
                painter.setPen(QPen(QColor(255, 0, 0), 1, Qt.PenStyle.DashLine))
                painter.drawLine(0, self.drag_pos, self.width(), self.drag_pos)

class CanvasView(QWidget):
    def __init__(self, canvas_widget, parent=None):
        super().__init__(parent)
        self.canvas = canvas_widget
        
        layout = QGridLayout(); layout.setSpacing(0); layout.setContentsMargins(0, 0, 0, 0)
        
        self.top_ruler = Ruler(Qt.Orientation.Horizontal)
        self.left_ruler = Ruler(Qt.Orientation.Vertical)
        
        corner = QWidget(); corner.setFixedSize(RULER_SIZE, RULER_SIZE); corner.setStyleSheet("background-color: #f0f0f0;")

        layout.addWidget(corner, 0, 0); layout.addWidget(self.top_ruler, 0, 1)
        layout.addWidget(self.left_ruler, 1, 0); layout.addWidget(self.canvas, 1, 1)
        
        self.setLayout(layout)
        
        self.canvas.mouse_moved_signal.connect(self.update_rulers)
        self.top_ruler.guide_dragged.connect(self.canvas.add_vertical_guide)
        self.left_ruler.guide_dragged.connect(self.canvas.add_horizontal_guide)
    
    def update_rulers(self, pos):
        self.top_ruler.set_mouse_pos(pos)
        self.left_ruler.set_mouse_pos(pos)