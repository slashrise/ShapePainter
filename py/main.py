import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QToolBar, QColorDialog,
                             QSpinBox, QLabel, QFileDialog, QComboBox,
                             QFontComboBox, QWidgetAction, QDialog, QMessageBox,
                             QVBoxLayout, QTextBrowser, QCheckBox, QDialogButtonBox)
from PyQt6.QtGui import QAction, QKeySequence, QIcon, QPalette, QColor, QBrush, QFont
from PyQt6.QtCore import Qt, QSize, QTimer

from canvas import CanvasWidget
from layer_panel import LayerPanel
from rulers import CanvasView
from settings_manager import SettingsManager
from preferences_dialog import PreferencesDialog
from shapes import Text, Path, BezierSurface
from tools import PenTool
# 🟢 导入我们新创建的对话框
from welcome_dialog import WelcomeDialog

def resource_path(relative_path):
    """
    获取资源的绝对路径, 兼容开发模式和 PyInstaller 打包后的模式。
    这是一个健壮的最终版本。
    """
    try:
        # PyInstaller 创建一个临时文件夹，并将路径存储在 _MEIPASS 中
        base_path = sys._MEIPASS
    except Exception:
        # 在开发模式下，我们从 main.py 向上两级找到项目根目录
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    return os.path.join(base_path, relative_path)


class MainWindow(QMainWindow):
    def __init__(self, settings):
        super().__init__()
        self.setWindowTitle('我的绘图系统 - ShapePainter')
        self.setGeometry(200, 200, 1400, 800)

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
        self._create_docks_and_statusbar()
        self._apply_initial_settings()
        self._connect_signals()
        
        self.update_fill_styles_for_algo(self.algo_combo.currentText())
        
        # 🟢 用新的欢迎对话框逻辑替换旧的逻辑
        if self.settings.get("show_welcome_on_startup", True):
            QTimer.singleShot(0, self.show_welcome_dialog)

    def _create_menus(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("文件")
        edit_menu = menu_bar.addMenu("编辑")
        insert_menu = menu_bar.addMenu("插入")
        view_menu = menu_bar.addMenu("视图")
        export_menu = menu_bar.addMenu("导出")
        help_menu = menu_bar.addMenu("帮助")
        
        action_save = QAction("保存项目...", self); action_save.triggered.connect(self.canvas.save_shapes); file_menu.addAction(action_save)
        action_load = QAction("加载项目...", self); action_load.triggered.connect(self.canvas.load_shapes); file_menu.addAction(action_load)
        
        self.undo_action = QAction("撤销", self); self.undo_action.setShortcut(QKeySequence.StandardKey.Undo); self.undo_action.triggered.connect(self.smart_undo); edit_menu.addAction(self.undo_action)
        self.redo_action = QAction("重做", self); self.redo_action.setShortcut(QKeySequence.StandardKey.Redo); self.redo_action.triggered.connect(self.canvas.redo); edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        
        self.copy_action = QAction("复制", self); self.copy_action.setShortcut(QKeySequence.StandardKey.Copy); self.copy_action.triggered.connect(self.canvas.copy_selected); edit_menu.addAction(self.copy_action)
        self.paste_action = QAction("粘贴", self); self.paste_action.setShortcut(QKeySequence.StandardKey.Paste); self.paste_action.triggered.connect(self.canvas.paste); edit_menu.addAction(self.paste_action)
        self.paste_in_place_action = QAction("原位粘贴", self); self.paste_in_place_action.setShortcut("Ctrl+Shift+V"); self.paste_in_place_action.triggered.connect(self.canvas.paste_in_place); edit_menu.addAction(self.paste_in_place_action)
        
        edit_menu.addSeparator()
        action_prefs = QAction("偏好设置...", self); action_prefs.triggered.connect(self.open_preferences_dialog); edit_menu.addAction(action_prefs)
        
        action_add_text = QAction("文本框", self); action_add_text.triggered.connect(self.add_text); insert_menu.addAction(action_add_text)
        insert_menu.addSeparator()
        
        font_combo_action = QWidgetAction(self); self.font_combo = QFontComboBox(); self.font_combo.currentFontChanged.connect(self.canvas.set_font); font_combo_action.setDefaultWidget(self.font_combo); insert_menu.addAction(font_combo_action)
        font_size_action = QWidgetAction(self); self.font_size_spinbox = QSpinBox(); self.font_size_spinbox.setRange(1, 200); self.font_size_spinbox.setPrefix("字号: "); self.font_size_spinbox.valueChanged.connect(self.canvas.set_font_size); font_size_action.setDefaultWidget(self.font_size_spinbox); insert_menu.addAction(font_size_action)
        
        reset_ui_action = QAction("重置界面布局", self); reset_ui_action.triggered.connect(self.reset_ui_layout); view_menu.addAction(reset_ui_action)
        view_menu.addSeparator()
        
        self.show_grid_action = QAction("显示网格", self); self.show_grid_action.setCheckable(True); self.show_grid_action.toggled.connect(self.canvas.toggle_grid); view_menu.addAction(self.show_grid_action)
        self.show_guides_action = QAction("显示参考线", self); self.show_guides_action.setCheckable(True); self.show_guides_action.setChecked(True); self.show_guides_action.toggled.connect(self.canvas.toggle_guides); view_menu.addAction(self.show_guides_action)
        self.snap_to_grid_action = QAction("吸附", self); self.snap_to_grid_action.setCheckable(True); self.snap_to_grid_action.toggled.connect(self.canvas.toggle_snapping); view_menu.addAction(self.snap_to_grid_action)
        
        view_menu.addSeparator()
        self.ssaa_action = QAction("启用抗锯齿 (SSAA)", self); self.ssaa_action.setCheckable(True); self.ssaa_action.setChecked(True); self.ssaa_action.toggled.connect(self.canvas.toggle_ssaa); view_menu.addAction(self.ssaa_action)
        # 🟢 [新增] 曲面显示设置子菜单
        view_menu.addSeparator()
        surface_view_menu = view_menu.addMenu("曲面显示模式")
        
        # 1. 显示填充 Action
        self.action_view_surf_fill = QAction("显示曲面填充", self)
        self.action_view_surf_fill.setCheckable(True)
        self.action_view_surf_fill.setEnabled(False) # 默认禁用，只有选中曲面时才启用
        # 连接信号：触发时调用 canvas 的方法
        self.action_view_surf_fill.triggered.connect(
            lambda checked: self.canvas.toggle_surface_property('show_fill', checked)
        )
        surface_view_menu.addAction(self.action_view_surf_fill)

        # 2. 显示网格线 Action
        self.action_view_surf_wire = QAction("显示网格线", self)
        self.action_view_surf_wire.setCheckable(True)
        self.action_view_surf_wire.setEnabled(False) # 默认禁用
        self.action_view_surf_wire.triggered.connect(
            lambda checked: self.canvas.toggle_surface_property('show_wireframe', checked)
        )
        surface_view_menu.addAction(self.action_view_surf_wire)
        action_export_png = QAction("导出为PNG...", self); action_export_png.triggered.connect(self.canvas.export_as_png); export_menu.addAction(action_export_png)
        action_export_svg = QAction("导出为SVG...", self); action_export_svg.triggered.connect(self.canvas.export_as_svg); export_menu.addAction(action_export_svg)
        
        # 🟢 修改为：
        action_show_welcome = QAction("查看帮助与版本信息...", self)
        # 核心修改：让它调用和启动时一样的欢迎对话框
        action_show_welcome.triggered.connect(self.show_welcome_dialog)
        help_menu.addAction(action_show_welcome)

    def _create_toolbars(self):
        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks | QMainWindow.DockOption.AllowNestedDocks)

        self.draw_toolbar = QToolBar("绘图工具"); self.draw_toolbar.setIconSize(QSize(24, 24)); self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.draw_toolbar); self.draw_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.edit_attr_toolbar = QToolBar("功能与属性"); self.edit_attr_toolbar.setIconSize(QSize(24, 24)); self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.edit_attr_toolbar); self.edit_attr_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.align_toolbar = QToolBar("对齐"); self.align_toolbar.setIconSize(QSize(24, 24)); self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.align_toolbar); self.align_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.text_format_toolbar = QToolBar("文本格式"); self.text_format_toolbar.setIconSize(QSize(24, 24)); self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.text_format_toolbar); self.text_format_toolbar.setVisible(False)

        def create_action_with_icon(icon_name, text, parent, tooltip=None):
            path = resource_path(os.path.join("icons", icon_name)); action = QAction(text, parent)
            if os.path.exists(path): action.setIcon(QIcon(path))
            else: print(f"Warning: Icon not found at '{path}'")
            action.setToolTip(tooltip or text); return action

        tools_to_add = [("mouse pointer.svg", "选择", "select"), ("separator",), ("line_curve.svg", "贝塞尔曲线", "pen"),("curve_bspline.svg", "B样条曲线", "bspline"), ("draw.svg", "手绘", "freehand"), ("separator",), ("point.svg", "画点", "point"), ("remove.svg", "画直线", "line"), ("arrow.svg", "箭头", "arrow"), ("rectangle.svg", "画矩形", "rect"), ("square.svg", "画正方形", "square"), ("circle.svg", "画圆形", "circle"), ("ellipse.svg", "画椭圆", "ellipse"), ("rounded rectangle.svg", "画圆角矩形", "rounded_rect"), ("pentagon.svg", "画多边形", "polygon"), ("polyline.svg", "画折线", "polyline"),("grid.svg", "贝塞尔曲面", "surface"),]
        for item in tools_to_add:
            if item[0] == "separator": self.draw_toolbar.addSeparator(); continue
            icon, text, tool_name = item; action = create_action_with_icon(icon, text, self); action.triggered.connect(lambda checked=False, t=tool_name: self.canvas.set_tool(t)); self.draw_toolbar.addAction(action)

        action_eraser = create_action_with_icon("eraser.svg", "橡皮擦", self); action_eraser.triggered.connect(lambda: self.canvas.set_tool("eraser")); self.edit_attr_toolbar.addAction(action_eraser)
        action_clear = create_action_with_icon("clear all.svg", "清空", self); action_clear.triggered.connect(self.canvas.clear_canvas); self.edit_attr_toolbar.addAction(action_clear)
        self.edit_attr_toolbar.addSeparator()
        
        action_group = QAction("组合", self); action_group.setShortcut("Ctrl+G"); action_group.triggered.connect(self.canvas.group_selected); self.edit_attr_toolbar.addAction(action_group)
        action_ungroup = QAction("解组", self); action_ungroup.setShortcut("Ctrl+Shift+G"); action_ungroup.triggered.connect(self.canvas.ungroup_selected); self.edit_attr_toolbar.addAction(action_ungroup)
        self.edit_attr_toolbar.addSeparator()

        action_pen_color = create_action_with_icon("format_color_text.svg", "边框色", self); action_pen_color.triggered.connect(self.show_pen_color_dialog); self.edit_attr_toolbar.addAction(action_pen_color)
        action_fill_color = create_action_with_icon("palette.svg", "填充色", self); action_fill_color.triggered.connect(self.show_fill_color_dialog); self.edit_attr_toolbar.addAction(action_fill_color)
        action_canvas_color = create_action_with_icon("background.svg", "画布颜色", self); action_canvas_color.triggered.connect(self.show_canvas_color_dialog); self.edit_attr_toolbar.addAction(action_canvas_color)
        action_no_fill = create_action_with_icon("format_color_reset.svg", "无填充", self); action_no_fill.triggered.connect(self.canvas.set_no_fill); self.edit_attr_toolbar.addAction(action_no_fill)
        action_paint_bucket = create_action_with_icon("paint_bucket.svg", "颜料桶", self); action_paint_bucket.triggered.connect(lambda: self.canvas.set_tool("paint_bucket")); self.edit_attr_toolbar.addAction(action_paint_bucket)
        self.edit_attr_toolbar.addSeparator()
        
        self.edit_attr_toolbar.addWidget(QLabel("填充:")); self.combo_fill_style = QComboBox()
        self.fill_styles = { "无": Qt.BrushStyle.NoBrush, "纯色": Qt.BrushStyle.SolidPattern, "水平": Qt.BrushStyle.HorPattern, "垂直": Qt.BrushStyle.VerPattern, "交叉": Qt.BrushStyle.CrossPattern, "斜线": Qt.BrushStyle.BDiagPattern, "反斜": Qt.BrushStyle.FDiagPattern, "斜叉": Qt.BrushStyle.DiagCrossPattern, "点1": Qt.BrushStyle.Dense1Pattern, "点2": Qt.BrushStyle.Dense4Pattern, "点3": Qt.BrushStyle.Dense7Pattern }
        for name, style in self.fill_styles.items(): self.combo_fill_style.addItem(name, style)
        self.combo_fill_style.activated.connect(self.on_fill_style_changed); self.edit_attr_toolbar.addWidget(self.combo_fill_style)
        self.edit_attr_toolbar.addSeparator()

        self.edit_attr_toolbar.addWidget(QLabel("线宽:")); self.spinbox_width = QSpinBox(); self.spinbox_width.setRange(1, 100); self.spinbox_width.valueChanged.connect(self.canvas.set_pen_width); self.edit_attr_toolbar.addWidget(self.spinbox_width)
        self.edit_attr_toolbar.addSeparator()
        
        self.edit_attr_toolbar.addWidget(QLabel("直线算法:")); self.algo_combo = QComboBox(); self.algo_combo.addItems(["Bresenham", "DDA", "PyQt原生"]); self.edit_attr_toolbar.addWidget(self.algo_combo)

        align_actions_data = [("align_left.svg", "左对齐", "left"), ("align_center_h.svg", "水平居中", "center_h"), ("align_right.svg", "右对齐", "right"), ("separator",), ("align_top.svg", "顶对齐", "top"), ("align_center_v.svg", "垂直居中", "center_v"), ("align_bottom.svg", "底对齐", "bottom")]
        for item in align_actions_data:
            if item[0] == "separator": self.align_toolbar.addSeparator(); continue
            icon, text, mode = item; action = create_action_with_icon(icon, text, self); action.triggered.connect(lambda checked=False, m=mode: self.canvas.align_selected_shapes(m)); self.align_toolbar.addAction(action)
        self.align_actions = self.align_toolbar.actions()

        self.action_bold = create_action_with_icon("bold.svg", "粗体", self); self.action_bold.setCheckable(True); self.action_bold.triggered.connect(self.handle_text_bold_toggle); self.text_format_toolbar.addAction(self.action_bold)
        self.action_italic = create_action_with_icon("italic.svg", "斜体", self); self.action_italic.setCheckable(True); self.action_italic.triggered.connect(self.handle_text_italic_toggle); self.text_format_toolbar.addAction(self.action_italic)
        self.text_format_toolbar.addSeparator()
        self.action_align_left_text = create_action_with_icon("align_left.svg", "文本左对齐", self); self.action_align_left_text.triggered.connect(lambda: self.handle_text_alignment(Qt.AlignmentFlag.AlignLeft)); self.text_format_toolbar.addAction(self.action_align_left_text)
        self.action_align_center_text = create_action_with_icon("align_center_h.svg", "文本居中对齐", self); self.action_align_center_text.triggered.connect(lambda: self.handle_text_alignment(Qt.AlignmentFlag.AlignHCenter)); self.text_format_toolbar.addAction(self.action_align_center_text)
        self.action_align_right_text = create_action_with_icon("align_right.svg", "文本右对齐", self); self.action_align_right_text.triggered.connect(lambda: self.handle_text_alignment(Qt.AlignmentFlag.AlignRight)); self.text_format_toolbar.addAction(self.action_align_right_text)
    
    def _connect_signals(self):
        self.algo_combo.currentTextChanged.connect(self.update_fill_styles_for_algo)

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
        self.layer_panel.add_button.clicked.connect(self.canvas.add_layer); self.layer_panel.remove_button.clicked.connect(self.canvas.remove_current_layer); self.layer_panel.up_button.clicked.connect(self.canvas.move_layer_up); self.layer_panel.down_button.clicked.connect(self.canvas.move_layer_down)
        self.canvas.layers_changed.connect(self.layer_panel.update_layer_list); self.canvas.initialize_layers()
        self.status_bar = self.statusBar(); self.mouse_pos_label = QLabel("坐标: (0, 0)"); self.status_bar.addPermanentWidget(self.mouse_pos_label); self.canvas.mouse_moved_signal.connect(self.update_mouse_pos)

    def _apply_initial_settings(self):
        self.spinbox_width.setValue(self.settings.get("default_pen_width", 2))
        font = self.settings.get("default_font", QFont("Arial", 24))
        self.font_combo.setCurrentFont(font)
        self.font_size_spinbox.setValue(font.pointSize())

    def smart_undo(self):
        current_tool = self.canvas.current_tool_obj
        if isinstance(current_tool, PenTool) and current_tool.current_path:
            current_tool.undo_last_point()
        else:
            self.canvas.undo()

    def show_welcome_dialog(self, is_startup_call=False):
        """
        显示欢迎/帮助对话框。
        is_startup_call: 标记这次调用是否来自程序启动。
        """
        dialog = WelcomeDialog(resource_path, self)
        
        # 判断调用来源
        if self.sender() is None or isinstance(self.sender(), QTimer):
            # 如果是程序启动时调用 (没有发送者或发送者是QTimer)
            is_startup_call = True
        else:
            is_startup_call = False

        if is_startup_call:
            # 启动时调用：显示复选框，并设置其状态
            dialog.show_on_startup_checkbox.setVisible(True)
            dialog.show_on_startup_checkbox.setChecked(self.settings.get("show_welcome_on_startup", True))
        else:
            # 从菜单调用：隐藏复选框
            dialog.show_on_startup_checkbox.setVisible(False)
            
        dialog.exec()
        
        if is_startup_call:
            # 只有在启动时调用，我们才处理并保存用户的选择
            user_wants_to_show_next_time = dialog.get_show_on_startup_choice()
            if user_wants_to_show_next_time != self.settings.get("show_welcome_on_startup"):
                self.settings["show_welcome_on_startup"] = user_wants_to_show_next_time
                self.settings_manager.save_settings(self.settings)

    def closeEvent(self, event):
        if self.canvas.is_dirty:
            reply = QMessageBox.question(self, '退出确认', "您有未保存的更改，是否要保存？", QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
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
            self.settings = dialog.get_settings()
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

    def update_fill_styles_for_algo(self, algo_name):
        """根据选择的算法，动态重建填充样式下拉框的内容。"""
        self.canvas.set_raster_algorithm(algo_name)
        current_style_data = self.combo_fill_style.currentData()
        self.combo_fill_style.clear()
        is_native = (algo_name == "PyQt原生")
        if is_native:
            for name, style in self.fill_styles.items():
                self.combo_fill_style.addItem(name, style)
        else:
            self.combo_fill_style.addItem("无", Qt.BrushStyle.NoBrush)
            self.combo_fill_style.addItem("纯色", Qt.BrushStyle.SolidPattern)
            self.combo_fill_style.insertSeparator(self.combo_fill_style.count())
            self.combo_fill_style.addItem("— 其他样式需原生模式 —")
            info_item_index = self.combo_fill_style.count() - 1
            self.combo_fill_style.model().item(info_item_index).setEnabled(False)
        new_index = self.combo_fill_style.findData(current_style_data)
        if new_index != -1:
            self.combo_fill_style.setCurrentIndex(new_index)
        else:
            self.combo_fill_style.setCurrentIndex(0)
            self.canvas.set_fill_style(Qt.BrushStyle.NoBrush)
        
    def update_toolbars(self):
        is_text_selected = any(isinstance(s, Text) for s in self.canvas.selected_shapes)
        is_text_tool_active = isinstance(self.canvas.current_tool_obj, self.canvas.tools.get("text").__class__)
        show_toolbar = is_text_selected or is_text_tool_active
        self.text_format_toolbar.setVisible(show_toolbar)
        if show_toolbar:
            first_text = next((s for s in self.canvas.selected_shapes if isinstance(s, Text)), None)
            font = first_text.font if first_text else self.canvas.current_font
            self.action_bold.setChecked(font.bold())
            self.action_italic.setChecked(font.italic())
        # 🟢 [新增] 检查曲面选择状态，更新菜单项
        # 1. 找出选中的所有曲面
        surfaces = [s for s in self.canvas.selected_shapes if isinstance(s, BezierSurface)]
        has_surface = bool(surfaces)

        # 2. 启用/禁用菜单项
        if hasattr(self, 'action_view_surf_fill'): #以此防卫性编程，防止初始化时报错
            self.action_view_surf_fill.setEnabled(has_surface)
            self.action_view_surf_wire.setEnabled(has_surface)

            # 3. 同步勾选状态 (以第一个选中的曲面为准)
            if has_surface:
                first_surf = surfaces[0]
                # 这里的 blockSignals 是为了防止设置 Checked 时误触发 triggered 信号导致死循环
                self.action_view_surf_fill.blockSignals(True)
                self.action_view_surf_wire.blockSignals(True)
                
                self.action_view_surf_fill.setChecked(first_surf.show_fill)
                self.action_view_surf_wire.setChecked(first_surf.show_wireframe)
                
                self.action_view_surf_fill.blockSignals(False)
                self.action_view_surf_wire.blockSignals(False)

    def update_align_actions(self):
        enable = len(self.canvas.selected_shapes) >= 2
        for action in self.align_actions:
            action.setEnabled(enable)

    def update_edit_actions(self):
        has_selection = bool(self.canvas.selected_shapes)
        has_clipboard = bool(self.canvas.clipboard)
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
        initial_color = self.canvas.current_fill_color or Qt.GlobalColor.white
        color = QColorDialog.getColor(initial_color, self, "选择填充颜色")
        if color.isValid():
            self.canvas.set_fill_color(color)
        
    def show_canvas_color_dialog(self):
        color = QColorDialog.getColor(self.canvas.background_color, self, "选择画布背景颜色")
        if color.isValid():
            self.canvas.set_background_color(color)

    def on_fill_style_changed(self, index):
        style = self.combo_fill_style.itemData(index)
        if style is not None:  # 确保说明项不会触发
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