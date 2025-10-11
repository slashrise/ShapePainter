# --- START OF FILE preferences_dialog.py ---

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QLabel, QSpinBox, 
                             QPushButton, QFrame, QColorDialog, QFontDialog, QDialogButtonBox)
from PyQt6.QtGui import QPalette, QFont
from PyQt6.QtCore import Qt

class PreferencesDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("偏好设置")
        self.settings = current_settings.copy() # 创建副本以备取消操作

        layout = QVBoxLayout(self)
        grid_layout = QGridLayout()

        # 1. 默认画笔颜色
        grid_layout.addWidget(QLabel("默认画笔颜色:"), 0, 0)
        self.pen_color_preview = QFrame()
        self.pen_color_preview.setFrameShape(QFrame.Shape.StyledPanel)
        self.pen_color_preview.setAutoFillBackground(True)
        self._update_color_preview(self.pen_color_preview, self.settings["default_pen_color"])
        grid_layout.addWidget(self.pen_color_preview, 0, 1)
        pen_color_button = QPushButton("选择...")
        pen_color_button.clicked.connect(self._select_pen_color)
        grid_layout.addWidget(pen_color_button, 0, 2)

        # 2. 默认画笔宽度
        grid_layout.addWidget(QLabel("默认画笔宽度:"), 1, 0)
        self.pen_width_spinbox = QSpinBox()
        self.pen_width_spinbox.setRange(1, 100)
        self.pen_width_spinbox.setValue(self.settings["default_pen_width"])
        grid_layout.addWidget(self.pen_width_spinbox, 1, 1, 1, 2)

        # 3. 默认字体
        grid_layout.addWidget(QLabel("默认字体:"), 2, 0)
        self.font_label = QLabel(self._font_to_string(self.settings["default_font"]))
        grid_layout.addWidget(self.font_label, 2, 1)
        font_button = QPushButton("选择...")
        font_button.clicked.connect(self._select_font)
        grid_layout.addWidget(font_button, 2, 2)

        # 4. 画布背景色
        grid_layout.addWidget(QLabel("画布背景颜色:"), 3, 0)
        self.bg_color_preview = QFrame()
        self.bg_color_preview.setFrameShape(QFrame.Shape.StyledPanel)
        self.bg_color_preview.setAutoFillBackground(True)
        self._update_color_preview(self.bg_color_preview, self.settings["canvas_background_color"])
        grid_layout.addWidget(self.bg_color_preview, 3, 1)
        bg_color_button = QPushButton("选择...")
        bg_color_button.clicked.connect(self._select_bg_color)
        grid_layout.addWidget(bg_color_button, 3, 2)

        # OK 和 Cancel 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addLayout(grid_layout)
        layout.addWidget(button_box)

    def _update_color_preview(self, frame, color):
        palette = frame.palette()
        palette.setColor(QPalette.ColorRole.Window, color)
        frame.setPalette(palette)

    def _font_to_string(self, font):
        return f"{font.family()}, {font.pointSize()}pt"

    def _select_pen_color(self):
        color = QColorDialog.getColor(self.settings["default_pen_color"], self, "选择默认画笔颜色")
        if color.isValid():
            self.settings["default_pen_color"] = color
            self._update_color_preview(self.pen_color_preview, color)

    def _select_bg_color(self):
        color = QColorDialog.getColor(self.settings["canvas_background_color"], self, "选择画布背景颜色")
        if color.isValid():
            self.settings["canvas_background_color"] = color
            self._update_color_preview(self.bg_color_preview, color)

    def _select_font(self):
        font, ok = QFontDialog.getFont(self.settings["default_font"], self, "选择默认字体")
        if ok:
            self.settings["default_font"] = font
            self.font_label.setText(self._font_to_string(font))

    def get_settings(self):
        """在点击OK后，从UI控件收集最终的设置值。"""
        self.settings["default_pen_width"] = self.pen_width_spinbox.value()
        return self.settings

# --- END OF FILE preferences_dialog.py ---