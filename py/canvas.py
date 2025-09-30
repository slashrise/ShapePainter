# --- START OF FILE canvas.py ---

from PyQt6.QtWidgets import QWidget, QFileDialog, QMenu, QColorDialog, QTextEdit, QFontDialog, QApplication
from PyQt6.QtGui import QPainter, QColor, QPixmap, QAction, QFont, QBrush
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtSvg import QSvgGenerator

from shapes import *
from commands import *
from file_handler import ProjectHandler
from renderer import CanvasRenderer
from tools import *

class CanvasWidget(QWidget):
    undo_stack_changed = pyqtSignal(bool)
    redo_stack_changed = pyqtSignal(bool)
    layers_changed = pyqtSignal(list, int)
    mouse_moved_signal = pyqtSignal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        
        self.layers, self.current_layer_index = [], -1
        self.undo_stack, self.redo_stack = [], []
        self.selected_shapes = []
        self.current_pen_color = QColor(0, 0, 0)
        self.current_width = 2
        self.current_fill_color = None
        self.current_fill_style = Qt.BrushStyle.NoBrush
        self.current_font = QFont("Arial", 24)
        self.editing_shape = None
        self.text_editor = None
        self.tools = {
            "select": SelectTool(self),
            "point": PointTool(self),
            "line": LineTool(self),
            "arrow": ArrowTool(self),
            "rect": RectangleTool(self),
            "square": SquareTool(self),
            "circle": CircleTool(self),
            "ellipse": EllipseTool(self),
            "rounded_rect": RoundedRectangleTool(self),
            "text": TextTool(self),
            "polyline": PolylineTool(self),
            "polygon": PolygonTool(self),
            "arc": ArcTool(self),
            "freehand": FreehandTool(self),
            "eraser": EraserTool(self),
            "paint_bucket": PaintBucketTool(self),
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
        if self.current_tool_obj:
            self.current_tool_obj.deactivate()
        if tool_name in self.tools:
            self.current_tool_obj = self.tools[tool_name]
            self.current_tool_obj.activate()

    def set_pen_color(self, color):
        if color.isValid():
            self.current_pen_color = color

    def set_fill_color(self, color):
        if color.isValid():
            self.current_fill_color = color

    def set_no_fill(self):
        self.current_fill_style = Qt.BrushStyle.NoBrush
        self.current_fill_color = None
        self.update()

    def set_fill_style(self, style):
        self.current_fill_style = style
        if style != Qt.BrushStyle.NoBrush and self.current_fill_color is None:
            self.current_fill_color = QColor(0, 0, 0)

    def set_pen_width(self, width):
        self.current_width = width

    def set_font(self, font):
        self.current_font = font

    def set_font_size(self, size):
        self.current_font.setPointSize(size)

    def initialize_layers(self):
        self.add_layer("背景")

    def get_current_layer(self):
        if 0 <= self.current_layer_index < len(self.layers):
            return self.layers[self.current_layer_index]
        return None

    def add_layer(self, name=None):
        if name is None:
            name = f"图层 {len(self.layers) + 1}"
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
            if hasattr(self.current_tool_obj, 'deactivate'):
                self.current_tool_obj.deactivate()
                self.current_tool_obj.activate()
            self.layers_changed.emit(self.layers, self.current_layer_index)
            self.update()

    def rename_layer(self, index, new_name):
        if 0 <= index < len(self.layers) and new_name:
            layer_to_rename = self.layers[index]
            if new_name != layer_to_rename.name:
                command = ChangePropertiesCommand([layer_to_rename], {'name': new_name})
                self.execute_command(command)
                self.layers_changed.emit(self.layers, self.current_layer_index)

    def save_shapes(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "保存项目", "", "JSON Files (*.json)")
        if file_path:
            ProjectHandler.save(self.layers, file_path)

    def load_shapes(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "加载项目", "", "JSON Files (*.json)")
        if file_path:
            self.layers = ProjectHandler.load(file_path)
            self.set_current_layer(0)
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.update_stacks_and_canvas()

    def export_as_png(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "导出为PNG", "", "PNG Files (*.png)")
        if file_path:
            pixmap = QPixmap(self.size())
            pixmap.fill(Qt.GlobalColor.white)
            original_tool = self.current_tool_obj
            self.current_tool_obj = Tool(self)
            painter = QPainter(pixmap)
            CanvasRenderer.paint(painter, self)
            painter.end()
            self.current_tool_obj = original_tool
            pixmap.save(file_path, "PNG")

    def export_as_svg(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "导出为SVG", "", "SVG Files (*.svg)")
        if not file_path:
            return
        generator = QSvgGenerator()
        generator.setFileName(file_path)
        generator.setSize(self.size())
        generator.setViewBox(self.rect())
        generator.setTitle("ShapePainter Export")
        generator.setDescription("Generated by ShapePainter.")
        painter = QPainter(generator)
        original_tool = self.current_tool_obj
        self.current_tool_obj = Tool(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        CanvasRenderer.paint(painter, self)
        painter.end()
        self.current_tool_obj = original_tool

    def clear_canvas(self):
        current_layer = self.get_current_layer()
        if current_layer and not current_layer.is_locked and current_layer.shapes:
            command = RemoveShapesCommand(current_layer, current_layer.shapes)
            self.execute_command(command)
            if hasattr(self.current_tool_obj, 'node_editing_active'):
                self.current_tool_obj.node_editing_active = False

    def group_selected(self):
        current_layer = self.get_current_layer()
        if current_layer and not current_layer.is_locked and len(self.selected_shapes) > 1:
            command = GroupCommand(current_layer, self.selected_shapes)
            self.execute_command(command)
            self.selected_shapes = [command.group]
            self.update()

    def ungroup_selected(self):
        current_layer = self.get_current_layer()
        if not current_layer or current_layer.is_locked:
            return
        groups_in_selection = [s for s in self.selected_shapes if isinstance(s, ShapeGroup)]
        if groups_in_selection:
            newly_ungrouped_shapes = []
            for group in groups_in_selection:
                command = UngroupCommand(current_layer, group)
                self.execute_command(command)
                newly_ungrouped_shapes.extend(command.shapes_inside)
            remaining_selection = [s for s in self.selected_shapes if not isinstance(s, ShapeGroup)]
            self.selected_shapes = remaining_selection + newly_ungrouped_shapes
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        CanvasRenderer.paint(painter, self)

    def mousePressEvent(self, event):
        self._finish_text_editing()
        if self.current_tool_obj:
            self.current_tool_obj.mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self.mouse_moved_signal.emit(event.pos())
        if self.current_tool_obj:
            self.current_tool_obj.mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.current_tool_obj:
            self.current_tool_obj.mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        shape_clicked, layer_of_shape = self._get_shape_at(event.pos())
        if shape_clicked and isinstance(shape_clicked, Text) and layer_of_shape and not layer_of_shape.is_locked:
            self._start_text_editing(shape_clicked)
        elif self.current_tool_obj:
            self.current_tool_obj.mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if self.current_tool_obj:
            self.current_tool_obj.keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        if isinstance(self.current_tool_obj, SelectTool) and self.selected_shapes:
            menu = QMenu(self)
            menu.setStyleSheet("QMenu::item:selected { background-color: #0078d7; color: white; }")
            delete_action = QAction("删除", self)
            delete_action.triggered.connect(self.delete_selected)
            menu.addAction(delete_action)
            
            has_text = any(isinstance(s, Text) for s in self.selected_shapes)
            has_other_shapes = any(not isinstance(s, Text) for s in self.selected_shapes)
            has_fillable = any(hasattr(s, 'fill_color') for s in self.selected_shapes)
            
            if has_text:
                change_text_color_action = QAction("修改文字颜色", self); change_text_color_action.triggered.connect(self.change_selected_text_color); menu.addAction(change_text_color_action)
                change_font_action = QAction("修改字体...", self); change_font_action.triggered.connect(self.change_selected_font); menu.addAction(change_font_action)
                menu.addSeparator(); toggle_border_action = QAction("显示边框", self); toggle_border_action.setCheckable(True)
                if all(s.has_border for s in self.selected_shapes if isinstance(s, Text)):
                    toggle_border_action.setChecked(True)
                toggle_border_action.triggered.connect(self.toggle_selected_text_border); menu.addAction(toggle_border_action)
                if any(s.has_border for s in self.selected_shapes if isinstance(s, Text)):
                    change_border_color_action = QAction("修改文本框边框颜色", self); change_border_color_action.triggered.connect(self.change_selected_text_border_color); menu.addAction(change_border_color_action)
            if has_other_shapes:
                change_pen_color_action = QAction("修改图形边框颜色", self); change_pen_color_action.triggered.connect(self.change_selected_pen_color); menu.addAction(change_pen_color_action)
            if has_fillable:
                menu.addSeparator()
                change_fill_color_action = QAction("修改填充颜色", self); change_fill_color_action.triggered.connect(self.change_selected_fill_color); menu.addAction(change_fill_color_action)
                fill_style_menu = menu.addMenu("修改填充方式"); main_window = self.window()
                if hasattr(main_window, 'fill_styles'):
                    for name, style in main_window.fill_styles.items():
                        action = QAction(name, self); action.triggered.connect(lambda checked=False, s=style: self.change_selected_fill_style(s)); fill_style_menu.addAction(action)
            menu.exec(event.globalPos()); self.setFocus()

    def delete_selected(self):
        if self.selected_shapes:
            shapes_by_layer = {}
            for shape in self.selected_shapes:
                layer = self._get_layer_for_shape(shape)
                if layer and not layer.is_locked:
                    if layer not in shapes_by_layer:
                        shapes_by_layer[layer] = []
                    shapes_by_layer[layer].append(shape)
            for layer, shapes_in_layer in shapes_by_layer.items():
                command = RemoveShapesCommand(layer, shapes_in_layer)
                self.execute_command(command)
            self.selected_shapes.clear()
            if hasattr(self.current_tool_obj, 'node_editing_active'):
                self.current_tool_obj.node_editing_active = False
            self.update()

    def change_selected_pen_color(self):
        if self.selected_shapes:
            color = QColorDialog.getColor(self.selected_shapes[0].color, self, "选择边框颜色")
            if color.isValid():
                command = ChangePropertiesCommand(self.selected_shapes, {'color': color})
                self.execute_command(command)

    def change_selected_text_color(self):
        text_shapes = [s for s in self.selected_shapes if isinstance(s, Text)]
        if text_shapes:
            color = QColorDialog.getColor(text_shapes[0].color, self, "选择文字颜色")
            if color.isValid():
                command = ChangePropertiesCommand(text_shapes, {'color': color})
                self.execute_command(command)

    def change_selected_text_border_color(self):
        text_shapes = [s for s in self.selected_shapes if isinstance(s, Text) and s.has_border]
        if text_shapes:
            color = QColorDialog.getColor(text_shapes[0].border_color, self, "选择文本框边框颜色")
            if color.isValid():
                command = ChangePropertiesCommand(text_shapes, {'border_color': color})
                self.execute_command(command)

    def change_selected_fill_color(self):
        fillable_shapes = [s for s in self.selected_shapes if hasattr(s, 'fill_color')]
        if fillable_shapes:
            initial_color = next((s.fill_color for s in fillable_shapes if s.fill_color), Qt.GlobalColor.white)
            color = QColorDialog.getColor(initial_color, self, "选择填充颜色")
            if color.isValid():
                command = ChangePropertiesCommand(fillable_shapes, {'fill_color': color, 'fill_style': Qt.BrushStyle.SolidPattern})
                self.execute_command(command)

    def change_selected_fill_style(self, style):
        fillable_shapes = [s for s in self.selected_shapes if hasattr(s, 'fill_color')]
        if fillable_shapes:
            props = {'fill_style': style}
            if style == Qt.BrushStyle.NoBrush:
                props['fill_color'] = None
            else:
                current_color = next((s.fill_color for s in fillable_shapes if s.fill_color), None)
                if not current_color:
                    props['fill_color'] = QColor(0,0,0)
            command = ChangePropertiesCommand(fillable_shapes, props)
            self.execute_command(command)

    def change_selected_font(self):
        text_shapes = [s for s in self.selected_shapes if isinstance(s, Text)]
        if not text_shapes:
            return
        font, ok = QFontDialog.getFont(text_shapes[0].font, self, "选择字体")
        if ok:
            command = ChangePropertiesCommand(text_shapes, {'font': font})
            self.execute_command(command)

    def toggle_selected_text_border(self, checked):
        text_shapes = [s for s in self.selected_shapes if isinstance(s, Text)]
        if text_shapes:
            command = ChangePropertiesCommand(text_shapes, {'has_border': checked})
            self.execute_command(command)

    def start_text_editing_on_creation(self, text_shape):
        command = AddShapeCommand(self.get_current_layer(), text_shape)
        self.execute_command(command)
        self._start_text_editing(text_shape)

    def _start_text_editing(self, text_shape):
        if self.text_editor:
            self._finish_text_editing()
        self.editing_shape = text_shape
        self.text_editor = QTextEdit(self)
        self.text_editor.setText(self.editing_shape.text)
        self.text_editor.setFont(self.editing_shape.font)
        self.text_editor.setStyleSheet(f"QTextEdit {{ background-color: rgba(255, 255, 255, 0.9); border: 1px solid #0078d7; color: {text_shape.color.name()}; }}")
        self.text_editor.setGeometry(text_shape.get_bounding_box())
        self.text_editor.installEventFilter(self)
        self.text_editor.show()
        self.text_editor.setFocus()
        self.update()

    def _finish_text_editing(self):
        if self.text_editor and self.editing_shape:
            new_text = self.text_editor.toPlainText()
            if new_text != self.editing_shape.text:
                command = ChangePropertiesCommand([self.editing_shape], {'text': new_text})
                self.execute_command(command)
            self.text_editor.deleteLater()
            self.text_editor = None
            self.editing_shape = None
            self.update()

    def eventFilter(self, obj, event):
        if obj is self.text_editor and event.type() == event.Type.FocusOut:
            self._finish_text_editing()
            return True
        return super().eventFilter(obj, event)

    def _get_selection_bbox(self):
        if not self.selected_shapes:
            return QRect()
        total_bbox = self.selected_shapes[0].get_bounding_box()
        for shape in self.selected_shapes[1:]:
            total_bbox = total_bbox.united(shape.get_bounding_box())
        return total_bbox

    def _get_layer_for_shape(self, shape_to_find):
        for layer in self.layers:
            if shape_to_find in layer.shapes or (isinstance(shape_to_find, ShapeGroup) and shape_to_find in layer.shapes):
                return layer
        return None

    def _get_shape_at(self, pos):
        for layer in self.layers:
            if not layer.is_visible:
                continue
            for shape in reversed(layer.shapes):
                if shape.get_bounding_box().contains(pos):
                    return shape, layer
        return None, None

    def _draw_arrow(self, painter, p1, p2, color, width):
        CanvasRenderer.draw_arrow(painter, p1, p2, color, width)