import math
from typing import Union
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import (QPainter, QPen, QColor, QBrush, QPolygon, QPolygonF, 
                         QPainterPath, QPixmap)
from PyQt6.QtCore import Qt, QRect, QPoint, QPointF, QLineF, QRectF

from shapes import (Text, Square, Ellipse, RoundedRectangle, Polygon, Circle, Rectangle,
                    Point, Line, Path, Polyline, ShapeGroup, Arrow)
import raster_algorithms

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
            if not layer.is_visible: continue
            pixel_ratio = canvas.devicePixelRatioF(); size = canvas.size() * pixel_ratio
            layer_buffer = QPixmap(size); layer_buffer.setDevicePixelRatio(pixel_ratio)
            layer_buffer.fill(Qt.GlobalColor.transparent)
            buffer_painter = QPainter(layer_buffer); buffer_painter.canvas = canvas 
            buffer_painter.setRenderHint(QPainter.RenderHint.Antialiasing) 
            for shape in layer.shapes:
                if shape == canvas.editing_shape: continue
                CanvasRenderer._draw_shape_recursive(buffer_painter, shape)
            buffer_painter.end()
            painter.setOpacity(layer.opacity); painter.setCompositionMode(layer.blend_mode)
            painter.drawPixmap(0, 0, layer_buffer)
        painter.setOpacity(1.0); painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    @staticmethod
    def _draw_shape_recursive(painter: QPainter, shape: AnyShape):
        painter.save()
        bbox = shape.get_bounding_box(); center = bbox.center()
        painter.translate(center); painter.scale(shape.scale_x, shape.scale_y)
        painter.rotate(shape.angle); painter.translate(-center)
        if isinstance(shape, ShapeGroup):
            for sub_shape in shape.shapes:
                CanvasRenderer._draw_shape_recursive(painter, sub_shape)
        else:
            CanvasRenderer._draw_single_shape_no_transform(painter, shape)
        painter.restore()

    @staticmethod
    def _draw_single_shape_no_transform(painter: QPainter, shape: AnyShape):
        current_algo = getattr(painter.canvas, 'current_raster_algorithm', 'PyQt原生')
        shape_type = type(shape)

        should_fill = (hasattr(shape, 'fill_color') and shape.fill_color and 
                       hasattr(shape, 'fill_style') and shape.fill_style != Qt.BrushStyle.NoBrush)

        def to_qpoints(pixels):
            return [QPoint(x, y) for x, y in pixels]

        if shape_type is Text:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setFont(shape.font); painter.setPen(QPen(shape.color))
            painter.drawText(QRectF(shape.get_bounding_box()), int(shape.alignment) | Qt.TextFlag.TextWordWrap, shape.text)
            if shape.has_border:
                painter.setPen(QPen(shape.border_color, 1)); painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(shape.get_bounding_box())
        else:
            # --- 1. 绘制填充 (仅在光栅化模式下) ---
            if should_fill and current_algo != 'PyQt原生':
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                painter.setPen(QPen(shape.fill_color))
                fill_pixels = []
                fill_style = shape.fill_style

                if shape_type in [Rectangle, Square]:
                    bbox = shape.get_bounding_box()
                    for y in range(bbox.top(), bbox.bottom() + 1):
                        for x in range(bbox.left(), bbox.right() + 1): fill_pixels.append((x, y))
                elif shape_type is Circle:
                     fill_pixels = raster_algorithms.scanline_fill_circle(shape.center.x(), shape.center.y(), int(shape.radius))
                elif shape_type is Polygon:
                     fill_pixels = raster_algorithms.scanline_fill_polygon(shape.points)
                
                if fill_pixels:
                    if fill_style == Qt.BrushStyle.SolidPattern:
                        painter.drawPoints(to_qpoints(fill_pixels))
                    else: # 处理样式
                        filtered_pixels = []
                        pattern_size = 4
                        for x, y in fill_pixels:
                            if (fill_style == Qt.BrushStyle.HorPattern and y % pattern_size == 0) or \
                               (fill_style == Qt.BrushStyle.VerPattern and x % pattern_size == 0) or \
                               (fill_style == Qt.BrushStyle.CrossPattern and (x % pattern_size == 0 or y % pattern_size == 0)) or \
                               (fill_style == Qt.BrushStyle.DiagCrossPattern and (x + y) % pattern_size == 0):
                                filtered_pixels.append(QPoint(x, y))
                        if filtered_pixels: painter.drawPoints(filtered_pixels)

            # --- 2. 绘制轮廓 ---
            base_pen = QPen(shape.color, shape.width)
            if hasattr(shape, 'stroke_linecap'): base_pen.setCapStyle(shape.stroke_linecap)
            if hasattr(shape, 'stroke_linejoin'): base_pen.setJoinStyle(shape.stroke_linejoin)
            painter.setPen(base_pen)
            
            if current_algo == 'PyQt原生':
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                if should_fill: painter.setBrush(QBrush(shape.fill_color, shape.fill_style))
                else: painter.setBrush(Qt.BrushStyle.NoBrush)
                
                if shape_type is Point: painter.drawEllipse(shape.pos, shape.width, shape.width)
                elif shape_type is Arrow: CanvasRenderer.draw_arrow(painter, shape.p1, shape.p2, shape.color, shape.width)
                elif shape_type is Line: painter.drawLine(shape.p1, shape.p2)
                elif shape_type is Circle: painter.drawEllipse(shape.center, int(shape.radius), int(shape.radius))
                elif shape_type in [Rectangle, Square]: painter.drawRect(shape.get_bounding_box())
                elif shape_type in [Polygon, Polyline]:
                    if shape_type is Polyline: painter.drawPolyline(QPolygon(shape.points))
                    else: painter.drawPolygon(QPolygon(shape.points))
                elif shape_type is RoundedRectangle: painter.drawRoundedRect(shape.get_bounding_box(), 20, 20)
                elif shape_type is Ellipse: painter.drawEllipse(shape.get_bounding_box())
                elif isinstance(shape, Path): painter.drawPath(shape.get_painter_path())
                return
            
            # --- 光栅化绘制轮廓 ---
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            outline_pixels = []
            line_drawer = raster_algorithms.bresenham_line if current_algo == 'Bresenham' else raster_algorithms.dda_line

            if shape_type is Point:
                outline_pixels = raster_algorithms.scanline_fill_circle(shape.pos.x(), shape.pos.y(), shape.width)
            elif shape_type in [Arrow, Line]:
                outline_pixels = line_drawer(shape.p1.x(), shape.p1.y(), shape.p2.x(), shape.p2.y())
            elif shape_type is Circle:
                outline_pixels = raster_algorithms.midpoint_circle(shape.center.x(), shape.center.y(), int(shape.radius))
            elif shape_type in [Rectangle, Square]:
                bbox = shape.get_bounding_box()
                tl, tr, bl, br = bbox.topLeft(), bbox.topRight(), bbox.bottomLeft(), bbox.bottomRight()
                outline_pixels.extend(line_drawer(tl.x(), tl.y(), tr.x(), tr.y()))
                outline_pixels.extend(line_drawer(bl.x(), bl.y(), br.x(), br.y()))
                outline_pixels.extend(line_drawer(tl.x(), tl.y(), bl.x(), bl.y()))
                outline_pixels.extend(line_drawer(tr.x(), tr.y(), br.x(), br.y()))
            elif shape_type in [Polygon, Polyline]:
                points = shape.points
                if len(points) >= 2:
                    for i in range(len(points) - 1):
                        outline_pixels.extend(line_drawer(points[i].x(), points[i].y(), points[i+1].x(), points[i+1].y()))
                    if shape_type is Polygon and len(points) > 2:
                        outline_pixels.extend(line_drawer(points[-1].x(), points[-1].y(), points[0].x(), points[0].y()))
            elif shape_type is RoundedRectangle:
                bbox = shape.get_bounding_box()
                
                # 核心修复：计算自适应半径
                fixed_radius = 20
                adaptive_radius = min(fixed_radius, bbox.width() // 2, bbox.height() // 2)
                r = adaptive_radius # 使用自适应半径进行后续所有计算

                if r > 0:
                    c1,c2,c3,c4 = bbox.topLeft()+QPoint(r,r), bbox.topRight()+QPoint(-r,r), bbox.bottomLeft()+QPoint(r,-r), bbox.bottomRight()+QPoint(-r,-r)
                    # 绘制圆弧
                    outline_pixels.extend(raster_algorithms.rasterize_quarter_circle(c1.x(), c1.y(), r, 2))
                    outline_pixels.extend(raster_algorithms.rasterize_quarter_circle(c2.x(), c2.y(), r, 1))
                    outline_pixels.extend(raster_algorithms.rasterize_quarter_circle(c3.x(), c3.y(), r, 3))
                    outline_pixels.extend(raster_algorithms.rasterize_quarter_circle(c4.x(), c4.y(), r, 4))
                    # 绘制直线
                    outline_pixels.extend(line_drawer(c1.x(), bbox.top(), c2.x(), bbox.top()))
                    outline_pixels.extend(line_drawer(c3.x(), bbox.bottom(), c4.x(), bbox.bottom()))
                    outline_pixels.extend(line_drawer(bbox.left(), c1.y(), bbox.left(), c3.y()))
                    outline_pixels.extend(line_drawer(bbox.right(), c2.y(), bbox.right(), c4.y()))
                else: # 如果半径为0或负，直接画一个普通矩形
                    tl, tr, bl, br = bbox.topLeft(), bbox.topRight(), bbox.bottomLeft(), bbox.bottomRight()
                    outline_pixels.extend(line_drawer(tl.x(), tl.y(), tr.x(), tr.y()))
                    outline_pixels.extend(line_drawer(bl.x(), bl.y(), br.x(), br.y()))
                    outline_pixels.extend(line_drawer(tl.x(), tl.y(), bl.x(), bl.y()))
                    outline_pixels.extend(line_drawer(tr.x(), tr.y(), br.x(), br.y()))

            elif shape_type is Ellipse:
                bbox, center = shape.get_bounding_box(), shape.get_bounding_box().center()
                rx, ry = int(bbox.width()/2), int(bbox.height()/2)
                if rx > 0 and ry > 0:
                    outline_pixels = raster_algorithms.midpoint_ellipse(center.x(), center.y(), rx, ry)
            
            if outline_pixels:
                painter.drawPoints(to_qpoints(outline_pixels))
            
            if shape_type is Arrow:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                CanvasRenderer.draw_arrow(painter, shape.p1, shape.p2, shape.color, shape.width, only_head=True)

    @staticmethod
    def draw_arrow(painter: QPainter, p1: QPoint, p2: QPoint, color: QColor, width: int, only_head=False):
        if p1 is None or p2 is None or p1 == p2:
            return

        # 1. 设置画笔
        pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        
        # 2. 计算角度和尺寸 (来自您提供的正确版本)
        angle = math.atan2(p1.y() - p2.y(), p1.x() - p2.x())
        arrow_size = 10 + width * 2
        arrow_angle = math.pi / 6

        # 3. 如果需要画线段，则计算缩短后的线段并绘制
        if not only_head:
            line_to_draw = QLineF(QPointF(p1), QPointF(p2))
            # 缩短距离稍微调整，以更好地匹配头部大小
            shorten_dist = arrow_size * math.cos(arrow_angle) 
            if line_to_draw.length() > shorten_dist:
                line_to_draw.setLength(line_to_draw.length() - shorten_dist)
            painter.drawLine(line_to_draw)
        
        # 4. 计算箭头头部的三个顶点 (来自您提供的正确版本)
        p_left_x = p2.x() + arrow_size * math.cos(angle + arrow_angle)
        p_left_y = p2.y() + arrow_size * math.sin(angle + arrow_angle)
        p_right_x = p2.x() + arrow_size * math.cos(angle - arrow_angle)
        p_right_y = p2.y() + arrow_size * math.sin(angle - arrow_angle)
        
        arrow_head = QPolygonF()
        arrow_head.append(QPointF(p2))
        arrow_head.append(QPointF(p_left_x, p_left_y))
        arrow_head.append(QPointF(p_right_x, p_right_y))
        
        # 5. 绘制填充好的箭头头部
        painter.setBrush(color)
        painter.drawPolygon(arrow_head)