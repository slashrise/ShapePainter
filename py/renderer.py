import math
from typing import Union
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPolygon, QPolygonF, QPainterPath
from PyQt6.QtCore import Qt, QRect, QPoint, QPointF, QLineF, QRectF

from shapes import (Text, Square, Ellipse, RoundedRectangle, Polygon, Circle, Rectangle,
                    Point, Line, Path, Polyline, ShapeGroup, Arrow)

AnyShape = Union[Text, Square, Ellipse, RoundedRectangle, Polygon, Circle, Rectangle,
                 Point, Line, Path, Polyline, ShapeGroup, Arrow]

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
        painter.save() # 保存当前状态

        # --- 新增逻辑：应用当前图形(可能是组合)的变换 ---
        bbox = shape.get_bounding_box()
        center = bbox.center()
        painter.translate(center)
        painter.scale(shape.scale_x, shape.scale_y)
        painter.rotate(shape.angle)
        painter.translate(-center)
        # --- 结束新增 ---
        
        if isinstance(shape, ShapeGroup):
            # 对于组合，我们已经应用了组合的变换，现在只需要画出它的子图形
            # 注意：子图形自身的变换也需要被绘制，所以再次调用递归函数
            for sub_shape in shape.shapes:
                # 再次调用递归，而不是直接调用 _draw_single_shape
                CanvasRenderer._draw_shape_recursive(painter, sub_shape)
        else:
            # 对于单个图形，我们不需要再应用变换，因为已经在上面应用过了
            # 所以我们创建一个 "dummy_draw" 方法来跳过变换部分
            CanvasRenderer._draw_single_shape_no_transform(painter, shape)

        painter.restore() # 恢复到调用前的状态

    @staticmethod
    def _draw_single_shape_no_transform(painter: QPainter, shape: AnyShape):
        # 这是一个新的辅助方法，它只包含绘制逻辑，没有变换逻辑
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