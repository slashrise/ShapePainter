import math
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import (QPainter, QPen, QColor, QBrush, QPolygon, QPainterPath, QCursor, QTransform, QFont, QKeySequence, QPixmap)
from PyQt6.QtCore import Qt, QPoint, QRect, QPointF ,QRectF

from shapes import *
from commands import (AddShapeCommand, RemoveShapesCommand, MoveShapesCommand,
                      ScaleCommand, ChangePropertiesCommand, RotateCommand, FlipCommand, ModifyNodeCommand,
                      CompositeCommand, ModifyPathCommand)
from renderer import CanvasRenderer
import raster_algorithms


class Tool:
    def __init__(self, canvas): self.canvas = canvas
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
        self.dragged_node_info = None
        self.original_node_position = None
        self.continuing_path_info = None
        self.is_dragging_new_handle = False
        self.new_node_start_pos = None
        self.old_paths_snapshot = None
        self.original_sub_paths_for_drag = None

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
        self.continuing_path_info = None
        self.is_dragging_new_handle = False
        self.new_node_start_pos = None
        self.old_paths_snapshot = None
        self.original_sub_paths_for_drag = None
        self.canvas.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().deactivate()

    def _get_transform_for_shape(self, shape):
        original_bbox = shape.get_bounding_box() # QRectF
        center = original_bbox.center()
        transform = QTransform().translate(center.x(), center.y()).scale(shape.scale_x, shape.scale_y).rotate(
            shape.angle).translate(-center.x(), -center.y())
        inverted_transform, _ = transform.inverted()
        return transform, inverted_transform

    # 🟢 [新增] 辅助方法：根据角度获取合适的光标
    def _get_cursor_for_angle(self, angle_deg):
        # 将角度规范化到 0-180 (因为双向箭头是对称的)
        angle = angle_deg % 180
        if angle < 0: angle += 180
        
        # 0度: 水平, 45: 左下右上, 90: 垂直, 135: 左上右下
        if 22.5 <= angle < 67.5: return Qt.CursorShape.SizeBDiagCursor  # /
        elif 67.5 <= angle < 112.5: return Qt.CursorShape.SizeVerCursor # |
        elif 112.5 <= angle < 157.5: return Qt.CursorShape.SizeFDiagCursor # \
        else: return Qt.CursorShape.SizeHorCursor # -

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton: return
        self.action_start_position = event.pos()

        if self.continuing_path_info:
            shape, sp_idx = self.continuing_path_info
            snapped_pos = self.canvas.snap_point(event.pos())
            self.old_paths_snapshot = [ [s.clone() for s in sp] for sp in shape.sub_paths ]
            shape.sub_paths[sp_idx].append(PathSegment(QPointF(snapped_pos), node_type=PathSegment.CORNER))
            self.new_node_start_pos = snapped_pos
            if shape.layer: shape.layer.is_dirty = True
            self.canvas.update()
            return

        self.original_shapes_for_action.clear()
        self.dragging, self.scaling, self.rotating = False, False, False
        self.dragged_node_info = None

        if self.node_editing_active:
            if self._handle_node_press(event): return

        handle_type = self._get_handle_type_at(event.pos())
        if handle_type and self.canvas.selected_shapes:
            if any(s.layer and not s.layer.is_locked for s in self.canvas.selected_shapes):
                if handle_type == "rotate":
                    self._handle_rotate_start(event)
                else:
                    self._handle_scale_start(event, handle_type)
        else:
            self._handle_select_press(event)

    def mouseMoveEvent(self, event):
        if self.dragged_node_info:
            self._handle_node_move_with_reset(event); return
            
        if self.continuing_path_info and self.new_node_start_pos and (event.buttons() & Qt.MouseButton.LeftButton):
            shape, sp_idx = self.continuing_path_info
            snapped_pos = self.canvas.snap_point(event.pos())
            if not self.is_dragging_new_handle and (snapped_pos - self.new_node_start_pos).manhattanLength() > 4:
                self.is_dragging_new_handle = True
            if self.is_dragging_new_handle:
                sub_path = shape.sub_paths[sp_idx]
                if sub_path: sub_path[-1].to_smooth(handle=QPointF(snapped_pos))
            if shape.layer: shape.layer.is_dirty = True
            self.canvas.update(); return

        if self.continuing_path_info: self.canvas.update(); return

        if not (event.buttons() & Qt.MouseButton.LeftButton):
            self._update_cursor(event.pos()); return

        if self.rotating: self._handle_rotate_move(event)
        elif self.scaling: self._handle_scale_move(event)
        elif self.dragging: self._handle_drag_move(event)
        elif self.is_multiselecting:
            self.selection_rect = QRect(self.action_start_position, event.pos()).normalized()
            self.canvas.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton: return

        if self.continuing_path_info and self.old_paths_snapshot:
            shape, _ = self.continuing_path_info
            new_paths = [ [s.clone() for s in sp] for sp in shape.sub_paths ]
            command = ModifyPathCommand(shape, self.old_paths_snapshot, new_paths)
            self.canvas.execute_command(command)
            self.is_dragging_new_handle = False
            self.new_node_start_pos = None
            self.old_paths_snapshot = None
            self.canvas.update(); return

        if self.dragged_node_info: self._handle_node_release(event)
        elif self.rotating: self._handle_rotate_finish(event)
        elif self.scaling: self._handle_scale_finish(event)
        elif self.dragging: self._handle_drag_finish(event)
        elif self.is_multiselecting: self._handle_multiselect_finish()

        self.action_start_position = None
        self.original_shapes_for_action.clear()
        self.dragging = False
        self.scaling = False
        self.rotating = False
        self.is_multiselecting = False
        self.selection_rect = None

    def _handle_select_press(self, event):
        self.continuing_path_info = None
        modifiers = QApplication.keyboardModifiers()
        is_shift_pressed = modifiers == Qt.KeyboardModifier.ShiftModifier
        shape_clicked, layer_of_shape = self.canvas._get_shape_at(event.pos()) # canvas 那边已修复 posF

        if self.node_editing_active:
            if not shape_clicked or (self.canvas.selected_shapes and shape_clicked is not self.canvas.selected_shapes[0]):
                self.node_editing_active = False

        if shape_clicked:
            if layer_of_shape and not layer_of_shape.is_locked:
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
        snapped_current_pos = self.canvas.snap_point(event.pos())
        if not self.action_start_position: return
        delta = snapped_current_pos - self.action_start_position
        
        affected_layers = set()
        for i, original_shape in enumerate(self.original_shapes_for_action):
            current_shape = self.canvas.selected_shapes[i]
            original_layer_ref = current_shape.layer
            
            current_shape.__dict__ = original_shape.clone().__dict__
            current_shape.move(delta.x(), delta.y())
            
            current_shape.layer = original_layer_ref
            if current_shape.layer: affected_layers.add(current_shape.layer)

        for layer in affected_layers: layer.is_dirty = True
        self.canvas.update()

    def _handle_drag_finish(self, event):
        if not self.action_start_position: return
        snapped_current_pos = self.canvas.snap_point(event.pos())
        total_delta = snapped_current_pos - self.action_start_position
        
        if total_delta.manhattanLength() > 2:
            for shape in self.canvas.selected_shapes:
                shape.move(-total_delta.x(), -total_delta.y())
            
            command = MoveShapesCommand(self.canvas.selected_shapes, total_delta.x(), total_delta.y())
            self.canvas.execute_command(command)
        else:
            self.canvas.update()

    def _handle_multiselect_finish(self):
        if not self.selection_rect: return
        # selection_rect 是整数 QRect，但 get_transformed_bounding_box 是 QRectF
        # intersects 支持混合类型
        selection_box = self.selection_rect.normalized()
        modifiers = QApplication.keyboardModifiers()
        if not (modifiers == Qt.KeyboardModifier.ShiftModifier): 
            self.canvas.selected_shapes.clear()
        for layer in self.canvas.layers:
            if not layer.is_visible or layer.is_locked: continue
            for shape in layer.shapes:
                if selection_box.intersects(shape.get_transformed_bounding_box().toRect()) and shape not in self.canvas.selected_shapes:
                    self.canvas.selected_shapes.append(shape)
        self.canvas.update()

    # 🟢 [核心重写] 解决漂移问题
    def _handle_scale_start(self, event, corner_name):
        self.dragging = False; self.scaling = True; self.scale_corner = corner_name
        self.action_start_position = event.pos()
        self.original_shapes_for_action = [s.clone() for s in self.canvas.selected_shapes]
        
        # 1. 如果选中了多个图形，不得不使用 AABB (Axis-Aligned Bounding Box)
        # 这时只能退回到旧的逻辑，会有微小漂移，但这是多选变换的数学代价
        if len(self.canvas.selected_shapes) > 1:
            total_bbox = self.canvas._get_selection_bbox() # AABB
            corners = self._get_corner_rects(total_bbox.adjusted(-5, -5, 5, 5))
            if corner_name == 'topLeft': self.scale_center = QPointF(corners['bottomRight'].center())
            elif corner_name == 'topRight': self.scale_center = QPointF(corners['bottomLeft'].center())
            elif corner_name == 'bottomLeft': self.scale_center = QPointF(corners['topRight'].center())
            elif corner_name == 'bottomRight': self.scale_center = QPointF(corners['topLeft'].center())
            
        # 2. 🟢 如果只选中一个图形，使用 OBB (Oriented Bounding Box)
        # 通过图形自身的矩阵变换来寻找绝对精确的对角点
        else:
            shape = self.canvas.selected_shapes[0]
            local_bbox = shape.get_bounding_box() # 原始无变换的 Rect
            transform, _ = self._get_transform_for_shape(shape)
            
            # 找到局部坐标系下的对角点
            local_anchor = QPointF()
            if corner_name == 'topLeft': local_anchor = local_bbox.bottomRight()
            elif corner_name == 'topRight': local_anchor = local_bbox.bottomLeft()
            elif corner_name == 'bottomLeft': local_anchor = local_bbox.topRight()
            elif corner_name == 'bottomRight': local_anchor = local_bbox.topLeft()
            
            # 将局部对角点变换到世界坐标，这才是真正的固定点！
            self.scale_center = transform.map(local_anchor)
    def _handle_scale_move(self, event):
        if not self.scale_center: return
        snapped_pos = QPointF(self.canvas.snap_point(event.pos()))
        # 计算距离使用浮点数
        dist_start_vec = QPointF(self.action_start_position) - self.scale_center
        dist_end_vec = snapped_pos - self.scale_center
        dist_start_len = math.sqrt(dist_start_vec.x() ** 2 + dist_start_vec.y() ** 2)
        dist_end_len = math.sqrt(dist_end_vec.x() ** 2 + dist_end_vec.y() ** 2)
        if dist_start_len == 0: return
        factor = dist_end_len / dist_start_len
        
        affected_layers = set()
        for i, original_shape in enumerate(self.original_shapes_for_action):
            current_shape = self.canvas.selected_shapes[i]
            original_layer_ref = current_shape.layer
            
            current_shape.__dict__ = original_shape.clone().__dict__
            current_shape.scale(factor, self.scale_center)
            
            current_shape.layer = original_layer_ref
            if current_shape.layer: affected_layers.add(current_shape.layer)

        for layer in affected_layers: layer.is_dirty = True
        self.canvas.update()

    def _handle_scale_finish(self, event):
        if not self.scale_center: return
        snapped_pos = QPointF(self.canvas.snap_point(event.pos()))
        dist_start_vec = QPointF(self.action_start_position) - self.scale_center
        dist_end_vec = snapped_pos - self.scale_center
        dist_start_len = math.sqrt(dist_start_vec.x() ** 2 + dist_start_vec.y() ** 2)
        dist_end_len = math.sqrt(dist_end_vec.x() ** 2 + dist_end_vec.y() ** 2)
        final_factor = dist_end_len / dist_start_len if dist_start_len != 0 else 1.0

        if abs(final_factor - 1.0) > 0.001:
            for shape in self.canvas.selected_shapes:
                shape.scale(1.0 / final_factor, self.scale_center)

            command = ScaleCommand(self.canvas.selected_shapes, final_factor, self.scale_center)
            self.canvas.execute_command(command)

    def _handle_rotate_start(self, event):
        self.rotating = True; self.action_start_position = event.pos()
        self.original_shapes_for_action = [s.clone() for s in self.canvas.selected_shapes]
        self.scale_center = self.canvas._get_selection_bbox().center() # QPointF

    def _handle_rotate_move(self, event):
        if not self.scale_center: return
        start_vec = QPointF(self.action_start_position) - self.scale_center
        current_vec = QPointF(event.pos()) - self.scale_center
        start_angle = math.atan2(start_vec.y(), start_vec.x())
        current_angle = math.atan2(current_vec.y(), current_vec.x())
        angle_delta_rad = current_angle - start_angle
        angle_delta_deg = math.degrees(angle_delta_rad)

        affected_layers = set()
        for i, original_shape in enumerate(self.original_shapes_for_action):
            current_shape = self.canvas.selected_shapes[i]
            original_layer_ref = current_shape.layer

            current_shape.__dict__ = original_shape.clone().__dict__
            final_angle_delta = angle_delta_deg
            if current_shape.scale_x * current_shape.scale_y < 0:
                final_angle_delta = -angle_delta_deg
            current_shape.rotate(rotation_delta=final_angle_delta)
            
            current_shape.layer = original_layer_ref
            if current_shape.layer: affected_layers.add(current_shape.layer)

        for layer in affected_layers: layer.is_dirty = True
        self.canvas.update()

    def _handle_rotate_finish(self, event):
        if not self.scale_center: return
        start_vec = QPointF(self.action_start_position) - self.scale_center
        current_vec = QPointF(event.pos()) - self.scale_center
        start_angle = math.atan2(start_vec.y(), start_vec.x())
        current_angle = math.atan2(current_vec.y(), current_vec.x())
        angle_delta_rad = current_angle - start_angle
        final_angle_delta_deg = math.degrees(angle_delta_rad)

        if self.original_shapes_for_action:
            original_shape = self.original_shapes_for_action[0]
            final_angle_delta = final_angle_delta_deg
            if original_shape.scale_x * original_shape.scale_y < 0:
                final_angle_delta = -final_angle_delta_deg
            
            if abs(final_angle_delta_deg) > 0.1:
                for shape in self.canvas.selected_shapes:
                    shape.rotate(-final_angle_delta)

                command = RotateCommand(self.canvas.selected_shapes, rotation_delta=final_angle_delta)
                self.canvas.execute_command(command)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            shape_clicked, layer_of_shape = self.canvas._get_shape_at(event.pos())
            if shape_clicked and layer_of_shape and not layer_of_shape.is_locked:
                if hasattr(shape_clicked, 'get_nodes') and len(
                        self.canvas.selected_shapes) == 1 and self.canvas.selected_shapes[0] is shape_clicked:
                    self.node_editing_active = not self.node_editing_active
                    self.continuing_path_info = None
                    self.dragged_node_info = None
                    self.canvas.update()

    def keyPressEvent(self, event):
        if self.continuing_path_info and event.key() == Qt.Key.Key_Escape:
            if self.old_paths_snapshot:
                shape, _ = self.continuing_path_info
                shape.sub_paths = self.old_paths_snapshot
                self.old_paths_snapshot = None
                self.is_dragging_new_handle = False
                self.new_node_start_pos = None
            self.continuing_path_info = None
            self.canvas.update()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Backspace and self.canvas.selected_shapes:
            self.canvas.delete_selected()

    def paint(self, painter):
        # 1. 绘制多选框
        if self.is_multiselecting and self.selection_rect:
            pen = QPen(QColor(0, 150, 255), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(0, 150, 255, 30))
            painter.drawRect(self.selection_rect)

        if not self.canvas.selected_shapes:
            return

        # 2. 节点编辑模式
        if self.node_editing_active and len(self.canvas.selected_shapes) == 1:
            shape = self.canvas.selected_shapes[0]
            transform, _ = self._get_transform_for_shape(shape)
            
            if self.continuing_path_info:
                path_shape, sp_idx = self.continuing_path_info
                sub_path = path_shape.sub_paths[sp_idx]
                if sub_path:
                    if self.is_dragging_new_handle:
                        temp_path = QPainterPath(transform.map(QPointF(sub_path[-2].anchor)))
                        temp_path.cubicTo(transform.map(QPointF(sub_path[-2].handle2)),
                                          transform.map(QPointF(sub_path[-1].handle1)),
                                          transform.map(QPointF(sub_path[-1].anchor)))
                        pen = QPen(QColor("magenta"), 1, Qt.PenStyle.DashLine)
                        painter.setPen(pen)
                        painter.drawPath(temp_path)
                    else:
                        last_point = transform.map(QPointF(sub_path[-1].anchor))
                        cursor_pos = self.canvas.last_mouse_pos
                        pen = QPen(QColor("blue"), 1, Qt.PenStyle.DashLine)
                        painter.setPen(pen)
                        painter.drawLine(last_point, cursor_pos)

            painter.setPen(QPen(QColor("blue"), 1))

            if isinstance(shape, BSpline):
                pen_dashed = QPen(QColor(120, 120, 120), 1, Qt.PenStyle.DashLine)
                painter.setPen(pen_dashed)
                mapped_points = [transform.map(p) for p in shape.points]
                painter.drawPolyline(QPolygonF(mapped_points))
                
                painter.setBrush(QColor("white"))
                painter.setPen(QPen(QColor("black"), 1))
                for p in mapped_points:
                    painter.drawRect(QRectF(p.x() - 4, p.y() - 4, 8.0, 8.0)) # 🟢 QRectF

            elif isinstance(shape, BezierSurface):
                cage_pen = QPen(QColor(100, 100, 100), 1, Qt.PenStyle.DashLine)
                painter.setPen(cage_pen)
                # 🟢 强制转换 QPointF，防止 drawPolyline 报错
                for r in range(4):
                    row_pts = [QPointF(transform.map(shape.points[r*4 + c])) for c in range(4)]
                    painter.drawPolyline(QPolygonF(row_pts))
                for c in range(4):
                    col_pts = [QPointF(transform.map(shape.points[r*4 + c])) for r in range(4)]
                    painter.drawPolyline(QPolygonF(col_pts))
                
                for i, node_pos in enumerate(shape.get_nodes()):
                    transformed_node = transform.map(node_pos)
                    node_rect = QRectF(transformed_node.x() - 4, transformed_node.y() - 4, 8, 8) # 🟢 QRectF
                    painter.setBrush(QColor("white"))
                    painter.setPen(QPen(QColor("black"), 1))
                    painter.drawRect(node_rect)

            elif isinstance(shape, Path):
                for sub_path in shape.sub_paths:
                    for seg in sub_path:
                        if seg.node_type == PathSegment.SMOOTH:
                            painter.drawLine(transform.map(seg.handle1), transform.map(seg.anchor))
                            painter.drawLine(transform.map(seg.handle2), transform.map(seg.anchor))
                
                for sub_path in shape.sub_paths:
                    for seg in sub_path:
                        transformed_anchor = transform.map(seg.anchor)
                        anchor_rect = QRectF(transformed_anchor.x() - 4, transformed_anchor.y() - 4, 8, 8) # 🟢 QRectF
                        painter.setBrush(QColor("white"))
                        painter.setPen(QPen(QColor("black"), 1))
                        painter.drawRect(anchor_rect)
                        
                        if seg.node_type == PathSegment.SMOOTH:
                            transformed_h1 = transform.map(seg.handle1)
                            transformed_h2 = transform.map(seg.handle2)
                            painter.setBrush(QColor("lightblue"))
                            painter.setPen(QPen(QColor("blue"), 1))
                            painter.drawEllipse(transformed_h1, 4, 4)
                            painter.drawEllipse(transformed_h2, 4, 4)
            
            elif hasattr(shape, 'get_nodes'):
                for i, node_pos in enumerate(shape.get_nodes()):
                    transformed_node = transform.map(node_pos)
                    node_rect = QRectF(transformed_node.x() - 4, transformed_node.y() - 4, 8, 8) # 🟢 QRectF
                    painter.setBrush(QColor("white"))
                    painter.setPen(QPen(QColor("black"), 1))
                    painter.drawRect(node_rect)

        # 3. 普通选择模式
        elif not self.node_editing_active:
            total_bbox_transformed = self.canvas._get_selection_bbox() # QRectF
            if total_bbox_transformed.isEmpty(): return
            
            painter.save()
            if len(self.canvas.selected_shapes) == 1:
                shape = self.canvas.selected_shapes[0]
                center = shape.get_bounding_box().center()
                painter.translate(center)
                painter.scale(shape.scale_x, shape.scale_y)
                painter.rotate(shape.angle)
                painter.translate(-center)
                bbox_to_draw = shape.get_bounding_box() # QRectF
            else:
                bbox_to_draw = total_bbox_transformed
            
            pen = QPen(QColor(0, 150, 255), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(bbox_to_draw.adjusted(-5, -5, 5, 5))
            
            # 🟢 [关键修复] QPointF
            handle_start = QPointF(bbox_to_draw.center().x(), bbox_to_draw.top() - 5)
            handle_end = QPointF(handle_start.x(), handle_start.y() - 20)
            painter.setPen(QPen(QColor(0, 150, 255), 2))
            painter.drawLine(handle_start, handle_end)
            painter.setBrush(QColor("white"))
            painter.setPen(QColor("black"))
            painter.drawEllipse(handle_end, 5, 5)
            
            for corner_rect in self._get_corner_rects(bbox_to_draw.adjusted(-5, -5, 5, 5)).values():
                painter.drawRect(corner_rect) # QRectF
            
            painter.restore()

    def _handle_node_press(self, event):
        if not (len(self.canvas.selected_shapes) == 1 and hasattr(self.canvas.selected_shapes[0], 'get_nodes')):
            return False
        
        shape = self.canvas.selected_shapes[0]
        transform, _ = self._get_transform_for_shape(shape)
        self.dragged_node_info = None
        
        posF = QPointF(event.pos()) # 🟢

        if isinstance(shape, Path):
            self.original_sub_paths_for_drag = [ [s.clone() for s in sp] for sp in shape.sub_paths ]
            modifiers = QApplication.keyboardModifiers()
            is_delete_action = (modifiers == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier))

            if not is_delete_action:
                for sp_idx, sub_path in enumerate(shape.sub_paths):
                    for seg_idx, seg in enumerate(sub_path):
                        if seg.node_type == PathSegment.SMOOTH:
                            if (posF - transform.map(seg.handle1)).manhattanLength() < 5: 
                                self.dragged_node_info = (shape, (sp_idx, seg_idx), "handle1")
                                self.original_node_position = QPointF(seg.handle1) # 🟢
                                return True
                            if (posF - transform.map(seg.handle2)).manhattanLength() < 5: 
                                self.dragged_node_info = (shape, (sp_idx, seg_idx), "handle2")
                                self.original_node_position = QPointF(seg.handle2) # 🟢
                                return True

            for sp_idx, sub_path in enumerate(shape.sub_paths):
                for seg_idx, seg in enumerate(sub_path):
                    if (posF - transform.map(seg.anchor)).manhattanLength() < 5:
                        self.dragged_node_info = (shape, (sp_idx, seg_idx), "anchor")
                        self.original_node_position = (QPointF(seg.anchor), QPointF(seg.handle1), QPointF(seg.handle2)) # 🟢
                        return True
        else:
            self.original_sub_paths_for_drag = None
            for i, node_pos in enumerate(shape.get_nodes()):
                if (posF - transform.map(node_pos)).manhattanLength() < 5:
                    self.dragged_node_info = (shape, i, 'node')
                    self.original_node_position = QPointF(node_pos) # 🟢
                    return True
        
        self.original_sub_paths_for_drag = None
        return False

    def _handle_node_move_with_reset(self, event):
        shape, index, node_type_str = self.dragged_node_info
        
        if isinstance(shape, Path) and self.original_sub_paths_for_drag:
            shape.sub_paths = [ [s.clone() for s in sp] for sp in self.original_sub_paths_for_drag ]

        snapped_pos = self.canvas.snap_point(event.pos())
        _, inverted_transform = self._get_transform_for_shape(shape)
        local_mouse_pos = inverted_transform.map(QPointF(snapped_pos)) # 🟢

        if node_type_str == "anchor":
            original_anchor_pos = self.original_node_position[0]
            offset = local_mouse_pos - original_anchor_pos
            for sub_path in shape.sub_paths:
                for seg in sub_path:
                    if (seg.anchor - original_anchor_pos).manhattanLength() < 1:
                        seg.anchor += offset
                        seg.handle1 += offset
                        seg.handle2 += offset
                        
        elif isinstance(shape, Path): # Handle
            sub_path_idx, seg_idx = index
            seg = shape.sub_paths[sub_path_idx][seg_idx]
            if node_type_str == "handle1":
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

        if shape.layer: shape.layer.is_dirty = True
        self.canvas.update()

    def _handle_node_release(self, event):
        if not (self.dragged_node_info and self.original_node_position):
            self.original_sub_paths_for_drag = None
            return

        shape, index, node_type_str = self.dragged_node_info
        is_click = (event.pos() - self.action_start_position).manhattanLength() < 3

        if is_click:
            modifiers = QApplication.keyboardModifiers()
            is_delete_action = (modifiers == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier))
            
            if isinstance(shape, Path) and node_type_str == 'anchor':
                sub_path_idx, seg_idx = index
                sub_path = shape.sub_paths[sub_path_idx]
                
                if is_delete_action:
                    if len(sub_path) > 2:
                        old_paths = self.original_sub_paths_for_drag
                        shape.remove_segment(sub_path_idx, seg_idx)
                        new_paths = [ [s.clone() for s in sp] for sp in shape.sub_paths ]
                        command = ModifyPathCommand(shape, old_paths, new_paths)
                        self.canvas.execute_command(command)
                
                elif modifiers == Qt.KeyboardModifier.AltModifier:
                    old_paths = self.original_sub_paths_for_drag
                    seg = sub_path[seg_idx]
                    if seg.node_type == PathSegment.CORNER: seg.to_smooth()
                    else: seg.to_corner()
                    new_paths = [ [s.clone() for s in sp] for sp in shape.sub_paths ]
                    command = ModifyPathCommand(shape, old_paths, new_paths)
                    self.canvas.execute_command(command)
                
                elif not shape.is_closed:
                    is_start_node = (seg_idx == 0)
                    is_end_node = (seg_idx == len(sub_path) - 1)
                    if is_start_node or is_end_node:
                        if is_start_node: sub_path.reverse()
                        self.continuing_path_info = (shape, sub_path_idx)
            
            self.canvas.update()
            
        else: # Is a drag
            commands = []
            _, inverted_transform = self._get_transform_for_shape(shape)

            if isinstance(shape, Path) and node_type_str == "anchor":
                original_anchor_pos, _, _ = self.original_node_position
                final_mouse_pos = inverted_transform.map(QPointF(self.canvas.snap_point(event.pos())))
                offset = final_mouse_pos - original_anchor_pos
                if offset.manhattanLength() >= 1:
                    flat_index_counter = 0
                    for sp_idx, sub_path in enumerate(self.original_sub_paths_for_drag):
                        for seg_idx, original_seg in enumerate(sub_path):
                            if (original_seg.anchor - original_anchor_pos).manhattanLength() < 1:
                                current_seg = shape.sub_paths[sp_idx][seg_idx]
                                
                                # 🟢 [关键修复] 强制使用 QPointF，否则 ModifyNodeCommand 报错
                                orig_anchor = QPointF(original_seg.anchor)
                                orig_h1 = QPointF(original_seg.handle1)
                                orig_h2 = QPointF(original_seg.handle2)
                                final_anchor = QPointF(current_seg.anchor)
                                final_h1 = QPointF(current_seg.handle1)
                                final_h2 = QPointF(current_seg.handle2)
                                
                                anchor_flat_idx, h1_flat_idx, h2_flat_idx = flat_index_counter, flat_index_counter + 1, flat_index_counter + 2
                                shape.set_node_at(anchor_flat_idx, orig_anchor); shape.set_node_at(h1_flat_idx, orig_h1); shape.set_node_at(h2_flat_idx, orig_h2)
                                cmd_anchor = ModifyNodeCommand(shape, anchor_flat_idx, orig_anchor, final_anchor)
                                cmd_h1 = ModifyNodeCommand(shape, h1_flat_idx, orig_h1, final_h1)
                                cmd_h2 = ModifyNodeCommand(shape, h2_flat_idx, orig_h2, final_h2)
                                commands.append(CompositeCommand([cmd_anchor, cmd_h1, cmd_h2]))
                            flat_index_counter += 3
            elif isinstance(shape, Path): 
                final_pos = None
                sub_path_idx, seg_idx = index
                if node_type_str == "handle1": final_pos = QPointF(shape.sub_paths[sub_path_idx][seg_idx].handle1)
                elif node_type_str == "handle2": final_pos = QPointF(shape.sub_paths[sub_path_idx][seg_idx].handle2)
                if final_pos and final_pos != self.original_node_position:
                    flat_index = -1; count = 0; found = False
                    for sp_idx, sub_path in enumerate(shape.sub_paths):
                        for s_idx in range(len(sub_path)):
                            if sp_idx == sub_path_idx and s_idx == seg_idx:
                                if node_type_str == "handle1": flat_index = count + 1
                                elif node_type_str == "handle2": flat_index = count + 2
                                found = True; break
                            count += 3
                        if found: break
                    if flat_index != -1:
                        shape.set_node_at(flat_index, self.original_node_position)
                        command = ModifyNodeCommand(shape, flat_index, self.original_node_position, final_pos)
                        commands.append(command)
            else:
                final_pos = QPointF(shape.get_nodes()[index])
                if final_pos != self.original_node_position:
                    shape.set_node_at(index, self.original_node_position)
                    command = ModifyNodeCommand(shape, index, self.original_node_position, final_pos)
                    commands.append(command)

            if len(commands) > 1:
                self.canvas.execute_command(CompositeCommand(commands))
            elif len(commands) == 1:
                self.canvas.execute_command(commands[0])

        self.dragged_node_info = None
        self.original_node_position = None
        self.original_sub_paths_for_drag = None
        self.canvas.update()

    def _get_corner_rects(self, main_rect):
        size = 10.0
        # 🟢 [关键修复] 返回 QRectF
        return { 
            'topLeft': QRectF(main_rect.left()-size/2, main_rect.top()-size/2, size, size), 
            'topRight': QRectF(main_rect.right()-size/2, main_rect.top()-size/2, size, size), 
            'bottomLeft': QRectF(main_rect.left()-size/2, main_rect.bottom()-size/2, size, size), 
            'bottomRight': QRectF(main_rect.right()-size/2, main_rect.bottom()-size/2, size, size) 
        }

    def _get_handle_type_at(self, pos):
        if not self.canvas.selected_shapes or self.node_editing_active: return None
        
        posF = QPointF(pos) # 🟢 统一使用浮点
        
        if len(self.canvas.selected_shapes) > 1:
            total_bbox = self.canvas._get_selection_bbox() # QRectF
            handle_end = QPointF(total_bbox.center().x(), total_bbox.top() - 25) # 🟢 QPointF
            
            if (posF - handle_end).manhattanLength() < 10: return "rotate"
            
            corners = self._get_corner_rects(total_bbox.adjusted(-5,-5,5,5))
            for name, rect in corners.items():
                if rect.contains(posF): return name
            return None
            
        shape_to_check = self.canvas.selected_shapes[0]; bbox_untransformed = shape_to_check.get_bounding_box()
        _, inverted_transform = self._get_transform_for_shape(shape_to_check)
        local_pos = inverted_transform.map(posF)
        handle_end = QPointF(bbox_untransformed.center().x(), bbox_untransformed.top() - 25) # 🟢 QPointF
        
        if (local_pos - handle_end).manhattanLength() < 10: return "rotate"
        
        corners = self._get_corner_rects(bbox_untransformed.adjusted(-5,-5,5,5))
        for name, rect in corners.items():
            if rect.contains(local_pos): return name
        return None
    # 🟢 [新增] 动态绘制旋转光标 (360度无死角)
    def _create_rotated_cursor(self, angle_degrees):
        size = 32
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 移到中心并旋转
        painter.translate(size/2, size/2)
        painter.rotate(angle_degrees)
        
        # 绘制双向箭头
        # 1. 描边 (Outline) - 设为白色，为了在深色背景也能看清
        # 宽度设为 3，稍微粗一点做衬底
        pen = QPen(QColor("white"), 1)
        painter.setPen(pen)
        
        # 2. 填充 (Fill) - 设为黑色，这是主色调
        painter.setBrush(QColor("black"))
        
        # 定义箭头形状 (向右指)
        arrow_len = 12
        path = QPainterPath()
        path.moveTo(-arrow_len, 0)
        path.lineTo(arrow_len, 0)
        
        # 左箭头
        path.moveTo(-arrow_len + 4, -4)
        path.lineTo(-arrow_len, 0)
        path.lineTo(-arrow_len + 4, 4)
        
        # 右箭头
        path.moveTo(arrow_len - 4, -4)
        path.lineTo(arrow_len, 0)
        path.lineTo(arrow_len - 4, 4)
        
        # 先画描边 (由 Pen 决定) 和 填充 (由 Brush 决定)
        # drawPath 会同时画出轮廓和填充内容
        painter.drawPath(path)
        
        pen.setColor(QColor("black"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        
        painter.end()
        
        # 热点设在中心 (16, 16)
        return QCursor(pixmap, 16, 16)
    # 🟢 [修改] 结合旋转角度，更新光标
    def _update_cursor(self, pos):
        if self.scaling or self.dragging or self.rotating or (self.dragged_node_info is not None): return
        cursor = QCursor(Qt.CursorShape.ArrowCursor)
        posF = QPointF(pos)
        
        if self.node_editing_active and len(self.canvas.selected_shapes) == 1:
            # ... (节点编辑模式的光标逻辑保持不变，为了篇幅省略，请保留原来的逻辑) ...
            # ... (只要把这一块原来的代码保留即可) ...
            shape = self.canvas.selected_shapes[0]
            transform, _ = self._get_transform_for_shape(shape)
            if self.continuing_path_info: self.canvas.setCursor(QCursor(Qt.CursorShape.CrossCursor)); return
            if isinstance(shape, Path):
                if not shape.is_closed:
                    for sp_idx, sub_path in enumerate(shape.sub_paths):
                        if not sub_path: continue
                        if (posF - transform.map(sub_path[0].anchor)).manhattanLength() < 5 or \
                           (posF - transform.map(sub_path[-1].anchor)).manhattanLength() < 5:
                            self.canvas.setCursor(QCursor(Qt.CursorShape.CrossCursor)); return
            if hasattr(shape, 'get_nodes'):
                nodes_to_check = []
                if isinstance(shape, Path):
                    for sub_path in shape.sub_paths:
                        for seg in sub_path:
                            nodes_to_check.append(seg.anchor)
                            if seg.node_type == PathSegment.SMOOTH: nodes_to_check.append(seg.handle1); nodes_to_check.append(seg.handle2)
                else: nodes_to_check = shape.get_nodes()
                for node in nodes_to_check:
                    if (posF - transform.map(node)).manhattanLength() < 5: cursor = QCursor(Qt.CursorShape.PointingHandCursor); break

        else:
            # 普通选择模式
            handle_type = self._get_handle_type_at(pos)
            if handle_type:
                if any(not self.canvas._get_layer_for_shape(s).is_locked for s in self.canvas.selected_shapes):
                    if handle_type == 'rotate': 
                        # 旋转光标用系统自带的 CrossCursor 或 自定义旋转图标
                        cursor = QCursor(Qt.CursorShape.CrossCursor)
                    else:
                        # 🟢 [核心修改] 动态计算光标角度
                        if len(self.canvas.selected_shapes) == 1:
                            shape = self.canvas.selected_shapes[0]
                            # 获取变换后的包围盒中心
                            total_bbox = self.canvas._get_selection_bbox() # 这里已经是 OBB 变换后的框了
                            center_pos = total_bbox.center()
                            
                            # 获取当前鼠标位置（即手柄位置）
                            handle_pos = posF
                            
                            # 计算向量 (手柄 - 中心)
                            diff = handle_pos - center_pos
                            
                            # 计算角度 (atan2 返回弧度，转为度数)
                            angle_rad = math.atan2(diff.y(), diff.x())
                            angle_deg = math.degrees(angle_rad)
                            
                            # 生成自定义光标
                            cursor = self._create_rotated_cursor(angle_deg)
                        else:
                            # 多选时，因为框是 AABB（水平的），所以用回系统光标即可
                            if handle_type in ['topLeft', 'bottomRight']: cursor = QCursor(Qt.CursorShape.SizeFDiagCursor)
                            else: cursor = QCursor(Qt.CursorShape.SizeBDiagCursor)
                else: 
                    cursor = QCursor(Qt.CursorShape.ForbiddenCursor)
        
        self.canvas.setCursor(cursor)

class PenTool(Tool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.current_path = None
        self.is_dragging_handle = False
        self.drag_start_pos = None

    def activate(self):
        self.current_path = None
        self.is_dragging_handle = False
        self.drag_start_pos = None
        self.canvas.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def deactivate(self):
        self.finish_drawing()
        self.canvas.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().deactivate()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
            
        snapped_pos = self.canvas.snap_point(event.pos())
        self.drag_start_pos = snapped_pos
        self.is_dragging_handle = False

        if self.current_path:
            active_sub_path = next((sp for sp in reversed(self.current_path.sub_paths) if sp), None)

            # 🔴 --- 逻辑 1：闭合路径并准备新路径 ---
            if active_sub_path and len(active_sub_path) > 1 and (snapped_pos - active_sub_path[0].anchor).manhattanLength() < 10:
                active_sub_path.append(PathSegment(active_sub_path[0].anchor, node_type=PathSegment.CORNER))
                # 不结束绘制，而是准备开始一个新的子路径
                self.current_path.sub_paths.append([])
                self.canvas.update()
                return

            # 逻辑 2：创建新分支
            for sub_path in self.current_path.sub_paths:
                for seg in sub_path:
                    if (snapped_pos - seg.anchor).manhattanLength() < 10:
                        new_branch_start_segment = PathSegment(seg.anchor, node_type=PathSegment.CORNER)
                        self.current_path.sub_paths.append([new_branch_start_segment])
                        self.canvas.update()
                        return

        # 逻辑 3：追加新节点
        if self.current_path is None:
            new_segment = PathSegment(snapped_pos, node_type=PathSegment.CORNER)
            self.current_path = Path([[new_segment]], self.canvas.current_pen_color, self.canvas.current_width)
        else:
            if not self.current_path.sub_paths[-1]:
                self.current_path.sub_paths[-1].append(PathSegment(snapped_pos, node_type=PathSegment.CORNER))
            else:
                self.current_path.sub_paths[-1].append(PathSegment(snapped_pos, node_type=PathSegment.CORNER))
        
        self.canvas.update()

    def mouseMoveEvent(self, event):
        snapped_pos = self.canvas.snap_point(event.pos())
        if self.current_path and self.drag_start_pos and (event.buttons() & Qt.MouseButton.LeftButton):
            active_sub_path = next((sp for sp in reversed(self.current_path.sub_paths) if sp), None)
            if not active_sub_path: return

            if not self.is_dragging_handle and (snapped_pos - self.drag_start_pos).manhattanLength() > 4:
                self.is_dragging_handle = True
            
            if self.is_dragging_handle:
                last_seg = active_sub_path[-1]
                if last_seg.anchor == self.drag_start_pos:
                    last_seg.to_smooth(handle=snapped_pos)
                    self.canvas.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = None
            self.is_dragging_handle = False
            self.canvas.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.finish_drawing()
        
    def mouseDoubleClickEvent(self, event):
        self.finish_drawing()
        
    def keyPressEvent(self, event):
        # 这个方法现在由 main.py 的 smart_undo 统一处理，可以保持为空
        pass

    def undo_last_point(self):
        if not self.current_path:
            return
        last_sub_path = next((sp for sp in reversed(self.current_path.sub_paths) if sp), None)
        
        if last_sub_path:
            last_sub_path.pop()
            
            if not last_sub_path:
                # 如果移除后子路径为空，则直接移除这个空子路径
                self.current_path.sub_paths = [sp for sp in self.current_path.sub_paths if sp]

            if not self.current_path.sub_paths:
                 self.current_path = None

            self.canvas.update()

    def finish_drawing(self):
        if self.current_path:
            # 过滤掉所有空的或只有一个点的子路径
            self.current_path.sub_paths = [sp for sp in self.current_path.sub_paths if len(sp) > 1]
            if self.current_path.sub_paths:
                current_layer = self.canvas.get_current_layer()
                if current_layer:
                    command = AddShapeCommand(current_layer, self.current_path)
                    self.canvas.execute_command(command)
        self.current_path = None
        self.canvas.update()
    
    def paint(self, painter):
        if self.current_path:
            painter.setPen(QPen(self.current_path.color, self.current_path.width, Qt.PenStyle.SolidLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self.current_path.get_painter_path())
            
            painter.setPen(QPen(QColor("blue"), 1))
            for sub_path in self.current_path.sub_paths:
                for seg in sub_path:
                    painter.setBrush(QColor("white"))
                    painter.drawRect(QRect(seg.anchor.x() - 3, seg.anchor.y() - 3, 6, 6))
                    if seg.node_type == PathSegment.SMOOTH:
                        painter.setBrush(QColor("lightblue"))
                        painter.drawLine(seg.anchor, seg.handle1)
                        painter.drawEllipse(seg.handle1, 3, 3)
                        painter.drawLine(seg.anchor, seg.handle2)
                        painter.drawEllipse(seg.handle2, 3, 3)

class BaseDrawingTool(Tool):
    def __init__(self, canvas):
        super().__init__(canvas); self.drawing = False; self.start_point = None; self.end_point = None
    def mousePressEvent(self, event):
        current_layer = self.canvas.get_current_layer()
        if event.button() == Qt.MouseButton.LeftButton and current_layer and not current_layer.is_locked:
            self.drawing = True
            snapped_pos = self.canvas.snap_point(event.pos())
            self.start_point, self.end_point = snapped_pos, snapped_pos
    def mouseMoveEvent(self, event):
        if self.drawing: self.end_point = self.canvas.snap_point(event.pos()); self.canvas.update()
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            current_layer = self.canvas.get_current_layer()
            if current_layer:
                final_rect = QRect(self.start_point, self.end_point).normalized()
                if final_rect.width() < 2 and final_rect.height() < 2 and not isinstance(self, (LineTool, ArrowTool, CircleTool)): self.canvas.update(); return
                new_shape = self.create_shape()
                if new_shape:
                    command = AddShapeCommand(current_layer, new_shape)
                    self.canvas.execute_command(command)
                else: self.canvas.update()
    def create_shape(self): raise NotImplementedError
    def paint(self, painter):
        if self.drawing and self.start_point and self.end_point:
            pen = QPen(self.canvas.current_pen_color, self.canvas.current_width, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            if self.canvas.current_fill_color and self.canvas.current_fill_style != Qt.BrushStyle.NoBrush: painter.setBrush(QBrush(self.canvas.current_fill_color, self.canvas.current_fill_style))
            else: painter.setBrush(Qt.BrushStyle.NoBrush)
            self.draw_preview(painter)
    def draw_preview(self, painter): raise NotImplementedError

class PointTool(Tool):
    def mousePressEvent(self, event):
        current_layer = self.canvas.get_current_layer()
        if event.button() == Qt.MouseButton.LeftButton and current_layer and not current_layer.is_locked:
            snapped_pos = self.canvas.snap_point(event.pos())
            new_shape = Point(snapped_pos, self.canvas.current_pen_color, self.canvas.current_width)
            command = AddShapeCommand(current_layer, new_shape); self.canvas.execute_command(command)

class LineTool(BaseDrawingTool):
    def create_shape(self):
        # 在创建图形时，检查Shift键的状态
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.KeyboardModifier.ShiftModifier:
            return Arrow(self.start_point, self.end_point, self.canvas.current_pen_color, self.canvas.current_width)
        else:
            return Line(self.start_point, self.end_point, self.canvas.current_pen_color, self.canvas.current_width)

    def draw_preview(self, painter):
        # 在预览时，也检查Shift键的状态来决定画什么预览
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.KeyboardModifier.ShiftModifier:
            # 如果是Shift，调用renderer的arrow方法画箭头预览
            CanvasRenderer.draw_arrow(painter, self.start_point, self.end_point, self.canvas.current_pen_color, self.canvas.current_width)
        else:
            # 否则，直接用painter画一条普通的虚线作为预览
            painter.drawLine(self.start_point, self.end_point)

class ArrowTool(BaseDrawingTool):
    def create_shape(self):
        return Arrow(self.start_point, self.end_point, self.canvas.current_pen_color, self.canvas.current_width)
    
    def draw_preview(self, painter):
        # 箭头工具的预览总是箭头
        CanvasRenderer.draw_arrow(painter, self.start_point, self.end_point, self.canvas.current_pen_color, self.canvas.current_width)
class RectangleTool(BaseDrawingTool):
    def create_shape(self): rect = QRect(self.start_point, self.end_point).normalized(); return Rectangle(rect.topLeft(), rect.bottomRight(), self.canvas.current_pen_color, self.canvas.current_width, self.canvas.current_fill_color, self.canvas.current_fill_style)
    def draw_preview(self, painter): painter.drawRect(QRect(self.start_point, self.end_point).normalized())

class SquareTool(BaseDrawingTool):
    def create_shape(self): rect = QRect(self.start_point, self.end_point).normalized(); side = max(rect.width(), rect.height()); return Square(rect.topLeft(), side, self.canvas.current_pen_color, self.canvas.current_width, self.canvas.current_fill_color, self.canvas.current_fill_style)
    def draw_preview(self, painter): rect = QRect(self.start_point, self.end_point).normalized(); side = max(rect.width(), rect.height()); painter.drawRect(QRect(rect.left(), rect.top(), side, side))

class CircleTool(BaseDrawingTool):
    def create_shape(self): radius = math.sqrt((self.end_point.x() - self.start_point.x())**2 + (self.end_point.y() - self.start_point.y())**2); return Circle(self.start_point, radius, self.canvas.current_pen_color, self.canvas.current_width, self.canvas.current_fill_color, self.canvas.current_fill_style)
    def draw_preview(self, painter): radius = math.sqrt((self.end_point.x() - self.start_point.x())**2 + (self.end_point.y() - self.start_point.y())**2); painter.drawEllipse(self.start_point, int(radius), int(radius))

class EllipseTool(BaseDrawingTool):
    def create_shape(self): rect = QRect(self.start_point, self.end_point).normalized(); return Ellipse(rect.topLeft(), rect.bottomRight(), self.canvas.current_pen_color, self.canvas.current_width, self.canvas.current_fill_color, self.canvas.current_fill_style)
    def draw_preview(self, painter): painter.drawEllipse(QRect(self.start_point, self.end_point).normalized())

class RoundedRectangleTool(BaseDrawingTool):
    def create_shape(self): rect = QRect(self.start_point, self.end_point).normalized(); return RoundedRectangle(rect.topLeft(), rect.bottomRight(), self.canvas.current_pen_color, self.canvas.current_width, self.canvas.current_fill_color, self.canvas.current_fill_style)
    def draw_preview(self, painter): painter.drawRoundedRect(QRect(self.start_point, self.end_point).normalized(), 20, 20)

class TextTool(BaseDrawingTool):
    def create_shape(self):
        text_rect = QRect(self.start_point, self.end_point).normalized()
        if text_rect.width() > 10 and text_rect.height() > 10:
            font = QFont(self.canvas.current_font)
            new_shape = Text(
                text_rect, 
                "", 
                font, 
                self.canvas.current_pen_color, 
                has_border=True, 
                border_color=self.canvas.current_pen_color, 
                alignment=self.canvas.current_alignment
            )
            self.canvas.start_text_editing_on_creation(new_shape)
            return None
        return None
    def draw_preview(self, painter): painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawRect(QRect(self.start_point, self.end_point).normalized())

class BaseMultiStepTool(Tool):
    def __init__(self, canvas):
        super().__init__(canvas); self.points = []; self.cursor_pos = None
    def activate(self): self.points = []; self.cursor_pos = None
    def deactivate(self): self.points = []; self.cursor_pos = None; super().deactivate()
    def mousePressEvent(self, event):
        current_layer = self.canvas.get_current_layer()
        if event.button() == Qt.MouseButton.LeftButton and current_layer and not current_layer.is_locked:
            snapped_pos = self.canvas.snap_point(event.pos())
            self.points.append(snapped_pos); self.cursor_pos = snapped_pos
            self.handle_step(); self.canvas.update()
    def mouseMoveEvent(self, event):
        self.cursor_pos = self.canvas.snap_point(event.pos()); self.canvas.update()
    def handle_step(self): pass

class PolylineTool(BaseMultiStepTool):
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.finish_drawing()
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton: self.finish_drawing()
    def finish_drawing(self):
        if len(self.points) >= 2:
            current_layer = self.canvas.get_current_layer()
            if current_layer:
                shape = Polyline(self.points, self.canvas.current_pen_color, self.canvas.current_width)
                command = AddShapeCommand(current_layer, shape); self.canvas.execute_command(command)
        self.points = []
    def paint(self, painter):
        if not self.points: return
        pen = QPen(self.canvas.current_pen_color, self.canvas.current_width, Qt.PenStyle.DashLine); painter.setPen(pen)
        points_to_draw = self.points + ([self.cursor_pos] if self.cursor_pos else [])
        painter.drawPolyline(QPolygon(points_to_draw))

class BSplineTool(BaseMultiStepTool):
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.finish_drawing()
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton: self.finish_drawing()
        
    def finish_drawing(self):
        # 🟢 核心修复：清理连续的重复点
        # 双击操作会触发两次 mousePress，导致最后一个点被添加两次。
        # 这在 B 样条中会导致曲线形状改变（变尖）。必须在生成图形前去除。
        if not self.points: return

        unique_points = []
        if self.points:
            unique_points.append(self.points[0])
            for i in range(1, len(self.points)):
                # 只有当当前点和前一个点距离大于 0 时才添加
                if self.points[i] != self.points[i-1]:
                    unique_points.append(self.points[i])
        
        # 使用清理后的点集进行判断和创建
        if len(unique_points) >= 2:
            current_layer = self.canvas.get_current_layer()
            if current_layer:
                shape = BSpline(unique_points, degree=3, color=self.canvas.current_pen_color, width=self.canvas.current_width)
                command = AddShapeCommand(current_layer, shape)
                self.canvas.execute_command(command)
        
        self.points = []
        self.cursor_pos = None
        self.canvas.update()
        
    def paint(self, painter):
        if not self.points and not self.cursor_pos: return
        
        # 🟢 回归本源：直接组合已有点和鼠标点，不做任何去重
        # 这样当你鼠标靠近端点时，预览会真实地显示“双重节点”的效果（曲线变紧），
        # 移开后又变回正常，这是符合逻辑的“所见即所得”，不会出现莫名其妙的跳变。
        points_to_draw = self.points + ([self.cursor_pos] if self.cursor_pos else [])

        # 1. 绘制控制多边形 (灰色虚线)
        if len(points_to_draw) > 1:
            pen_dashed = QPen(QColor(120, 120, 120), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen_dashed)
            painter.drawPolyline(QPolygonF([QPointF(p) for p in points_to_draw]))
        
        # 2. 绘制控制点 (灰色小圆点)
        painter.setBrush(QColor(120, 120, 120))
        painter.setPen(Qt.PenStyle.NoPen)
        for p in points_to_draw:
            painter.drawEllipse(p, 2, 2)
        
        # 3. 绘制实时 B样条曲线预览
        if len(points_to_draw) >= 2:
            pen_curve = QPen(self.canvas.current_pen_color, self.canvas.current_width, Qt.PenStyle.SolidLine)
            painter.setPen(pen_curve)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            # 使用 float 精度计算
            curve_points = raster_algorithms.compute_bspline_points(points_to_draw, degree=3)
            
            if curve_points:
                painter.drawPolyline(QPolygonF(curve_points))
class PolygonTool(BaseMultiStepTool):
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.finish_drawing()
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton: self.finish_drawing()
    def finish_drawing(self):
        if len(self.points) >= 3:
            current_layer = self.canvas.get_current_layer()
            if current_layer:
                shape = Polygon(self.points, self.canvas.current_pen_color, self.canvas.current_width, self.canvas.current_fill_color, self.canvas.current_fill_style)
                command = AddShapeCommand(current_layer, shape); self.canvas.execute_command(command)
        self.points = []
    def paint(self, painter):
        if not self.points: return
        pen = QPen(self.canvas.current_pen_color, self.canvas.current_width, Qt.PenStyle.DashLine)
        painter.setPen(pen); painter.setBrush(Qt.BrushStyle.NoBrush)
        points_to_draw = self.points + ([self.cursor_pos] if self.cursor_pos else [])
        painter.drawPolyline(QPolygon(points_to_draw))
        if len(self.points) >= 2 and self.cursor_pos: painter.drawLine(self.cursor_pos, self.points[0])

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
            self.points.append(self.canvas.snap_point(event.pos()))
    def mouseMoveEvent(self, event):
        if self.drawing:
            self.points.append(self.canvas.snap_point(event.pos()))
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
        super().__init__(canvas); self.erasing = False; self.cursor_pos = None
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.erasing = True; self.cursor_pos = event.pos()
            self._erase_at(self.cursor_pos); self.canvas.update()
    def mouseMoveEvent(self, event):
        self.cursor_pos = event.pos()
        if self.erasing: self._erase_at(self.cursor_pos)
        self.canvas.update()
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.erasing:
            self.erasing = False; self.cursor_pos = None; self.canvas.update()
    def paint(self, painter):
        if self.cursor_pos:
            painter.setPen(QPen(Qt.GlobalColor.black, 1, Qt.PenStyle.DashLine)); painter.setBrush(Qt.BrushStyle.NoBrush)
            eraser_size = self.canvas.current_width * 5
            painter.drawEllipse(self.cursor_pos, eraser_size, eraser_size)
    def _erase_at(self, pos):
        eraser_size = self.canvas.current_width * 5
        eraser_rect = QRect(pos.x() - eraser_size, pos.y() - eraser_size, eraser_size * 2, eraser_size * 2)
        shapes_to_delete_map = {}
        for layer in self.canvas.layers:
            if layer.is_locked or not layer.is_visible: continue
            shapes_in_layer_to_delete = [s for s in layer.shapes if eraser_rect.intersects(s.get_bounding_box())]
            if shapes_in_layer_to_delete: shapes_to_delete_map[layer] = shapes_in_layer_to_delete
        if shapes_to_delete_map:
            for layer, shapes in shapes_to_delete_map.items():
                command = RemoveShapesCommand(layer, shapes); self.canvas.execute_command(command)

class PaintBucketTool(Tool):
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton: return
        shape_clicked, layer_of_shape = self.canvas._get_shape_at(event.pos())
        if (shape_clicked and layer_of_shape and not layer_of_shape.is_locked and hasattr(shape_clicked, 'fill_color')):
            properties_to_change = { 'fill_style': self.canvas.current_fill_style, 'fill_color': self.canvas.current_fill_color }
            command = ChangePropertiesCommand([shape_clicked], properties_to_change); self.canvas.execute_command(command)

class SurfaceTool(BaseDrawingTool):
    def create_shape(self):
        rect = QRect(self.start_point, self.end_point).normalized()
        # 限制最小尺寸
        if rect.width() < 20 or rect.height() < 20: return None
        return BezierSurface(rect, self.canvas.current_pen_color, self.canvas.current_width)
        
    def draw_preview(self, painter):
        # 🟢 预览时也画真实的 4x4 网格，实现“所见即所得”
        rect = QRect(self.start_point, self.end_point).normalized()
        
        # 临时生成一个 BezierSurface 对象用来计算网格点
        # 这里只做轻量级计算，不需要创建真正的 Shape 对象
        cols, rows = 4, 4
        x_step = rect.width() / (cols - 1)
        y_step = rect.height() / (rows - 1)
        
        temp_points = []
        for r in range(rows):
            for c in range(cols):
                temp_points.append(QPoint(int(rect.x() + c * x_step), int(rect.y() + r * y_step)))
        
       # 🟢 修改：将 steps 提高到 12，与 renderer.py 保持一致，实现所见即所得
        # 现在的渲染引擎足够快，不需要降级处理
        preview_lines = raster_algorithms.compute_bezier_surface_wireframe(temp_points, steps=12)
        
        pen = QPen(self.canvas.current_pen_color, 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        for line in preview_lines:
            painter.drawPolyline(QPolygonF(line))