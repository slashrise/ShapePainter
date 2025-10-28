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
    pixels = []; y_min = min(p[1] for p in point_tuples); y_max = max(p[1] for p in point_tuples)
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