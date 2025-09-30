# --- START OF FILE main.py ---

import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QToolBar, QColorDialog,
                             QSpinBox, QLabel, QFileDialog, QComboBox,
                             QFontComboBox, QWidgetAction)
from PyQt6.QtGui import QAction, QKeySequence, QIcon, QPalette, QColor, QBrush
from PyQt6.QtCore import Qt, QSize
from canvas import CanvasWidget
from layer_panel import LayerPanel

def resource_path(relative_path):
    """
    获取资源的绝对路径, 兼容开发模式和 PyInstaller 打包后的模式。
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        py_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.dirname(py_dir)
    return os.path.join(base_path, relative_path)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('我的绘图系统 - ShapePainter')
        self.setGeometry(200, 200, 1400, 800)
        self.canvas = CanvasWidget()
        self.setCentralWidget(self.canvas)

        # --- 菜单栏 ---
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("文件")
        edit_menu = menu_bar.addMenu("编辑")
        insert_menu = menu_bar.addMenu("插入")
        view_menu = menu_bar.addMenu("视图")
        export_menu = menu_bar.addMenu("导出")

        action_save = QAction("保存项目...", self)
        action_save.triggered.connect(self.canvas.save_shapes)
        file_menu.addAction(action_save)

        action_load = QAction("加载项目...", self)
        action_load.triggered.connect(self.canvas.load_shapes)
        file_menu.addAction(action_load)

        self.undo_action = QAction("撤销", self)
        self.undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        self.undo_action.triggered.connect(self.canvas.undo)
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction("重做", self)
        self.redo_action.setShortcut(QKeySequence("Ctrl+Y"))
        self.redo_action.triggered.connect(self.canvas.redo)
        edit_menu.addAction(self.redo_action)

        self.canvas.undo_stack_changed.connect(self.undo_action.setEnabled)
        self.canvas.redo_stack_changed.connect(self.redo_action.setEnabled)
        self.undo_action.setEnabled(False)
        self.redo_action.setEnabled(False)

        action_add_text = QAction("文本框", self)
        action_add_text.triggered.connect(self.add_text)
        insert_menu.addAction(action_add_text)
        insert_menu.addSeparator()

        font_combo_action = QWidgetAction(self)
        self.font_combo = QFontComboBox()
        self.font_combo.currentFontChanged.connect(self.canvas.set_font)
        font_combo_action.setDefaultWidget(self.font_combo)
        insert_menu.addAction(font_combo_action)

        font_size_action = QWidgetAction(self)
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(1, 200)
        self.font_size_spinbox.setValue(24)
        self.font_size_spinbox.setPrefix("字号: ")
        self.font_size_spinbox.valueChanged.connect(self.canvas.set_font_size)
        font_size_action.setDefaultWidget(self.font_size_spinbox)
        insert_menu.addAction(font_size_action)

        reset_ui_action = QAction("重置界面布局", self)
        reset_ui_action.triggered.connect(self.reset_ui_layout)
        view_menu.addAction(reset_ui_action)

        action_export_png = QAction("导出为PNG...", self)
        action_export_png.triggered.connect(self.canvas.export_as_png)
        export_menu.addAction(action_export_png)

        action_export_svg = QAction("导出为SVG...", self)
        action_export_svg.triggered.connect(self.canvas.export_as_svg)
        export_menu.addAction(action_export_svg)

        # --- 工具栏 ---
        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks | QMainWindow.DockOption.AllowNestedDocks)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.draw_toolbar = QToolBar("绘图工具")
        self.draw_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.draw_toolbar)
        self.edit_attr_toolbar = QToolBar("功能与属性")
        self.edit_attr_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.edit_attr_toolbar)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)

        def create_action_with_icon(icon_name, text, parent):
            path = resource_path(os.path.join('icons', icon_name))
            if os.path.exists(path):
                return QAction(QIcon(path), text, parent)
            else:
                print(f"Warning: Icon not found at '{path}'")
                return QAction(text, parent)

        action_freehand = create_action_with_icon("draw.svg", "手绘", self); action_freehand.triggered.connect(lambda: self.canvas.set_tool("freehand")); self.draw_toolbar.addAction(action_freehand)
        self.draw_toolbar.addSeparator()
        action_point = create_action_with_icon("point.svg", "画点", self); action_point.triggered.connect(lambda: self.canvas.set_tool("point")); self.draw_toolbar.addAction(action_point)
        action_line = create_action_with_icon("remove.svg", "画直线", self); action_line.triggered.connect(lambda: self.canvas.set_tool("line")); self.draw_toolbar.addAction(action_line)
        action_arrow = create_action_with_icon("arrow.svg", "箭头", self); action_arrow.triggered.connect(lambda: self.canvas.set_tool("arrow")); self.draw_toolbar.addAction(action_arrow)
        action_rect = create_action_with_icon("rectangle.svg", "画矩形", self); action_rect.triggered.connect(lambda: self.canvas.set_tool("rect")); self.draw_toolbar.addAction(action_rect)
        action_square = create_action_with_icon("square.svg", "画正方形", self); action_square.triggered.connect(lambda: self.canvas.set_tool("square")); self.draw_toolbar.addAction(action_square)
        action_circle = create_action_with_icon("circle.svg", "画圆形", self); action_circle.triggered.connect(lambda: self.canvas.set_tool("circle")); self.draw_toolbar.addAction(action_circle)
        action_ellipse = create_action_with_icon("ellipse.svg", "画椭圆", self); action_ellipse.triggered.connect(lambda: self.canvas.set_tool("ellipse")); self.draw_toolbar.addAction(action_ellipse)
        action_rounded_rect = create_action_with_icon("rounded rectangle.svg", "画圆角矩形", self); action_rounded_rect.triggered.connect(lambda: self.canvas.set_tool("rounded_rect")); self.draw_toolbar.addAction(action_rounded_rect)
        action_polygon = create_action_with_icon("pentagon.svg", "画多边形", self); action_polygon.triggered.connect(lambda: self.canvas.set_tool("polygon")); self.draw_toolbar.addAction(action_polygon)
        action_polyline = create_action_with_icon("polyline.svg", "画折线", self); action_polyline.triggered.connect(lambda: self.canvas.set_tool("polyline")); self.draw_toolbar.addAction(action_polyline)
        action_arc = create_action_with_icon("line_curve.svg", "画弧形", self); action_arc.triggered.connect(lambda: self.canvas.set_tool("arc")); self.draw_toolbar.addAction(action_arc)
        
        action_select = create_action_with_icon("mouse pointer.svg", "选择", self); action_select.triggered.connect(lambda: self.canvas.set_tool("select")); self.edit_attr_toolbar.addAction(action_select)
        action_eraser = create_action_with_icon("eraser.svg", "橡皮擦", self); action_eraser.triggered.connect(lambda: self.canvas.set_tool("eraser")); self.edit_attr_toolbar.addAction(action_eraser)
        action_clear = create_action_with_icon("clear all.svg", "清空", self); action_clear.triggered.connect(self.canvas.clear_canvas); self.edit_attr_toolbar.addAction(action_clear)
        self.edit_attr_toolbar.addSeparator()

        action_group = QAction("组合", self); action_group.setShortcut(QKeySequence("Ctrl+G")); action_group.triggered.connect(self.canvas.group_selected); self.edit_attr_toolbar.addAction(action_group)
        action_ungroup = QAction("解组", self); action_ungroup.setShortcut(QKeySequence("Ctrl+Shift+G")); action_ungroup.triggered.connect(self.canvas.ungroup_selected); self.edit_attr_toolbar.addAction(action_ungroup)
        self.edit_attr_toolbar.addSeparator()

        action_pen_color = create_action_with_icon("format_color_text.svg", "边框色", self); action_pen_color.triggered.connect(self.show_pen_color_dialog); self.edit_attr_toolbar.addAction(action_pen_color)
        action_fill_color = create_action_with_icon("palette.svg", "填充色", self); action_fill_color.triggered.connect(self.show_fill_color_dialog); self.edit_attr_toolbar.addAction(action_fill_color)
        action_no_fill = create_action_with_icon("format_color_reset.svg", "无填充", self); action_no_fill.triggered.connect(self.canvas.set_no_fill); self.edit_attr_toolbar.addAction(action_no_fill)
        
        action_paint_bucket = create_action_with_icon("paint_bucket.svg", "颜料桶", self)
        action_paint_bucket.triggered.connect(lambda: self.canvas.set_tool("paint_bucket"))
        self.edit_attr_toolbar.addAction(action_paint_bucket)
        
        self.edit_attr_toolbar.addSeparator()
        self.edit_attr_toolbar.addWidget(QLabel("填充:"))
        self.combo_fill_style = QComboBox()
        self.fill_styles = {
            "无": Qt.BrushStyle.NoBrush, "纯色": Qt.BrushStyle.SolidPattern,
            "水平": Qt.BrushStyle.HorPattern, "垂直": Qt.BrushStyle.VerPattern,
            "交叉": Qt.BrushStyle.CrossPattern, "斜线": Qt.BrushStyle.BDiagPattern,
            "反斜": Qt.BrushStyle.FDiagPattern, "斜叉": Qt.BrushStyle.DiagCrossPattern,
            "点1": Qt.BrushStyle.Dense1Pattern, "点2": Qt.BrushStyle.Dense4Pattern,
            "点3": Qt.BrushStyle.Dense7Pattern,
        }
        for name, style in self.fill_styles.items():
            self.combo_fill_style.addItem(name, style)
        self.combo_fill_style.activated.connect(self.on_fill_style_changed)
        self.edit_attr_toolbar.addWidget(self.combo_fill_style)
        self.edit_attr_toolbar.addSeparator()

        self.edit_attr_toolbar.addWidget(QLabel("线宽:"))
        self.spinbox_width = QSpinBox()
        self.spinbox_width.setRange(1, 100)
        self.spinbox_width.setValue(2)
        self.spinbox_width.valueChanged.connect(self.canvas.set_pen_width)
        self.edit_attr_toolbar.addWidget(self.spinbox_width)

        # --- 其他 ---
        self.layer_panel = LayerPanel(self); self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.layer_panel)
        self.layer_panel.add_button.clicked.connect(self.canvas.add_layer)
        self.layer_panel.remove_button.clicked.connect(self.canvas.remove_current_layer)
        self.layer_panel.up_button.clicked.connect(self.canvas.move_layer_up)
        self.layer_panel.down_button.clicked.connect(self.canvas.move_layer_down)
        self.layer_panel.list_widget.currentRowChanged.connect(self.canvas.set_current_layer)
        self.canvas.layers_changed.connect(self.layer_panel.update_layer_list)
        self.canvas.initialize_layers()
        self.status_bar = self.statusBar(); self.mouse_pos_label = QLabel("坐标: (0, 0)"); self.status_bar.addPermanentWidget(self.mouse_pos_label)
        self.canvas.mouse_moved_signal.connect(self.update_mouse_pos)

    def reset_ui_layout(self):
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.draw_toolbar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.edit_attr_toolbar)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.layer_panel)
        self.layer_panel.setFloating(False)
        for toolbar in self.findChildren(QToolBar):
            toolbar.show()

    def show_pen_color_dialog(self):
        color = QColorDialog.getColor(self.canvas.current_pen_color, self, "选择边框/文字颜色")
        if color.isValid():
            self.canvas.set_pen_color(color)

    def show_fill_color_dialog(self):
        initial_color = self.canvas.current_fill_color if self.canvas.current_fill_color else Qt.GlobalColor.white
        color = QColorDialog.getColor(initial_color, self, "选择填充颜色")
        if color.isValid():
            self.canvas.set_fill_color(color)

    def on_fill_style_changed(self, index):
        style = self.combo_fill_style.itemData(index)
        self.canvas.set_fill_style(style)

    def add_text(self):
        self.canvas.set_tool("text")

    def update_mouse_pos(self, pos):
        self.mouse_pos_label.setText(f"坐标: ({pos.x()}, {pos.y()})")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    app.setStyle("Fusion")
    
    light_palette = QPalette()
    light_palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    light_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
    light_palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
    light_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(233, 233, 233))
    light_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    light_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
    light_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
    light_palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    light_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
    light_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    light_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    light_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    light_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
    app.setPalette(light_palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())