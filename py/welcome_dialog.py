import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QTextBrowser, 
                             QDialogButtonBox, QCheckBox, QWidget)
from PyQt6.QtCore import Qt

class WelcomeDialog(QDialog):
    def __init__(self, resource_path_func, parent=None):
        super().__init__(parent)
        self.setWindowTitle("欢迎使用 ShapePainter v4.3")
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
        self.tab_widget.addTab(diff_tab, "🚀 版本区别报告 (v4.3 Update)")

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
        file_path = resource_path_func(os.path.join("assets", filename))
        
        # 🟢 [修改] 强制让浏览器能够打开外部链接（如果以后有的话），并禁用交互
        browser.setOpenExternalLinks(True)
        
        try:
            # 🟢 [修改] 使用 'utf-8-sig' 可以自动处理带 BOM 的 UTF-8 文件，容错率更高
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            
            # 🟢 [关键修改] 显式调用 setHtml 而不是 setMarkdown
            # 这样浏览器就会把它当网页渲染，而不是当 Markdown 渲染
            # 如果文件是 .md，Qt 也能识别简单的 HTML 标签，所以用 setHtml 最稳
            browser.setHtml(content)
            
        except (FileNotFoundError, UnicodeDecodeError):
            # 备用方案：如果 UTF-8 读取失败，尝试系统默认编码（防止 Windows 上保存成 GBK）
            try:
                with open(file_path, 'r') as f: # 不指定 encoding，使用系统默认
                    content = f.read()
                browser.setHtml(content)
            except Exception:
                browser.setPlainText(f"{error_message}\n路径: {file_path}")

    def get_show_on_startup_choice(self):
        """获取用户是否希望下次启动时继续显示此对话框"""
        return self.show_on_startup_checkbox.isChecked()