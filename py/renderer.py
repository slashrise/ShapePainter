# --- START OF FILE renderer.py (Updated for SVG Fill and Stroke Styles) ---

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
        CanvasRenderer.draw_layers(painter, canvas)
        if canvas.current_tool_obj:
            canvas.current_tool_obj.paint(painter)

    @staticmethod
    def draw_layers(painter: QPainter, canvas: QWidget):
        for layer in reversed(canvas.layers):
            if not layer.is_visible:
                continue

            pixel_ratio = canvas.devicePixelRatioF()
            size = canvas.size() * pixel_ratio
            layer_buffer = QPixmap(size)
            layer_buffer.setDevicePixelRatio(pixel_ratio)
            layer_buffer.fill(Qt.GlobalColor.transparent)
            buffer_painter = QPainter(layer_buffer)
            buffer_painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            for shape in layer.shapes:
                if shape == canvas.editing_shape:
                    continue
                CanvasRenderer._draw_shape_recursive(buffer_painter, shape)
            
            buffer_painter.end()

            painter.setOpacity(layer.opacity)
            painter.setCompositionMode(layer.blend_mode)
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
            painter.setPen(QPen(shape.color))
            painter.drawText(QRectF(shape.get_bounding_box()), int(shape.alignment) | Qt.TextFlag.TextWordWrap, shape.text)
            if shape.has_border:
                painter.setPen(QPen(shape.border_color, 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(shape.get_bounding_box())
        else:
            pen = QPen(shape.color, shape.width)
            if hasattr(shape, 'stroke_linecap'):
                pen.setCapStyle(shape.stroke_linecap)
            if hasattr(shape, 'stroke_linejoin'):
                pen.setJoinStyle(shape.stroke_linejoin)
            painter.setPen(pen)
            
            if hasattr(shape, 'fill_color') and shape.fill_color:
                if isinstance(shape, Path) and not shape.is_closed:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                else:
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

    # 🔴 --- 重大优化：重写 draw_arrow 方法 ---
    @staticmethod
    def draw_arrow(painter: QPainter, p1: QPoint, p2: QPoint, color: QColor, width: int):
        if p1 is None or p2 is None or p1 == p2:
            return
        
        pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        
        # 1. 绘制线杆
        main_line = QLineF(QPointF(p1), QPointF(p2))
        painter.drawLine(main_line)
        
        # 2. 准备绘制箭头 (设置填充色)
        painter.setBrush(color)

        # 3. 计算箭头头部的多边形
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
        
        # 4. 绘制填充好的箭头
        painter.drawPolygon(arrow_head)

# --- END OF FILE renderer.py ---