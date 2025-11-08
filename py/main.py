import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QToolBar, QColorDialog,
                             QSpinBox, QLabel, QFileDialog, QComboBox,
                             QFontComboBox, QWidgetAction, QDialog, QMessageBox,
                             QVBoxLayout, QTextBrowser, QCheckBox)
from PyQt6.QtGui import QAction, QKeySequence, QIcon, QPalette, QColor, QBrush, QFont
from PyQt6.QtCore import Qt, QSize, QTimer
from canvas import CanvasWidget
from layer_panel import LayerPanel
from rulers import CanvasView
from settings_manager import SettingsManager
from preferences_dialog import PreferencesDialog
from shapes import Text, Path
from tools import PenTool

def resource_path(relative_path):
    """
    获取资源的绝对路径, 兼容开发模式和 PyInstaller 打包后的模式。
    这是一个健壮的最终版本。
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # 如果是 PyInstaller 打包后的 .exe
        # 此时，资源文件与可执行文件在同一个临时目录 _MEIPASS 下
        base_path = sys._MEIPASS
    else:
        # 如果是在开发环境中运行 .py
        # __file__ 指向当前脚本 (e.g., .../ShapePainter/py/main.py)
        # 我们需要的是项目根目录 (ShapePainter)
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class MainWindow(QMainWindow):
    def __init__(self, settings):
        super().__init__()
        self.setWindowTitle('我的绘图系统 - ShapePainter')
        self.setGeometry(200, 200, 1400, 800)

        # 🔴 核心修改：简化图标路径调用
        app_icon_path = resource_path("icons/mouse pointer.svg")
        if os.path.exists(app_icon_path):
            self.setWindowIcon(QIcon(app_icon_path))

        self.settings = settings
        self.settings_manager = SettingsManager()
        self.canvas = CanvasWidget(settings=self.settings)
        self.canvas_view = CanvasView(self.canvas)
        self.setCentralWidget(self.canvas_view)

        self._create_menus()
        self._create_toolbars()
        self._connect_signals()
        self._create_docks_and_statusbar()
        self._apply_initial_settings()
        self.canvas.set_raster_algorithm(self.algo_combo.currentText())
        
        if self.settings.get("show_manual_on_startup", True):
            QTimer.singleShot(0, lambda: self.show_user_manual(is_startup=True))


    def _create_menus(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("文件")
        edit_menu = menu_bar.addMenu("编辑")
        insert_menu = menu_bar.addMenu("插入")
        view_menu = menu_bar.addMenu("视图")
        export_menu = menu_bar.addMenu("导出")
        help_menu = menu_bar.addMenu("帮助")

        action_save = QAction("保存项目...", self)
        action_save.triggered.connect(self.canvas.save_shapes)
        file_menu.addAction(action_save)

        action_load = QAction("加载项目...", self)
        action_load.triggered.connect(self.canvas.load_shapes)
        file_menu.addAction(action_load)

        self.undo_action = QAction("撤销", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self.smart_undo)
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction("重做", self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.triggered.connect(self.canvas.redo)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()

        self.copy_action = QAction("复制", self)
        self.copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.copy_action.triggered.connect(self.canvas.copy_selected)
        edit_menu.addAction(self.copy_action)

        self.paste_action = QAction("粘贴", self)
        self.paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        self.paste_action.triggered.connect(self.canvas.paste)
        edit_menu.addAction(self.paste_action)

        self.paste_in_place_action = QAction("原位粘贴", self)
        self.paste_in_place_action.setShortcut("Ctrl+Shift+V")
        self.paste_in_place_action.triggered.connect(self.canvas.paste_in_place)
        edit_menu.addAction(self.paste_in_place_action)

        edit_menu.addSeparator()
        action_prefs = QAction("偏好设置...", self)
        action_prefs.triggered.connect(self.open_preferences_dialog)
        edit_menu.addAction(action_prefs)

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
        self.font_size_spinbox.setPrefix("字号: ")
        self.font_size_spinbox.valueChanged.connect(self.canvas.set_font_size)
        font_size_action.setDefaultWidget(self.font_size_spinbox)
        insert_menu.addAction(font_size_action)

        reset_ui_action = QAction("重置界面布局", self)
        reset_ui_action.triggered.connect(self.reset_ui_layout)
        view_menu.addAction(reset_ui_action)
        view_menu.addSeparator()

        self.show_grid_action = QAction("显示网格", self)
        self.show_grid_action.setCheckable(True)
        self.show_grid_action.toggled.connect(self.canvas.toggle_grid)
        view_menu.addAction(self.show_grid_action)

        self.show_guides_action = QAction("显示参考线", self)
        self.show_guides_action.setCheckable(True)
        self.show_guides_action.setChecked(True)
        self.show_guides_action.toggled.connect(self.canvas.toggle_guides)
        view_menu.addAction(self.show_guides_action)

        self.snap_to_grid_action = QAction("吸附", self)
        self.snap_to_grid_action.setCheckable(True)
        self.snap_to_grid_action.toggled.connect(self.canvas.toggle_snapping)
        view_menu.addAction(self.snap_to_grid_action)

        view_menu.addSeparator() # 添加一个分隔线

        self.ssaa_action = QAction("启用抗锯齿 (SSAA)", self)
        self.ssaa_action.setCheckable(True)
        self.ssaa_action.setChecked(True) # 默认开启
        self.ssaa_action.toggled.connect(self.canvas.toggle_ssaa)
        view_menu.addAction(self.ssaa_action)

        action_export_png = QAction("导出为PNG...", self)
        action_export_png.triggered.connect(self.canvas.export_as_png)
        export_menu.addAction(action_export_png)

        action_export_svg = QAction("导出为SVG...", self)
        action_export_svg.triggered.connect(self.canvas.export_as_svg)
        export_menu.addAction(action_export_svg)

        action_show_manual = QAction("查看用户手册...", self)
        action_show_manual.triggered.connect(self.show_user_manual)
        help_menu.addAction(action_show_manual)

        

    def _create_toolbars(self):
        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks | QMainWindow.DockOption.AllowNestedDocks)

        # --- 1. 创建工具栏实例 ---
        self.draw_toolbar = QToolBar("绘图工具")
        self.draw_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.draw_toolbar)
        self.draw_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        self.edit_attr_toolbar = QToolBar("功能与属性")
        self.edit_attr_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.edit_attr_toolbar)
        self.edit_attr_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

        self.align_toolbar = QToolBar("对齐")
        self.align_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.align_toolbar)
        self.align_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

        self.text_format_toolbar = QToolBar("文本格式")
        self.text_format_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.text_format_toolbar)
        self.text_format_toolbar.setVisible(False)

        # --- 2. 创建一个辅助函数来加载图标 ---
        def create_action_with_icon(icon_name, text, parent, tooltip=None):
            path = resource_path(os.path.join("icons", icon_name))
            action = QAction(text, parent)
            if os.path.exists(path):
                action.setIcon(QIcon(path))
            else:
                print(f"Warning: Icon not found at '{path}'")
            action.setToolTip(tooltip or text)
            return action

        # --- 3. 向【绘图工具栏】添加动作 ---
        action_select = create_action_with_icon("mouse pointer.svg", "选择", self)
        action_select.triggered.connect(lambda: self.canvas.set_tool("select"))
        self.draw_toolbar.addAction(action_select)
        
        self.draw_toolbar.addSeparator()

        action_pen = create_action_with_icon("line_curve.svg", "贝塞尔曲线", self)
        action_pen.triggered.connect(lambda: self.canvas.set_tool("pen"))
        self.draw_toolbar.addAction(action_pen)

        action_freehand = create_action_with_icon("draw.svg", "手绘", self)
        action_freehand.triggered.connect(lambda: self.canvas.set_tool("freehand"))
        self.draw_toolbar.addAction(action_freehand)
        
        self.draw_toolbar.addSeparator()

        action_point = create_action_with_icon("point.svg", "画点", self)
        action_point.triggered.connect(lambda: self.canvas.set_tool("point"))
        self.draw_toolbar.addAction(action_point)

        action_line = create_action_with_icon("remove.svg", "画直线", self)
        action_line.triggered.connect(lambda: self.canvas.set_tool("line"))
        self.draw_toolbar.addAction(action_line)
        
        action_arrow = create_action_with_icon("arrow.svg", "箭头", self)
        action_arrow.triggered.connect(lambda: self.canvas.set_tool("arrow"))
        self.draw_toolbar.addAction(action_arrow)
        
        action_rect = create_action_with_icon("rectangle.svg", "画矩形", self)
        action_rect.triggered.connect(lambda: self.canvas.set_tool("rect"))
        self.draw_toolbar.addAction(action_rect)
        
        action_square = create_action_with_icon("square.svg", "画正方形", self)
        action_square.triggered.connect(lambda: self.canvas.set_tool("square"))
        self.draw_toolbar.addAction(action_square)
        
        action_circle = create_action_with_icon("circle.svg", "画圆形", self)
        action_circle.triggered.connect(lambda: self.canvas.set_tool("circle"))
        self.draw_toolbar.addAction(action_circle)
        
        action_ellipse = create_action_with_icon("ellipse.svg", "画椭圆", self)
        action_ellipse.triggered.connect(lambda: self.canvas.set_tool("ellipse"))
        self.draw_toolbar.addAction(action_ellipse)
        
        action_rounded_rect = create_action_with_icon("rounded rectangle.svg", "画圆角矩形", self)
        action_rounded_rect.triggered.connect(lambda: self.canvas.set_tool("rounded_rect"))
        self.draw_toolbar.addAction(action_rounded_rect)
        
        action_polygon = create_action_with_icon("pentagon.svg", "画多边形", self)
        action_polygon.triggered.connect(lambda: self.canvas.set_tool("polygon"))
        self.draw_toolbar.addAction(action_polygon)
        
        action_polyline = create_action_with_icon("polyline.svg", "画折线", self)
        action_polyline.triggered.connect(lambda: self.canvas.set_tool("polyline"))
        self.draw_toolbar.addAction(action_polyline)
        
        # --- 4. 向【功能与属性工具栏】添加动作 ---
        action_eraser = create_action_with_icon("eraser.svg", "橡皮擦", self)
        action_eraser.triggered.connect(lambda: self.canvas.set_tool("eraser"))
        self.edit_attr_toolbar.addAction(action_eraser)

        action_clear = create_action_with_icon("clear all.svg", "清空", self)
        action_clear.triggered.connect(self.canvas.clear_canvas)
        self.edit_attr_toolbar.addAction(action_clear)
        
        self.edit_attr_toolbar.addSeparator()
        
        action_group = QAction("组合", self)
        action_group.setShortcut("Ctrl+G")
        action_group.triggered.connect(self.canvas.group_selected)
        self.edit_attr_toolbar.addAction(action_group)
        
        action_ungroup = QAction("解组", self)
        action_ungroup.setShortcut("Ctrl+Shift+G")
        action_ungroup.triggered.connect(self.canvas.ungroup_selected)
        self.edit_attr_toolbar.addAction(action_ungroup)
        
        self.edit_attr_toolbar.addSeparator()
        
        action_pen_color = create_action_with_icon("format_color_text.svg", "边框色", self)
        action_pen_color.triggered.connect(self.show_pen_color_dialog)
        self.edit_attr_toolbar.addAction(action_pen_color)
        
        action_fill_color = create_action_with_icon("palette.svg", "填充色", self)
        action_fill_color.triggered.connect(self.show_fill_color_dialog)
        self.edit_attr_toolbar.addAction(action_fill_color)
        
        action_canvas_color = create_action_with_icon("background.svg", "画布颜色", self)
        action_canvas_color.triggered.connect(self.show_canvas_color_dialog)
        self.edit_attr_toolbar.addAction(action_canvas_color)
        
        action_no_fill = create_action_with_icon("format_color_reset.svg", "无填充", self)
        action_no_fill.triggered.connect(self.canvas.set_no_fill)
        self.edit_attr_toolbar.addAction(action_no_fill)
        
        action_paint_bucket = create_action_with_icon("paint_bucket.svg", "颜料桶", self)
        action_paint_bucket.triggered.connect(lambda: self.canvas.set_tool("paint_bucket"))
        self.edit_attr_toolbar.addAction(action_paint_bucket)
        
        self.edit_attr_toolbar.addSeparator()
        
        self.edit_attr_toolbar.addWidget(QLabel("填充:"))
        self.combo_fill_style = QComboBox()
        self.fill_styles = {
            "无": Qt.BrushStyle.NoBrush, "纯色": Qt.BrushStyle.SolidPattern, "水平": Qt.BrushStyle.HorPattern,
            "垂直": Qt.BrushStyle.VerPattern, "交叉": Qt.BrushStyle.CrossPattern, "斜线": Qt.BrushStyle.BDiagPattern,
            "反斜": Qt.BrushStyle.FDiagPattern, "斜叉": Qt.BrushStyle.DiagCrossPattern, "点1": Qt.BrushStyle.Dense1Pattern,
            "点2": Qt.BrushStyle.Dense4Pattern, "点3": Qt.BrushStyle.Dense7Pattern,
        }
        for name, style in self.fill_styles.items():
            self.combo_fill_style.addItem(name, style)
        self.combo_fill_style.activated.connect(self.on_fill_style_changed)
        self.edit_attr_toolbar.addWidget(self.combo_fill_style)
        
        self.edit_attr_toolbar.addSeparator()
        
        self.edit_attr_toolbar.addWidget(QLabel("线宽:"))
        self.spinbox_width = QSpinBox()
        self.spinbox_width.setRange(1, 100)
        self.spinbox_width.valueChanged.connect(self.canvas.set_pen_width)
        self.edit_attr_toolbar.addWidget(self.spinbox_width)
        
        # --- 🔴 新增：添加算法选择的下拉菜单 ---
        self.edit_attr_toolbar.addSeparator()
        self.edit_attr_toolbar.addWidget(QLabel("直线算法:"))
        self.algo_combo = QComboBox()
        self.algo_combo.addItems(["Bresenham", "DDA", "PyQt原生"])
        self.algo_combo.currentTextChanged.connect(self.canvas.set_raster_algorithm)
        self.edit_attr_toolbar.addWidget(self.algo_combo)
        
        # --- 5. 向【对齐工具栏】添加动作 ---
        action_align_left = create_action_with_icon("align_left.svg", "左对齐", self)
        action_align_left.triggered.connect(lambda: self.canvas.align_selected_shapes('left'))
        self.align_toolbar.addAction(action_align_left)
        
        action_align_center_h = create_action_with_icon("align_center_h.svg", "水平居中", self)
        action_align_center_h.triggered.connect(lambda: self.canvas.align_selected_shapes('center_h'))
        self.align_toolbar.addAction(action_align_center_h)
        
        action_align_right = create_action_with_icon("align_right.svg", "右对齐", self)
        action_align_right.triggered.connect(lambda: self.canvas.align_selected_shapes('right'))
        self.align_toolbar.addAction(action_align_right)
        
        self.align_toolbar.addSeparator()
        
        action_align_top = create_action_with_icon("align_top.svg", "顶对齐", self)
        action_align_top.triggered.connect(lambda: self.canvas.align_selected_shapes('top'))
        self.align_toolbar.addAction(action_align_top)
        
        action_align_center_v = create_action_with_icon("align_center_v.svg", "垂直居中", self)
        action_align_center_v.triggered.connect(lambda: self.canvas.align_selected_shapes('center_v'))
        self.align_toolbar.addAction(action_align_center_v)
        
        action_align_bottom = create_action_with_icon("align_bottom.svg", "底对齐", self)
        action_align_bottom.triggered.connect(lambda: self.canvas.align_selected_shapes('bottom'))
        self.align_toolbar.addAction(action_align_bottom)
        
        self.align_actions = self.align_toolbar.actions()
        
        # --- 6. 向【文本格式工具栏】添加动作 ---
        self.action_bold = create_action_with_icon("bold.svg", "粗体", self)
        self.action_bold.setCheckable(True)
        self.action_bold.triggered.connect(self.handle_text_bold_toggle)
        self.text_format_toolbar.addAction(self.action_bold)
        
        self.action_italic = create_action_with_icon("italic.svg", "斜体", self)
        self.action_italic.setCheckable(True)
        self.action_italic.triggered.connect(self.handle_text_italic_toggle)
        self.text_format_toolbar.addAction(self.action_italic)
        
        self.text_format_toolbar.addSeparator()
        
        self.action_align_left_text = create_action_with_icon("align_left.svg", "文本左对齐", self)
        self.action_align_left_text.triggered.connect(lambda: self.handle_text_alignment(Qt.AlignmentFlag.AlignLeft))
        self.text_format_toolbar.addAction(self.action_align_left_text)
        
        self.action_align_center_text = create_action_with_icon("align_center_h.svg", "文本居中对齐", self)
        self.action_align_center_text.triggered.connect(lambda: self.handle_text_alignment(Qt.AlignmentFlag.AlignHCenter))
        self.text_format_toolbar.addAction(self.action_align_center_text)
        
        self.action_align_right_text = create_action_with_icon("align_right.svg", "文本右对齐", self)
        self.action_align_right_text.triggered.connect(lambda: self.handle_text_alignment(Qt.AlignmentFlag.AlignRight))
        self.text_format_toolbar.addAction(self.action_align_right_text)
    
    def _connect_signals(self):
        for action in self.align_actions:
            action.setEnabled(False)
        self.canvas.selection_changed_signal.connect(self.update_align_actions)

        self.undo_action.setEnabled(False)
        self.redo_action.setEnabled(False)
        self.canvas.undo_stack_changed.connect(self.undo_action.setEnabled)
        self.canvas.redo_stack_changed.connect(self.redo_action.setEnabled)

        self.copy_action.setEnabled(False)
        self.paste_action.setEnabled(False)
        self.paste_in_place_action.setEnabled(False)
        self.canvas.selection_changed_signal.connect(self.update_edit_actions)
        self.canvas.clipboard_changed_signal.connect(self.update_edit_actions)
        
        self.canvas.selection_changed_signal.connect(self.update_toolbars)
        self.canvas.tool_changed_signal.connect(self.update_toolbars)

    def _create_docks_and_statusbar(self):
        self.layer_panel = LayerPanel(self); self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.layer_panel)
        self.layer_panel.add_button.clicked.connect(self.canvas.add_layer); self.layer_panel.remove_button.clicked.connect(self.canvas.remove_current_layer); self.layer_panel.up_button.clicked.connect(self.canvas.move_layer_up); self.layer_panel.down_button.clicked.connect(self.canvas.move_layer_down); self.layer_panel.list_widget.currentRowChanged.connect(self.canvas.set_current_layer); self.canvas.layers_changed.connect(self.layer_panel.update_layer_list); self.canvas.initialize_layers()
        self.status_bar = self.statusBar(); self.mouse_pos_label = QLabel("坐标: (0, 0)"); self.status_bar.addPermanentWidget(self.mouse_pos_label); self.canvas.mouse_moved_signal.connect(self.update_mouse_pos)

    def _apply_initial_settings(self):
        self.spinbox_width.setValue(self.settings.get("default_pen_width", 2))
        self.font_combo.setCurrentFont(self.settings.get("default_font", QFont("Arial")))
        font = self.settings.get("default_font", QFont("Arial", 24))
        self.font_size_spinbox.setValue(font.pointSize())

    def smart_undo(self):
        current_tool = self.canvas.current_tool_obj
        if isinstance(current_tool, PenTool) and current_tool.current_path:
            current_tool.undo_last_point()
        else:
            self.canvas.undo()

    def show_user_manual(self, is_startup=False):
        dialog = QDialog(self)
        dialog.setWindowTitle("ShapePainter 用户手册")
        dialog.setGeometry(300, 300, 700, 500)

        layout = QVBoxLayout(dialog)
        text_browser = QTextBrowser(dialog)
        
        manual_path = resource_path("user_manual.txt")
        try:
            with open(manual_path, 'r', encoding='utf-8') as f:
                manual_content = f.read()
            text_browser.setPlainText(manual_content)
        except FileNotFoundError:
            text_browser.setPlainText(f"错误：找不到用户手册文件。\n请确保 user_manual.txt 与主程序在同一目录下。\n尝试搜索路径: {manual_path}")

        layout.addWidget(text_browser)
        
        if is_startup:
            checkbox = QCheckBox("不再显示此欢迎界面", dialog)
            checkbox.setChecked(not self.settings.get("show_manual_on_startup", True))
            checkbox.stateChanged.connect(self._on_show_manual_checkbox_changed)
            layout.addWidget(checkbox)

        dialog.setLayout(layout)
        dialog.exec()

    def _on_show_manual_checkbox_changed(self, state):
        show = not bool(state)
        self.settings["show_manual_on_startup"] = show
        self.settings_manager.save_settings(self.settings)

    def closeEvent(self, event):
        if self.canvas.is_dirty:
            reply = QMessageBox.question(self, '退出确认',
                                           "您有未保存的更改，是否要保存？",
                                           QMessageBox.StandardButton.Save |
                                           QMessageBox.StandardButton.Discard |
                                           QMessageBox.StandardButton.Cancel)

            if reply == QMessageBox.StandardButton.Save:
                if self.canvas.save_shapes():
                    event.accept()
                else:
                    event.ignore()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def open_preferences_dialog(self):
        dialog = PreferencesDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_settings = dialog.get_settings()
            self.settings = new_settings
            self.settings_manager.save_settings(self.settings)
            self.apply_settings()
    
    def apply_settings(self):
        self.canvas.current_pen_color = self.settings["default_pen_color"]
        self.canvas.current_width = self.settings["default_pen_width"]
        self.canvas.current_font = self.settings["default_font"]
        self.canvas.background_color = self.settings["canvas_background_color"]
        self.spinbox_width.setValue(self.settings["default_pen_width"])
        self.font_combo.setCurrentFont(self.settings["default_font"])
        self.font_size_spinbox.setValue(self.settings["default_font"].pointSize())
        self.canvas.update()
        
    def update_toolbars(self):
        is_text_selected = any(isinstance(s, Text) for s in self.canvas.selected_shapes)
        is_text_tool_active = isinstance(self.canvas.current_tool_obj, self.canvas.tools.get("text").__class__)
        show_toolbar = is_text_selected or is_text_tool_active
        self.text_format_toolbar.setVisible(show_toolbar)
        if show_toolbar:
            if is_text_selected:
                first_text = next((s for s in self.canvas.selected_shapes if isinstance(s, Text)), None)
                if first_text:
                    font = first_text.font
                    self.action_bold.setChecked(font.bold())
                    self.action_italic.setChecked(font.italic())
            else:
                font = self.canvas.current_font
                self.action_bold.setChecked(font.bold())
                self.action_italic.setChecked(font.italic())

    def update_align_actions(self):
        enable = len(self.canvas.selected_shapes) >= 2
        for action in self.align_actions:
            action.setEnabled(enable)

    def update_edit_actions(self):
        has_selection = len(self.canvas.selected_shapes) > 0
        has_clipboard = len(self.canvas.clipboard) > 0
        self.copy_action.setEnabled(has_selection)
        self.paste_action.setEnabled(has_clipboard)
        self.paste_in_place_action.setEnabled(has_clipboard)

    def reset_ui_layout(self):
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.draw_toolbar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.edit_attr_toolbar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.align_toolbar)
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
        
    def show_canvas_color_dialog(self):
        initial_color = self.canvas.background_color
        color = QColorDialog.getColor(initial_color, self, "选择画布背景颜色")
        if color.isValid():
            self.canvas.set_background_color(color)

    def on_fill_style_changed(self, index):
        style = self.combo_fill_style.itemData(index)
        self.canvas.set_fill_style(style)
    
    def handle_text_bold_toggle(self, checked):
        if any(isinstance(s, Text) for s in self.canvas.selected_shapes):
            self.canvas.set_selected_text_style('bold', checked)
        else:
            self.canvas.set_current_font_style('bold', checked)

    def handle_text_italic_toggle(self, checked):
        if any(isinstance(s, Text) for s in self.canvas.selected_shapes):
            self.canvas.set_selected_text_style('italic', checked)
        else:
            self.canvas.set_current_font_style('italic', checked)

    def handle_text_alignment(self, alignment):
        if any(isinstance(s, Text) for s in self.canvas.selected_shapes):
            self.canvas.set_selected_text_alignment(alignment)
        else:
            self.canvas.set_text_alignment(alignment)

    def add_text(self):
        self.canvas.set_tool("text")

    def update_mouse_pos(self, pos):
        self.mouse_pos_label.setText(f"坐标: ({pos.x()}, {pos.y()})")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    settings_manager = SettingsManager()
    loaded_settings = settings_manager.load_settings()
    
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

    window = MainWindow(settings=loaded_settings)
    window.show()
    sys.exit(app.exec())