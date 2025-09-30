import copy
from PyQt6.QtGui import QColor, QPolygonF, QPainterPath, QFont
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

class Text:
    def __init__(self, rect, text, font, color=QColor(0,0,0), has_border=False, border_color=QColor(0,0,0)):
        self.rect = rect
        self.text = text
        self.font = font
        self.color = color
        self.has_border = has_border
        self.border_color = border_color
    def get_bounding_box(self):
        return self.rect
    def move(self, dx, dy):
        self.rect.translate(dx, dy)
    def clone(self):
        return Text(QRect(self.rect), self.text, QFont(self.font), QColor(self.color), self.has_border, QColor(self.border_color))
    def scale(self, factor, center):
        centerF = QPointF(center)
        new_top_left = centerF + (QPointF(self.rect.topLeft()) - centerF) * factor
        new_bottom_right = centerF + (QPointF(self.rect.bottomRight()) - centerF) * factor
        self.rect = QRect(new_top_left.toPoint(), new_bottom_right.toPoint())
        original_size = self.font.pointSizeF()
        new_size = original_size * factor
        if new_size >= 1:
            self.font.setPointSizeF(new_size)

class Square:
    def __init__(self, top_left, size, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        self.top_left, self.size, self.color, self.width, self.fill_color, self.fill_style = top_left, size, color, width, fill_color, fill_style
    def get_bounding_box(self):
        return QRect(self.top_left.x(), self.top_left.y(), int(self.size), int(self.size))
    def move(self, dx, dy):
        self.top_left.setX(self.top_left.x() + dx)
        self.top_left.setY(self.top_left.y() + dy)
    def clone(self):
        return copy.deepcopy(self)
    def scale(self, factor, center):
        centerF = QPointF(center)
        new_top_left = centerF + (QPointF(self.top_left) - centerF) * factor
        self.top_left = new_top_left.toPoint()
        self.size *= factor

class Ellipse:
    def __init__(self, top_left, bottom_right, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        self.top_left, self.bottom_right, self.color, self.width, self.fill_color, self.fill_style = top_left, bottom_right, color, width, fill_color, fill_style
    def get_bounding_box(self):
        return QRect(self.top_left, self.bottom_right).normalized()
    def move(self, dx, dy):
        self.top_left.setX(self.top_left.x() + dx)
        self.top_left.setY(self.top_left.y() + dy)
        self.bottom_right.setX(self.bottom_right.x() + dx)
        self.bottom_right.setY(self.bottom_right.y() + dy)
    def clone(self):
        return copy.deepcopy(self)
    def scale(self, factor, center):
        centerF = QPointF(center)
        new_top_left = centerF + (QPointF(self.top_left) - centerF) * factor
        new_bottom_right = centerF + (QPointF(self.bottom_right) - centerF) * factor
        self.top_left = new_top_left.toPoint()
        self.bottom_right = new_bottom_right.toPoint()

class RoundedRectangle:
    def __init__(self, top_left, bottom_right, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        self.top_left, self.bottom_right, self.color, self.width, self.fill_color, self.fill_style = top_left, bottom_right, color, width, fill_color, fill_style
    def get_bounding_box(self):
        return QRect(self.top_left, self.bottom_right).normalized()
    def move(self, dx, dy):
        self.top_left.setX(self.top_left.x() + dx)
        self.top_left.setY(self.top_left.y() + dy)
        self.bottom_right.setX(self.bottom_right.x() + dx)
        self.bottom_right.setY(self.bottom_right.y() + dy)
    def clone(self):
        return copy.deepcopy(self)
    def scale(self, factor, center):
        centerF = QPointF(center)
        new_top_left = centerF + (QPointF(self.top_left) - centerF) * factor
        new_bottom_right = centerF + (QPointF(self.bottom_right) - centerF) * factor
        self.top_left = new_top_left.toPoint()
        self.bottom_right = new_bottom_right.toPoint()

class Polygon:
    def __init__(self, points, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        self.points, self.color, self.width, self.fill_color, self.fill_style = points, color, width, fill_color, fill_style
    def get_bounding_box(self):
        return QPolygonF([QPointF(p) for p in self.points]).boundingRect().toRect()
    def move(self, dx, dy):
        for p in self.points:
            p.setX(p.x() + dx)
            p.setY(p.y() + dy)
    def clone(self):
        return copy.deepcopy(self)
    def scale(self, factor, center):
        new_points = []
        centerF = QPointF(center)
        for p in self.points:
            new_p = centerF + (QPointF(p) - centerF) * factor
            new_points.append(new_p.toPoint())
        self.points = new_points
    def get_nodes(self):
        return self.points
    def set_node_at(self, index, pos):
        if 0 <= index < len(self.points):
            self.points[index] = pos

class Circle:
    def __init__(self, center, radius, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        self.center, self.radius, self.color, self.width, self.fill_color, self.fill_style = center, radius, color, width, fill_color, fill_style
    def get_bounding_box(self):
        return QRect(self.center.x() - int(self.radius), self.center.y() - int(self.radius), int(self.radius) * 2, int(self.radius) * 2)
    def move(self, dx, dy):
        self.center.setX(self.center.x() + dx)
        self.center.setY(self.center.y() + dy)
    def clone(self):
        return copy.deepcopy(self)
    def scale(self, factor, center_of_selection):
        centerF = QPointF(center_of_selection)
        new_center = centerF + (QPointF(self.center) - centerF) * factor
        self.center = new_center.toPoint()
        self.radius *= factor

class Rectangle:
    def __init__(self, top_left, bottom_right, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        self.top_left, self.bottom_right, self.color, self.width, self.fill_color, self.fill_style = top_left, bottom_right, color, width, fill_color, fill_style
    def get_bounding_box(self):
        return QRect(self.top_left, self.bottom_right).normalized()
    def move(self, dx, dy):
        self.top_left.setX(self.top_left.x() + dx)
        self.top_left.setY(self.top_left.y() + dy)
        self.bottom_right.setX(self.bottom_right.x() + dx)
        self.bottom_right.setY(self.bottom_right.y() + dy)
    def clone(self):
        return copy.deepcopy(self)
    def scale(self, factor, center):
        centerF = QPointF(center)
        new_top_left = centerF + (QPointF(self.top_left) - centerF) * factor
        new_bottom_right = centerF + (QPointF(self.bottom_right) - centerF) * factor
        self.top_left = new_top_left.toPoint()
        self.bottom_right = new_bottom_right.toPoint()

class Point:
    def __init__(self, pos, color=QColor(0,0,0), width=2):
        self.pos = pos
        self.color = color
        self.width = width
    def get_bounding_box(self):
        return QRect(self.pos.x() - self.width, self.pos.y() - self.width, self.width * 2, self.width * 2)
    def move(self, dx, dy):
        self.pos.setX(self.pos.x() + dx)
        self.pos.setY(self.pos.y() + dy)
    def clone(self):
        return copy.deepcopy(self)
    def scale(self, factor, center):
        centerF = QPointF(center)
        new_pos = centerF + (QPointF(self.pos) - centerF) * factor
        self.pos = new_pos.toPoint()

class Line:
    def __init__(self, p1, p2, color=QColor(0,0,0), width=2):
        self.p1, self.p2, self.color, self.width = p1, p2, color, width
    def get_bounding_box(self):
        return QRect(self.p1, self.p2).normalized()
    def move(self, dx, dy):
        self.p1.setX(self.p1.x() + dx); self.p1.setY(self.p1.y() + dy)
        self.p2.setX(self.p2.x() + dx); self.p2.setY(self.p2.y() + dy)
    def clone(self):
        return copy.deepcopy(self)
    def scale(self, factor, center):
        centerF = QPointF(center)
        new_p1 = centerF + (QPointF(self.p1) - centerF) * factor
        new_p2 = centerF + (QPointF(self.p2) - centerF) * factor
        self.p1, self.p2 = new_p1.toPoint(), new_p2.toPoint()

class Arc:
    def __init__(self, p1, p2, p3, color=QColor(0,0,0), width=2):
        self.p1, self.p2, self.p3 = p1, p2, p3
        self.color, self.width = color, width
    def get_painter_path(self):
        path = QPainterPath()
        path.moveTo(QPointF(self.p1))
        path.quadTo(QPointF(self.p3), QPointF(self.p2))
        return path
    def get_bounding_box(self):
        return self.get_painter_path().boundingRect().toRect()
    def move(self, dx, dy):
        self.p1.setX(self.p1.x() + dx); self.p1.setY(self.p1.y() + dy)
        self.p2.setX(self.p2.x() + dx); self.p2.setY(self.p2.y() + dy)
        self.p3.setX(self.p3.x() + dx); self.p3.setY(self.p3.y() + dy)
    def clone(self):
        return copy.deepcopy(self)
    def scale(self, factor, center):
        centerF = QPointF(center)
        new_p1 = centerF + (QPointF(self.p1) - centerF) * factor
        new_p2 = centerF + (QPointF(self.p2) - centerF) * factor
        new_p3 = centerF + (QPointF(self.p3) - centerF) * factor
        self.p1, self.p2, self.p3 = new_p1.toPoint(), new_p2.toPoint(), new_p3.toPoint()
    def get_nodes(self):
        return [self.p1, self.p2, self.p3]
    def set_node_at(self, index, pos):
        if index == 0: self.p1 = pos
        elif index == 1: self.p2 = pos
        elif index == 2: self.p3 = pos

class Polyline:
    def __init__(self, points, color=QColor(0,0,0), width=2):
        self.points, self.color, self.width = points, color, width
    def get_bounding_box(self):
        return QPolygonF([QPointF(p) for p in self.points]).boundingRect().toRect()
    def move(self, dx, dy):
        for p in self.points:
            p.setX(p.x() + dx)
            p.setY(p.y() + dy)
    def clone(self):
        return copy.deepcopy(self)
    def scale(self, factor, center):
        new_points = []
        centerF = QPointF(center)
        for p in self.points:
            new_p = centerF + (QPointF(p) - centerF) * factor
            new_points.append(new_p.toPoint())
        self.points = new_points
    def get_nodes(self):
        return self.points
    def set_node_at(self, index, pos):
        if 0 <= index < len(self.points):
            self.points[index] = pos

class ShapeGroup:
    def __init__(self, shapes):
        self.shapes = shapes
        self.color = QColor(0,0,0)
    def get_bounding_box(self):
        if not self.shapes:
            return QRect()
        # 修复了单行 if/else 的语法错误
        total_bbox = self.shapes[0].get_bounding_box()
        for shape in self.shapes[1:]:
            total_bbox = total_bbox.united(shape.get_bounding_box())
        return total_bbox
    def move(self, dx, dy):
        for shape in self.shapes:
            shape.move(dx, dy)
    def clone(self):
        return ShapeGroup([s.clone() for s in self.shapes])
    def scale(self, factor, center):
        for shape in self.shapes:
            shape.scale(factor, center)

class Arrow(Line):
    pass
