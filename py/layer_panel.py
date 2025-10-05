# --- START OF FILE layer_panel.py (Final Optimized Version) ---

from PyQt6.QtWidgets import (QDockWidget, QListWidget, QListWidgetItem, QVBoxLayout,
                             QWidget, QPushButton, QHBoxLayout, QLabel, QLineEdit,
                             QSlider, QComboBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter

class LayerPanel(QDockWidget):
    def __init__(self, main_window, parent=None):
        super().__init__("图层", parent)
        self.main_window = main_window 
        
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setMinimumWidth(250)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 5, 0, 0)
        
        self.list_widget = QListWidget()
        self.list_widget.setSpacing(4)
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
        
        self.name_editor = None
        self.editing_index = -1
        
        self.blend_modes = {
            "正常": QPainter.CompositionMode.CompositionMode_SourceOver,
            "正片叠底": QPainter.CompositionMode.CompositionMode_Multiply,
            "滤色": QPainter.CompositionMode.CompositionMode_Screen,
            "叠加": QPainter.CompositionMode.CompositionMode_Overlay,
            "变暗": QPainter.CompositionMode.CompositionMode_Darken,
            "变亮": QPainter.CompositionMode.CompositionMode_Lighten,
            "颜色减淡": QPainter.CompositionMode.CompositionMode_ColorDodge,
            "颜色加深": QPainter.CompositionMode.CompositionMode_ColorBurn,
            "差值": QPainter.CompositionMode.CompositionMode_Difference,
        }

    def update_layer_list(self, layers, current_layer_index):
        try:
            self.list_widget.currentRowChanged.disconnect()
        except TypeError:
            pass
            
        self.list_widget.clear()

        for i, layer in enumerate(layers):
            item = QListWidgetItem()
            item_widget = QWidget()
            item_v_layout = QVBoxLayout(item_widget)
            item_v_layout.setContentsMargins(5, 5, 5, 5)
            item_v_layout.setSpacing(4)

            # --- 第一行：可见性、名称、锁定 ---
            top_row_layout = QHBoxLayout()
            visibility_button = QPushButton("👁️" if layer.is_visible else "⚪")
            visibility_button.setFlat(True)
            visibility_button.setFixedWidth(30)
            visibility_button.clicked.connect(lambda checked=False, idx=i: self.main_window.canvas.toggle_layer_visibility(idx))
            
            layer_name_label = QLabel(str(layer.name))
            
            # 🔴 --- 修正点 ---
            # 将解锁状态的图标从 " " 改为 "🔓"，使其始终可见
            lock_button = QPushButton("🔒" if layer.is_locked else "🔓")
            # 🔴 --- 修正结束 ---
            lock_button.setFlat(True)
            lock_button.setFixedWidth(30)
            lock_button.clicked.connect(lambda checked=False, idx=i: self.main_window.canvas.toggle_layer_lock(idx))
            
            top_row_layout.addWidget(visibility_button)
            top_row_layout.addWidget(layer_name_label, 1)
            top_row_layout.addWidget(lock_button)

            # --- 第二行：不透明度和混合模式 ---
            bottom_row_layout = QHBoxLayout()
            bottom_row_layout.setContentsMargins(0, 2, 0, 0)
            
            blend_combo = QComboBox()
            for name, mode in self.blend_modes.items():
                blend_combo.addItem(name, mode)
            
            current_mode_val = layer.blend_mode
            for idx in range(blend_combo.count()):
                if blend_combo.itemData(idx) == current_mode_val:
                    blend_combo.setCurrentIndex(idx)
                    break
            blend_combo.currentIndexChanged.connect(
                lambda c_idx, l_idx=i, combo=blend_combo: self.main_window.canvas.set_layer_blend_mode(l_idx, combo.itemData(c_idx))
            )

            opacity_label = QLabel("不透明度:")
            opacity_slider = QSlider(Qt.Orientation.Horizontal)
            opacity_slider.setRange(0, 100)
            opacity_slider.setValue(int(layer.opacity * 100))
            opacity_slider.valueChanged.connect(
                lambda value, idx=i: self.main_window.canvas.set_layer_opacity(idx, value)
            )

            bottom_row_layout.addWidget(blend_combo)
            bottom_row_layout.addWidget(opacity_label)
            bottom_row_layout.addWidget(opacity_slider, 1)

            item_v_layout.addLayout(top_row_layout)
            item_v_layout.addLayout(bottom_row_layout)
            
            if layer.is_locked:
                blend_combo.setEnabled(False)
                opacity_slider.setEnabled(False)

            item.setSizeHint(item_widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, item_widget)
        
        if 0 <= current_layer_index < len(layers):
            self.list_widget.setCurrentRow(current_layer_index)
            
        self.list_widget.currentRowChanged.connect(self.main_window.canvas.set_current_layer)

    def on_item_double_clicked(self, item):
        index = self.list_widget.row(item)
        
        if not (0 <= index < len(self.main_window.canvas.layers)):
            return
            
        current_layer = self.main_window.canvas.layers[index]
        
        if current_layer.is_locked:
            return

        self.editing_index = index
        item_widget = self.list_widget.itemWidget(item)
        
        label = item_widget.findChild(QLabel)
        if label and "不透明度" not in label.text():
            label.hide()

            self.name_editor = QLineEdit(label.text(), item_widget)
            self.name_editor.editingFinished.connect(self._finish_renaming)
            item_widget.layout().itemAt(0).layout().insertWidget(1, self.name_editor)
            self.name_editor.selectAll()
            self.name_editor.setFocus()

    def _finish_renaming(self):
        if self.name_editor and self.editing_index != -1:
            new_name = self.name_editor.text()
            
            self.main_window.canvas.rename_layer(self.editing_index, new_name)
            
            self.name_editor.deleteLater()
            self.name_editor = None
            self.editing_index = -1
            
            self.main_window.canvas.setFocus()

# --- END OF FILE layer_panel.py ---