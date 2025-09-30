# --- START OF FILE tools.py ---

import math
from PyQt6.QtWidgets import QApplication, QTextEdit
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPolygon, QPainterPath, QCursor
from PyQt6.QtCore import Qt, QPoint, QRect, QPointF, QLineF

from shapes import *
from commands import (AddShapeCommand, RemoveShapesCommand, MoveShapesCommand,
                      ScaleCommand, ChangePropertiesCommand)

class Tool:
    def __init__(self, canvas):
        self.canvas = canvas
    def mousePressEvent(self, event):
        pass
    def mouseMoveEvent(self, event):
        pass
    def mouseReleaseEvent(self, event):
        pass
    def mouseDoubleClickEvent(self, event):
        pass
    def keyPressEvent(self, event):
        pass
    def activate(self):
        pass
    def deactivate(self):
        self.canvas.update()
    def paint(self, painter):
        pass

class SelectTool(Tool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.is_multiselecting = False
        self.selection_rect = None
        self.action_start_position = None
        self.original_shapes_for_action = []
        self.dragging = False
        self.scaling = False
        self.scale_corner = None
        self.scale_center = None
        self.node_editing_active = False
        self.selected_node_index = -1
        self.original_shape_for_node_edit = None
        
    def activate(self):
        self.deactivate()

    def deactivate(self):
        self.canvas.selected_shapes.clear()
        self.is_multiselecting = False
        self.selection_rect = None
        self.action_start_position = None
        self.original_shapes_for_action.clear()
        self.dragging = False
        self.scaling = False
        self.node_editing_active = False
        self.selected_node_index = -1
        self.canvas.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().deactivate()
        
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.original_shapes_for_action.clear()
        self.dragging = False
        self.scaling = False
        if self.node_editing_active:
            self._handle_node_press(event)
            return
        on_corner = self._is_on_corner(event.pos())
        if on_corner and self.canvas.selected_shapes:
            if any(self.canvas._get_layer_for_shape(s) is not None and not self.canvas._get_layer_for_shape(s).is_locked for s in self.canvas.selected_shapes):
                self._handle_scale_start(event, on_corner)
        else:
            self._handle_select_press(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            self._update_cursor(event.pos())
            return
        if self.node_editing_active and self.selected_node_index != -1:
            self._handle_node_move(event)
            return
        if self.scaling:
            self._handle_scale_move(event)
            return
        if self.dragging:
            self._handle_drag_move(event)
            return
        if self.is_multiselecting:
            self.selection_rect.setBottomRight(event.pos())
            self.canvas.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.node_editing_active:
            self._handle_node_release(event)
            return
        if self.scaling:
            self._handle_scale_finish(event)
        elif self.dragging:
            self._handle_drag_finish(event)
        elif self.is_multiselecting:
            self._handle_multiselect_finish()
        self.action_start_position = None
        self.original_shapes_for_action.clear()
        self.dragging = False
        self.scaling = False
        self.is_multiselecting = False
        self.selection_rect = None
        self.canvas.update()

    def _handle_select_press(self, event):
        modifiers = QApplication.keyboardModifiers()
        is_shift_pressed = modifiers == Qt.KeyboardModifier.ShiftModifier
        shape_clicked, layer_of_shape = self.canvas._get_shape_at(event.pos())
        self.node_editing_active = False

        if shape_clicked:
            if layer_of_shape and not layer_of_shape.is_locked:
                self.action_start_position = event.pos() 
                if not is_shift_pressed and shape_clicked not in self.canvas.selected_shapes:
                    self.canvas.selected_shapes.clear()
                
                if is_shift_pressed and shape_clicked in self.canvas.selected_shapes:
                    self.canvas.selected_shapes.remove(shape_clicked)
                elif shape_clicked not in self.canvas.selected_shapes:
                    self.canvas.selected_shapes.append(shape_clicked)
                
                self.dragging = True
                self.original_shapes_for_action = [s.clone() for s in self.canvas.selected_shapes]
        else:
            if not is_shift_pressed:
                self.canvas.selected_shapes.clear()
            self.is_multiselecting = True
            self.selection_rect = QRect(event.pos(), event.pos())
        self.canvas.update()

    def _handle_drag_move(self, event):
        delta = event.pos() - self.action_start_position
        for i, original_shape in enumerate(self.original_shapes_for_action):
            self.canvas.selected_shapes[i].__dict__ = original_shape.clone().__dict__
            self.canvas.selected_shapes[i].move(delta.x(), delta.y())
        self.canvas.update()

    def _handle_drag_finish(self, event):
        total_delta = event.pos() - self.action_start_position
        for i, original_shape in enumerate(self.original_shapes_for_action):
            self.canvas.selected_shapes[i].__dict__ = original_shape.__dict__
        if total_delta.x() != 0 or total_delta.y() != 0:
            command = MoveShapesCommand(self.canvas.selected_shapes, total_delta.x(), total_delta.y())
            self.canvas.execute_command(command)

    def _handle_scale_start(self, event, corner_name):
        self.dragging = False
        self.scaling = True
        self.scale_corner = corner_name
        self.action_start_position = event.pos()
        self.original_shapes_for_action = [s.clone() for s in self.canvas.selected_shapes]
        total_bbox = self.canvas._get_selection_bbox()
        corners = self._get_corner_rects(total_bbox.adjusted(-5, -5, 5, 5))
        if corner_name == 'topLeft': self.scale_center = corners['bottomRight'].center()
        elif corner_name == 'topRight': self.scale_center = corners['bottomLeft'].center()
        elif corner_name == 'bottomLeft': self.scale_center = corners['topRight'].center()
        elif corner_name == 'bottomRight': self.scale_center = corners['topLeft'].center()

    def _handle_scale_move(self, event):
        dist_start_vec = self.action_start_position - self.scale_center
        dist_end_vec = event.pos() - self.scale_center
        dist_start_len = math.sqrt(dist_start_vec.x()**2 + dist_start_vec.y()**2)
        dist_end_len = math.sqrt(dist_end_vec.x()**2 + dist_end_vec.y()**2)
        if dist_start_len == 0:
            return
        factor = dist_end_len / dist_start_len
        for i, original_shape in enumerate(self.original_shapes_for_action):
            self.canvas.selected_shapes[i].__dict__ = original_shape.clone().__dict__
            self.canvas.selected_shapes[i].scale(factor, self.scale_center)
        self.canvas.update()

    def _handle_scale_finish(self, event):
        dist_start_vec = self.action_start_position - self.scale_center
        dist_end_vec = event.pos() - self.scale_center
        dist_start_len = math.sqrt(dist_start_vec.x()**2 + dist_start_vec.y()**2)
        dist_end_len = math.sqrt(dist_end_vec.x()**2 + dist_end_vec.y()**2)
        final_factor = dist_end_len / dist_start_len if dist_start_len != 0 else 1.0
        for i, original_shape in enumerate(self.original_shapes_for_action):
            self.canvas.selected_shapes[i].__dict__ = original_shape.__dict__
        if abs(final_factor - 1.0) > 0.001:
            command = ScaleCommand(self.canvas.selected_shapes, final_factor, self.scale_center)
            self.canvas.execute_command(command)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            shape_clicked, layer_of_shape = self.canvas._get_shape_at(event.pos())
            if shape_clicked and layer_of_shape and not layer_of_shape.is_locked:
                if not isinstance(shape_clicked, Text) and hasattr(shape_clicked, 'get_nodes') and len(self.canvas.selected_shapes) == 1 and self.canvas.selected_shapes[0] is shape_clicked:
                    self.node_editing_active = not self.node_editing_active
                    self.selected_node_index = -1
                    self.canvas.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Backspace and self.canvas.selected_shapes:
            self.canvas.delete_selected()

    def paint(self, painter):
        if self.is_multiselecting and self.selection_rect:
            pen = QPen(QColor(0, 150, 255), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(0, 150, 255, 30))
            painter.drawRect(self.selection_rect)
        if self.canvas.selected_shapes:
            if self.node_editing_active:
                shape = self.canvas.selected_shapes[0]
                painter.setBrush(QColor("white"))
                painter.setPen(QColor("black"))
                for i, node in enumerate(shape.get_nodes()):
                    node_rect = QRect(node.x() - 4, node.y() - 4, 8, 8)
                    if i == self.selected_node_index:
                        painter.setBrush(QColor("#0078d7"))
                    else:
                        painter.setBrush(QColor("white"))
                    painter.drawRect(node_rect)
            else:
                total_bbox = self.canvas._get_selection_bbox()
                if not total_bbox.isEmpty():
                    pen = QPen(QColor(0, 150, 255), 2, Qt.PenStyle.DashLine)
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(total_bbox.adjusted(-5, -5, 5, 5))
                    painter.setBrush(QColor("white"))
                    painter.setPen(QColor("black"))
                    for corner in self._get_corner_rects(total_bbox.adjusted(-5, -5, 5, 5)).values():
                        painter.drawRect(corner)

    def _handle_multiselect_finish(self):
        selection_box = self.selection_rect.normalized()
        modifiers = QApplication.keyboardModifiers()
        if not (modifiers == Qt.KeyboardModifier.ShiftModifier):
            self.canvas.selected_shapes.clear()
        for layer in self.canvas.layers:
            if not layer.is_visible or layer.is_locked:
                continue
            for shape in layer.shapes:
                if selection_box.intersects(shape.get_bounding_box()) and shape not in self.canvas.selected_shapes:
                    self.canvas.selected_shapes.append(shape)

    def _handle_node_press(self, event):
        if len(self.canvas.selected_shapes) == 1:
            shape = self.canvas.selected_shapes[0]
            self.selected_node_index = -1
            for i, node in enumerate(shape.get_nodes()):
                if QRect(node.x() - 5, node.y() - 5, 10, 10).contains(event.pos()):
                    self.selected_node_index = i
                    self.action_start_position = event.pos()
                    self.original_shape_for_node_edit = shape.clone()
                    break
            self.canvas.update()

    def _handle_node_move(self, event):
        if self.selected_node_index != -1 and (event.buttons() & Qt.MouseButton.LeftButton):
            shape = self.canvas.selected_shapes[0]
            shape.set_node_at(self.selected_node_index, event.pos())
            self.canvas.update()

    def _handle_node_release(self, event):
        self.selected_node_index = -1
        self.action_start_position = None
        self.original_shape_for_node_edit = None
        self.canvas.update()

    def _get_corner_rects(self, main_rect):
        size = 10
        return {
            'topLeft': QRect(main_rect.left()-size//2, main_rect.top()-size//2, size, size),
            'topRight': QRect(main_rect.right()-size//2, main_rect.top()-size//2, size, size),
            'bottomLeft': QRect(main_rect.left()-size//2, main_rect.bottom()-size//2, size, size),
            'bottomRight': QRect(main_rect.right()-size//2, main_rect.bottom()-size//2, size, size)
        }

    def _is_on_corner(self, pos):
        if self.canvas.selected_shapes and not self.node_editing_active:
            total_bbox = self.canvas._get_selection_bbox()
            if not total_bbox.isEmpty():
                corners = self._get_corner_rects(total_bbox.adjusted(-5,-5,5,5))
                for corner_name, rect in corners.items():
                    if rect.contains(pos):
                        return corner_name
        return None

    def _update_cursor(self, pos):
        if self.scaling or self.dragging:
            return
        cursor_shape = Qt.CursorShape.ArrowCursor
        if self.node_editing_active and self.canvas.selected_shapes:
            shape = self.canvas.selected_shapes[0]
            on_node = False
            for node in shape.get_nodes():
                if QRect(node.x()-4, node.y()-4, 8, 8).contains(pos):
                    cursor_shape = Qt.CursorShape.PointingHandCursor
                    on_node = True
                    break
            if not on_node:
                cursor_shape = Qt.CursorShape.ArrowCursor
        else:
            corner = self._is_on_corner(pos)
            if corner:
                if any(self.canvas._get_layer_for_shape(s) is not None and not self.canvas._get_layer_for_shape(s).is_locked for s in self.canvas.selected_shapes):
                    if corner in ['topLeft', 'bottomRight']:
                        cursor_shape = Qt.CursorShape.SizeFDiagCursor
                    else:
                        cursor_shape = Qt.CursorShape.SizeBDiagCursor
                else:
                    cursor_shape = Qt.CursorShape.ForbiddenCursor
            else:
                cursor_shape = Qt.CursorShape.ArrowCursor
        self.canvas.setCursor(QCursor(cursor_shape))

class BaseDrawingTool(Tool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.drawing = False
        self.start_point = None
        self.end_point = None
    def mousePressEvent(self, event):
        current_layer = self.canvas.get_current_layer()
        if event.button() == Qt.MouseButton.LeftButton and current_layer and not current_layer.is_locked:
            self.drawing = True
            self.start_point = event.pos()
            self.end_point = event.pos()
    def mouseMoveEvent(self, event):
        if self.drawing:
            self.end_point = event.pos()
            self.canvas.update()
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            current_layer = self.canvas.get_current_layer()
            if current_layer:
                final_rect = QRect(self.start_point, self.end_point).normalized()
                if final_rect.width() < 2 and final_rect.height() < 2 and not isinstance(self, (LineTool, ArrowTool, CircleTool)):
                    self.canvas.update()
                    return
                new_shape = self.create_shape()
                if new_shape:
                    command = AddShapeCommand(current_layer, new_shape)
                    self.canvas.execute_command(command)
                else:
                    self.canvas.update()
    def create_shape(self):
        raise NotImplementedError
    def paint(self, painter):
        if self.drawing and self.start_point and self.end_point:
            pen = QPen(self.canvas.current_pen_color, self.canvas.current_width, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            if self.canvas.current_fill_color and self.canvas.current_fill_style != Qt.BrushStyle.NoBrush:
                painter.setBrush(QBrush(self.canvas.current_fill_color, self.canvas.current_fill_style))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            self.draw_preview(painter)
    def draw_preview(self, painter):
        raise NotImplementedError

class PointTool(Tool):
    def mousePressEvent(self, event):
        current_layer = self.canvas.get_current_layer()
        if event.button() == Qt.MouseButton.LeftButton and current_layer and not current_layer.is_locked:
            new_shape = Point(event.pos(), self.canvas.current_pen_color, self.canvas.current_width)
            command = AddShapeCommand(current_layer, new_shape)
            self.canvas.execute_command(command)

class LineTool(BaseDrawingTool):
    def create_shape(self):
        return Line(self.start_point, self.end_point, self.canvas.current_pen_color, self.canvas.current_width)
    def draw_preview(self, painter):
        painter.drawLine(self.start_point, self.end_point)

class ArrowTool(BaseDrawingTool):
    def create_shape(self):
        return Arrow(self.start_point, self.end_point, self.canvas.current_pen_color, self.canvas.current_width)
    def draw_preview(self, painter):
        self.canvas._draw_arrow(painter, self.start_point, self.end_point, self.canvas.current_pen_color, self.canvas.current_width)

class RectangleTool(BaseDrawingTool):
    def create_shape(self):
        rect = QRect(self.start_point, self.end_point).normalized()
        return Rectangle(rect.topLeft(), rect.bottomRight(), self.canvas.current_pen_color, self.canvas.current_width, self.canvas.current_fill_color, self.canvas.current_fill_style)
    def draw_preview(self, painter):
        painter.drawRect(QRect(self.start_point, self.end_point).normalized())

class SquareTool(BaseDrawingTool):
    def create_shape(self):
        rect = QRect(self.start_point, self.end_point).normalized()
        side = max(rect.width(), rect.height())
        return Square(rect.topLeft(), side, self.canvas.current_pen_color, self.canvas.current_width, self.canvas.current_fill_color, self.canvas.current_fill_style)
    def draw_preview(self, painter):
        rect = QRect(self.start_point, self.end_point).normalized()
        side = max(rect.width(), rect.height())
        painter.drawRect(QRect(rect.left(), rect.top(), side, side))

class CircleTool(BaseDrawingTool):
    def create_shape(self):
        radius = math.sqrt((self.end_point.x() - self.start_point.x())**2 + (self.end_point.y() - self.start_point.y())**2)
        return Circle(self.start_point, radius, self.canvas.current_pen_color, self.canvas.current_width, self.canvas.current_fill_color, self.canvas.current_fill_style)
    def draw_preview(self, painter):
        radius = math.sqrt((self.end_point.x() - self.start_point.x())**2 + (self.end_point.y() - self.start_point.y())**2)
        painter.drawEllipse(self.start_point, int(radius), int(radius))

class EllipseTool(BaseDrawingTool):
    def create_shape(self):
        rect = QRect(self.start_point, self.end_point).normalized()
        return Ellipse(rect.topLeft(), rect.bottomRight(), self.canvas.current_pen_color, self.canvas.current_width, self.canvas.current_fill_color, self.canvas.current_fill_style)
    def draw_preview(self, painter):
        painter.drawEllipse(QRect(self.start_point, self.end_point).normalized())

class RoundedRectangleTool(BaseDrawingTool):
    def create_shape(self):
        rect = QRect(self.start_point, self.end_point).normalized()
        return RoundedRectangle(rect.topLeft(), rect.bottomRight(), self.canvas.current_pen_color, self.canvas.current_width, self.canvas.current_fill_color, self.canvas.current_fill_style)
    def draw_preview(self, painter):
        painter.drawRoundedRect(QRect(self.start_point, self.end_point).normalized(), 20, 20)

class TextTool(BaseDrawingTool):
    def create_shape(self):
        text_rect = QRect(self.start_point, self.end_point).normalized()
        if text_rect.width() > 10 and text_rect.height() > 10:
            font = QFont(self.canvas.current_font)
            new_shape = Text(text_rect, "", font, self.canvas.current_pen_color, has_border=True, border_color=self.canvas.current_pen_color)
            self.canvas.start_text_editing_on_creation(new_shape)
            return new_shape
        return None
    def draw_preview(self, painter):
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRect(self.start_point, self.end_point).normalized())

class BaseMultiStepTool(Tool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.points = []
        self.cursor_pos = None
    def activate(self):
        self.points = []
        self.cursor_pos = None
    def deactivate(self):
        self.points = []
        self.cursor_pos = None
        super().deactivate()
    def mousePressEvent(self, event):
        current_layer = self.canvas.get_current_layer()
        if event.button() == Qt.MouseButton.LeftButton and current_layer and not current_layer.is_locked:
            self.points.append(event.pos())
            self.cursor_pos = event.pos()
            self.handle_step()
            self.canvas.update()
    def mouseMoveEvent(self, event):
        self.cursor_pos = event.pos()
        self.canvas.update()
    def handle_step(self):
        pass

class PolylineTool(BaseMultiStepTool):
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.finish_drawing()
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.finish_drawing()
    def finish_drawing(self):
        if len(self.points) >= 2:
            current_layer = self.canvas.get_current_layer()
            if current_layer:
                shape = Polyline(self.points, self.canvas.current_pen_color, self.canvas.current_width)
                command = AddShapeCommand(current_layer, shape)
                self.canvas.execute_command(command)
        self.points = []
    def paint(self, painter):
        if not self.points:
            return
        pen = QPen(self.canvas.current_pen_color, self.canvas.current_width, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        points_to_draw = self.points + ([self.cursor_pos] if self.cursor_pos else [])
        painter.drawPolyline(QPolygon(points_to_draw))

class PolygonTool(BaseMultiStepTool):
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.finish_drawing()
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.finish_drawing()
    def finish_drawing(self):
        if len(self.points) >= 3:
            current_layer = self.canvas.get_current_layer()
            if current_layer:
                shape = Polygon(self.points, self.canvas.current_pen_color, self.canvas.current_width, self.canvas.current_fill_color, self.canvas.current_fill_style)
                command = AddShapeCommand(current_layer, shape)
                self.canvas.execute_command(command)
        self.points = []
    def paint(self, painter):
        if not self.points:
            return
        pen = QPen(self.canvas.current_pen_color, self.canvas.current_width, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        points_to_draw = self.points + ([self.cursor_pos] if self.cursor_pos else [])
        painter.drawPolyline(QPolygon(points_to_draw))
        if len(self.points) >= 2 and self.cursor_pos:
            painter.drawLine(self.cursor_pos, self.points[0])

class ArcTool(BaseMultiStepTool):
    def handle_step(self):
        if len(self.points) == 3:
            current_layer = self.canvas.get_current_layer()
            if current_layer:
                shape = Arc(*self.points, self.canvas.current_pen_color, self.canvas.current_width)
                command = AddShapeCommand(current_layer, shape)
                self.canvas.execute_command(command)
            self.points = []
    def paint(self, painter):
        if not self.points:
            return
        pen = QPen(self.canvas.current_pen_color, self.canvas.current_width, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if len(self.points) == 1:
            painter.drawLine(self.points[0], self.cursor_pos)
        elif len(self.points) == 2:
            path = QPainterPath()
            path.moveTo(QPointF(self.points[0]))
            path.quadTo(QPointF(self.cursor_pos), QPointF(self.points[1]))
            painter.drawPath(path)

class FreehandTool(Tool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.drawing = False
        self.points = []
    def mousePressEvent(self, event):
        current_layer = self.canvas.get_current_layer()
        if event.button() == Qt.MouseButton.LeftButton and current_layer and not current_layer.is_locked:
            self.drawing = True
            self.points.clear()
            self.points.append(event.pos())
    def mouseMoveEvent(self, event):
        if self.drawing:
            self.points.append(event.pos())
            self.canvas.update()
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            current_layer = self.canvas.get_current_layer()
            if current_layer and len(self.points) >= 2:
                shape = Polyline(self.points.copy(), self.canvas.current_pen_color, self.canvas.current_width)
                command = AddShapeCommand(current_layer, shape)
                self.canvas.execute_command(command)
            self.points.clear()
    def paint(self, painter):
        if self.drawing and len(self.points) >= 2:
            pen = QPen(self.canvas.current_pen_color, self.canvas.current_width, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawPolyline(QPolygon(self.points))

class EraserTool(Tool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.erasing = False
        self.cursor_pos = None
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.erasing = True
            self.cursor_pos = event.pos()
            self._erase_at(self.cursor_pos)
            self.canvas.update()
    def mouseMoveEvent(self, event):
        self.cursor_pos = event.pos()
        if self.erasing:
            self._erase_at(self.cursor_pos)
        self.canvas.update()
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.erasing:
            self.erasing = False
            self.cursor_pos = None
            self.canvas.update()
    def paint(self, painter):
        if self.cursor_pos:
            painter.setPen(QPen(Qt.GlobalColor.black, 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            eraser_size = self.canvas.current_width * 5
            painter.drawEllipse(self.cursor_pos, eraser_size, eraser_size)
    def _erase_at(self, pos):
        eraser_size = self.canvas.current_width * 5
        eraser_rect = QRect(pos.x() - eraser_size, pos.y() - eraser_size, eraser_size * 2, eraser_size * 2)
        shapes_to_delete_map = {}
        for layer in self.canvas.layers:
            if layer.is_locked or not layer.is_visible:
                continue
            shapes_in_layer_to_delete = [s for s in layer.shapes if eraser_rect.intersects(s.get_bounding_box())]
            if shapes_in_layer_to_delete:
                shapes_to_delete_map[layer] = shapes_in_layer_to_delete
        if shapes_to_delete_map:
            for layer, shapes in shapes_to_delete_map.items():
                command = RemoveShapesCommand(layer, shapes)
                self.canvas.execute_command(command)

class PaintBucketTool(Tool):
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        shape_clicked, layer_of_shape = self.canvas._get_shape_at(event.pos())
        if (shape_clicked and layer_of_shape and 
            not layer_of_shape.is_locked and hasattr(shape_clicked, 'fill_color')):
            
            properties_to_change = {
                'fill_style': self.canvas.current_fill_style,
                'fill_color': self.canvas.current_fill_color
            }
            command = ChangePropertiesCommand([shape_clicked], properties_to_change)
            self.canvas.execute_command(command)

# --- END OF FILE tools.py ---