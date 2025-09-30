# --- START OF FILE renderer.py ---

import math
from typing import Union
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPolygon, QPolygonF, QPainterPath
from PyQt6.QtCore import Qt, QRect, QPoint, QPointF, QLineF

from shapes import (Text, Square, Ellipse, RoundedRectangle, Polygon, Circle, Rectangle,
                    Point, Line, Arc, Polyline, ShapeGroup, Arrow)

AnyShape = Union[Text, Square, Ellipse, RoundedRectangle, Polygon, Circle, Rectangle,
                 Point, Line, Arc, Polyline, ShapeGroup, Arrow]

class CanvasRenderer:
    @staticmethod
    def paint(painter: QPainter, canvas: QWidget):
        CanvasRenderer.draw_layers(painter, canvas.layers, canvas.editing_shape)
        if canvas.current_tool_obj:
            canvas.current_tool_obj.paint(painter)

    @staticmethod
    def draw_layers(painter: QPainter, layers: list, editing_shape: AnyShape):
        for layer in reversed(layers):
            if not layer.is_visible:
                continue
            for shape in layer.shapes:
                if shape == editing_shape:
                    continue
                CanvasRenderer._draw_shape_recursive(painter, shape)

    @staticmethod
    def _draw_shape_recursive(painter: QPainter, shape: AnyShape):
        if isinstance(shape, ShapeGroup):
            for sub_shape in shape.shapes:
                CanvasRenderer._draw_shape_recursive(painter, sub_shape)
        else:
            CanvasRenderer._draw_single_shape(painter, shape)

    @staticmethod
    def _draw_single_shape(painter: QPainter, shape: AnyShape):
        if isinstance(shape, Text):
            painter.setFont(shape.font)
            pen = QPen(shape.color)
            painter.setPen(pen)
            painter.drawText(shape.get_bounding_box(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, shape.text)
            if shape.has_border:
                pen = QPen(shape.border_color, 1)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(shape.get_bounding_box())
        else:
            pen = QPen(shape.color, shape.width)
            painter.setPen(pen)
            
            if hasattr(shape, 'fill_color') and shape.fill_color:
                painter.setBrush(QBrush(shape.fill_color, shape.fill_style))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            
            if isinstance(shape, Arrow):
                CanvasRenderer.draw_arrow(painter, shape.p1, shape.p2, shape.color, shape.width)
            elif isinstance(shape, Arc):
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
