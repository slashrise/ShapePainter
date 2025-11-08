import math

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

def rasterize_quarter_circle(xc, yc, r, quadrant):
    """光栅化四分之一圆弧"""
    pixels = []; x, y, d = 0, r, 1 - r
    while x <= y:
        _plot_arc_points(xc, yc, x, y, quadrant, pixels); x += 1
        if d < 0: d += 2 * x + 3
        else: y -= 1; d += 2 * (x - y) + 5
    return pixels

def _plot_arc_points(xc, yc, x, y, quadrant, pixels):
    if quadrant == 1: pixels.extend([(xc + x, yc - y), (xc + y, yc - x)])
    elif quadrant == 2: pixels.extend([(xc - y, yc - x), (xc - x, yc - y)])
    elif quadrant == 3: pixels.extend([(xc - x, yc + y), (xc - y, yc + x)])
    elif quadrant == 4: pixels.extend([(xc + y, yc + x), (xc + x, yc + y)])

def scanline_fill_polygon(points):
    """健壮的通用扫描线多边形填充算法"""
    if not points or len(points) < 3: return []
    point_tuples = [(p.x(), p.y()) if not isinstance(p, tuple) else p for p in points]
    pixels = []
    
    y_min_float = min(p[1] for p in point_tuples)
    y_max_float = max(p[1] for p in point_tuples)
    
    # 🔴 核心修复：在使用前，将浮点数坐标强制转换为整数
    y_min = int(y_min_float)
    y_max = int(y_max_float)

    edge_table = {y: [] for y in range(y_min, y_max + 1)}
    edge_table = {y: [] for y in range(y_min, y_max + 1)}
    for i in range(len(point_tuples)):
        p1, p2 = point_tuples[i], point_tuples[(i + 1) % len(point_tuples)]
        if p1[1] == p2[1]: continue
        y_start, y_end = min(p1[1], p2[1]), max(p1[1], p2[1])
        x_start = p1[0] if p1[1] < p2[1] else p2[0]
        dx, dy = float(p1[0] - p2[0]), float(p1[1] - p2[1])
        inverse_slope = dx / dy
        edge_table[y_start].append([y_end, x_start, inverse_slope])
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
    """
    计算箭头三角形头部的三个整数顶点坐标。
    返回一个包含三个 (x, y) 元组的列表。
    """
    # 这是从终点p2指向起点p1的向量的角度
    angle = math.atan2(y1 - y2, x1 - x2)
    
    # 定义箭头头部的大小和张开角度，并随线宽缩放
    arrow_size = 10 + width * 2
    arrow_spread_angle = math.pi / 6  # 30度的张开角度

    # 计算三角形的另外两个侧边顶点
    p_left_x = x2 + arrow_size * math.cos(angle - arrow_spread_angle)
    p_left_y = y2 + arrow_size * math.sin(angle - arrow_spread_angle)
    
    p_right_x = x2 + arrow_size * math.cos(angle + arrow_spread_angle)
    p_right_y = y2 + arrow_size * math.sin(angle + arrow_spread_angle)

    # 三个顶点分别是：原始终点，以及两个新的侧边点
    # 我们将坐标转换为整数以用于我们的光栅化器
    return [
        (int(x2), int(y2)),
        (int(p_left_x), int(p_left_y)),
        (int(p_right_x), int(p_right_y))
    ]

def calculate_wide_line_polygon(x1, y1, x2, y2, width):
    """计算代表一条粗线的四边形的四个顶点。"""
    offset = width / 2.0
    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx*dx + dy*dy)
    if length == 0:
        # 处理零长度线段的情况
        return [(x1-offset, y1-offset), (x1+offset, y1-offset), 
                (x1+offset, y1+offset), (x1-offset, y1+offset)]

    # 计算线段的法线向量 (单位向量)
    nx = -dy / length
    ny = dx / length
    
    # 计算四个顶点
    p1 = (int(x1 + nx * offset), int(y1 + ny * offset))
    p2 = (int(x2 + nx * offset), int(y2 + ny * offset))
    p3 = (int(x2 - nx * offset), int(y2 - ny * offset))
    p4 = (int(x1 - nx * offset), int(y1 - ny * offset))
    
    return [p1, p2, p3, p4]