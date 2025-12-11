import copy
from PyQt6.QtGui import QColor, QPolygonF, QPainterPath, QFont, QTransform, QPainter
from PyQt6.QtCore import Qt, QRect, QPoint, QPointF, QRectF

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
        # 手动实现克隆
        new_layer = Layer(self.name)
        new_layer.is_visible = self.is_visible
        new_layer.is_locked = self.is_locked
        new_layer.opacity = self.opacity
        new_layer.blend_mode = self.blend_mode
        # 递归地克隆所有图形
        new_layer.shapes = [s.clone() for s in self.shapes]
        return new_layer

class PathSegment:
    CORNER = 'corner'; SMOOTH = 'smooth'
    def __init__(self, anchor, handle1=None, handle2=None, node_type=CORNER): 
        # 🟢 [修改] 强制转为 QPointF
        self.anchor = QPointF(anchor)
        self.handle1 = QPointF(handle1) if handle1 is not None else QPointF(anchor)
        self.handle2 = QPointF(handle2) if handle2 is not None else QPointF(anchor)
        self.node_type = node_type
        
    def clone(self): 
        return PathSegment(QPointF(self.anchor), QPointF(self.handle1), QPointF(self.handle2), self.node_type)
        
    def to_corner(self): 
        self.handle1 = QPointF(self.anchor)
        self.handle2 = QPointF(self.anchor)
        self.node_type = self.CORNER
        
    def to_smooth(self, handle=None):
        if handle: 
            self.handle2 = QPointF(handle)
            self.handle1 = self.anchor - (self.handle2 - self.anchor)
        else:
            if self.handle1 == self.anchor and self.handle2 == self.anchor: 
                self.handle1 = self.anchor - QPointF(20, 0)
                self.handle2 = self.anchor + QPointF(20, 0)
        self.node_type = self.SMOOTH

def get_transformed_rect(shape):
    if shape.angle == 0 and shape.scale_x == 1 and shape.scale_y == 1: 
        return shape.get_bounding_box() # 返回 QRectF
        
    original_bbox = shape.get_bounding_box()
    center = original_bbox.center()
    
    transform = QTransform().translate(center.x(), center.y()).rotate(shape.angle).scale(shape.scale_x, shape.scale_y).translate(-center.x(), -center.y())
    
    # mapRect 返回的就是 QRectF
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
        cloned_shape.layer = None
        return cloned_shape

class Text(BaseShape):
    def __init__(self, rect, text, font, color=QColor(0,0,0), has_border=False, border_color=QColor(0,0,0), alignment=Qt.AlignmentFlag.AlignLeft):
        super().__init__()
        # Text 比较特殊，Qt 底层绘制依赖整数 Rect，但我们这里存 Rect 并在 scale 时做浮点计算
        self.rect = rect 
        self.text, self.font, self.color = text, font, color
        self.has_border, self.border_color, self.alignment = has_border, border_color, alignment
        
    def get_bounding_box(self): 
        # 🟢 [修改] 返回 QRectF
        return QRectF(self.rect)
        
    def move(self, dx, dy): 
        self.rect.translate(int(dx), int(dy))
        
    def clone(self): 
        cloned = Text(QRect(self.rect), self.text, QFont(self.font), QColor(self.color), self.has_border, QColor(self.border_color), self.alignment)
        return self.clone_transform(cloned)
        
    def scale(self, factor, center):
        centerF = QPointF(center)
        # 🟢 [修改] 使用浮点运算后转回 Int，避免累积误差
        tl = centerF + (QPointF(self.rect.topLeft()) - centerF) * factor
        br = centerF + (QPointF(self.rect.bottomRight()) - centerF) * factor
        self.rect = QRectF(tl, br).toRect()
        
        new_size = self.font.pointSizeF() * factor
        if new_size >= 1: self.font.setPointSizeF(new_size)

class Square(BaseShape):
    def __init__(self, top_left, size, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        super().__init__()
        # 🟢 [修改] QPointF
        self.top_left = QPointF(top_left)
        self.size = float(size)
        self.color, self.width = color, width
        self.fill_color, self.fill_style = fill_color, fill_style
        
    def get_bounding_box(self): 
        return QRectF(self.top_left.x(), self.top_left.y(), self.size, self.size)
        
    def move(self, dx, dy): 
        self.top_left.setX(self.top_left.x() + dx)
        self.top_left.setY(self.top_left.y() + dy)
        
    def clone(self): 
        cloned = Square(QPointF(self.top_left), self.size, QColor(self.color), self.width, QColor(self.fill_color) if self.fill_color else None, self.fill_style)
        return self.clone_transform(cloned)
        
    def scale(self, factor, center): 
        centerF = QPointF(center)
        # 🟢 [修改] 移除 .toPoint()
        self.top_left = centerF + (self.top_left - centerF) * factor
        self.size *= factor

class Ellipse(BaseShape):
    def __init__(self, top_left, bottom_right, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        super().__init__()
        # 🟢 [修改] QPointF
        self.top_left = QPointF(top_left)
        self.bottom_right = QPointF(bottom_right)
        self.color, self.width = color, width
        self.fill_color, self.fill_style = fill_color, fill_style
        
    def get_bounding_box(self): 
        return QRectF(self.top_left, self.bottom_right).normalized()
        
    def move(self, dx, dy): 
        self.top_left.setX(self.top_left.x() + dx)
        self.top_left.setY(self.top_left.y() + dy)
        self.bottom_right.setX(self.bottom_right.x() + dx)
        self.bottom_right.setY(self.bottom_right.y() + dy)
        
    def clone(self): 
        cloned = Ellipse(QPointF(self.top_left), QPointF(self.bottom_right), QColor(self.color), self.width, QColor(self.fill_color) if self.fill_color else None, self.fill_style)
        return self.clone_transform(cloned)
        
    def scale(self, factor, center): 
        centerF = QPointF(center)
        # 🟢 [修改] 移除 .toPoint()
        self.top_left = centerF + (self.top_left - centerF) * factor
        self.bottom_right = centerF + (self.bottom_right - centerF) * factor

class RoundedRectangle(Ellipse):
    def clone(self):
        cloned = RoundedRectangle(QPointF(self.top_left), QPointF(self.bottom_right), QColor(self.color), self.width, QColor(self.fill_color) if self.fill_color else None, self.fill_style)
        return self.clone_transform(cloned)

class Rectangle(Ellipse):
    def clone(self):
        cloned = Rectangle(QPointF(self.top_left), QPointF(self.bottom_right), QColor(self.color), self.width, QColor(self.fill_color) if self.fill_color else None, self.fill_style)
        return self.clone_transform(cloned)

class Polygon(BaseShape):
    def __init__(self, points, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        super().__init__()
        # 🟢 [修改] QPointF List
        self.points = [QPointF(p) for p in points]
        self.color, self.width, self.fill_color = color, width, fill_color
        self.fill_style = fill_style
        
    def get_bounding_box(self): 
        return QPolygonF(self.points).boundingRect()
        
    def move(self, dx, dy):
        for p in self.points: 
            p.setX(p.x() + dx); p.setY(p.y() + dy)
            
    def clone(self): 
        cloned_points = [QPointF(p) for p in self.points]
        cloned = Polygon(cloned_points, QColor(self.color), self.width, QColor(self.fill_color) if self.fill_color else None, self.fill_style)
        return self.clone_transform(cloned)
        
    def scale(self, factor, center): 
        centerF = QPointF(center)
        # 🟢 [修改] 移除 .toPoint()
        self.points = [centerF + (p - centerF) * factor for p in self.points]
        
    def get_nodes(self): return self.points
    def set_node_at(self, index, pos):
        if 0 <= index < len(self.points): self.points[index] = QPointF(pos)

class Circle(BaseShape):
    def __init__(self, center, radius, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        super().__init__()
        # 🟢 [修改] QPointF
        self.center = QPointF(center)
        self.radius = float(radius)
        self.color, self.width = color, width
        self.fill_color, self.fill_style = fill_color, fill_style
        
    def get_bounding_box(self): 
        return QRectF(self.center.x() - self.radius, self.center.y() - self.radius, self.radius * 2, self.radius * 2)
        
    def move(self, dx, dy): 
        self.center.setX(self.center.x() + dx)
        self.center.setY(self.center.y() + dy)
        
    def clone(self): 
        cloned = Circle(QPointF(self.center), self.radius, QColor(self.color), self.width, QColor(self.fill_color) if self.fill_color else None, self.fill_style)
        return self.clone_transform(cloned)
        
    def scale(self, factor, center_of_selection): 
        centerF = QPointF(center_of_selection)
        # 🟢 [修改] 移除 .toPoint()
        self.center = centerF + (self.center - centerF) * factor
        self.radius *= factor

class Point(BaseShape):
    def __init__(self, pos, color=QColor(0,0,0), width=2): 
        super().__init__()
        self.pos = QPointF(pos) # 🟢 QPointF
        self.color, self.width = color, width
        
    def get_bounding_box(self): 
        return QRectF(self.pos.x() - self.width, self.pos.y() - self.width, self.width * 2, self.width * 2)
        
    def move(self, dx, dy): 
        self.pos.setX(self.pos.x() + dx)
        self.pos.setY(self.pos.y() + dy)
        
    def clone(self):
        cloned = Point(QPointF(self.pos), QColor(self.color), self.width)
        return self.clone_transform(cloned)
        
    def scale(self, factor, center): 
        centerF = QPointF(center)
        self.pos = centerF + (self.pos - centerF) * factor

class Line(BaseShape):
    def __init__(self, p1, p2, color=QColor(0,0,0), width=2): 
        super().__init__()
        self.p1 = QPointF(p1) # 🟢 QPointF
        self.p2 = QPointF(p2)
        self.color, self.width = color, width
        
    def get_bounding_box(self): 
        return QRectF(self.p1, self.p2).normalized()
        
    def move(self, dx, dy): 
        self.p1.setX(self.p1.x() + dx)
        self.p1.setY(self.p1.y() + dy)
        self.p2.setX(self.p2.x() + dx)
        self.p2.setY(self.p2.y() + dy)
        
    def clone(self):
        cloned = Line(QPointF(self.p1), QPointF(self.p2), QColor(self.color), self.width)
        return self.clone_transform(cloned)
        
    def scale(self, factor, center): 
        centerF = QPointF(center)
        self.p1 = centerF + (self.p1 - centerF) * factor
        self.p2 = centerF + (self.p2 - centerF) * factor

class Path(BaseShape):
    def __init__(self, sub_paths, color=QColor(0,0,0), width=2, fill_color=None, fill_style=Qt.BrushStyle.SolidPattern):
        super().__init__()
        self.sub_paths = sub_paths; self.color = color; self.width = width; self.fill_color = fill_color; self.fill_style = fill_style
    
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
            for i in range(len(sub_path) - 1): 
                start_seg, end_seg = sub_path[i], sub_path[i+1]
                path.cubicTo(QPointF(start_seg.handle2), QPointF(end_seg.handle1), QPointF(end_seg.anchor))
            if len(sub_path) > 1 and sub_path[0].anchor == sub_path[-1].anchor: path.closeSubpath()
            final_path.addPath(path)
        return final_path
        
    def get_bounding_box(self): 
        return self.get_painter_path().boundingRect() # 返回 QRectF
        
    def move(self, dx, dy):
        for sub_path in self.sub_paths:
            for seg in sub_path: 
                seg.anchor += QPointF(dx, dy)
                seg.handle1 += QPointF(dx, dy)
                seg.handle2 += QPointF(dx, dy)
                
    def clone(self):
        cloned_sub_paths = [[seg.clone() for seg in sp] for sp in self.sub_paths]
        cloned = Path(cloned_sub_paths, QColor(self.color), self.width, QColor(self.fill_color) if self.fill_color else None, self.fill_style)
        return self.clone_transform(cloned)
        
    def scale(self, factor, center):
        centerF = QPointF(center)
        # 🟢 [修改] 移除 .toPoint()
        for sub_path in self.sub_paths:
            for seg in sub_path: 
                seg.anchor = centerF + (QPointF(seg.anchor) - centerF) * factor
                seg.handle1 = centerF + (QPointF(seg.handle1) - centerF) * factor
                seg.handle2 = centerF + (QPointF(seg.handle2) - centerF) * factor
                
    def get_nodes(self):
        nodes = [];
        for sub_path in self.sub_paths:
            for seg in sub_path: nodes.append(seg.anchor); nodes.append(seg.handle1); nodes.append(seg.handle2)
        return nodes
        
    def set_node_at(self, index, pos):
        count = 0
        posF = QPointF(pos)
        for sub_path in self.sub_paths:
            num_nodes_in_subpath = len(sub_path) * 3
            if count + num_nodes_in_subpath > index:
                local_index = index - count; seg_index = local_index // 3; node_type = local_index % 3
                if node_type == 0: sub_path[seg_index].anchor = posF
                elif node_type == 1: sub_path[seg_index].handle1 = posF
                elif node_type == 2: sub_path[seg_index].handle2 = posF
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
    def clone(self): 
        cloned_points = [QPointF(p) for p in self.points]
        cloned = Polyline(cloned_points, QColor(self.color), self.width, QColor(self.fill_color) if self.fill_color else None, self.fill_style)
        return self.clone_transform(cloned)

class ShapeGroup(BaseShape):
    def __init__(self, shapes): super().__init__(); self.shapes = shapes; self.color = QColor(0,0,0)
    
    def get_bounding_box(self):
        if not self.shapes: return QRectF() # QRectF
        total_bbox = self.shapes[0].get_bounding_box()
        for shape in self.shapes[1:]: total_bbox = total_bbox.united(shape.get_bounding_box())
        return total_bbox
        
    def move(self, dx, dy):
        for shape in self.shapes: shape.move(dx, dy)
        
    def clone(self): 
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
    def clone(self):
        cloned = Arrow(QPointF(self.p1), QPointF(self.p2), QColor(self.color), self.width)
        return self.clone_transform(cloned)
    
class BSpline(BaseShape):
    def __init__(self, points, degree=3, color=QColor(0,0,0), width=2):
        super().__init__()
        # 🟢 [修改] QPointF
        self.points = [QPointF(p) for p in points]
        self.degree = degree 
        self.color = color
        self.width = width
    
    def get_bounding_box(self):
        if not self.points: return QRectF()
        return QPolygonF(self.points).boundingRect()
    
    def move(self, dx, dy):
        for p in self.points:
            p.setX(p.x() + dx)
            p.setY(p.y() + dy)
            
    def clone(self):
        cloned_points = [QPointF(p) for p in self.points]
        cloned = BSpline(cloned_points, self.degree, QColor(self.color), self.width)
        return self.clone_transform(cloned)
        
    def scale(self, factor, center):
        centerF = QPointF(center)
        # 🟢 [修改] 移除 .toPoint()
        self.points = [centerF + (p - centerF) * factor for p in self.points]
        
    def get_nodes(self): return self.points
        
    def set_node_at(self, index, pos):
        if 0 <= index < len(self.points):
            self.points[index] = QPointF(pos)

class BezierSurface(BaseShape):
    def __init__(self, rect, color=QColor(0,0,0), width=1):
        super().__init__()
        self.color = color
        self.width = width
        self.points = []
        
        # 🟢 [新增] 显示属性开关
        self.show_fill = True
        self.show_wireframe = True

        rows, cols = 4, 4
        # 初始创建时使用 rect (整数或浮点皆可)
        x_step = rect.width() / (cols - 1)
        y_step = rect.height() / (rows - 1)
        for r in range(rows):
            for c in range(cols):
                x = rect.x() + c * x_step
                y = rect.y() + r * y_step
                # 🟢 [修改] 存储为 QPointF
                self.points.append(QPointF(x, y))

    def get_bounding_box(self):
        if not self.points: return QRectF()
        return QPolygonF(self.points).boundingRect()

    def move(self, dx, dy):
        for p in self.points:
            p.setX(p.x() + dx)
            p.setY(p.y() + dy)

    def clone(self):
        dummy_rect = QRect(0,0,1,1)
        cloned = BezierSurface(dummy_rect, self.color, self.width)
        cloned.points = [QPointF(p) for p in self.points]
        
        # 🟢 [关键] 手动克隆显示属性，防止拖动时状态重置
        cloned.show_fill = self.show_fill
        cloned.show_wireframe = self.show_wireframe
        
        return self.clone_transform(cloned)

    def scale(self, factor, center):
        centerF = QPointF(center)
        # 🟢 [修改] 移除 .toPoint()
        self.points = [centerF + (p - centerF) * factor for p in self.points]

    def get_nodes(self):
        return self.points

    def set_node_at(self, index, pos):
        if 0 <= index < len(self.points):
            self.points[index] = QPointF(pos)