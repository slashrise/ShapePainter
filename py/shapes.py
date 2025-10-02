import copy
from PyQt6.QtGui import QColor, QPolygonF, QPainterPath, QFont, QTransform
from PyQt6.QtCore import Qt, QRect, QPoint, QPointF

class Layer:
    def __init__(self, name):
        self.name = name
        self.shapes = []
        self.is_visible = True
        self.is_locked = False
    def clone(self):
        new_layer = Layer(self.name)
        new_layer.is_visible = self.is_visible
        new_layer.is_locked = self.is_locked
        new_layer.shapes = [s.clone() for s in self.shapes]
        return new_layer

def get_transformed_rect(shape):
    if shape.angle == 0 and shape.scale_x == 1 and shape.scale_y == 1:
        return shape.get_bounding_box()
    original_bbox = shape.get_bounding_box()
    center = original_bbox.center()
    transform = QTransform().translate(center.x(), center.y()).rotate(shape.angle).scale(shape.scale_x, shape.scale_y).translate(-center.x(), -center.y())
    return transform.mapRect(original_bbox)

# --- Base class for all shapes to avoid code duplication ---
class BaseShape:
    def __init__(self):
        self.angle = 0.0
        self.scale_x = 1.0
        self.scale_y = 1.0
    def get_transformed_bounding_box(self): return get_transformed_rect(self)
    def rotate(self, rotation_delta=0):
        self.angle = (self.angle + rotation_delta) % 360
    def flip_horizontal(self):
        self.scale_x *= -1
    def flip_vertical(self):
        self.scale_y *= -1
    def clone_transform(self, cloned_shape):
        cloned_shape.angle, cloned_shape.scale_x, cloned_shape.scale_y = self.angle, self.scale_x, self.scale_y
        return cloned_shape

class Text(BaseShape):
    def __init__(self, rect, text, font, color=QColor(0,0,0), has_border=False, border_color=QColor(0,0,0)):
        super().__init__()
        self.rect, self.text, self.font, self.color, self.has_border, self.border_color = rect, text, font, color, has_border, border_color
    def get_bounding_box(self): return self.rect
    def move(self, dx, dy): self.rect.translate(dx, dy)
    def clone(self):
        cloned = Text(QRect(self.rect), self.text, QFont(self.font), QColor(self.color), self.has_border, QColor(self.border_color))
        return self.clone_transform(cloned)
    def scale(self, factor, center):
        centerF = QPointF(center)
        self.rect = QRect((centerF + (QPointF(self.rect.topLeft()) - centerF) * factor).toPoint(), (centerF + (QPointF(self.rect.bottomRight()) - centerF) * factor).toPoint())
        new_size = self.font.pointSizeF() * factor
        if new_size >= 1: self.font.setPointSizeF(new_size)

class Square(BaseShape):
    def __init__(self, top_left, size, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        super().__init__()
        self.top_left, self.size, self.color, self.width, self.fill_color, self.fill_style = top_left, size, color, width, fill_color, fill_style
    def get_bounding_box(self): return QRect(self.top_left.x(), self.top_left.y(), int(self.size), int(self.size))
    def move(self, dx, dy): self.top_left.setX(self.top_left.x() + dx); self.top_left.setY(self.top_left.y() + dy)
    def clone(self): return self.clone_transform(copy.deepcopy(self))
    def scale(self, factor, center):
        centerF = QPointF(center)
        self.top_left = (centerF + (QPointF(self.top_left) - centerF) * factor).toPoint()
        self.size *= factor

class Ellipse(BaseShape):
    def __init__(self, top_left, bottom_right, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        super().__init__()
        self.top_left, self.bottom_right, self.color, self.width, self.fill_color, self.fill_style = top_left, bottom_right, color, width, fill_color, fill_style
    def get_bounding_box(self): return QRect(self.top_left, self.bottom_right).normalized()
    def move(self, dx, dy): self.top_left.setX(self.top_left.x() + dx); self.top_left.setY(self.top_left.y() + dy); self.bottom_right.setX(self.bottom_right.x() + dx); self.bottom_right.setY(self.bottom_right.y() + dy)
    def clone(self): return self.clone_transform(copy.deepcopy(self))
    def scale(self, factor, center):
        centerF = QPointF(center)
        self.top_left = (centerF + (QPointF(self.top_left) - centerF) * factor).toPoint()
        self.bottom_right = (centerF + (QPointF(self.bottom_right) - centerF) * factor).toPoint()

class RoundedRectangle(Ellipse): pass
class Rectangle(Ellipse): pass

class Polygon(BaseShape):
    def __init__(self, points, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        super().__init__()
        self.points, self.color, self.width, self.fill_color, self.fill_style = points, color, width, fill_color, fill_style
    def get_bounding_box(self): return QPolygonF([QPointF(p) for p in self.points]).boundingRect().toRect()
    def move(self, dx, dy):
        for p in self.points: p.setX(p.x() + dx); p.setY(p.y() + dy)
    def clone(self): return self.clone_transform(copy.deepcopy(self))
    def scale(self, factor, center):
        centerF = QPointF(center)
        self.points = [(centerF + (QPointF(p) - centerF) * factor).toPoint() for p in self.points]
    def get_nodes(self): return self.points
    def set_node_at(self, index, pos):
        if 0 <= index < len(self.points): self.points[index] = pos

class Circle(BaseShape):
    def __init__(self, center, radius, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        super().__init__()
        self.center, self.radius, self.color, self.width, self.fill_color, self.fill_style = center, radius, color, width, fill_color, fill_style
    def get_bounding_box(self): return QRect(int(self.center.x() - self.radius), int(self.center.y() - self.radius), int(self.radius * 2), int(self.radius * 2))
    def move(self, dx, dy): self.center.setX(self.center.x() + dx); self.center.setY(self.center.y() + dy)
    def clone(self): return self.clone_transform(copy.deepcopy(self))
    def scale(self, factor, center_of_selection):
        centerF = QPointF(center_of_selection)
        self.center = (centerF + (QPointF(self.center) - centerF) * factor).toPoint()
        self.radius *= factor

class Point(BaseShape):
    def __init__(self, pos, color=QColor(0,0,0), width=2):
        super().__init__()
        self.pos, self.color, self.width = pos, color, width
    def get_bounding_box(self): return QRect(self.pos.x() - self.width, self.pos.y() - self.width, self.width * 2, self.width * 2)
    def move(self, dx, dy): self.pos.setX(self.pos.x() + dx); self.pos.setY(self.pos.y() + dy)
    def clone(self): return self.clone_transform(copy.deepcopy(self))
    def scale(self, factor, center):
        centerF = QPointF(center)
        self.pos = (centerF + (QPointF(self.pos) - centerF) * factor).toPoint()

class Line(BaseShape):
    def __init__(self, p1, p2, color=QColor(0,0,0), width=2):
        super().__init__()
        self.p1, self.p2, self.color, self.width = p1, p2, color, width
    def get_bounding_box(self): return QRect(self.p1, self.p2).normalized()
    def move(self, dx, dy): self.p1.setX(self.p1.x() + dx); self.p1.setY(self.p1.y() + dy); self.p2.setX(self.p2.x() + dx); self.p2.setY(self.p2.y() + dy)
    def clone(self): return self.clone_transform(copy.deepcopy(self))
    def scale(self, factor, center):
        centerF = QPointF(center)
        self.p1 = (centerF + (QPointF(self.p1) - centerF) * factor).toPoint()
        self.p2 = (centerF + (QPointF(self.p2) - centerF) * factor).toPoint()

class Arc(BaseShape):
    def __init__(self, p1, p2, p3, color=QColor(0,0,0), width=2):
        super().__init__()
        self.p1, self.p2, self.p3, self.color, self.width = p1, p2, p3, color, width
    def get_painter_path(self):
        path = QPainterPath(QPointF(self.p1)) # 使用 QPointF 初始化
        path.quadTo(QPointF(self.p3), QPointF(self.p2))
        return path
    def get_bounding_box(self): return self.get_painter_path().boundingRect().toRect()
    def move(self, dx, dy): self.p1.setX(self.p1.x() + dx); self.p1.setY(self.p1.y() + dy); self.p2.setX(self.p2.x() + dx); self.p2.setY(self.p2.y() + dy); self.p3.setX(self.p3.x() + dx); self.p3.setY(self.p3.y() + dy)
    def clone(self): return self.clone_transform(copy.deepcopy(self))
    def scale(self, factor, center):
        centerF = QPointF(center)
        self.p1 = (centerF + (QPointF(self.p1) - centerF) * factor).toPoint()
        self.p2 = (centerF + (QPointF(self.p2) - centerF) * factor).toPoint()
        self.p3 = (centerF + (QPointF(self.p3) - centerF) * factor).toPoint()
    def get_nodes(self): return [self.p1, self.p2, self.p3]
    def set_node_at(self, index, pos):
        if index == 0: self.p1 = pos
        elif index == 1: self.p2 = pos
        elif index == 2: self.p3 = pos

class Polyline(Polygon): pass

class ShapeGroup:
    def __init__(self, shapes):
        self.shapes = shapes
        self.color = QColor(0,0,0)
    def get_bounding_box(self):
        if not self.shapes: return QRect()
        total_bbox = self.shapes[0].get_bounding_box()
        for shape in self.shapes[1:]: total_bbox = total_bbox.united(shape.get_bounding_box())
        return total_bbox
    def get_transformed_bounding_box(self):
        if not self.shapes: return QRect()
        total_bbox = self.shapes[0].get_transformed_bounding_box()
        for shape in self.shapes[1:]: total_bbox = total_bbox.united(shape.get_transformed_bounding_box())
        return total_bbox
    def move(self, dx, dy):
        for shape in self.shapes: shape.move(dx, dy)
    def clone(self): return ShapeGroup([s.clone() for s in self.shapes])
    def scale(self, factor, center):
        for shape in self.shapes: shape.scale(factor, center)
    def rotate(self, rotation_delta=0):
        for shape in self.shapes: shape.rotate(rotation_delta)
    def flip_horizontal(self):
        for shape in self.shapes: shape.flip_horizontal()
    def flip_vertical(self):
        for shape in self.shapes: shape.flip_vertical()

class Arrow(Line):
    pass
