import math
from typing import Union
from PyQt6.QtWidgets import QWidget
# 🔴 修正：从这里删除了 QLine
from PyQt6.QtGui import (QPainter, QPen, QColor, QBrush, QPolygon, QPolygonF, 
                         QPainterPath, QImage, QTransform, QLinearGradient)
# 🟢 修正：将 QLine 加到了这里
from PyQt6.QtCore import Qt, QRect, QPoint, QPointF, QLineF, QRectF, QLine

from shapes import *
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
        
        # 1. 填充背景色
        final_buffer.fill(canvas.background_color)

        # 🟢 [最终修正版] 网格绘制：利用 Qt 原生逻辑坐标
        if canvas.grid_enabled:
            grid_painter = QPainter(final_buffer)
            
            # ❌ 不要手动 scale，Qt 会根据 setDevicePixelRatio 自动处理
            # ❌ 不要手动乘 total_scale
            
            # 🟢 关键：使用宽度为 0 的 Cosmetic Pen
            # 含义："在屏幕上永远只占 1 物理像素"，无论缩放倍率是多少
            # 这样既能对齐刻度，线又非常细致
            grid_pen = QPen(QColor(150, 150, 150), 0, Qt.PenStyle.SolidLine)
            grid_painter.setPen(grid_pen)

            # 直接使用逻辑宽、高
            w_logical = canvas.width()
            h_logical = canvas.height()
            step = canvas.grid_size # 直接用 50
            
            # 画竖线
            for x in range(0, w_logical, step):
                grid_painter.drawLine(x, 0, x, h_logical)
                
            # 画横线
            for y in range(0, h_logical, step):
                grid_painter.drawLine(0, y, w_logical, y)
                
            grid_painter.end()
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
        
        # 构建变换矩阵 (注意 center 现在可能是 QPointF)
        base_transform = QTransform().translate(center.x(), center.y()).scale(shape.scale_x, shape.scale_y).rotate(shape.angle).translate(-center.x(), -center.y())
        
        total_pixel_ratio = framebuffer.devicePixelRatioF()
        current_algo = canvas.current_raster_algorithm
        shape_type = type(shape)

        # --- 模式 1: Native Qt Rendering (原生渲染) ---
        # 文本始终使用原生渲染，或者当用户选择 "PyQt原生" 算法时
        if shape_type is Text or current_algo == 'PyQt原生':
            painter = QPainter(framebuffer)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setTransform(base_transform)
            
            should_fill = (hasattr(shape, 'fill_color') and shape.fill_color and hasattr(shape, 'fill_style') and shape.fill_style != Qt.BrushStyle.NoBrush)
            
            if should_fill: painter.setBrush(QBrush(shape.fill_color, shape.fill_style))
            else: painter.setBrush(Qt.BrushStyle.NoBrush)
            
            pen = QPen(shape.color, shape.width if hasattr(shape, 'width') else 1)
            if hasattr(shape, 'stroke_linecap'): pen.setCapStyle(shape.stroke_linecap)
            if hasattr(shape, 'stroke_linejoin'): pen.setJoinStyle(shape.stroke_linejoin)
            painter.setPen(pen)
            
            if shape_type is Text:
                # Text 的 bbox 现在是 QRectF，Qt 能够处理
                painter.setFont(shape.font)
                painter.drawText(shape.get_bounding_box(), int(shape.alignment) | Qt.TextFlag.TextWordWrap, shape.text)
                if shape.has_border:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(shape.border_color, 1))
                    painter.drawRect(shape.get_bounding_box())
            elif shape_type is Point: painter.drawEllipse(shape.pos, shape.width, shape.width)
            elif shape_type is Arrow: CanvasRenderer.draw_arrow(painter, shape.p1, shape.p2, shape.color, shape.width)
            elif shape_type is Line: painter.drawLine(shape.p1, shape.p2)
            elif shape_type is Circle: painter.drawEllipse(shape.center, shape.radius, shape.radius)
            elif shape_type in [Rectangle, Square]: painter.drawRect(shape.get_bounding_box())
            elif shape_type in [Polygon, Polyline]:
                if shape_type is Polyline: painter.drawPolyline(QPolygonF(shape.points))
                else: painter.drawPolygon(QPolygonF(shape.points))
            elif shape_type is RoundedRectangle: painter.drawRoundedRect(shape.get_bounding_box(), 20, 20)
            elif shape_type is Ellipse: painter.drawEllipse(shape.get_bounding_box())
            elif isinstance(shape, Path): painter.drawPath(shape.get_painter_path())
            
            painter.end()
            return

        # --- 模式 2: Custom Rasterization Engine (自定义光栅化引擎) ---
        
        final_transform = base_transform * QTransform().scale(total_pixel_ratio, total_pixel_ratio)
        physical_width = max(1, int(shape.width * total_pixel_ratio))
        should_fill = (hasattr(shape, 'fill_color') and shape.fill_color and hasattr(shape, 'fill_style') and shape.fill_style != Qt.BrushStyle.NoBrush)

        fill_spans = []      # 填充区域
        outline_spans = []   # 边框区域
        points_to_draw = []  # 离散点

        # 1. 填充计算 (Generate Fill Spans)
        if should_fill:
            if shape_type in [Rectangle, Square]:
                # QRectF 转 QPolygonF
                r = shape.get_bounding_box()
                corners_poly = QPolygonF([r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()])
                t_poly = final_transform.map(corners_poly)
                fill_spans.extend(raster_algorithms.scanline_fill_polygon(t_poly))
                
            elif shape_type is Circle:
                t_center = final_transform.map(shape.center)
                t_radius = shape.radius * (abs(shape.scale_x)+abs(shape.scale_y))/2 * total_pixel_ratio
                # 🟢 强制转 int，防止 range() 报错
                fill_spans.extend(raster_algorithms.scanline_fill_circle(
                    int(t_center.x()), int(t_center.y()), int(t_radius)
                ))
                
            elif shape_type is Polygon:
                t_points = final_transform.map(QPolygonF(shape.points))
                fill_spans.extend(raster_algorithms.scanline_fill_polygon(t_points))
                
            elif shape_type is Ellipse:
                t_bbox = final_transform.mapRect(shape.get_bounding_box())
                t_center = t_bbox.center()
                rx, ry = t_bbox.width() / 2, t_bbox.height() / 2
                # 🟢 强制转 int
                fill_spans.extend(raster_algorithms.scanline_fill_ellipse(
                    int(t_center.x()), int(t_center.y()), int(rx), int(ry)
                ))
                
            elif shape_type is RoundedRectangle:
                t_bbox = final_transform.mapRect(shape.get_bounding_box())
                # 计算平均缩放后的圆角半径
                avg_scale = (t_bbox.width() / bbox.width() + t_bbox.height() / bbox.height()) / 2 if bbox.width() > 0 and bbox.height() > 0 else 1
                radius = 20 * avg_scale
                # 🟢 强制转 int
                fill_spans.extend(raster_algorithms.scanline_fill_rounded_rect(
                    int(t_bbox.x()), int(t_bbox.y()), int(t_bbox.width()), int(t_bbox.height()), int(radius)
                ))

        # 2. 轮廓计算 (Generate Outline Spans or Points)
        if shape_type is Point:
            t_pos = final_transform.map(shape.pos)
            # Point 也是画一个小圆
            outline_spans.extend(raster_algorithms.scanline_fill_circle(int(t_pos.x()), int(t_pos.y()), physical_width))
            
        elif shape_type is Line:
            t_p1, t_p2 = final_transform.map(shape.p1), final_transform.map(shape.p2)
            poly_points = raster_algorithms.calculate_wide_line_polygon(t_p1.x(), t_p1.y(), t_p2.x(), t_p2.y(), physical_width)
            outline_spans.extend(raster_algorithms.scanline_fill_polygon(poly_points))
            
        elif shape_type is Arrow:
            t_p1, t_p2 = final_transform.map(shape.p1), final_transform.map(shape.p2)
            # 箭头头部
            head_points = raster_algorithms.calculate_arrow_head_points(t_p1.x(), t_p1.y(), t_p2.x(), t_p2.y(), physical_width)
            outline_spans.extend(raster_algorithms.scanline_fill_polygon(head_points))
            
            # 箭头杆身 (缩短一点)
            angle = math.atan2(t_p1.y() - t_p2.y(), t_p1.x() - t_p2.x())
            shorten_dist = (10 + physical_width * 2) * 0.8
            shortened_p2_x = t_p2.x() + shorten_dist * math.cos(angle)
            shortened_p2_y = t_p2.y() + shorten_dist * math.sin(angle)
            poly_points = raster_algorithms.calculate_wide_line_polygon(t_p1.x(), t_p1.y(), shortened_p2_x, shortened_p2_y, physical_width)
            outline_spans.extend(raster_algorithms.scanline_fill_polygon(poly_points))
            
        elif shape_type in [Rectangle, Square]:
            r = shape.get_bounding_box()
            corners = [r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()]
            t_poly = final_transform.map(QPolygonF(corners))
            for i in range(4):
                p1, p2 = t_poly[i], t_poly[(i + 1) % 4]
                poly_points = raster_algorithms.calculate_wide_line_polygon(p1.x(), p1.y(), p2.x(), p2.y(), physical_width)
                outline_spans.extend(raster_algorithms.scanline_fill_polygon(poly_points))
                
        elif shape_type is RoundedRectangle:
            # 圆角矩形轮廓比较复杂，由直线段和圆角弧组成
            t_bbox = final_transform.mapRect(shape.get_bounding_box())
            avg_scale = (t_bbox.width() / bbox.width() + t_bbox.height() / bbox.height()) / 2 if bbox.width() > 0 and bbox.height() > 0 else 1
            base_radius = int(20 * avg_scale)
            base_radius = min(base_radius, int(t_bbox.width() / 2), int(t_bbox.height() / 2))

            offset = int(physical_width / 2)
            center_tl = QPoint(int(t_bbox.left() + base_radius), int(t_bbox.top() + base_radius))
            center_tr = QPoint(int(t_bbox.right() - base_radius), int(t_bbox.top() + base_radius))
            center_bl = QPoint(int(t_bbox.left() + base_radius), int(t_bbox.bottom() - base_radius))
            center_br = QPoint(int(t_bbox.right() - base_radius), int(t_bbox.bottom() - base_radius))

            # 绘制圆角 (四分之一圆弧)
            for i in range(-offset, offset + 1):
                r = base_radius + i
                if r > 0:
                    points_to_draw.extend(raster_algorithms.rasterize_quarter_circle(center_tr.x(), center_tr.y(), r, 1))
                    points_to_draw.extend(raster_algorithms.rasterize_quarter_circle(center_tl.x(), center_tl.y(), r, 2))
                    points_to_draw.extend(raster_algorithms.rasterize_quarter_circle(center_bl.x(), center_bl.y(), r, 3))
                    points_to_draw.extend(raster_algorithms.rasterize_quarter_circle(center_br.x(), center_br.y(), r, 4))

            # 绘制四条边 (矩形连接)
            # Top
            p1 = QPointF(t_bbox.left() + base_radius, t_bbox.top())
            p2 = QPointF(t_bbox.right() - base_radius, t_bbox.top())
            outline_spans.extend(raster_algorithms.scanline_fill_polygon(raster_algorithms.calculate_wide_line_polygon(p1.x(), p1.y(), p2.x(), p2.y(), physical_width)))
            # Bottom
            p1 = QPointF(t_bbox.left() + base_radius, t_bbox.bottom())
            p2 = QPointF(t_bbox.right() - base_radius, t_bbox.bottom())
            outline_spans.extend(raster_algorithms.scanline_fill_polygon(raster_algorithms.calculate_wide_line_polygon(p1.x(), p1.y(), p2.x(), p2.y(), physical_width)))
            # Left
            p1 = QPointF(t_bbox.left(), t_bbox.top() + base_radius)
            p2 = QPointF(t_bbox.left(), t_bbox.bottom() - base_radius)
            outline_spans.extend(raster_algorithms.scanline_fill_polygon(raster_algorithms.calculate_wide_line_polygon(p1.x(), p1.y(), p2.x(), p2.y(), physical_width)))
            # Right
            p1 = QPointF(t_bbox.right(), t_bbox.top() + base_radius)
            p2 = QPointF(t_bbox.right(), t_bbox.bottom() - base_radius)
            outline_spans.extend(raster_algorithms.scanline_fill_polygon(raster_algorithms.calculate_wide_line_polygon(p1.x(), p1.y(), p2.x(), p2.y(), physical_width)))

        elif shape_type in [Polygon, Polyline]:
            t_points = final_transform.map(QPolygonF(shape.points))
            if len(t_points) >= 2:
                for i in range(len(t_points) - 1):
                    poly_points = raster_algorithms.calculate_wide_line_polygon(t_points[i].x(), t_points[i].y(), t_points[i+1].x(), t_points[i+1].y(), physical_width)
                    outline_spans.extend(raster_algorithms.scanline_fill_polygon(poly_points))
                # 如果是闭合多边形，连接首尾
                if shape_type is Polygon and len(t_points) > 2:
                    poly_points = raster_algorithms.calculate_wide_line_polygon(t_points[-1].x(), t_points[-1].y(), t_points[0].x(), t_points[0].y(), physical_width)
                    outline_spans.extend(raster_algorithms.scanline_fill_polygon(poly_points))
                    
        elif shape_type is Circle:
            t_center = final_transform.map(shape.center)
            base_radius = shape.radius * (abs(shape.scale_x)+abs(shape.scale_y))/2 * total_pixel_ratio
            offset = int(physical_width / 2)
            # 🟢 强制转 int
            base_r_int = int(base_radius)
            for i in range(-offset, offset + 1):
                if (r := base_r_int + i) > 0: 
                    points_to_draw.extend(raster_algorithms.midpoint_circle(int(t_center.x()), int(t_center.y()), r))
                    
        elif shape_type is Ellipse:
            t_bbox = final_transform.mapRect(shape.get_bounding_box())
            t_center = t_bbox.center()
            base_rx = t_bbox.width() / 2
            base_ry = t_bbox.height() / 2
            offset = int(physical_width / 2)
            # 🟢 强制转 int
            base_rx_int, base_ry_int = int(base_rx), int(base_ry)
            for i in range(-offset, offset + 1):
                if (rx := base_rx_int + i) > 0 and (ry := base_ry_int + i) > 0: 
                    points_to_draw.extend(raster_algorithms.midpoint_ellipse(int(t_center.x()), int(t_center.y()), rx, ry))
                    
        elif isinstance(shape, Path):
            # 贝塞尔曲线光栅化
            for sub_path in shape.sub_paths:
                if len(sub_path) < 2: continue
                flattened_points = []
                for i in range(len(sub_path) - 1):
                    start_seg, end_seg = sub_path[i], sub_path[i+1]
                    # 贝塞尔平坦化
                    segment_points = raster_algorithms.flatten_bezier(start_seg.anchor, start_seg.handle2, end_seg.handle1, end_seg.anchor, tolerance=0.75)
                    if flattened_points: flattened_points.extend(segment_points[1:])
                    else: flattened_points.extend(segment_points)
                
                # 转换坐标
                t_points = final_transform.map(QPolygonF([QPointF(p) for p in flattened_points]))
                
                # 绘制宽线
                if len(t_points) >= 2:
                    for i in range(len(t_points) - 1):
                        poly_points = raster_algorithms.calculate_wide_line_polygon(t_points[i].x(), t_points[i].y(), t_points[i+1].x(), t_points[i+1].y(), physical_width)
                        outline_spans.extend(raster_algorithms.scanline_fill_polygon(poly_points))
                        
        elif isinstance(shape, BSpline):
            # B样条
            curve_points = raster_algorithms.compute_bspline_points(shape.points, shape.degree)
            t_points = final_transform.map(QPolygonF(curve_points))
            
            if len(t_points) >= 2:
                for i in range(len(t_points) - 1):
                    poly_points = raster_algorithms.calculate_wide_line_polygon(
                        t_points[i].x(), t_points[i].y(), 
                        t_points[i+1].x(), t_points[i+1].y(), 
                        physical_width
                    )
                    outline_spans.extend(raster_algorithms.scanline_fill_polygon(poly_points))
                    
        elif isinstance(shape, BezierSurface):
            # 贝塞尔曲面 (重点逻辑)
            t_control_points = [final_transform.map(p) for p in shape.points]
            
            # 1. 如果开启填充 -> Gouraud 着色
            if getattr(shape, 'show_fill', True):
                triangles = raster_algorithms.tessellate_bezier_surface(t_control_points, steps=15)
                gouraud_spans = []
                for p1, c1, p2, c2, p3, c3 in triangles:
                    spans = raster_algorithms.rasterize_triangle_gouraud(p1, c1, p2, c2, p3, c3)
                    gouraud_spans.extend(spans)
                
                local_painter = QPainter(framebuffer)
                inv_scale = 1.0 / total_pixel_ratio
                local_painter.scale(inv_scale, inv_scale)
                CanvasRenderer.draw_gouraud_spans(local_painter, gouraud_spans)
                local_painter.end()

            # 2. 如果开启网格线 -> 绘制 Wireframe
            if getattr(shape, 'show_wireframe', True):
                wireframe_width = max(1, int(1 * total_pixel_ratio))
                grid_lines = raster_algorithms.compute_bezier_surface_wireframe(shape.points, steps=12)
                for line_points in grid_lines:
                     t_points = final_transform.map(QPolygonF(line_points))
                     if len(t_points) >= 2:
                         for i in range(len(t_points) - 1):
                             poly_points = raster_algorithms.calculate_wide_line_polygon(
                                 t_points[i].x(), t_points[i].y(),
                                 t_points[i+1].x(), t_points[i+1].y(),
                                 wireframe_width
                             )
                             outline_spans.extend(raster_algorithms.scanline_fill_polygon(poly_points))

        # 3. 最终批量绘制 (Batch Draw)
        
        batch_painter = QPainter(framebuffer)
        inv_scale = 1.0 / total_pixel_ratio
        batch_painter.scale(inv_scale, inv_scale)
        
        # A. Fill (纯色填充)
        if fill_spans:
            batch_painter.setPen(QPen(shape.fill_color, 1))
            lines = [QLine(x1, y, x2, y) for y, x1, x2 in fill_spans]
            batch_painter.drawLines(lines)

        # B. Outline (边框)
        if outline_spans:
            batch_painter.setPen(QPen(shape.color, 1))
            lines = [QLine(x1, y, x2, y) for y, x1, x2 in outline_spans]
            batch_painter.drawLines(lines)

        # C. Points (离散点)
        if points_to_draw:
            batch_painter.setPen(QPen(shape.color, 1))
            points = [QPoint(x, y) for x, y in points_to_draw]
            batch_painter.drawPoints(points)
            
        batch_painter.end()
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
    @staticmethod
    def draw_gouraud_spans(painter: QPainter, spans: list):
        """
        绘制带有颜色插值的 Spans。
        spans: [(y, x_start, x_end, c_start, c_end), ...]
        """
        # 禁用画笔边框，只填充
        painter.setPen(Qt.PenStyle.NoPen)
        
        for y, x_start, x_end, c_start, c_end in spans:
            width = x_end - x_start
            if width <= 0: continue
            
            # 性能优化：如果起始颜色和结束颜色非常接近，直接画纯色矩形
            # 避免构建昂贵的 QLinearGradient
            if (abs(c_start.red() - c_end.red()) < 2 and
                abs(c_start.green() - c_end.green()) < 2 and
                abs(c_start.blue() - c_end.blue()) < 2):
                
                painter.fillRect(x_start, y, width, 1, c_start)
            else:
                # 构建线性渐变
                # 注意：QLinearGradient 的坐标是相对于 painter 当前变换的
                gradient = QLinearGradient(x_start, y, x_end, y)
                gradient.setColorAt(0.0, c_start)
                gradient.setColorAt(1.0, c_end)
                
                # 使用渐变刷子绘制单像素高的矩形
                painter.fillRect(x_start, y, width, 1, QBrush(gradient))