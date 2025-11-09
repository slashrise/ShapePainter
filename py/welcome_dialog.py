import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QTextBrowser, 
                             QDialogButtonBox, QCheckBox, QWidget)
from PyQt6.QtCore import Qt

class WelcomeDialog(QDialog):
    def __init__(self, resource_path_func, parent=None):
        super().__init__(parent)
        self.setWindowTitle("欢迎使用 ShapePainter v4.1")
        self.setGeometry(300, 300, 750, 550)

        # 主布局
        layout = QVBoxLayout(self)

        # 1. 创建选项卡控件
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # 2. 创建并填充 "用户手册" 选项卡
        manual_tab = QWidget()
        manual_layout = QVBoxLayout(manual_tab)
        manual_browser = QTextBrowser()
        self._load_file_to_browser(manual_browser, resource_path_func, "user_manual.txt", "错误：找不到用户手册文件。")
        manual_layout.addWidget(manual_browser)
        self.tab_widget.addTab(manual_tab, "📖 用户手册")

        # 3. 创建并填充 "版本区别报告" 选项卡
        diff_tab = QWidget()
        diff_layout = QVBoxLayout(diff_tab)
        diff_browser = QTextBrowser()
        self._load_file_to_browser(diff_browser, resource_path_func, "different.txt", "错误：找不到版本区别报告文件。")
        diff_layout.addWidget(diff_browser)
        self.tab_widget.addTab(diff_tab, "🚀 版本区别报告 (v1 vs v2)")

        # 4. 创建 "不再显示" 复选框
        self.show_on_startup_checkbox = QCheckBox("启动时显示此欢迎界面")
        self.show_on_startup_checkbox.setChecked(True) # 默认勾选
        layout.addWidget(self.show_on_startup_checkbox, 0, Qt.AlignmentFlag.AlignLeft)

        # 5. 创建 OK 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

    def _load_file_to_browser(self, browser, resource_path_func, filename, error_message):
        """辅助函数，用于加载文本文件到 QTextBrowser"""
        # 🟢 核心修改：在文件名前面加上 "assets/" 路径
        file_path = resource_path_func(os.path.join("assets", filename))
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            browser.setMarkdown(content)
        except FileNotFoundError:
            browser.setPlainText(f"{error_message}\n请确保 {filename} 文件位于 'assets' 文件夹中。\n尝试搜索路径: {file_path}")

    def get_show_on_startup_choice(self):
        """获取用户是否希望下次启动时继续显示此对话框"""
        return self.show_on_startup_checkbox.isChecked()