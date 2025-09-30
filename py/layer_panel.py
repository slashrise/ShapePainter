from PyQt6.QtWidgets import QDockWidget, QListWidget, QListWidgetItem, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel, QLineEdit
from PyQt6.QtCore import Qt

class LayerPanel(QDockWidget):
    def __init__(self, main_window, parent=None):
        super().__init__("图层", parent)
        self.main_window = main_window # 持有主窗口的引用
        
        # 核心修改 1：禁止关闭，只允许移动和浮动
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setMinimumWidth(200)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 5, 0, 0)
        
        self.list_widget = QListWidget()
        self.list_widget.setSpacing(2)
        # 连接双击信号
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("➕ 添加")
        self.remove_button = QPushButton("➖ 删除")
        self.up_button = QPushButton("🔼 上移")
        self.down_button = QPushButton("🔽 下移")
        
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.up_button)
        button_layout.addWidget(self.down_button)
        
        layout.addWidget(self.list_widget)
        layout.addLayout(button_layout)
        
        self.setWidget(container)
        
        # 用于重命名的编辑器
        self.name_editor = None
        self.editing_index = -1

    def update_layer_list(self, layers, current_layer_index):
        try:
            self.list_widget.currentRowChanged.disconnect()
        except TypeError:
            pass
            
        self.list_widget.clear()

        for i, layer in enumerate(layers):
            item = QListWidgetItem()
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(5, 2, 5, 2)

            visibility_button = QPushButton("👁️" if layer.is_visible else "⚪")
            visibility_button.setFlat(True)
            visibility_button.setFixedWidth(30)
            visibility_button.clicked.connect(lambda checked=False, idx=i: self.main_window.canvas.toggle_layer_visibility(idx))

            layer_name_label = QLabel(str(layer.name))

            lock_button = QPushButton("🔒" if layer.is_locked else " ")
            lock_button.setFlat(True)
            lock_button.setFixedWidth(30)
            lock_button.clicked.connect(lambda checked=False, idx=i: self.main_window.canvas.toggle_layer_lock(idx))

            item_layout.addWidget(visibility_button)
            item_layout.addWidget(layer_name_label, 1)
            item_layout.addWidget(lock_button)
            
            item.setSizeHint(item_widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, item_widget)
        
        if 0 <= current_layer_index < len(layers):
            self.list_widget.setCurrentRow(current_layer_index)
            
        self.list_widget.currentRowChanged.connect(self.main_window.canvas.set_current_layer)

    def on_item_double_clicked(self, item):
        index = self.list_widget.row(item)
        
        # 确保索引有效
        if not (0 <= index < len(self.main_window.canvas.layers)):
            return
            
        current_layer = self.main_window.canvas.layers[index]
        
        if current_layer.is_locked:
            return

        self.editing_index = index
        item_widget = self.list_widget.itemWidget(item)
        
        label = item_widget.findChild(QLabel)
        if label:
            label.hide()

            self.name_editor = QLineEdit(label.text(), item_widget)
            self.name_editor.editingFinished.connect(self._finish_renaming)
            item_widget.layout().insertWidget(1, self.name_editor)
            self.name_editor.selectAll()
            self.name_editor.setFocus()

    def _finish_renaming(self):
        if self.name_editor and self.editing_index != -1:
            new_name = self.name_editor.text()
            
            self.main_window.canvas.rename_layer(self.editing_index, new_name)
            
            self.name_editor.deleteLater()
            self.name_editor = None
            self.editing_index = -1
            
            # 重命名结束后，让画布重新获得焦点，以便键盘快捷键（如删除）能继续工作
            self.main_window.canvas.setFocus()