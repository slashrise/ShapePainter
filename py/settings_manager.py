from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QColor, QFont

class SettingsManager:
    def __init__(self, organization="ShapePainterOrg", application="ShapePainter"):
        self.settings = QSettings(organization, application)

    def get_defaults(self):
        return {
            "default_pen_color": QColor(0, 0, 0),
            "default_pen_width": 2,
            "default_font": QFont("Arial", 24),
            "canvas_background_color": QColor(255, 255, 255),
            "show_manual_on_startup": True  # 🔴 新增默认设置
        }

    def load_settings(self):
        defaults = self.get_defaults()
        settings = {}

        pen_color_str = self.settings.value("defaults/pen_color", defaults["default_pen_color"].name())
        settings["default_pen_color"] = QColor(pen_color_str)

        settings["default_pen_width"] = int(self.settings.value("defaults/pen_width", defaults["default_pen_width"]))

        font_str = self.settings.value("defaults/font", defaults["default_font"].toString())
        font = QFont(); font.fromString(font_str)
        settings["default_font"] = font

        bg_color_str = self.settings.value("canvas/background_color", defaults["canvas_background_color"].name())
        settings["canvas_background_color"] = QColor(bg_color_str)
        
        # 🔴 新增加载逻辑
        settings["show_manual_on_startup"] = self.settings.value("general/show_manual_on_startup", 
                                                                  defaults["show_manual_on_startup"], 
                                                                  type=bool)
        return settings

    def save_settings(self, settings):
        self.settings.setValue("defaults/pen_color", settings["default_pen_color"].name())
        self.settings.setValue("defaults/pen_width", settings["default_pen_width"])
        self.settings.setValue("defaults/font", settings["default_font"].toString())
        self.settings.setValue("canvas/background_color", settings["canvas_background_color"].name())
        
        # 🔴 新增保存逻辑
        if "show_manual_on_startup" in settings:
            self.settings.setValue("general/show_manual_on_startup", settings["show_manual_on_startup"])
        
        self.settings.sync()