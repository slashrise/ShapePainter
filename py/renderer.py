import math
from typing import Union
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import (QPainter, QPen, QColor, QBrush, QPolygon, QPolygonF, 
                         QPainterPath, QImage, QTransform)
from PyQt6.QtCore import Qt, QRect, QPoint, QPointF, QLineF, QRectF

from shapes import (Text, Square, Ellipse, RoundedRectangle, Polygon, Circle, Rectangle,
                    Point, Line, Path, Polyline, ShapeGroup, Arrow)
import raster_algorithms

AnyShape = Union[Text, Square, Ellipse, RoundedRectangle, Polygon, Circle, Rectangle,
                 Point, Line, Path, Polyline, ShapeGroup, Arrow]

class CanvasRenderer:
    SSAA_BASE_FACTOR = 2

    @staticmethod
    def paint(painter: QPainter, canvas: QWidget):
        CanvasRenderer.draw_layers(painter, canvas)
        if canvas.current_tool_obj:
            canvas.current_tool_obj.paint(painter)

    @staticmethod
    def draw_layers(painter: QPainter, canvas: QWidget):
        ssaa_factor = CanvasRenderer.SSAA_BASE_FACTOR if canvas.ssaa_enabled else 1
        size = canvas.size()
        pixel_ratio = canvas.devicePixelRatioF()
        buffer_size = size * pixel_ratio * ssaa_factor
        
        final_buffer = QImage(buffer_size, QImage.Format.Format_ARGB32_Premultiplied)
        final_buffer.setDevicePixelRatio(pixel_ratio * ssaa_factor)
        final_buffer.fill(canvas.background_color)

        for layer in canvas.layers:
            if not layer.is_visible: continue
            if layer.is_dirty or layer.cache is None or layer.cache.size() != buffer_size:
                layer.cache = QImage(buffer_size, QImage.Format.Format_ARGB32_Premultiplied)
                layer.cache.setDevicePixelRatio(pixel_ratio * ssaa_factor)
                layer.cache.fill(Qt.GlobalColor.transparent)
                for shape in layer.shapes:
                    if shape == canvas.editing_shape: continue
                    CanvasRenderer._draw_shape_recursive(layer.cache, shape, canvas)
                layer.is_dirty = False
            
            buffer_painter = QPainter(final_buffer)
            buffer_painter.setOpacity(layer.opacity)
            buffer_painter.setCompositionMode(layer.blend_mode)
            buffer_painter.drawImage(0, 0, layer.cache)
            buffer_painter.end()

        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(canvas.rect(), final_buffer)

    @staticmethod
    def _draw_shape_recursive(framebuffer: QImage, shape: AnyShape, canvas: QWidget):
        if isinstance(shape, ShapeGroup):
            for sub_shape in shape.shapes:
                CanvasRenderer._draw_shape_recursive(framebuffer, sub_shape, canvas)
        else:
            CanvasRenderer._draw_single_shape_to_buffer(framebuffer, shape, canvas)
            
    @staticmethod
    def _draw_single_shape_to_buffer(framebuffer: QImage, shape: AnyShape, canvas: QWidget):
        ssaa_factor = CanvasRenderer.SSAA_BASE_FACTOR if canvas.ssaa_enabled else 1
        
        bbox = shape.get_bounding_box()
        center = bbox.center()
        base_transform = QTransform().translate(center.x(), center.y()) \
                                   .scale(shape.scale_x, shape.scale_y) \
                                   .rotate(shape.angle) \
                                   .translate(-center.x(), -center.y())
        
        total_pixel_ratio = framebuffer.devicePixelRatioF()
        current_algo = canvas.current_raster_algorithm
        shape_type = type(shape)

        # 🔴 核心修复：Text 对象现在和其他原生图形一样，统一由 QPainter 以标准方式处理
        # 无论是我方算法还是原生算法，文本都由 QPainter 绘制，因为它不适合光栅化
        if shape_type is Text or current_algo == 'PyQt原生':
            painter = QPainter(framebuffer)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # 关键：我们只给 QPainter 提供图形自身的逻辑变换 (旋转/缩放)
            # QPainter 会根据 framebuffer 的 devicePixelRatio 自动处理所有 DPI 和 SSAA 缩放
            painter.setTransform(base_transform)
            
            should_fill = (hasattr(shape, 'fill_color') and shape.fill_color and 
                           hasattr(shape, 'fill_style') and shape.fill_style != Qt.BrushStyle.NoBrush)
            
            if should_fill: painter.setBrush(QBrush(shape.fill_color, shape.fill_style))
            else: painter.setBrush(Qt.BrushStyle.NoBrush)
            
            # 对于 Text，我们使用 .color。对于其他图形，使用 .width
            pen_color = shape.color
            pen_width = shape.width if hasattr(shape, 'width') else 1 # Text 没有 width, 设为1
            pen = QPen(pen_color, pen_width)

            if hasattr(shape, 'stroke_linecap'): pen.setCapStyle(shape.stroke_linecap)
            if hasattr(shape, 'stroke_linejoin'): pen.setJoinStyle(shape.stroke_linejoin)
            painter.setPen(pen)

            if shape_type is Text:
                painter.setFont(shape.font)
                # 直接使用 shape 的逻辑包围盒
                painter.drawText(QRectF(shape.get_bounding_box()), int(shape.alignment) | Qt.TextFlag.TextWordWrap, shape.text)
                if shape.has_border:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(shape.border_color, 1))
                    painter.drawRect(shape.get_bounding_box())
            elif shape_type is Point: painter.drawEllipse(shape.pos, shape.width, shape.width)
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
            
            painter.end()
            return

        # --- 从这里开始，是我方自定义光栅化算法的逻辑 ---
        
        def write_pixels_to_buffer(pixels, color):
            for x, y in pixels:
                if 0 <= x < framebuffer.width() and 0 <= y < framebuffer.height():
                    framebuffer.setPixelColor(x, y, color)
        
        final_transform = base_transform * QTransform().scale(total_pixel_ratio, total_pixel_ratio)
        
        fill_pixels, outline_pixels = [], []
        
        physical_width = max(1, int(shape.width * total_pixel_ratio))

        should_fill = (hasattr(shape, 'fill_color') and shape.fill_color and 
                       hasattr(shape, 'fill_style') and shape.fill_style != Qt.BrushStyle.NoBrush)

        if should_fill:
            if shape_type in [Rectangle, Square]: poly = QPolygon(final_transform.map(bbox)); fill_pixels = raster_algorithms.scanline_fill_polygon(poly)
            elif shape_type is Circle:
                t_center = final_transform.map(shape.center); t_radius = int(shape.radius * (abs(shape.scale_x)+abs(shape.scale_y))/2 * total_pixel_ratio)
                fill_pixels = raster_algorithms.scanline_fill_circle(t_center.x(), t_center.y(), t_radius)
            elif shape_type is Polygon: t_points = final_transform.map(QPolygon(shape.points)); fill_pixels = raster_algorithms.scanline_fill_polygon(t_points)

        if shape_type is Point: t_pos = final_transform.map(shape.pos); outline_pixels = raster_algorithms.scanline_fill_circle(t_pos.x(), t_pos.y(), physical_width)
        elif shape_type is Line:
            t_p1, t_p2 = final_transform.map(shape.p1), final_transform.map(shape.p2)
            poly_points = raster_algorithms.calculate_wide_line_polygon(t_p1.x(), t_p1.y(), t_p2.x(), t_p2.y(), physical_width)
            outline_pixels = raster_algorithms.scanline_fill_polygon(poly_points)
        elif shape_type is Arrow:
            t_p1, t_p2 = final_transform.map(shape.p1), final_transform.map(shape.p2)
            head_points = raster_algorithms.calculate_arrow_head_points(t_p1.x(), t_p1.y(), t_p2.x(), t_p2.y(), physical_width)
            outline_pixels.extend(raster_algorithms.scanline_fill_polygon(head_points))
            angle = math.atan2(t_p1.y() - t_p2.y(), t_p1.x() - t_p2.x())
            shorten_dist = (10 + physical_width * 2) * 0.8 
            shortened_p2_x = int(t_p2.x() + shorten_dist * math.cos(angle)); shortened_p2_y = int(t_p2.y() + shorten_dist * math.sin(angle))
            poly_points = raster_algorithms.calculate_wide_line_polygon(t_p1.x(), t_p1.y(), shortened_p2_x, shortened_p2_y, physical_width)
            outline_pixels.extend(raster_algorithms.scanline_fill_polygon(poly_points))
        elif shape_type in [Rectangle, Square, RoundedRectangle]:
            bbox = shape.get_bounding_box(); t_poly = final_transform.map(QPolygon([bbox.topLeft(), bbox.topRight(), bbox.bottomRight(), bbox.bottomLeft()]))
            for i in range(4):
                p1 = t_poly[i]; p2 = t_poly[(i + 1) % 4]
                poly_points = raster_algorithms.calculate_wide_line_polygon(p1.x(), p1.y(), p2.x(), p2.y(), physical_width)
                outline_pixels.extend(raster_algorithms.scanline_fill_polygon(poly_points))
        elif shape_type in [Polygon, Polyline]:
            t_points = final_transform.map(QPolygon(shape.points))
            if len(t_points) >= 2:
                for i in range(len(t_points) - 1):
                    poly_points = raster_algorithms.calculate_wide_line_polygon(t_points[i].x(), t_points[i].y(), t_points[i+1].x(), t_points[i+1].y(), physical_width)
                    outline_pixels.extend(raster_algorithms.scanline_fill_polygon(poly_points))
                if shape_type is Polygon and len(t_points) > 2:
                    poly_points = raster_algorithms.calculate_wide_line_polygon(t_points[-1].x(), t_points[-1].y(), t_points[0].x(), t_points[0].y(), physical_width)
                    outline_pixels.extend(raster_algorithms.scanline_fill_polygon(poly_points))
        elif shape_type is Circle:
            t_center = final_transform.map(shape.center); base_radius = int(shape.radius * (abs(shape.scale_x)+abs(shape.scale_y))/2 * total_pixel_ratio)
            offset = int(physical_width / 2)
            for i in range(-offset, offset + 1):
                r = base_radius + i
                if r > 0: outline_pixels.extend(raster_algorithms.midpoint_circle(t_center.x(), t_center.y(), r))
        elif shape_type is Ellipse:
            t_bbox = final_transform.mapRect(bbox); t_center = t_bbox.center()
            base_rx = int(t_bbox.width() / 2); base_ry = int(t_bbox.height() / 2)
            offset = int(physical_width / 2)
            for i in range(-offset, offset + 1):
                rx = base_rx + i; ry = base_ry + i
                if rx > 0 and ry > 0: outline_pixels.extend(raster_algorithms.midpoint_ellipse(t_center.x(), t_center.y(), rx, ry))
        
        if fill_pixels: write_pixels_to_buffer(fill_pixels, shape.fill_color)
        if outline_pixels: write_pixels_to_buffer(outline_pixels, shape.color)

    @staticmethod
    def draw_arrow(painter: QPainter, p1: QPoint, p2: QPoint, color: QColor, width: int, only_head=False):
        if p1 is None or p2 is None or p1 == p2: return
        pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        angle = math.atan2(p1.y() - p2.y(), p1.x() - p2.x())
        arrow_size = 10 + width * 2
        arrow_angle = math.pi / 6
        if not only_head:
            line_to_draw = QLineF(QPointF(p1), QPointF(p2))
            shorten_dist = arrow_size * math.cos(arrow_angle) 
            if line_to_draw.length() > shorten_dist:
                line_to_draw.setLength(line_to_draw.length() - shorten_dist)
            painter.drawLine(line_to_draw)
        p_left_x = p2.x() + arrow_size * math.cos(angle + arrow_angle)
        p_left_y = p2.y() + arrow_size * math.sin(angle + arrow_angle)
        p_right_x = p2.x() + arrow_size * math.cos(angle - arrow_angle)
        p_right_y = p2.y() + arrow_size * math.sin(angle - arrow_angle)
        arrow_head = QPolygonF()
        arrow_head.append(QPointF(p2)); arrow_head.append(QPointF(p_left_x, p_left_y)); arrow_head.append(QPointF(p_right_x, p_right_y))
        painter.setBrush(color)
        painter.drawPolygon(arrow_head)