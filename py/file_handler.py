# --- START OF FILE file_handler.py (Complete and Corrected) ---

import json
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt, QRect, QPoint

from shapes import *

class ProjectHandler:
    @staticmethod
    def save(layers, file_path):
        """将图层和图形数据序列化并保存到JSON文件。"""
        data_to_save = []
        for layer in layers:
            shapes_data = []
            for shape in layer.shapes:
                shape_dict = None
                common_attrs = {
                    "color": shape.color.name(), 
                    "width": shape.width if hasattr(shape, 'width') else 0,
                    "angle": shape.angle,
                    "scale_x": shape.scale_x,
                    "scale_y": shape.scale_y
                }
                if hasattr(shape, 'fill_color'):
                    common_attrs["fill_color"] = shape.fill_color.name() if shape.fill_color else None
                    common_attrs["fill_style"] = int(shape.fill_style)
                
                if isinstance(shape, Text):
                    shape_dict = {"type": "text", "rect": [shape.rect.x(), shape.rect.y(), shape.rect.width(), shape.rect.height()], "text": shape.text, "font_family": shape.font.family(), "font_size": shape.font.pointSize(), "color": shape.color.name(), "has_border": shape.has_border, "border_color": shape.border_color.name()}
                    shape_dict.update(common_attrs)
                elif isinstance(shape, Arrow):
                    shape_dict = {"type": "arrow", "p1": [shape.p1.x(), shape.p1.y()], "p2": [shape.p2.x(), shape.p2.y()], **common_attrs}
                
                elif isinstance(shape, Path):
                    sub_paths_data = []
                    for sub_path in shape.sub_paths:
                        segments_data = []
                        for seg in sub_path:
                            segments_data.append({
                                "anchor": [seg.anchor.x(), seg.anchor.y()],
                                "handle1": [seg.handle1.x(), seg.handle1.y()],
                                "handle2": [seg.handle2.x(), seg.handle2.y()],
                                "node_type": seg.node_type
                            })
                        sub_paths_data.append(segments_data)
                    shape_dict = {"type": "path", "sub_paths": sub_paths_data, **common_attrs}
                
                elif isinstance(shape, (Polyline, Polygon)):
                    points_data = [[p.x(), p.y()] for p in shape.points]; shape_dict = {"type": "polyline" if isinstance(shape, Polyline) else "polygon", "points": points_data, **common_attrs}
                elif isinstance(shape, Point):
                    shape_dict = {"type": "point", "pos": [shape.pos.x(), shape.pos.y()], **common_attrs}
                elif isinstance(shape, Line):
                    shape_dict = {"type": "line", "p1": [shape.p1.x(), shape.p1.y()], "p2": [shape.p2.x(), shape.p2.y()], **common_attrs}
                elif isinstance(shape, Rectangle):
                    shape_dict = {"type": "rectangle", "top_left": [shape.top_left.x(), shape.top_left.y()], "bottom_right": [shape.bottom_right.x(), shape.bottom_right.y()], **common_attrs}
                elif isinstance(shape, Square):
                    shape_dict = {"type": "square", "top_left": [shape.top_left.x(), shape.top_left.y()], "size": shape.size, **common_attrs}
                elif isinstance(shape, Circle):
                    shape_dict = {"type": "circle", "center": [shape.center.x(), shape.center.y()], "radius": shape.radius, **common_attrs}
                elif isinstance(shape, Ellipse):
                    shape_dict = {"type": "ellipse", "top_left": [shape.top_left.x(), shape.top_left.y()], "bottom_right": [shape.bottom_right.x(), shape.bottom_right.y()], **common_attrs}
                elif isinstance(shape, RoundedRectangle):
                    shape_dict = {"type": "rounded_rect", "top_left": [shape.top_left.x(), shape.top_left.y()], "bottom_right": [shape.bottom_right.x(), shape.bottom_right.y()], **common_attrs}
                
                if shape_dict:
                    shapes_data.append(shape_dict)
            
            data_to_save.append({"name": layer.name, "is_visible": layer.is_visible, "is_locked": layer.is_locked, "shapes": shapes_data})
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)

    @staticmethod
    def load(file_path):
        """从JSON文件加载并反序列化图层和图形数据。"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data_to_load = json.load(f)
        
        loaded_layers = []
        for layer_data in data_to_load:
            new_layer = Layer(layer_data["name"])
            new_layer.is_visible = layer_data.get("is_visible", True)
            new_layer.is_locked = layer_data.get("is_locked", False)
            
            for shape_data in layer_data["shapes"]:
                pen_color = QColor(shape_data["color"])
                width = shape_data.get("width", 2)
                fill_color_name = shape_data.get("fill_color")
                fill_color = QColor(fill_color_name) if fill_color_name else None
                fill_style_val = shape_data.get("fill_style", int(Qt.BrushStyle.NoBrush))
                fill_style = Qt.BrushStyle(fill_style_val)

                new_shape = None
                shape_type = shape_data.get("type")

                if shape_type == "text":
                    r = shape_data["rect"]; rect = QRect(r[0], r[1], r[2], r[3])
                    font = QFont(shape_data.get("font_family", "Arial"), shape_data.get("font_size", 20))
                    has_border = shape_data.get("has_border", False); border_color = QColor(shape_data.get("border_color", "#000000"))
                    new_shape = Text(rect, shape_data["text"], font, pen_color, has_border, border_color)
                
                elif shape_type == "path":
                    sub_paths = []
                    # Handle old format (with "segments") and new format (with "sub_paths")
                    sub_paths_list_data = shape_data.get("sub_paths")
                    if sub_paths_list_data is None: # Legacy format
                        sub_paths_list_data = [shape_data.get("segments", [])]

                    for sub_path_data in sub_paths_list_data:
                        segments = []
                        for seg_data in sub_path_data:
                            anchor = QPoint(seg_data["anchor"][0], seg_data["anchor"][1])
                            handle1 = QPoint(seg_data["handle1"][0], seg_data["handle1"][1])
                            handle2 = QPoint(seg_data["handle2"][0], seg_data["handle2"][1])
                            node_type = seg_data.get("node_type", PathSegment.CORNER)
                            segments.append(PathSegment(anchor, handle1, handle2, node_type))
                        sub_paths.append(segments)
                    # The 'is_closed' property is now dynamically calculated, so we don't load it from the file for Path
                    new_shape = Path(sub_paths, pen_color, width)
                
                elif shape_type == "polyline":
                    points = [QPoint(p[0], p[1]) for p in shape_data["points"]]
                    new_shape = Polyline(points, pen_color, width)
                elif shape_type == "point":
                    new_shape = Point(QPoint(shape_data["pos"][0], shape_data["pos"][1]), pen_color, width)
                elif shape_type == "arrow":
                    p1 = QPoint(shape_data["p1"][0], shape_data["p1"][1]); p2 = QPoint(shape_data["p2"][0], shape_data["p2"][1])
                    new_shape = Arrow(p1, p2, pen_color, width)
                elif shape_type == "line":
                    p1 = QPoint(shape_data["p1"][0], shape_data["p1"][1]); p2 = QPoint(shape_data["p2"][0], shape_data["p2"][1])
                    new_shape = Line(p1, p2, pen_color, width)
                elif shape_type == "rectangle":
                    tl = QPoint(shape_data["top_left"][0], shape_data["top_left"][1]); br = QPoint(shape_data["bottom_right"][0], shape_data["bottom_right"][1])
                    new_shape = Rectangle(tl, br, pen_color, width, fill_color, fill_style)
                elif shape_type == "square":
                    tl = QPoint(shape_data["top_left"][0], shape_data["top_left"][1]); size = shape_data["size"]
                    new_shape = Square(tl, size, pen_color, width, fill_color, fill_style)
                elif shape_type == "circle":
                    center = QPoint(shape_data["center"][0], shape_data["center"][1]); radius = shape_data["radius"]
                    new_shape = Circle(center, radius, pen_color, width, fill_color, fill_style)
                elif shape_type == "ellipse":
                    tl = QPoint(shape_data["top_left"][0], shape_data["top_left"][1]); br = QPoint(shape_data["bottom_right"][0], shape_data["bottom_right"][1])
                    new_shape = Ellipse(tl, br, pen_color, width, fill_color, fill_style)
                elif shape_type == "rounded_rect":
                    tl = QPoint(shape_data["top_left"][0], shape_data["top_left"][1]); br = QPoint(shape_data["bottom_right"][0], shape_data["bottom_right"][1])
                    new_shape = RoundedRectangle(tl, br, pen_color, width, fill_color, fill_style)
                elif shape_type == "polygon":
                    points = [QPoint(p[0], p[1]) for p in shape_data["points"]]
                    new_shape = Polygon(points, pen_color, width, fill_color, fill_style)
                
                if new_shape:
                    new_shape.angle = shape_data.get("angle", 0.0)
                    new_shape.scale_x = shape_data.get("scale_x", 1.0)
                    new_shape.scale_y = shape_data.get("scale_y", 1.0)
                    if hasattr(new_shape, 'fill_color'): # Check again for shapes that might not have it
                        new_shape.fill_color = fill_color
                        new_shape.fill_style = fill_style
                    
                    new_layer.shapes.append(new_shape)
            
            loaded_layers.append(new_layer)
            
        return loaded_layers
        
# --- END OF FILE file_handler.py ---