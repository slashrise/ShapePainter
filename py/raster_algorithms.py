import math
# 🔴 确保导入 QPoint 和 QPointF
from PyQt6.QtCore import QPoint, QPointF

# 🟢 START: 新增贝塞尔曲线辅助函数
def lerp(p1, p2, t):
    """对两个QPointF进行线性插值"""
    return p1 * (1.0 - t) + p2 * (t)

def distance_point_to_line(p, v, w):
    """计算点p到线段vw的垂直距离的平方"""
    l2 = (v - w).x() * (v - w).x() + (v - w).y() * (v - w).y()
    if l2 == 0.0:
        return (p - v).x() * (p - v).x() + (p - v).y() * (p - v).y()
    t = max(0, min(1, ((p - v).x() * (w - v).x() + (p - v).y() * (w - v).y()) / l2))
    projection = v + t * (w - v)
    return (p - projection).x() * (p - projection).x() + (p - projection).y() * (p - projection).y()

def subdivide_bezier(p0, p1, p2, p3):
    """使用De Casteljau算法将一条三次贝塞尔曲线在 t=0.5 处分割成两条。"""
    p0, p1, p2, p3 = QPointF(p0), QPointF(p1), QPointF(p2), QPointF(p3)
    p01 = lerp(p0, p1, 0.5); p12 = lerp(p1, p2, 0.5); p23 = lerp(p2, p3, 0.5)
    p012 = lerp(p01, p12, 0.5); p123 = lerp(p12, p23, 0.5)
    p0123 = lerp(p012, p123, 0.5)
    left_curve = (p0, p01, p012, p0123); right_curve = (p0123, p123, p23, p3)
    return left_curve, right_curve

def flatten_bezier(p0, p1, p2, p3, tolerance=0.5):
    """递归地将贝塞尔曲线扁平化为一系列点。"""
    points = []; p0, p1, p2, p3 = QPointF(p0), QPointF(p1), QPointF(p2), QPointF(p3)
    dist_sq1 = distance_point_to_line(p1, p0, p3); dist_sq2 = distance_point_to_line(p2, p0, p3)
    if dist_sq1 < tolerance * tolerance and dist_sq2 < tolerance * tolerance:
        points.append(p0.toPoint()); points.append(p3.toPoint()); return points
    left, right = subdivide_bezier(p0, p1, p2, p3)
    left_points = flatten_bezier(left[0], left[1], left[2], left[3], tolerance)
    right_points = flatten_bezier(right[0], right[1], right[2], right[3], tolerance)
    points.extend(left_points[:-1]); points.extend(right_points)
    return points
# 🟢 END: 新增贝塞尔曲线辅助函数

def bresenham_line(x1, y1, x2, y2):
    """Bresenham 直线光栅化算法"""
    pixels = []; dx, dy = abs(x2 - x1), abs(y2 - y1)
    sx = 1 if x1 < x2 else -1; sy = 1 if y1 < y2 else -1
    err = dx - dy; x, y = x1, y1
    while True:
        pixels.append((x, y))
        if x == x2 and y == y2: break
        e2 = 2 * err
        if e2 > -dy: err -= dy; x += sx
        if e2 < dx: err += dx; y += sy
    return pixels

def dda_line(x1, y1, x2, y2):
    """DDA 直线光栅化算法"""
    pixels = []; dx, dy = x2 - x1, y2 - y1
    steps = max(abs(dx), abs(dy))
    if steps == 0: return [(x1, y1)]
    x_inc, y_inc = dx / float(steps), dy / float(steps)
    x, y = float(x1), float(y1)
    for _ in range(int(steps) + 1):
        pixels.append((int(round(x)), int(round(y)))); x += x_inc; y += y_inc
    return pixels

def midpoint_circle(xc, yc, r):
    """中点画圆算法，返回边界像素"""
    pixels = []; x, y, d = 0, r, 1 - r
    _plot_circle_points(xc, yc, x, y, pixels)
    while x < y:
        x += 1
        if d < 0: d += 2 * x + 3
        else: y -= 1; d += 2 * (x - y) + 5
        _plot_circle_points(xc, yc, x, y, pixels)
    return pixels

def _plot_circle_points(xc, yc, x, y, pixels):
    pixels.extend([(xc + x, yc + y), (xc - x, yc + y), (xc + x, yc - y), (xc - x, yc - y),
                   (xc + y, yc + x), (xc - y, yc + x), (xc + y, yc - x), (xc - y, yc - x)])

def scanline_fill_circle(xc, yc, r):
    """基于数学方程的扫描线圆形填充"""
    pixels = []; r_squared = r * r
    for y_offset in range(r + 1):
        x_half_width = int((r_squared - y_offset*y_offset)**0.5)
        for x_offset in range(-x_half_width, x_half_width + 1):
            pixels.append((xc + x_offset, yc - y_offset))
        if y_offset > 0:
            for x_offset in range(-x_half_width, x_half_width + 1):
                pixels.append((xc + x_offset, yc + y_offset))
    return pixels

def midpoint_ellipse(xc, yc, rx, ry):
    """中点椭圆光栅化算法"""
    pixels = []; rx2, ry2 = rx * rx, ry * ry; two_rx2, two_ry2 = 2 * rx2, 2 * ry2
    x, y = 0, ry; p1 = ry2 - rx2 * ry + 0.25 * rx2
    while two_ry2 * x < two_rx2 * y:
        _plot_ellipse_points(xc, yc, x, y, pixels); x += 1
        if p1 < 0: p1 += two_ry2 * x + ry2
        else: y -= 1; p1 += two_ry2 * x - two_rx2 * y + ry2
    p2 = ry2 * (x + 0.5)**2 + rx2 * (y - 1)**2 - rx2 * ry2
    while y >= 0:
        _plot_ellipse_points(xc, yc, x, y, pixels); y -= 1
        if p2 > 0: p2 += -two_rx2 * y + rx2
        else: x += 1; p2 += two_ry2 * x - two_rx2 * y + rx2
    return pixels

def _plot_ellipse_points(xc, yc, x, y, pixels):
    pixels.extend([(xc + x, yc + y), (xc - x, yc + y), (xc + x, yc - y), (xc - x, yc - y)])

# 🟢 START: 新增圆角矩形和椭圆填充/轮廓算法
def scanline_fill_ellipse(xc, yc, rx, ry):
    """使用扫描线算法填充椭圆。"""
    if rx <= 0 or ry <= 0: return []
    pixels = []; rx2 = rx * rx; ry2 = ry * ry
    for y_offset in range(-ry, ry + 1):
        x_half_width = round(rx * math.sqrt(max(0, 1 - (y_offset * y_offset) / ry2)))
        x_start, x_end = xc - x_half_width, xc + x_half_width
        y = yc + y_offset
        for x in range(x_start, x_end + 1): pixels.append((x, y))
    return pixels

def rasterize_quarter_circle(xc, yc, r, quadrant):
    """光栅化四分之一圆弧"""
    pixels = []; x, y, d = 0, r, 1 - r
    while x <= y:
        if quadrant == 1: pixels.extend([(xc + x, yc - y), (xc + y, yc - x)])
        elif quadrant == 2: pixels.extend([(xc - y, yc - x), (xc - x, yc - y)])
        elif quadrant == 3: pixels.extend([(xc - x, yc + y), (xc - y, yc + x)])
        elif quadrant == 4: pixels.extend([(xc + y, yc + x), (xc + x, yc + y)])
        x += 1
        if d < 0: d += 2 * x + 3
        else: y -= 1; d += 2 * (x - y) + 5
    return pixels

def scanline_fill_rounded_rect(x, y, w, h, r):
    """使用扫描线算法填充圆角矩形。"""
    if w <= 0 or h <= 0: return []
    r = min(r, w // 2, h // 2)
    pixels = []
    for current_y in range(y, y + h):
        x_start, x_end = 0, 0
        if current_y < y + r:
            y_offset = (y + r) - current_y
            x_offset = round(math.sqrt(max(0, r * r - y_offset * y_offset)))
            x_start, x_end = x + r - x_offset, x + w - r + x_offset
        elif current_y >= y + r and current_y <= y + h - r:
            x_start, x_end = x, x + w
        else:
            y_offset = current_y - (y + h - r)
            x_offset = round(math.sqrt(max(0, r * r - y_offset * y_offset)))
            x_start, x_end = x + r - x_offset, x + w - r + x_offset
        for current_x in range(x_start, x_end): pixels.append((current_x, current_y))
    return pixels
# 🟢 END: 新增算法

def scanline_fill_polygon(points):
    """健壮的通用扫描线多边形填充算法"""
    if not points or len(points) < 3: return []
    point_tuples = [(p.x(), p.y()) if not isinstance(p, tuple) else p for p in points]
    pixels = []; y_min_float = min(p[1] for p in point_tuples); y_max_float = max(p[1] for p in point_tuples)
    y_min, y_max = int(y_min_float), int(y_max_float)
    edge_table = {y: [] for y in range(y_min, y_max + 1)}
    for i in range(len(point_tuples)):
        p1, p2 = point_tuples[i], point_tuples[(i + 1) % len(point_tuples)]
        if p1[1] == p2[1]: continue
        y_start, y_end = min(p1[1], p2[1]), max(p1[1], p2[1])
        x_start = p1[0] if p1[1] < p2[1] else p2[0]
        dx, dy = float(p1[0] - p2[0]), float(p1[1] - p2[1])
        inverse_slope = dx / dy if dy != 0 else 0
        edge_table[int(y_start)].append([int(y_end), x_start, inverse_slope])
    active_edge_table = []
    for y in range(y_min, y_max + 1):
        active_edge_table.extend(edge_table[y])
        active_edge_table = [edge for edge in active_edge_table if edge[0] != y]
        active_edge_table.sort(key=lambda edge: edge[1])
        for i in range(0, len(active_edge_table), 2):
            if i + 1 < len(active_edge_table):
                x_start, x_end = int(active_edge_table[i][1]), int(active_edge_table[i+1][1])
                for x in range(x_start, x_end): pixels.append((x, y))
        for edge in active_edge_table:
            edge[1] += edge[2]
    return pixels

def calculate_arrow_head_points(x1, y1, x2, y2, width):
    """计算箭头三角形头部的三个整数顶点坐标。"""
    angle = math.atan2(y1 - y2, x1 - x2); arrow_size = 10 + width * 2; arrow_spread_angle = math.pi / 6
    p_left_x = x2 + arrow_size * math.cos(angle - arrow_spread_angle); p_left_y = y2 + arrow_size * math.sin(angle - arrow_spread_angle)
    p_right_x = x2 + arrow_size * math.cos(angle + arrow_spread_angle); p_right_y = y2 + arrow_size * math.sin(angle + arrow_spread_angle)
    return [(int(x2), int(y2)), (int(p_left_x), int(p_left_y)), (int(p_right_x), int(p_right_y))]

def calculate_wide_line_polygon(x1, y1, x2, y2, width):
    """计算代表一条粗线的四边形的四个顶点。"""
    offset = width / 2.0; dx = x2 - x1; dy = y2 - y1; length = math.sqrt(dx*dx + dy*dy)
    if length == 0: return [(x1-offset, y1-offset), (x1+offset, y1-offset), (x1+offset, y1+offset), (x1-offset, y1+offset)]
    nx = -dy / length; ny = dx / length
    p1 = (int(x1 + nx * offset), int(y1 + ny * offset)); p2 = (int(x2 + nx * offset), int(y2 + ny * offset))
    p3 = (int(x2 - nx * offset), int(y2 - ny * offset)); p4 = (int(x1 - nx * offset), int(y1 - ny * offset))
    return [p1, p2, p3, p4]