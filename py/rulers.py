from PyQt6.QtWidgets import QWidget, QGridLayout
from PyQt6.QtGui import QPainter, QPen, QColor, QFont
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QRect

# 🟢 [修改] 增大标尺宽度，解决拥挤问题
RULER_SIZE = 40 

class Ruler(QWidget):
    guide_dragged = pyqtSignal(int) # 发送拖拽结束的位置

    def __init__(self, orientation, parent=None):
        super().__init__(parent)
        self.orientation = orientation
        self.mouse_pos = QPoint(-100, -100) # 初始移出屏幕外
        self.is_dragging_guide = False
        self.drag_pos = 0
        self.setMouseTracking(True)
        
        if self.orientation == Qt.Orientation.Horizontal:
            self.setFixedHeight(RULER_SIZE)
        else:
            self.setFixedWidth(RULER_SIZE)

    def set_mouse_pos(self, pos):
        self.mouse_pos = pos
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging_guide = True
            # 记录初始拖拽位置
            if self.orientation == Qt.Orientation.Horizontal:
                self.drag_pos = event.pos().x()
            else:
                self.drag_pos = event.pos().y()
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
        # 🟢 [关键] 只有在拖拽状态下松开鼠标，才发射信号
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging_guide:
            self.is_dragging_guide = False
            self.guide_dragged.emit(self.drag_pos) # 发射信号给 CanvasView
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        # 绘制标尺背景
        painter.fillRect(self.rect(), QColor(240, 240, 240))
        
        # 绘制底边框线
        painter.setPen(QPen(QColor(180, 180, 180), 1))
        if self.orientation == Qt.Orientation.Horizontal:
            painter.drawLine(0, self.height()-1, self.width(), self.height()-1)
        else:
            painter.drawLine(self.width()-1, 0, self.width()-1, self.height())

        painter.setPen(QPen(QColor(80, 80, 80), 1))
        font = QFont("Arial", 9) # 稍微调大一点字体
        painter.setFont(font)

        if self.orientation == Qt.Orientation.Horizontal:
            start, end = 0, self.width()
            # 绘制水平刻度
            for i in range(start, end, 10):
                if i % 100 == 0: 
                    painter.drawLine(i, 0, i, 15)
                    # 调整文字位置，使其在宽标尺中居中
                    painter.drawText(i + 4, 25, str(i))
                elif i % 50 == 0: 
                    painter.drawLine(i, 0, i, 10)
                else: 
                    painter.drawLine(i, 0, i, 5)
            
            # 绘制鼠标追踪线
            painter.setPen(QPen(QColor(0, 150, 255), 1))
            painter.drawLine(self.mouse_pos.x(), 0, self.mouse_pos.x(), self.height())
            
            # 绘制拖拽预览红线
            if self.is_dragging_guide:
                painter.setPen(QPen(QColor(255, 0, 0), 1, Qt.PenStyle.DashLine))
                painter.drawLine(self.drag_pos, 0, self.drag_pos, self.height())
        else:
            start, end = 0, self.height()
            # 绘制垂直刻度
            for i in range(start, end, 10):
                if i % 100 == 0: 
                    painter.drawLine(0, i, 15, i)
                    painter.save()
                    painter.translate(0, i)
                    painter.rotate(-90) # 旋转文字让它竖着排，或者直接横排
                    painter.restore()
                    # 简单的横排显示
                    painter.drawText(15, i + 10, str(i))
                elif i % 50 == 0: 
                    painter.drawLine(0, i, 10, i)
                else: 
                    painter.drawLine(0, i, 5, i)
            
            # 绘制鼠标追踪线
            painter.setPen(QPen(QColor(0, 150, 255), 1))
            painter.drawLine(0, self.mouse_pos.y(), self.width(), self.mouse_pos.y())
            
            # 绘制拖拽预览红线
            if self.is_dragging_guide:
                painter.setPen(QPen(QColor(255, 0, 0), 1, Qt.PenStyle.DashLine))
                painter.drawLine(0, self.drag_pos, self.width(), self.drag_pos)

class CanvasView(QWidget):
    def __init__(self, canvas_widget, parent=None):
        super().__init__(parent)
        self.canvas = canvas_widget
        
        layout = QGridLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.top_ruler = Ruler(Qt.Orientation.Horizontal)
        self.left_ruler = Ruler(Qt.Orientation.Vertical)
        
        # 左上角空白块
        corner = QWidget()
        corner.setFixedSize(RULER_SIZE, RULER_SIZE)
        corner.setStyleSheet("background-color: #f0f0f0; border-right: 1px solid #b4b4b4; border-bottom: 1px solid #b4b4b4;")

        layout.addWidget(corner, 0, 0)
        layout.addWidget(self.top_ruler, 0, 1)
        layout.addWidget(self.left_ruler, 1, 0)
        layout.addWidget(self.canvas, 1, 1)
        
        self.setLayout(layout)
        
        # 信号连接
        self.canvas.mouse_moved_signal.connect(self.update_rulers)
        # 🟢 [关键连接] 确保这里连接了 add_xxx_guide 方法
        self.top_ruler.guide_dragged.connect(self.canvas.add_vertical_guide)
        self.left_ruler.guide_dragged.connect(self.canvas.add_horizontal_guide)
    
    def update_rulers(self, pos):
        self.top_ruler.set_mouse_pos(pos)
        self.left_ruler.set_mouse_pos(pos)