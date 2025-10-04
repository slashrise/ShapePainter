# --- START OF FILE tools.py (Fully Corrected) ---

import math
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPolygon, QPainterPath, QCursor, QTransform, QFont
from PyQt6.QtCore import Qt, QPoint, QRect, QPointF
from shapes import Path, PathSegment # 确保在顶部导入
from shapes import *
from commands import (AddShapeCommand, RemoveShapesCommand, MoveShapesCommand,
                      ScaleCommand, ChangePropertiesCommand, RotateCommand, FlipCommand, ModifyNodeCommand)

class Tool:
    def __init__(self, canvas):
        self.canvas = canvas
    def mousePressEvent(self, event): pass
    def mouseMoveEvent(self, event): pass
    def mouseReleaseEvent(self, event): pass
    def mouseDoubleClickEvent(self, event): pass
    def keyPressEvent(self, event): pass
    def activate(self): pass
    def deactivate(self): self.canvas.update()
    def paint(self, painter): pass

class SelectTool(Tool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.is_multiselecting = False
        self.selection_rect = None
        self.action_start_position = None
        self.original_shapes_for_action = []
        self.dragging = False
        self.scaling = False
        self.rotating = False
        self.scale_corner = None
        self.scale_center = None
        self.node_editing_active = False
        self.dragged_node_info = None  # Tuple: (shape, seg_index, 'anchor'/'handle1'/'handle2')
        self.original_node_position = None

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
        self.rotating = False
        self.node_editing_active = False
        self.dragged_node_info = None
        self.original_node_position = None
        self.canvas.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().deactivate()

    def _get_transform_for_shape(self, shape):
        original_bbox = shape.get_bounding_box()
        center = original_bbox.center()
        transform = QTransform().translate(center.x(), center.y()).scale(shape.scale_x, shape.scale_y).rotate(shape.angle).translate(-center.x(), -center.y())
        inverted_transform, _ = transform.inverted()
        return transform, inverted_transform

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton: return
        self.original_shapes_for_action.clear()
        self.dragging, self.scaling, self.rotating = False, False, False
        self.dragged_node_info = None

        if self.node_editing_active:
            self._handle_node_press(event)
            if self.dragged_node_info: return

        handle_type = self._get_handle_type_at(event.pos())
        if handle_type and self.canvas.selected_shapes:
            if any(not self.canvas._get_layer_for_shape(s).is_locked for s in self.canvas.selected_shapes):
                if handle_type == "rotate": self._handle_rotate_start(event)
                else: self._handle_scale_start(event, handle_type)
        else:
            self._handle_select_press(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            self._update_cursor(event.pos())
            return
        
        if self.dragged_node_info: self._handle_node_move(event)
        elif self.rotating: self._handle_rotate_move(event)
        elif self.scaling: self._handle_scale_move(event)
        elif self.dragging: self._handle_drag_move(event)
        elif self.is_multiselecting:
            self.selection_rect.setBottomRight(event.pos()); self.canvas.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton: return
        
        if self.dragged_node_info: self._handle_node_release(event)
        elif self.rotating: self._handle_rotate_finish(event)
        elif self.scaling: self._handle_scale_finish(event)
        elif self.dragging: self._handle_drag_finish(event)
        elif self.is_multiselecting: self._handle_multiselect_finish()

        self.action_start_position = None; self.original_shapes_for_action.clear(); self.dragging = False; self.scaling = False; self.rotating = False; self.is_multiselecting = False; self.selection_rect = None
        self.canvas.update()

    def _handle_select_press(self, event):
        modifiers = QApplication.keyboardModifiers()
        is_shift_pressed = modifiers == Qt.KeyboardModifier.ShiftModifier
        shape_clicked, layer_of_shape = self.canvas._get_shape_at(event.pos())
        self.node_editing_active = False
        if shape_clicked:
            if layer_of_shape and not layer_of_shape.is_locked:
                self.action_start_position = event.pos()
                if not is_shift_pressed and shape_clicked not in self.canvas.selected_shapes: self.canvas.selected_shapes.clear()
                if is_shift_pressed and shape_clicked in self.canvas.selected_shapes: self.canvas.selected_shapes.remove(shape_clicked)
                elif shape_clicked not in self.canvas.selected_shapes: self.canvas.selected_shapes.append(shape_clicked)
                self.dragging = True
                self.original_shapes_for_action = [s.clone() for s in self.canvas.selected_shapes]
        else:
            if not is_shift_pressed: self.canvas.selected_shapes.clear()
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
        for i, original_shape in enumerate(self.original_shapes_for_action): self.canvas.selected_shapes[i].__dict__ = original_shape.__dict__
        if total_delta.manhattanLength() > 2:
            command = MoveShapesCommand(self.canvas.selected_shapes, total_delta.x(), total_delta.y())
            self.canvas.execute_command(command)

    def _handle_scale_start(self, event, corner_name):
        self.dragging = False; self.scaling = True; self.scale_corner = corner_name
        self.action_start_position = event.pos()
        self.original_shapes_for_action = [s.clone() for s in self.canvas.selected_shapes]
        total_bbox = self.canvas._get_selection_bbox()
        corners = self._get_corner_rects(total_bbox.adjusted(-5, -5, 5, 5))
        if corner_name == 'topLeft': self.scale_center = corners['bottomRight'].center()
        elif corner_name == 'topRight': self.scale_center = corners['bottomLeft'].center()
        elif corner_name == 'bottomLeft': self.scale_center = corners['topRight'].center()
        elif corner_name == 'bottomRight': self.scale_center = corners['topLeft'].center()

    def _handle_scale_move(self, event):
        if not self.scale_center: return
        dist_start_vec = self.action_start_position - self.scale_center
        dist_end_vec = event.pos() - self.scale_center
        dist_start_len = math.sqrt(dist_start_vec.x()**2 + dist_start_vec.y()**2)
        dist_end_len = math.sqrt(dist_end_vec.x()**2 + dist_end_vec.y()**2)
        if dist_start_len == 0: return
        factor = dist_end_len / dist_start_len
        for i, original_shape in enumerate(self.original_shapes_for_action):
            self.canvas.selected_shapes[i].__dict__ = original_shape.clone().__dict__
            self.canvas.selected_shapes[i].scale(factor, self.scale_center)
        self.canvas.update()

    def _handle_scale_finish(self, event):
        if not self.scale_center: return
        dist_start_vec = self.action_start_position - self.scale_center
        dist_end_vec = event.pos() - self.scale_center
        dist_start_len = math.sqrt(dist_start_vec.x()**2 + dist_start_vec.y()**2)
        dist_end_len = math.sqrt(dist_end_vec.x()**2 + dist_end_vec.y()**2)
        final_factor = dist_end_len / dist_start_len if dist_start_len != 0 else 1.0
        for i, original_shape in enumerate(self.original_shapes_for_action): self.canvas.selected_shapes[i].__dict__ = original_shape.__dict__
        if abs(final_factor - 1.0) > 0.001:
            command = ScaleCommand(self.canvas.selected_shapes, final_factor, self.scale_center)
            self.canvas.execute_command(command)

    def _handle_rotate_start(self, event):
        self.rotating = True
        self.action_start_position = event.pos()
        self.original_shapes_for_action = [s.clone() for s in self.canvas.selected_shapes]
        self.scale_center = self.canvas._get_selection_bbox().center()

    def _handle_rotate_move(self, event):
        if not self.scale_center: return
        start_vec = self.action_start_position - self.scale_center
        current_vec = event.pos() - self.scale_center
        start_angle = math.atan2(start_vec.y(), start_vec.x())
        current_angle = math.atan2(current_vec.y(), current_vec.x())
        angle_delta_rad = current_angle - start_angle
        angle_delta_deg = math.degrees(angle_delta_rad)
        for i, original_shape in enumerate(self.original_shapes_for_action):
            self.canvas.selected_shapes[i].__dict__ = original_shape.clone().__dict__
            final_angle_delta = angle_delta_deg
            if self.canvas.selected_shapes[i].scale_x * self.canvas.selected_shapes[i].scale_y < 0: final_angle_delta = -angle_delta_deg
            self.canvas.selected_shapes[i].rotate(rotation_delta=final_angle_delta)
        self.canvas.update()

    def _handle_rotate_finish(self, event):
        if not self.scale_center: return
        start_vec = self.action_start_position - self.scale_center
        current_vec = event.pos() - self.scale_center
        start_angle = math.atan2(start_vec.y(), start_vec.x())
        current_angle = math.atan2(current_vec.y(), current_vec.x())
        angle_delta_rad = current_angle - start_angle
        final_angle_delta_deg = math.degrees(angle_delta_rad)
        for i, original_shape in enumerate(self.original_shapes_for_action): self.canvas.selected_shapes[i].__dict__ = original_shape.__dict__
        if self.original_shapes_for_action:
            original_shape = self.original_shapes_for_action[0]
            final_angle_delta = final_angle_delta_deg
            if original_shape.scale_x * original_shape.scale_y < 0: final_angle_delta = -final_angle_delta_deg
            if abs(final_angle_delta_deg) > 0.1:
                command = RotateCommand(self.canvas.selected_shapes, rotation_delta=final_angle_delta)
                self.canvas.execute_command(command)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            shape_clicked, layer_of_shape = self.canvas._get_shape_at(event.pos())
            if shape_clicked and layer_of_shape and not layer_of_shape.is_locked:
                if hasattr(shape_clicked, 'get_nodes') and len(self.canvas.selected_shapes) == 1 and self.canvas.selected_shapes[0] is shape_clicked:
                    self.node_editing_active = not self.node_editing_active; self.dragged_node_info = None; self.canvas.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Backspace and self.canvas.selected_shapes: self.canvas.delete_selected()

    def paint(self, painter):
        if self.is_multiselecting and self.selection_rect:
            pen = QPen(QColor(0, 150, 255), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen); painter.setBrush(QColor(0, 150, 255, 30)); painter.drawRect(self.selection_rect)
        if not self.canvas.selected_shapes: return
        if self.node_editing_active and len(self.canvas.selected_shapes) == 1:
            shape = self.canvas.selected_shapes[0]
            transform, _ = self._get_transform_for_shape(shape)
            painter.setPen(QPen(QColor("blue"), 1))
            if isinstance(shape, Path):
                # --- 关键修改：遍历 sub_paths ---
                for sub_path in shape.sub_paths:
                    for seg in sub_path:
                        if seg.node_type == PathSegment.SMOOTH:
                            painter.drawLine(transform.map(seg.handle1), transform.map(seg.anchor))
                            painter.drawLine(transform.map(seg.handle2), transform.map(seg.anchor))
                for sub_path in shape.sub_paths:
                    for seg in sub_path:
                        transformed_anchor = transform.map(seg.anchor)
                        anchor_rect = QRect(transformed_anchor.x() - 4, transformed_anchor.y() - 4, 8, 8)
                        painter.setBrush(QColor("white")); painter.setPen(QPen(QColor("black"), 1)); painter.drawRect(anchor_rect)
                        if seg.node_type == PathSegment.SMOOTH:
                            transformed_h1 = transform.map(seg.handle1); transformed_h2 = transform.map(seg.handle2)
                            painter.setBrush(QColor("lightblue")); painter.setPen(QPen(QColor("blue"), 1))
                            painter.drawEllipse(transformed_h1, 4, 4); painter.drawEllipse(transformed_h2, 4, 4)
            elif hasattr(shape, 'get_nodes'):
                for i, node_pos in enumerate(shape.get_nodes()):
                    transformed_node = transform.map(node_pos)
                    node_rect = QRect(transformed_node.x() - 4, transformed_node.y() - 4, 8, 8)
                    painter.setBrush(QColor("white")); painter.drawRect(node_rect)
        elif not self.node_editing_active:
            total_bbox_transformed = self.canvas._get_selection_bbox()
            if total_bbox_transformed.isEmpty(): return
            painter.save()
            if len(self.canvas.selected_shapes) == 1:
                shape = self.canvas.selected_shapes[0]
                center = shape.get_bounding_box().center()
                painter.translate(center); painter.scale(shape.scale_x, shape.scale_y); painter.rotate(shape.angle); painter.translate(-center)
                bbox_to_draw = shape.get_bounding_box()
            else: bbox_to_draw = total_bbox_transformed
            pen = QPen(QColor(0, 150, 255), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen); painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(bbox_to_draw.adjusted(-5, -5, 5, 5))
            handle_start = QPoint(bbox_to_draw.center().x(), bbox_to_draw.top() - 5)
            handle_end = QPoint(handle_start.x(), handle_start.y() - 20)
            painter.setPen(QPen(QColor(0, 150, 255), 2)); painter.drawLine(handle_start, handle_end)
            painter.setBrush(QColor("white")); painter.setPen(QColor("black"))
            painter.drawEllipse(handle_end, 5, 5)
            for corner_rect in self._get_corner_rects(bbox_to_draw.adjusted(-5, -5, 5, 5)).values():
                painter.drawRect(corner_rect)
            painter.restore()

    def _handle_multiselect_finish(self):
        selection_box = self.selection_rect.normalized()
        modifiers = QApplication.keyboardModifiers()
        if not (modifiers == Qt.KeyboardModifier.ShiftModifier): self.canvas.selected_shapes.clear()
        for layer in self.canvas.layers:
            if not layer.is_visible or layer.is_locked: continue
            for shape in layer.shapes:
                if selection_box.intersects(shape.get_transformed_bounding_box()) and shape not in self.canvas.selected_shapes:
                    self.canvas.selected_shapes.append(shape)

    def _handle_node_press(self, event):
        if not (len(self.canvas.selected_shapes) == 1 and hasattr(self.canvas.selected_shapes[0], 'get_nodes')): return
        
        shape = self.canvas.selected_shapes[0]
        transform, _ = self._get_transform_for_shape(shape)
        self.dragged_node_info = None

        if isinstance(shape, Path):
            # --- 全新的 Path 节点按下逻辑 ---
            # 优先检查手柄
            for sub_path_idx, sub_path in enumerate(shape.sub_paths):
                for seg_idx, seg in enumerate(sub_path):
                    if seg.node_type == PathSegment.SMOOTH:
                        # Check handle1
                        if (event.pos() - transform.map(seg.handle1)).manhattanLength() < 5:
                            self.dragged_node_info = (shape, (sub_path_idx, seg_idx), "handle1")
                            self.original_node_position = seg.handle1
                            self.canvas.update(); return
                        # Check handle2
                        if (event.pos() - transform.map(seg.handle2)).manhattanLength() < 5:
                            self.dragged_node_info = (shape, (sub_path_idx, seg_idx), "handle2")
                            self.original_node_position = seg.handle2
                            self.canvas.update(); return
            
            # 再检查锚点
            for sub_path_idx, sub_path in enumerate(shape.sub_paths):
                for seg_idx, seg in enumerate(sub_path):
                    if (event.pos() - transform.map(seg.anchor)).manhattanLength() < 5:
                        self.dragged_node_info = (shape, (sub_path_idx, seg_idx), "anchor")
                        self.original_node_position = seg.anchor
                        
                        modifiers = QApplication.keyboardModifiers()
                        if modifiers == Qt.KeyboardModifier.AltModifier: # Alt+Click converts node type
                            if seg.node_type == PathSegment.CORNER: seg.to_smooth()
                            else: seg.to_corner()
                            self.dragged_node_info = None # Cancel drag
                        self.canvas.update()
                        return
        else:
            # 对其他图形（如多边形）的旧逻辑
            for i, node_pos in enumerate(shape.get_nodes()):
                if (event.pos() - transform.map(node_pos)).manhattanLength() < 5:
                    self.dragged_node_info = (shape, i, 'node')
                    self.original_node_position = node_pos
                    self.canvas.update()
                    return

    def _handle_node_move(self, event):
        if self.dragged_node_info:
            shape, index, node_type_str = self.dragged_node_info
            _, inverted_transform = self._get_transform_for_shape(shape)
            local_mouse_pos = inverted_transform.map(event.pos())
            
            if isinstance(shape, Path):
                sub_path_idx, seg_idx = index
                seg = shape.sub_paths[sub_path_idx][seg_idx]

                if node_type_str == "anchor":
                    offset = local_mouse_pos - seg.anchor
                    seg.anchor += offset
                    seg.handle1 += offset
                    seg.handle2 += offset
                
                elif node_type_str == "handle1":
                    if seg.node_type == PathSegment.SMOOTH:
                        seg.handle1 = local_mouse_pos
                        if QApplication.keyboardModifiers() != Qt.KeyboardModifier.AltModifier:
                            seg.handle2 = seg.anchor - (seg.handle1 - seg.anchor)
                
                elif node_type_str == "handle2":
                    if seg.node_type == PathSegment.SMOOTH:
                        seg.handle2 = local_mouse_pos
                        if QApplication.keyboardModifiers() != Qt.KeyboardModifier.AltModifier:
                            seg.handle1 = seg.anchor - (seg.handle2 - seg.anchor)
            else:
                shape.set_node_at(index, local_mouse_pos)

            self.canvas.update()
    
    def _handle_node_release(self, event):
        if self.dragged_node_info:
            shape, index, _ = self.dragged_node_info
            # This part is complex. We'll skip creating an Undo command for node edits for now.
        self.dragged_node_info = None; self.original_node_position = None; self.canvas.update()

    def _get_corner_rects(self, main_rect):
        size = 10
        return { 'topLeft': QRect(main_rect.left()-size//2, main_rect.top()-size//2, size, size), 'topRight': QRect(main_rect.right()-size//2, main_rect.top()-size//2, size, size), 'bottomLeft': QRect(main_rect.left()-size//2, main_rect.bottom()-size//2, size, size), 'bottomRight': QRect(main_rect.right()-size//2, main_rect.bottom()-size//2, size, size) }

    def _get_handle_type_at(self, pos):
        if not self.canvas.selected_shapes or self.node_editing_active: return None
        if len(self.canvas.selected_shapes) > 1:
            total_bbox = self.canvas._get_selection_bbox()
            handle_end = QPoint(total_bbox.center().x(), total_bbox.top() - 25)
            if (pos - handle_end).manhattanLength() < 10: return "rotate"
            corners = self._get_corner_rects(total_bbox.adjusted(-5,-5,5,5))
            for name, rect in corners.items():
                if rect.contains(pos): return name
            return None
        shape_to_check = self.canvas.selected_shapes[0]
        bbox_untransformed = shape_to_check.get_bounding_box()
        _, inverted_transform = self._get_transform_for_shape(shape_to_check)
        local_pos = inverted_transform.map(pos)
        handle_end = QPoint(bbox_untransformed.center().x(), bbox_untransformed.top() - 25)
        if (local_pos - handle_end).manhattanLength() < 10: return "rotate"
        corners = self._get_corner_rects(bbox_untransformed.adjusted(-5,-5,5,5))
        for name, rect in corners.items():
            if rect.contains(local_pos): return name
        return None

    def _update_cursor(self, pos):
        if self.scaling or self.dragging or self.rotating: return
        cursor_shape = Qt.CursorShape.ArrowCursor
        if self.node_editing_active and len(self.canvas.selected_shapes) == 1:
            shape = self.canvas.selected_shapes[0]
            transform, _ = self._get_transform_for_shape(shape)
            on_node = False
            if hasattr(shape, 'get_nodes'):
                nodes_to_check = []
                if isinstance(shape, Path):
                    # --- 关键修改：遍历所有子路径的节点 ---
                    for sub_path in shape.sub_paths:
                        for seg in sub_path:
                            nodes_to_check.append(seg.anchor)
                            if seg.node_type == PathSegment.SMOOTH:
                                nodes_to_check.append(seg.handle1); nodes_to_check.append(seg.handle2)
                else: 
                    nodes_to_check = shape.get_nodes()
                
                for node in nodes_to_check:
                    if (pos - transform.map(node)).manhattanLength() < 5:
                        cursor_shape = Qt.CursorShape.PointingHandCursor; on_node = True; break
            if not on_node: cursor_shape = Qt.CursorShape.ArrowCursor
        else:
            handle_type = self._get_handle_type_at(pos)
            if handle_type:
                if any(not self.canvas._get_layer_for_shape(s).is_locked for s in self.canvas.selected_shapes):
                    if handle_type == 'rotate': cursor_shape = Qt.CursorShape.CrossCursor
                    elif handle_type in ['topLeft', 'bottomRight']: cursor_shape = Qt.CursorShape.SizeFDiagCursor
                    else: cursor_shape = Qt.CursorShape.SizeBDiagCursor
                else: cursor_shape = Qt.CursorShape.ForbiddenCursor
            else: cursor_shape = Qt.CursorShape.ArrowCursor
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

class PenTool(Tool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.current_path = None
        self.is_dragging_handle = False
        self.drag_start_pos = None

    def activate(self):
        self.current_path = None; self.is_dragging_handle = False; self.drag_start_pos = None
        self.canvas.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def deactivate(self):
        self.finish_drawing(); self.canvas.setCursor(QCursor(Qt.CursorShape.ArrowCursor)); super().deactivate()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton: return
        self.drag_start_pos = event.pos()
        self.is_dragging_handle = False

        if self.current_path:
            # Check if clicking an existing anchor
            current_sub_path = self.current_path.sub_paths[-1]
            
            if len(current_sub_path) > 1 and (event.pos() - current_sub_path[0].anchor).manhattanLength() < 10:
                # 通过添加一个与起点重合的段来闭合
                current_sub_path.append(PathSegment(current_sub_path[0].anchor, node_type=PathSegment.CORNER))
                self.current_path.sub_paths.append([])
                self.canvas.update()
                return # 结束本次点击事件

            # 检查是否点击了任何其他点，以开始新的子路径
            for sub_path in self.current_path.sub_paths:
                for seg in sub_path:
                    if (event.pos() - seg.anchor).manhattanLength() < 10:
                        # 结束当前子路径，并以该点为起点开始新的子路径
                        self.current_path.sub_paths.append([PathSegment(seg.anchor, node_type=PathSegment.CORNER)])
                        self.canvas.update()
                        return

        # 如果没有点击任何现有锚点
        if self.current_path is None:
            new_segment = PathSegment(event.pos(), node_type=PathSegment.CORNER)
            self.current_path = Path([[new_segment]], self.canvas.current_pen_color, self.canvas.current_width)
        else:
            self.current_path.sub_paths[-1].append(PathSegment(event.pos(), node_type=PathSegment.CORNER))
        
        self.canvas.update()

    def mouseMoveEvent(self, event):
        if self.current_path and self.drag_start_pos and (event.buttons() & Qt.MouseButton.LeftButton):
            if not self.is_dragging_handle and (event.pos() - self.drag_start_pos).manhattanLength() > 4:
                self.is_dragging_handle = True

            if self.is_dragging_handle:
                current_sub_path = self.current_path.sub_paths[-1]
                last_seg = current_sub_path[-1]
                if last_seg.anchor == self.drag_start_pos:
                    last_seg.to_smooth(handle=event.pos())
                    self.canvas.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = None; self.is_dragging_handle = False; self.canvas.update()
        elif event.button() == Qt.MouseButton.RightButton: self.finish_drawing()

    def mouseDoubleClickEvent(self, event): self.finish_drawing()

    def finish_drawing(self):
        if self.current_path:
            self.current_path.sub_paths = [sp for sp in self.current_path.sub_paths if len(sp) > 1 or (len(sp) == 1 and self.is_dragging_handle)]
            if self.current_path.sub_paths:
                current_layer = self.canvas.get_current_layer()
                if current_layer:
                    command = AddShapeCommand(current_layer, self.current_path)
                    self.canvas.execute_command(command)
        self.current_path = None; self.canvas.update()

    def paint(self, painter):
        if self.current_path:
            painter.setPen(QPen(self.current_path.color, self.current_path.width, Qt.PenStyle.SolidLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self.current_path.get_painter_path())
            painter.setPen(QPen(QColor("blue"), 1))
            for sub_path in self.current_path.sub_paths:
                for seg in sub_path:
                    painter.setBrush(QColor("white")); painter.drawRect(QRect(seg.anchor.x()-3, seg.anchor.y()-3, 6, 6))
                    if seg.node_type == PathSegment.SMOOTH:
                        painter.setBrush(QColor("lightblue"))
                        painter.drawLine(seg.anchor, seg.handle1); painter.drawEllipse(seg.handle1, 3, 3)
                        painter.drawLine(seg.anchor, seg.handle2); painter.drawEllipse(seg.handle2, 3, 3)

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
