# --- START OF FILE renderer.py (Updated for Layer Effects) ---

import math
from typing import Union
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import (QPainter, QPen, QColor, QBrush, QPolygon, QPolygonF, 
                         QPainterPath, QPixmap)
from PyQt6.QtCore import Qt, QRect, QPoint, QPointF, QLineF, QRectF

from shapes import (Text, Square, Ellipse, RoundedRectangle, Polygon, Circle, Rectangle,
                    Point, Line, Path, Polyline, ShapeGroup, Arrow)

AnyShape = Union[Text, Square, Ellipse, RoundedRectangle, Polygon, Circle, Rectangle,
                 Point, Line, Path, Polyline, ShapeGroup, Arrow]

class CanvasRenderer:
    @staticmethod
    def paint(painter: QPainter, canvas: QWidget):
        """主绘制函数，先绘制所有图层，再绘制当前工具的预览。"""
        CanvasRenderer.draw_layers(painter, canvas)
        if canvas.current_tool_obj:
            canvas.current_tool_obj.paint(painter)

    @staticmethod
    def draw_layers(painter: QPainter, canvas: QWidget):
        """
        使用离屏缓冲技术从下到上绘制所有可见图层，并应用每个图层的不透明度和混合模式。
        """
        for layer in reversed(canvas.layers):
            if not layer.is_visible:
                continue

            # 🔴 --- 修改开始 ---
            # 1. 获取设备的像素比例 (例如，200%缩放时，值为2.0)
            pixel_ratio = canvas.devicePixelRatioF()
            
            # 2. 创建一个物理像素足够多的高清临时画布
            size = canvas.size() * pixel_ratio
            layer_buffer = QPixmap(size)
            # 告诉 QPixmap 它的“逻辑”分辨率是多少，这样它在绘制时就能正确缩放
            layer_buffer.setDevicePixelRatio(pixel_ratio)
            
            # 3. 像之前一样填充为透明
            layer_buffer.fill(Qt.GlobalColor.transparent)
            # 🔴 --- 修改结束 ---

            # 2. 在这个临时缓冲区上进行绘制 (现在是高清的了)
            buffer_painter = QPainter(layer_buffer)
            buffer_painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # ... 后续代码完全不变 ...
            
            for shape in layer.shapes:
                if shape == canvas.editing_shape:
                    continue
                CanvasRenderer._draw_shape_recursive(buffer_painter, shape)
            
            buffer_painter.end() 

            painter.setOpacity(layer.opacity)
            painter.setCompositionMode(layer.blend_mode)
            # 这里绘制时，Qt会因为我们设置了 devicePixelRatio 而自动处理好缩放
            painter.drawPixmap(0, 0, layer_buffer)

        painter.setOpacity(1.0)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    @staticmethod
    def _draw_shape_recursive(painter: QPainter, shape: AnyShape):
        painter.save() 

        bbox = shape.get_bounding_box()
        center = bbox.center()
        painter.translate(center)
        painter.scale(shape.scale_x, shape.scale_y)
        painter.rotate(shape.angle)
        painter.translate(-center)
        
        if isinstance(shape, ShapeGroup):
            for sub_shape in shape.shapes:
                CanvasRenderer._draw_shape_recursive(painter, sub_shape)
        else:
            CanvasRenderer._draw_single_shape_no_transform(painter, shape)

        painter.restore() 

    @staticmethod
    def _draw_single_shape_no_transform(painter: QPainter, shape: AnyShape):
        if isinstance(shape, Text):
            painter.setFont(shape.font)
            pen = QPen(shape.color)
            painter.setPen(pen)
            painter.drawText(QRectF(shape.get_bounding_box()), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, shape.text)
            if shape.has_border:
                pen = QPen(shape.border_color, 1)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(shape.get_bounding_box())
        else:
            pen = QPen(shape.color, shape.width)
            painter.setPen(pen)
            
            if hasattr(shape, 'fill_color') and shape.fill_color and not (isinstance(shape, Path) and not shape.is_closed):
                painter.setBrush(QBrush(shape.fill_color, shape.fill_style))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            
            if isinstance(shape, Arrow):
                CanvasRenderer.draw_arrow(painter, shape.p1, shape.p2, shape.color, shape.width)
            elif isinstance(shape, Path):
                painter.drawPath(shape.get_painter_path())
            elif isinstance(shape, Polyline) and len(shape.points) >= 2:
                painter.drawPolyline(QPolygon(shape.points))
            elif isinstance(shape, Point):
                painter.setBrush(QBrush(shape.color))
                painter.drawEllipse(shape.pos, shape.width, shape.width)
            elif isinstance(shape, Line):
                painter.drawLine(shape.p1, shape.p2)
            elif isinstance(shape, (Rectangle, Square)):
                painter.drawRect(shape.get_bounding_box())
            elif isinstance(shape, Circle):
                painter.drawEllipse(shape.center, int(shape.radius), int(shape.radius))
            elif isinstance(shape, Ellipse):
                painter.drawEllipse(shape.get_bounding_box())
            elif isinstance(shape, RoundedRectangle):
                painter.drawRoundedRect(shape.get_bounding_box(), 20, 20)
            elif isinstance(shape, Polygon) and len(shape.points) >= 3:
                painter.drawPolygon(QPolygon(shape.points))

    @staticmethod
    def draw_arrow(painter: QPainter, p1: QPoint, p2: QPoint, color: QColor, width: int):
        if p1 is None or p2 is None or p1 == p2:
            return
        
        pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(color)
        
        main_line = QLineF(QPointF(p1), QPointF(p2))
        painter.drawLine(main_line)
        
        angle = math.atan2(p1.y() - p2.y(), p1.x() - p2.x())
        arrow_size = 10 + width * 2
        arrow_angle = math.pi / 6
        
        p_left_x = p2.x() + arrow_size * math.cos(angle + arrow_angle)
        p_left_y = p2.y() + arrow_size * math.sin(angle + arrow_angle)
        p_right_x = p2.x() + arrow_size * math.cos(angle - arrow_angle)
        p_right_y = p2.y() + arrow_size * math.sin(angle - arrow_angle)
        
        arrow_head = QPolygonF()
        arrow_head.append(QPointF(p2))
        arrow_head.append(QPointF(p_left_x, p_left_y))
        arrow_head.append(QPointF(p_right_x, p_right_y))
        painter.drawPolygon(arrow_head)

# --- END OF FILE renderer.py ---