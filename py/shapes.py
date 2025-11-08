import copy
from PyQt6.QtGui import QColor, QPolygonF, QPainterPath, QFont, QTransform, QPainter
from PyQt6.QtCore import Qt, QRect, QPoint, QPointF

class Layer:
    def __init__(self, name):
        self.name = name
        self.shapes = []
        self.is_visible = True
        self.is_locked = False
        self.opacity = 1.0
        self.blend_mode = QPainter.CompositionMode.CompositionMode_SourceOver
        self.cache = None
        self.is_dirty = True

    def clone(self):
        # 🔴 手动实现克隆，不再使用 deepcopy
        new_layer = Layer(self.name)
        new_layer.is_visible = self.is_visible
        new_layer.is_locked = self.is_locked
        new_layer.opacity = self.opacity
        new_layer.blend_mode = self.blend_mode
        # 递归地克隆所有图形
        new_layer.shapes = [s.clone() for s in self.shapes]
        # 关键：不复制 cache 和 is_dirty 状态，让新图层自然生成缓存
        return new_layer

class PathSegment:
    CORNER = 'corner'; SMOOTH = 'smooth'
    def __init__(self, anchor, handle1=None, handle2=None, node_type=CORNER): self.anchor = anchor; self.handle1 = handle1 if handle1 is not None else QPoint(anchor); self.handle2 = handle2 if handle2 is not None else QPoint(anchor); self.node_type = node_type
    def clone(self): return PathSegment(QPoint(self.anchor), QPoint(self.handle1), QPoint(self.handle2), self.node_type)
    def to_corner(self): self.handle1 = QPoint(self.anchor); self.handle2 = QPoint(self.anchor); self.node_type = self.CORNER
    def to_smooth(self, handle=None):
        if handle: self.handle2 = handle; self.handle1 = self.anchor - (self.handle2 - self.anchor)
        else:
            if self.handle1 == self.anchor and self.handle2 == self.anchor: self.handle1 = self.anchor - QPoint(20, 0); self.handle2 = self.anchor + QPoint(20, 0)
        self.node_type = self.SMOOTH

def get_transformed_rect(shape):
    if shape.angle == 0 and shape.scale_x == 1 and shape.scale_y == 1: return shape.get_bounding_box()
    original_bbox = shape.get_bounding_box(); center = original_bbox.center()
    transform = QTransform().translate(center.x(), center.y()).rotate(shape.angle).scale(shape.scale_x, shape.scale_y).translate(-center.x(), -center.y())
    return transform.mapRect(original_bbox)

class BaseShape:
    def __init__(self): self.angle = 0.0; self.scale_x = 1.0; self.scale_y = 1.0; self.layer = None
    def get_transformed_bounding_box(self): return get_transformed_rect(self)
    def rotate(self, rotation_delta=0): self.angle = (self.angle + rotation_delta) % 360
    def flip_horizontal(self): self.scale_x *= -1
    def flip_vertical(self): self.scale_y *= -1
    def clone_transform(self, cloned_shape):
        cloned_shape.angle = self.angle
        cloned_shape.scale_x = self.scale_x
        cloned_shape.scale_y = self.scale_y
        # 🔴 克隆时不复制 layer 引用，因为它可能指向一个包含不可复制缓存的旧图层
        cloned_shape.layer = None
        return cloned_shape

class Text(BaseShape):
    def __init__(self, rect, text, font, color=QColor(0,0,0), has_border=False, border_color=QColor(0,0,0), alignment=Qt.AlignmentFlag.AlignLeft):
        super().__init__(); self.rect, self.text, self.font, self.color = rect, text, font, color; self.has_border, self.border_color, self.alignment = has_border, border_color, alignment
    def get_bounding_box(self): return self.rect
    def move(self, dx, dy): self.rect.translate(dx, dy)
    def clone(self): 
        cloned = Text(QRect(self.rect), self.text, QFont(self.font), QColor(self.color), self.has_border, QColor(self.border_color), self.alignment)
        return self.clone_transform(cloned)
    def scale(self, factor, center):
        centerF = QPointF(center); self.rect = QRect((centerF + (QPointF(self.rect.topLeft()) - centerF) * factor).toPoint(), (centerF + (QPointF(self.rect.bottomRight()) - centerF) * factor).toPoint())
        new_size = self.font.pointSizeF() * factor
        if new_size >= 1: self.font.setPointSizeF(new_size)

class Square(BaseShape):
    def __init__(self, top_left, size, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        super().__init__(); self.top_left, self.size, self.color, self.width = top_left, size, color, width; self.fill_color, self.fill_style = fill_color, fill_style
    def get_bounding_box(self): return QRect(self.top_left.x(), self.top_left.y(), int(self.size), int(self.size))
    def move(self, dx, dy): self.top_left.setX(self.top_left.x() + dx); self.top_left.setY(self.top_left.y() + dy)
    def clone(self): 
        # 🔴 手动克隆
        cloned = Square(QPoint(self.top_left), self.size, QColor(self.color), self.width, QColor(self.fill_color) if self.fill_color else None, self.fill_style)
        return self.clone_transform(cloned)
    def scale(self, factor, center): centerF = QPointF(center); self.top_left = (centerF + (QPointF(self.top_left) - centerF) * factor).toPoint(); self.size *= factor

class Ellipse(BaseShape):
    def __init__(self, top_left, bottom_right, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        super().__init__(); self.top_left, self.bottom_right, self.color, self.width = top_left, bottom_right, color, width; self.fill_color, self.fill_style = fill_color, fill_style
    def get_bounding_box(self): return QRect(self.top_left, self.bottom_right).normalized()
    def move(self, dx, dy): self.top_left.setX(self.top_left.x() + dx); self.top_left.setY(self.top_left.y() + dy); self.bottom_right.setX(self.bottom_right.x() + dx); self.bottom_right.setY(self.bottom_right.y() + dy)
    def clone(self): 
        # 🔴 手动克隆
        cloned = Ellipse(QPoint(self.top_left), QPoint(self.bottom_right), QColor(self.color), self.width, QColor(self.fill_color) if self.fill_color else None, self.fill_style)
        return self.clone_transform(cloned)
    def scale(self, factor, center): centerF = QPointF(center); self.top_left = (centerF + (QPointF(self.top_left) - centerF) * factor).toPoint(); self.bottom_right = (centerF + (QPointF(self.bottom_right) - centerF) * factor).toPoint()

class RoundedRectangle(Ellipse):
    def clone(self): # 🔴 子类也需要覆盖clone
        cloned = RoundedRectangle(QPoint(self.top_left), QPoint(self.bottom_right), QColor(self.color), self.width, QColor(self.fill_color) if self.fill_color else None, self.fill_style)
        return self.clone_transform(cloned)

class Rectangle(Ellipse):
    def clone(self): # 🔴 子类也需要覆盖clone
        cloned = Rectangle(QPoint(self.top_left), QPoint(self.bottom_right), QColor(self.color), self.width, QColor(self.fill_color) if self.fill_color else None, self.fill_style)
        return self.clone_transform(cloned)

class Polygon(BaseShape):
    def __init__(self, points, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        super().__init__(); self.points, self.color, self.width, self.fill_color = points, color, width, fill_color; self.fill_style = fill_style
    def get_bounding_box(self): return QPolygonF([QPointF(p) for p in self.points]).boundingRect().toRect()
    def move(self, dx, dy):
        for p in self.points: p.setX(p.x() + dx); p.setY(p.y() + dy)
    def clone(self): 
        # 🔴 手动克隆
        cloned_points = [QPoint(p) for p in self.points]
        cloned = Polygon(cloned_points, QColor(self.color), self.width, QColor(self.fill_color) if self.fill_color else None, self.fill_style)
        return self.clone_transform(cloned)
    def scale(self, factor, center): centerF = QPointF(center); self.points = [(centerF + (QPointF(p) - centerF) * factor).toPoint() for p in self.points]
    def get_nodes(self): return self.points
    def set_node_at(self, index, pos):
        if 0 <= index < len(self.points): self.points[index] = pos

class Circle(BaseShape):
    def __init__(self, center, radius, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        super().__init__(); self.center, self.radius, self.color, self.width = center, radius, color, width; self.fill_color, self.fill_style = fill_color, fill_style
    def get_bounding_box(self): return QRect(int(self.center.x() - self.radius), int(self.center.y() - self.radius), int(self.radius * 2), int(self.radius * 2))
    def move(self, dx, dy): self.center.setX(self.center.x() + dx); self.center.setY(self.center.y() + dy)
    def clone(self): 
        cloned = Circle(QPoint(self.center), self.radius, QColor(self.color), self.width, QColor(self.fill_color) if self.fill_color else None, self.fill_style)
        return self.clone_transform(cloned)
    def scale(self, factor, center_of_selection): centerF = QPointF(center_of_selection); self.center = (centerF + (QPointF(self.center) - centerF) * factor).toPoint(); self.radius *= factor

class Point(BaseShape):
    def __init__(self, pos, color=QColor(0,0,0), width=2): super().__init__(); self.pos, self.color, self.width = pos, color, width
    def get_bounding_box(self): return QRect(self.pos.x() - self.width, self.pos.y() - self.width, self.width * 2, self.width * 2)
    def move(self, dx, dy): self.pos.setX(self.pos.x() + dx); self.pos.setY(self.pos.y() + dy)
    def clone(self):
        cloned = Point(QPoint(self.pos), QColor(self.color), self.width)
        return self.clone_transform(cloned)
    def scale(self, factor, center): centerF = QPointF(center); self.pos = (centerF + (QPointF(self.pos) - centerF) * factor).toPoint()

class Line(BaseShape):
    def __init__(self, p1, p2, color=QColor(0,0,0), width=2): super().__init__(); self.p1, self.p2, self.color, self.width = p1, p2, color, width
    def get_bounding_box(self): return QRect(self.p1, self.p2).normalized()
    def move(self, dx, dy): self.p1.setX(self.p1.x() + dx); self.p1.setY(self.p1.y() + dy); self.p2.setX(self.p2.x() + dx); self.p2.setY(self.p2.y() + dy)
    def clone(self):
        cloned = Line(QPoint(self.p1), QPoint(self.p2), QColor(self.color), self.width)
        return self.clone_transform(cloned)
    def scale(self, factor, center): centerF = QPointF(center); self.p1 = (centerF + (QPointF(self.p1) - centerF) * factor).toPoint(); self.p2 = (centerF + (QPointF(self.p2) - centerF) * factor).toPoint()

class Path(BaseShape):
    def __init__(self, sub_paths, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        super().__init__(); self.sub_paths = sub_paths; self.color = color; self.width = width; self.fill_color = fill_color; self.fill_style = fill_style
    @property
    def is_closed(self):
        if self.sub_paths and self.sub_paths[0] and len(self.sub_paths[0]) > 1: return self.sub_paths[0][0].anchor == self.sub_paths[0][-1].anchor
        return False
    def get_painter_path(self):
        if not self.sub_paths or not self.sub_paths[0]: return QPainterPath()
        final_path = QPainterPath()
        for sub_path in self.sub_paths:
            if not sub_path: continue
            path = QPainterPath(QPointF(sub_path[0].anchor))
            for i in range(len(sub_path) - 1): start_seg, end_seg = sub_path[i], sub_path[i+1]; path.cubicTo(QPointF(start_seg.handle2), QPointF(end_seg.handle1), QPointF(end_seg.anchor))
            if len(sub_path) > 1 and sub_path[0].anchor == sub_path[-1].anchor: path.closeSubpath()
            final_path.addPath(path)
        return final_path
    def get_bounding_box(self): return self.get_painter_path().boundingRect().toRect()
    def move(self, dx, dy):
        for sub_path in self.sub_paths:
            for seg in sub_path: seg.anchor.setX(seg.anchor.x() + dx); seg.anchor.setY(seg.anchor.y() + dy); seg.handle1.setX(seg.handle1.x() + dx); seg.handle1.setY(seg.handle1.y() + dy); seg.handle2.setX(seg.handle2.x() + dx); seg.handle2.setY(seg.handle2.y() + dy)
    def clone(self):
        cloned_sub_paths = [[seg.clone() for seg in sp] for sp in self.sub_paths]
        cloned = Path(cloned_sub_paths, QColor(self.color), self.width, QColor(self.fill_color) if self.fill_color else None, self.fill_style)
        return self.clone_transform(cloned)
    def scale(self, factor, center):
        centerF = QPointF(center)
        for sub_path in self.sub_paths:
            for seg in sub_path: seg.anchor = (centerF + (QPointF(seg.anchor) - centerF) * factor).toPoint(); seg.handle1 = (centerF + (QPointF(seg.handle1) - centerF) * factor).toPoint(); seg.handle2 = (centerF + (QPointF(seg.handle2) - centerF) * factor).toPoint()
    def get_nodes(self):
        nodes = [];
        for sub_path in self.sub_paths:
            for seg in sub_path: nodes.append(seg.anchor); nodes.append(seg.handle1); nodes.append(seg.handle2)
        return nodes
    def set_node_at(self, index, pos):
        count = 0
        for sub_path in self.sub_paths:
            num_nodes_in_subpath = len(sub_path) * 3
            if count + num_nodes_in_subpath > index:
                local_index = index - count; seg_index = local_index // 3; node_type = local_index % 3
                if node_type == 0: sub_path[seg_index].anchor = pos
                elif node_type == 1: sub_path[seg_index].handle1 = pos
                elif node_type == 2: sub_path[seg_index].handle2 = pos
                return
            count += num_nodes_in_subpath
    def remove_segment(self, sub_path_index, segment_index):
        if 0 <= sub_path_index < len(self.sub_paths):
            sub_path = self.sub_paths[sub_path_index]
            if 0 <= segment_index < len(sub_path):
                is_closed_path = len(sub_path) > 1 and sub_path[0].anchor == sub_path[-1].anchor
                if is_closed_path and (segment_index == 0 or segment_index == len(sub_path) - 1): sub_path.pop(-1); sub_path.pop(0)
                else: sub_path.pop(segment_index)
                if not sub_path: self.sub_paths.pop(sub_path_index)
                return True
        return False

class Polyline(Polygon):
    def clone(self): # 🔴 子类也需要覆盖clone
        cloned_points = [QPoint(p) for p in self.points]
        cloned = Polyline(cloned_points, QColor(self.color), self.width, QColor(self.fill_color) if self.fill_color else None, self.fill_style)
        return self.clone_transform(cloned)

class ShapeGroup(BaseShape):
    def __init__(self, shapes): super().__init__(); self.shapes = shapes; self.color = QColor(0,0,0)
    def get_bounding_box(self):
        if not self.shapes: return QRect()
        total_bbox = self.shapes[0].get_bounding_box()
        for shape in self.shapes[1:]: total_bbox = total_bbox.united(shape.get_bounding_box())
        return total_bbox
    def move(self, dx, dy):
        for shape in self.shapes: shape.move(dx, dy)
    def clone(self): 
        # 🔴 手动克隆
        cloned_shapes = [s.clone() for s in self.shapes]
        cloned_group = ShapeGroup(cloned_shapes)
        return self.clone_transform(cloned_group)
    def scale(self, factor, center):
        for shape in self.shapes: shape.scale(factor, center)
    def rotate(self, rotation_delta=0):
        for shape in self.shapes: shape.rotate(rotation_delta)
    def flip_horizontal(self):
        for shape in self.shapes: shape.flip_horizontal()
    def flip_vertical(self):
        for shape in self.shapes: shape.flip_vertical()

class Arrow(Line):
    def clone(self): # 🔴 子类也需要覆盖clone
        cloned = Arrow(QPoint(self.p1), QPoint(self.p2), QColor(self.color), self.width)
        return self.clone_transform(cloned)