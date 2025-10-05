from PyQt6.QtWidgets import QWidget, QFileDialog, QMenu, QColorDialog, QTextEdit, QFontDialog, QApplication
from PyQt6.QtGui import QPainter, QColor, QPixmap, QAction, QFont, QBrush, QKeySequence
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtSvg import QSvgGenerator

from shapes import *
from commands import *
from file_handler import ProjectHandler
from renderer import CanvasRenderer
from tools import *
from aligner import Aligner

class CanvasWidget(QWidget):
    undo_stack_changed = pyqtSignal(bool)
    redo_stack_changed = pyqtSignal(bool)
    layers_changed = pyqtSignal(list, int)
    mouse_moved_signal = pyqtSignal(QPoint)
    selection_changed_signal = pyqtSignal(bool)
    clipboard_changed_signal = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        
        self.layers, self.current_layer_index = [], -1
        self.undo_stack, self.redo_stack = [], []
        self.clipboard = []
        self.selected_shapes = []
        self.last_mouse_pos = QPoint(0, 0)
        self.current_pen_color = QColor(0, 0, 0)
        self.current_width = 2
        self.current_fill_color = None
        self.current_fill_style = Qt.BrushStyle.NoBrush
        self.current_font = QFont("Arial", 24)
        self.editing_shape = None
        self.text_editor = None
        self.grid_enabled = False
        self.snap_enabled = False
        self.grid_size = 20
        self.snap_threshold = 8
        self.horizontal_guides = []
        self.vertical_guides = []
        self.guides_enabled = True 
        self.tools = {
            "select": SelectTool(self), "point": PointTool(self),
            "line": LineTool(self), "arrow": ArrowTool(self),
            "rect": RectangleTool(self), "square": SquareTool(self),
            "circle": CircleTool(self), "ellipse": EllipseTool(self),
            "rounded_rect": RoundedRectangleTool(self), "text": TextTool(self),
            "polyline": PolylineTool(self), "polygon": PolygonTool(self),
            "pen": PenTool(self), "freehand": FreehandTool(self),
            "eraser": EraserTool(self), "paint_bucket": PaintBucketTool(self),
        }
        self.current_tool_obj = self.tools["select"]

    def execute_command(self, command):
        command.redo()
        self.undo_stack.append(command)
        self.redo_stack.clear()
        self.update_stacks_and_canvas()

    def undo(self):
        if self.undo_stack:
            command = self.undo_stack.pop()
            command.undo()
            self.redo_stack.append(command)
            self.update_stacks_and_canvas()

    def redo(self):
        if self.redo_stack:
            command = self.redo_stack.pop()
            command.redo()
            self.undo_stack.append(command)
            self.update_stacks_and_canvas()

    def update_stacks_and_canvas(self):
        self.undo_stack_changed.emit(bool(self.undo_stack))
        self.redo_stack_changed.emit(bool(self.redo_stack))
        self.layers_changed.emit(self.layers, self.current_layer_index)
        self.update()

    def set_tool(self, tool_name):
        self._finish_text_editing()
        if self.current_tool_obj: self.current_tool_obj.deactivate()
        if tool_name in self.tools:
            self.current_tool_obj = self.tools[tool_name]
            self.current_tool_obj.activate()
        self.selection_changed_signal.emit(False)

    def set_pen_color(self, color):
        if color.isValid(): self.current_pen_color = color
    def set_fill_color(self, color):
        if color.isValid(): self.current_fill_color = color
    def set_no_fill(self):
        self.current_fill_style = Qt.BrushStyle.NoBrush; self.current_fill_color = None; self.update()
    def set_fill_style(self, style):
        self.current_fill_style = style
        if style != Qt.BrushStyle.NoBrush and self.current_fill_color is None: self.current_fill_color = QColor(0, 0, 0)
    def set_pen_width(self, width): self.current_width = width
    def set_font(self, font): self.current_font = font
    def set_font_size(self, size): self.current_font.setPointSize(size)

    def initialize_layers(self): self.add_layer("背景")
    def get_current_layer(self):
        if 0 <= self.current_layer_index < len(self.layers): return self.layers[self.current_layer_index]
        return None

    def set_layer_opacity(self, index, value):
        if 0 <= index < len(self.layers):
            layer = self.layers[index]
            new_opacity = max(0.0, min(1.0, value / 100.0))
            if abs(layer.opacity - new_opacity) > 0.001:
                command = ChangePropertiesCommand([layer], {'opacity': new_opacity})
                self.execute_command(command)

    def set_layer_blend_mode(self, index, mode):
        if 0 <= index < len(self.layers):
            layer = self.layers[index]
            if layer.blend_mode != mode:
                command = ChangePropertiesCommand([layer], {'blend_mode': mode})
                self.execute_command(command)

    def add_layer(self, name=None):
        if name is None: name = f"图层 {len(self.layers) + 1}"
        new_layer = Layer(name)
        command = AddLayerCommand(self, new_layer, 0)
        self.execute_command(command)
        self.set_current_layer(0)

    def remove_current_layer(self):
        if len(self.layers) > 1 and self.get_current_layer():
            command = RemoveLayerCommand(self, self.get_current_layer(), self.current_layer_index)
            self.execute_command(command)
            new_index = min(self.current_layer_index, len(self.layers) - 1)
            self.set_current_layer(new_index)

    def move_layer_up(self):
        if self.current_layer_index > 0:
            command = MoveLayerCommand(self, self.current_layer_index, self.current_layer_index - 1)
            self.execute_command(command)
            self.set_current_layer(self.current_layer_index - 1)

    def move_layer_down(self):
        if 0 <= self.current_layer_index < len(self.layers) - 1:
            command = MoveLayerCommand(self, self.current_layer_index, self.current_layer_index + 1)
            self.execute_command(command)
            self.set_current_layer(self.current_layer_index + 1)

    def toggle_layer_visibility(self, index):
        if 0 <= index < len(self.layers):
            layer = self.layers[index]
            command = ChangePropertiesCommand([layer], {'is_visible': not layer.is_visible})
            self.execute_command(command)

    def toggle_layer_lock(self, index):
        if 0 <= index < len(self.layers):
            layer = self.layers[index]
            command = ChangePropertiesCommand([layer], {'is_locked': not layer.is_locked})
            self.execute_command(command)

    def set_current_layer(self, index):
        if 0 <= index < len(self.layers):
            self.current_layer_index = index
            if hasattr(self.current_tool_obj, 'deactivate'): self.current_tool_obj.deactivate(); self.current_tool_obj.activate()
            self.layers_changed.emit(self.layers, self.current_layer_index); self.update()

    def rename_layer(self, index, new_name):
        if 0 <= index < len(self.layers) and new_name:
            layer_to_rename = self.layers[index]
            if new_name != layer_to_rename.name:
                command = ChangePropertiesCommand([layer_to_rename], {'name': new_name})
                self.execute_command(command)
                self.layers_changed.emit(self.layers, self.current_layer_index)

    def save_shapes(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "保存项目", "", "JSON Files (*.json)")
        if file_path: ProjectHandler.save(self.layers, file_path)

    def load_shapes(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "加载项目", "", "JSON Files (*.json)")
        if file_path:
            self.layers = ProjectHandler.load(file_path)
            self.set_current_layer(0)
            self.undo_stack.clear(); self.redo_stack.clear()
            self.update_stacks_and_canvas()

    def export_as_png(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "导出为PNG", "", "PNG Files (*.png)")
        if file_path:
            pixmap = QPixmap(self.size()); pixmap.fill(Qt.GlobalColor.white)
            original_tool = self.current_tool_obj; self.current_tool_obj = Tool(self)
            painter = QPainter(pixmap)
            CanvasRenderer.paint(painter, self)
            painter.end()
            self.current_tool_obj = original_tool; pixmap.save(file_path, "PNG")

    def export_as_svg(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "导出为SVG", "", "SVG Files (*.svg)")
        if not file_path: return
        generator = QSvgGenerator(); generator.setFileName(file_path); generator.setSize(self.size()); generator.setViewBox(self.rect())
        painter = QPainter(generator); original_tool = self.current_tool_obj; self.current_tool_obj = Tool(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        CanvasRenderer.paint(painter, self)
        painter.end(); self.current_tool_obj = original_tool

    def clear_canvas(self):
        current_layer = self.get_current_layer()
        if current_layer and not current_layer.is_locked and current_layer.shapes:
            command = RemoveShapesCommand(current_layer, current_layer.shapes)
            self.execute_command(command)
            if hasattr(self.current_tool_obj, 'node_editing_active'): self.current_tool_obj.node_editing_active = False

    def group_selected(self):
        current_layer = self.get_current_layer()
        if current_layer and not current_layer.is_locked and len(self.selected_shapes) > 1:
            command = GroupCommand(current_layer, self.selected_shapes)
            self.execute_command(command)
            self.selected_shapes = [command.group]
            self.selection_changed_signal.emit(True); self.update()

    def ungroup_selected(self):
        current_layer = self.get_current_layer()
        if not current_layer or current_layer.is_locked: return
        groups_in_selection = [s for s in self.selected_shapes if isinstance(s, ShapeGroup)]
        if groups_in_selection:
            newly_ungrouped_shapes = []
            for group in groups_in_selection:
                command = UngroupCommand(current_layer, group)
                self.execute_command(command)
                newly_ungrouped_shapes.extend(command.shapes_inside)
            remaining_selection = [s for s in self.selected_shapes if not isinstance(s, ShapeGroup)]
            self.selected_shapes = remaining_selection + newly_ungrouped_shapes
            self.selection_changed_signal.emit(bool(self.selected_shapes)); self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        if self.grid_enabled: self.draw_grid(painter)
        self.draw_guides(painter)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        CanvasRenderer.paint(painter, self)
    
    def draw_grid(self, painter):
        pen = QPen(QColor(220, 220, 220), 1, Qt.PenStyle.DotLine); painter.setPen(pen)
        width, height = self.width(), self.height()
        for x in range(0, width, self.grid_size): painter.drawLine(x, 0, x, height)
        for y in range(0, height, self.grid_size): painter.drawLine(0, y, width, y)

    def mousePressEvent(self, event):
        self._finish_text_editing()
        if self.current_tool_obj: self.current_tool_obj.mousePressEvent(event)
        self.selection_changed_signal.emit(bool(self.selected_shapes))

    def mouseMoveEvent(self, event):
        self.last_mouse_pos = event.pos()
        self.mouse_moved_signal.emit(event.pos())
        if self.current_tool_obj: self.current_tool_obj.mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.current_tool_obj: self.current_tool_obj.mouseReleaseEvent(event)
        self.selection_changed_signal.emit(bool(self.selected_shapes))

    def mouseDoubleClickEvent(self, event):
        shape_clicked, layer_of_shape = self._get_shape_at(event.pos())
        if shape_clicked and isinstance(shape_clicked, Text) and layer_of_shape and not layer_of_shape.is_locked:
            self._start_text_editing(shape_clicked)
        elif self.current_tool_obj: self.current_tool_obj.mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy): self.copy_selected(); return
        if event.key() == Qt.Key.Key_V and event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier): self.paste_in_place(); return
        if event.matches(QKeySequence.StandardKey.Paste): self.paste(); return
        if self.current_tool_obj: self.current_tool_obj.keyPressEvent(event)
        else: super().keyPressEvent(event)

    def contextMenuEvent(self, event): pass

    def delete_selected(self):
        if self.selected_shapes:
            shapes_by_layer = {}
            for shape in self.selected_shapes:
                layer = self._get_layer_for_shape(shape)
                if layer and not layer.is_locked:
                    if layer not in shapes_by_layer: shapes_by_layer[layer] = []
                    shapes_by_layer[layer].append(shape)
            for layer, shapes_in_layer in shapes_by_layer.items():
                command = RemoveShapesCommand(layer, shapes_in_layer); self.execute_command(command)
            self.selected_shapes.clear(); self.selection_changed_signal.emit(False)
            if hasattr(self.current_tool_obj, 'node_editing_active'): self.current_tool_obj.node_editing_active = False
            self.update()

    def flip_selected_horizontal(self):
        if self.selected_shapes:
            unlocked_shapes = [s for s in self.selected_shapes if not self._get_layer_for_shape(s).is_locked]
            if unlocked_shapes: command = FlipCommand(unlocked_shapes, 'horizontal'); self.execute_command(command)
    def flip_selected_vertical(self):
        if self.selected_shapes:
            unlocked_shapes = [s for s in self.selected_shapes if not self._get_layer_for_shape(s).is_locked]
            if unlocked_shapes: command = FlipCommand(unlocked_shapes, 'vertical'); self.execute_command(command)
    def change_selected_pen_color(self): pass
    def change_selected_text_color(self): pass
    def change_selected_text_border_color(self): pass
    def change_selected_fill_color(self): pass
    def change_selected_fill_style(self, style): pass
    def change_selected_font(self): pass
    def toggle_selected_text_border(self, checked): pass

    def start_text_editing_on_creation(self, text_shape):
        command = AddShapeCommand(self.get_current_layer(), text_shape); self.execute_command(command)
        self._start_text_editing(text_shape)
    def _start_text_editing(self, text_shape): pass
    def _finish_text_editing(self): pass
    def eventFilter(self, obj, event): return super().eventFilter(obj, event)
    def _get_selection_bbox(self):
        if not self.selected_shapes: return QRect()
        total_bbox = self.selected_shapes[0].get_transformed_bounding_box()
        for shape in self.selected_shapes[1:]: total_bbox = total_bbox.united(shape.get_transformed_bounding_box())
        return total_bbox
    def _get_layer_for_shape(self, shape_to_find):
        for layer in self.layers:
            if shape_to_find in layer.shapes or (isinstance(shape_to_find, ShapeGroup) and shape_to_find in layer.shapes): return layer
        return None

    # 🔴 --- 修正开始 ---
    def _get_shape_at(self, pos):
        # 从顶层图层(index 0)开始遍历，而不是从底层
        for layer in self.layers:
            if not layer.is_visible: continue
            # 在一个图层内部，从最上方的图形(列表末尾)开始检查
            for shape in reversed(layer.shapes):
                if shape.get_transformed_bounding_box().contains(pos):
                    return shape, layer
        return None, None
    # 🔴 --- 修正结束 ---

    def _draw_arrow(self, painter, p1, p2, color, width): CanvasRenderer.draw_arrow(painter, p1, p2, color, width)

    def copy_selected(self):
        if self.selected_shapes: self.clipboard = [shape.clone() for shape in self.selected_shapes]; self.clipboard_changed_signal.emit(True)
    def paste(self, position=None):
        current_layer = self.get_current_layer()
        if not self.clipboard or not current_layer or current_layer.is_locked: return
        target_pos = position if isinstance(position, QPoint) else self.last_mouse_pos
        clipboard_bbox = self.clipboard[0].get_transformed_bounding_box()
        for shape in self.clipboard[1:]: clipboard_bbox = clipboard_bbox.united(shape.get_transformed_bounding_box())
        offset = target_pos - clipboard_bbox.topLeft()
        pasted_shapes = []
        for shape in self.clipboard:
            new_shape = shape.clone(); new_shape.move(offset.x(), offset.y()); pasted_shapes.append(new_shape)
        command = AddShapesCommand(current_layer, pasted_shapes); self.execute_command(command)
        self.selected_shapes = pasted_shapes; self.selection_changed_signal.emit(True); self.update()

    def paste_in_place(self):
        current_layer = self.get_current_layer()
        if not self.clipboard or not current_layer or current_layer.is_locked: return
        pasted_shapes = [shape.clone() for shape in self.clipboard]
        command = AddShapesCommand(current_layer, pasted_shapes); self.execute_command(command)
        self.selected_shapes = pasted_shapes; self.selection_changed_signal.emit(True); self.update()

    def align_selected_shapes(self, mode):
        if len(self.selected_shapes) < 2: return
        unlocked_shapes = [s for s in self.selected_shapes if not self._get_layer_for_shape(s).is_locked]
        if len(unlocked_shapes) < 2: return
        moves_to_perform = Aligner.align(unlocked_shapes, mode)
        if not moves_to_perform: return
        move_commands = [MoveShapesCommand([shape], dx, dy) for shape, dx, dy in moves_to_perform]
        composite_command = CompositeCommand(move_commands); self.execute_command(composite_command)

    def toggle_grid(self, enabled): self.grid_enabled = enabled; self.update()
    def toggle_snapping(self, enabled): self.snap_enabled = enabled
    def snap_point(self, point):
        if not self.snap_enabled: return point
        snapped_x, snapped_y = point.x(), point.y(); min_dist_x, min_dist_y = self.snap_threshold + 1, self.snap_threshold + 1
        if self.grid_enabled:
            grid_x = round(point.x() / self.grid_size) * self.grid_size; dist_x = abs(point.x() - grid_x)
            if dist_x < min_dist_x: min_dist_x = dist_x; snapped_x = grid_x
            grid_y = round(point.y() / self.grid_size) * self.grid_size; dist_y = abs(point.y() - grid_y)
            if dist_y < min_dist_y: min_dist_y = dist_y; snapped_y = grid_y
        for x_guide in self.vertical_guides:
            dist_x = abs(point.x() - x_guide)
            if dist_x < min_dist_x: min_dist_x = dist_x; snapped_x = x_guide
        for y_guide in self.horizontal_guides:
            dist_y = abs(point.y() - y_guide)
            if dist_y < min_dist_y: min_dist_y = dist_y; snapped_y = y_guide
        final_x = snapped_x if min_dist_x <= self.snap_threshold else point.x()
        final_y = snapped_y if min_dist_y <= self.snap_threshold else point.y()
        return QPoint(final_x, final_y)

    def toggle_guides(self, enabled): self.guides_enabled = enabled; self.update()
    def add_horizontal_guide(self, y):
        if y not in self.horizontal_guides: self.horizontal_guides.append(y); self.update()
    def add_vertical_guide(self, x):
        if x not in self.vertical_guides: self.vertical_guides.append(x); self.update()
    def draw_guides(self, painter):
        if not self.guides_enabled: return
        pen = QPen(QColor(0, 150, 255, 150), 1, Qt.PenStyle.DashLine); painter.setPen(pen)
        width, height = self.width(), self.height()
        for y in self.horizontal_guides: painter.drawLine(0, y, width, y)
        for x in self.vertical_guides: painter.drawLine(x, 0, x, height)
        
# --- END OF FILE canvas.py ---