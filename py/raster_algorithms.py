import math
from PyQt6.QtCore import QPoint, QPointF
from PyQt6.QtGui import QColor

# --- 贝塞尔曲线辅助函数 (保持不变) ---
def lerp(p1, p2, t):
    return p1 * (1.0 - t) + p2 * (t)

def distance_point_to_line(p, v, w):
    l2 = (v - w).x() * (v - w).x() + (v - w).y() * (v - w).y()
    if l2 == 0.0:
        return (p - v).x() * (p - v).x() + (p - v).y() * (p - v).y()
    t = max(0, min(1, ((p - v).x() * (w - v).x() + (p - v).y() * (w - v).y()) / l2))
    projection = v + t * (w - v)
    return (p - projection).x() * (p - projection).x() + (p - projection).y() * (p - projection).y()

def subdivide_bezier(p0, p1, p2, p3):
    p0, p1, p2, p3 = QPointF(p0), QPointF(p1), QPointF(p2), QPointF(p3)
    p01 = lerp(p0, p1, 0.5); p12 = lerp(p1, p2, 0.5); p23 = lerp(p2, p3, 0.5)
    p012 = lerp(p01, p12, 0.5); p123 = lerp(p12, p23, 0.5)
    p0123 = lerp(p012, p123, 0.5)
    left_curve = (p0, p01, p012, p0123); right_curve = (p0123, p123, p23, p3)
    return left_curve, right_curve

def flatten_bezier(p0, p1, p2, p3, tolerance=0.5):
    points = []; p0, p1, p2, p3 = QPointF(p0), QPointF(p1), QPointF(p2), QPointF(p3)
    dist_sq1 = distance_point_to_line(p1, p0, p3); dist_sq2 = distance_point_to_line(p2, p0, p3)
    if dist_sq1 < tolerance * tolerance and dist_sq2 < tolerance * tolerance:
        points.append(p0.toPoint()); points.append(p3.toPoint()); return points
    left, right = subdivide_bezier(p0, p1, p2, p3)
    left_points = flatten_bezier(left[0], left[1], left[2], left[3], tolerance)
    right_points = flatten_bezier(right[0], right[1], right[2], right[3], tolerance)
    points.extend(left_points[:-1]); points.extend(right_points)
    return points

# --- 轮廓算法 (返回点列表 pixels) ---

def bresenham_line(x1, y1, x2, y2):
    """Bresenham 直线算法，返回点列表"""
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
    """DDA 直线算法，返回点列表"""
    pixels = []; dx, dy = x2 - x1, y2 - y1
    steps = max(abs(dx), abs(dy))
    if steps == 0: return [(x1, y1)]
    x_inc, y_inc = dx / float(steps), dy / float(steps)
    x, y = float(x1), float(y1)
    for _ in range(int(steps) + 1):
        pixels.append((int(round(x)), int(round(y)))); x += x_inc; y += y_inc
    return pixels

def midpoint_circle(xc, yc, r):
    """中点画圆算法 (仅轮廓)，返回点列表"""
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

def midpoint_ellipse(xc, yc, rx, ry):
    """中点椭圆算法 (仅轮廓)，返回点列表"""
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
    """光栅化四分之一圆弧，返回点列表"""
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

# --- 🚀 优化后的填充算法 (返回 Spans 线段列表) ---
# 返回格式: [(y, x_start, x_end), ...]，其中 x_end 是包含的

def scanline_fill_circle(xc, yc, r):
    """扫描线圆形填充，返回水平线段列表"""
    spans = []; r_squared = r * r
    for y_offset in range(r + 1):
        x_half_width = int((r_squared - y_offset*y_offset)**0.5)
        # 上半部分
        spans.append((yc - y_offset, xc - x_half_width, xc + x_half_width))
        # 下半部分 (避免中心行重复)
        if y_offset > 0:
            spans.append((yc + y_offset, xc - x_half_width, xc + x_half_width))
    return spans

def scanline_fill_ellipse(xc, yc, rx, ry):
    """扫描线椭圆填充，返回水平线段列表"""
    if rx <= 0 or ry <= 0: return []
    spans = []; rx2 = rx * rx; ry2 = ry * ry
    for y_offset in range(-ry, ry + 1):
        # 计算每一行的半宽
        val = 1 - (y_offset * y_offset) / ry2
        if val < 0: val = 0
        x_half_width = round(rx * math.sqrt(val))
        spans.append((yc + y_offset, xc - x_half_width, xc + x_half_width))
    return spans

def scanline_fill_rounded_rect(x, y, w, h, r):
    """扫描线圆角矩形填充，返回水平线段列表"""
    if w <= 0 or h <= 0: return []
    r = min(r, w // 2, h // 2)
    spans = []
    
    # 遍历每一行
    for current_y in range(y, y + h):
        x_start, x_end = 0, 0
        
        # 上圆角区
        if current_y < y + r:
            y_offset = (y + r) - current_y
            val = r * r - y_offset * y_offset
            x_offset = round(math.sqrt(max(0, val)))
            x_start = x + r - x_offset
            x_end = x + w - r + x_offset - 1 # 减1以匹配坐标系
            
        # 中间矩形区
        elif current_y >= y + r and current_y <= y + h - r:
            x_start = x
            x_end = x + w - 1
            
        # 下圆角区
        else:
            y_offset = current_y - (y + h - r)
            val = r * r - y_offset * y_offset
            x_offset = round(math.sqrt(max(0, val)))
            x_start = x + r - x_offset
            x_end = x + w - r + x_offset - 1

        if x_end >= x_start:
            spans.append((current_y, x_start, x_end))
            
    return spans

def scanline_fill_polygon(points):
    """
    通用扫描线多边形填充算法。
    🚀 优化：返回水平线段 (spans) 而不是点列表。
    """
    if not points or len(points) < 3: return []
    
    point_tuples = [(p.x(), p.y()) if not isinstance(p, tuple) else p for p in points]
    spans = []
    
    y_min_float = min(p[1] for p in point_tuples)
    y_max_float = max(p[1] for p in point_tuples)
    y_min, y_max = int(y_min_float), int(y_max_float)
    
    # 建立边表 (ET)
    edge_table = {y: [] for y in range(y_min, y_max + 1)}
    for i in range(len(point_tuples)):
        p1, p2 = point_tuples[i], point_tuples[(i + 1) % len(point_tuples)]
        if p1[1] == p2[1]: continue # 跳过水平边
        
        y_start, y_end = min(p1[1], p2[1]), max(p1[1], p2[1])
        x_start = p1[0] if p1[1] < p2[1] else p2[0]
        dx, dy = float(p1[0] - p2[0]), float(p1[1] - p2[1])
        inverse_slope = dx / dy if dy != 0 else 0
        
        edge_table[int(y_start)].append([int(y_end), x_start, inverse_slope])
    
    # 建立活动边表 (AET) 并扫描
    active_edge_table = []
    for y in range(y_min, y_max + 1):
        # 1. 将当前扫描线 y 的所有新边加入 AET
        active_edge_table.extend(edge_table[y])
        
        # 2. 移除已经处理完的边 (y_max == current_y)
        active_edge_table = [edge for edge in active_edge_table if edge[0] != y]
        
        # 3. 对 AET 中的边按 x 坐标排序
        active_edge_table.sort(key=lambda edge: edge[1])
        
        # 4. 配对交点生成线段 (Spans)
        for i in range(0, len(active_edge_table), 2):
            if i + 1 < len(active_edge_table):
                x_start = int(math.ceil(active_edge_table[i][1]))
                x_end = int(math.floor(active_edge_table[i+1][1]))
                
                # 🚀 核心优化：直接存储线段
                if x_end >= x_start:
                    spans.append((y, x_start, x_end))
        
        # 5. 更新每条边的 x 坐标 (x = x + 1/k)
        for edge in active_edge_table:
            edge[1] += edge[2]
            
    return spans

def calculate_arrow_head_points(x1, y1, x2, y2, width):
    """计算箭头头部顶点 (用于后续填充)"""
    angle = math.atan2(y1 - y2, x1 - x2); arrow_size = 10 + width * 2; arrow_spread_angle = math.pi / 6
    p_left_x = x2 + arrow_size * math.cos(angle - arrow_spread_angle); p_left_y = y2 + arrow_size * math.sin(angle - arrow_spread_angle)
    p_right_x = x2 + arrow_size * math.cos(angle + arrow_spread_angle); p_right_y = y2 + arrow_size * math.sin(angle + arrow_spread_angle)
    return [(int(x2), int(y2)), (int(p_left_x), int(p_left_y)), (int(p_right_x), int(p_right_y))]

def calculate_wide_line_polygon(x1, y1, x2, y2, width):
    """计算宽线对应的多边形顶点"""
    offset = width / 2.0; dx = x2 - x1; dy = y2 - y1; length = math.sqrt(dx*dx + dy*dy)
    if length == 0: return [(x1-offset, y1-offset), (x1+offset, y1-offset), (x1+offset, y1+offset), (x1-offset, y1+offset)]
    nx = -dy / length; ny = dx / length
    p1 = (int(x1 + nx * offset), int(y1 + ny * offset)); p2 = (int(x2 + nx * offset), int(y2 + ny * offset))
    p3 = (int(x2 - nx * offset), int(y2 - ny * offset)); p4 = (int(x1 - nx * offset), int(y1 - ny * offset))
    return [p1, p2, p3, p4]

def b_spline_basis(i, k, t, knots):
    """
    计算 B 样条基函数 N_{i,k}(t)
    i: 控制点索引
    k: 阶数 (degree)
    t: 参数值
    knots: 节点向量
    """
    # 0阶基函数 (Box function)
    if k == 0:
        return 1.0 if knots[i] <= t < knots[i+1] else 0.0
    
    # 递归项 1
    denom1 = knots[i+k] - knots[i]
    term1 = 0.0
    if denom1 > 0:
        term1 = ((t - knots[i]) / denom1) * b_spline_basis(i, k-1, t, knots)
    
    # 递归项 2
    denom2 = knots[i+k+1] - knots[i+1]
    term2 = 0.0
    if denom2 > 0:
        term2 = ((knots[i+k+1] - t) / denom2) * b_spline_basis(i+1, k-1, t, knots)
        
    return term1 + term2

def compute_bspline_points(control_points, degree=3, num_samples=None):
    """
    计算 B 样条曲线上的采样点。
    采用 Clamped Knot Vector (准均匀 B 样条)。
    🟢 核心优化：自适应阶数。当点数不足时，自动降低阶数以保证曲线平滑，而不是退化为折线。
    """
    n = len(control_points)
    
    # 如果点太少，连直线都算不上，返回空
    if n < 2:
        return []
    
    # 🟢 自适应阶数逻辑
    # 目标是 degree (通常是3)，但如果点数 n 只有 3个，我们只能做 2次曲线。
    # 如果只有 2个点，只能做 1次曲线 (直线)。
    # 这样保证了预览阶段始终是平滑过渡的。
    effective_degree = min(degree, n - 1)
    
    # 自动计算采样点数量
    if num_samples is None:
        num_samples = n * 20 

    # 1. 生成节点向量 (Knot Vector)
    # 使用 effective_degree 而不是原 degree
    domain_max = n - effective_degree
    knots = [0] * effective_degree + list(range(0, domain_max + 1)) + [domain_max] * effective_degree
    
    result_points = []
    
    # 2. 遍历参数 t 计算点坐标
    if num_samples <= 1: step = 0
    else: step = domain_max / (num_samples - 1)
    
    for i in range(num_samples):
        t = i * step
        
        # 处理精度边界
        if i == num_samples - 1:
            t = domain_max - 0.000001
            
        x, y = 0.0, 0.0
        
        # 累加控制点贡献
        for j in range(n):
            # 只有当基函数非零时才计算
            if knots[j] <= t < knots[j+effective_degree+1]:
                # 🟢 注意：这里传递 effective_degree 给基函数递归
                basis = b_spline_basis(j, effective_degree, t, knots)
                if basis > 0:
                    x += control_points[j].x() * basis
                    y += control_points[j].y() * basis
        
        # 返回浮点点，保证精度
        result_points.append(QPointF(x, y))
        
    return result_points

# 🟢 END: B-Spline Algorithms

def evaluate_bezier_point(t, p0, p1, p2, p3):
    """计算三次贝塞尔曲线上的一点 (De Casteljau 公式)"""
    u = 1 - t
    tt = t * t
    uu = u * u
    u3 = uu * u
    t3 = tt * t
    
    # B(t) = (1-t)^3*P0 + 3(1-t)^2*t*P1 + 3(1-t)t^2*P2 + t^3*P3
    x = u3 * p0.x() + 3 * uu * t * p1.x() + 3 * u * tt * p2.x() + t3 * p3.x()
    y = u3 * p0.y() + 3 * uu * t * p1.y() + 3 * u * tt * p2.y() + t3 * p3.y()
    return QPointF(x, y)

def compute_bezier_surface_wireframe(points, steps=12):
    """
    计算曲面的网格线 (Wireframe)。
    points: 16个控制点 (4x4)
    steps: 网格密度 (例如 12x12)
    返回: 一组 Polyline (点列表的列表)
    """
    if len(points) != 16: return []
    
    wireframe_polylines = []
    
    def get_p(row, col):
        return points[row * 4 + col]

    # 1. 绘制 v 方向的曲线 (纵向)
    # 算法：先固定 u，算出 4 个临时控制点，再用这 4 个点算出 v 方向的曲线
    for i in range(steps + 1):
        u = i / steps
        
        # 计算该 u 处的 4 个临时控制点 (每一行做一次贝塞尔插值)
        q_points = []
        for row in range(4):
            p0, p1, p2, p3 = get_p(row,0), get_p(row,1), get_p(row,2), get_p(row,3)
            q_points.append(evaluate_bezier_point(u, p0, p1, p2, p3))
        
        # 利用这 4 个临时点，画一条 v 方向的贝塞尔曲线
        line_points = []
        for k in range(steps + 1):
            v = k / steps
            line_points.append(evaluate_bezier_point(v, *q_points))
        wireframe_polylines.append(line_points)

    # 2. 绘制 u 方向的曲线 (横向)
    # 算法：先固定 v，算出 4 个临时控制点，再用这 4 个点算出 u 方向的曲线
    for i in range(steps + 1):
        v = i / steps
        
        q_points = []
        for col in range(4):
            p0, p1, p2, p3 = get_p(0,col), get_p(1,col), get_p(2,col), get_p(3,col)
            q_points.append(evaluate_bezier_point(v, p0, p1, p2, p3))
            
        line_points = []
        for k in range(steps + 1):
            u = k / steps
            line_points.append(evaluate_bezier_point(u, *q_points))
        wireframe_polylines.append(line_points)
        
    return wireframe_polylines
class _EdgeWalker:
    """辅助类：用于在 Y 轴方向上插值 X 坐标和颜色 (R, G, B)"""
    def __init__(self, p1, c1, p2, c2):
        self.y_start = int(round(p1.y()))
        self.y_end = int(round(p2.y()))
        self.height = self.y_end - self.y_start
        
        self.x = p1.x()
        self.r = c1.red()
        self.g = c1.green()
        self.b = c1.blue()
        
        # 计算增量 (Slope)
        if self.height > 0:
            self.dx = (p2.x() - p1.x()) / self.height
            self.dr = (c2.red() - c1.red()) / self.height
            self.dg = (c2.green() - c1.green()) / self.height
            self.db = (c2.blue() - c1.blue()) / self.height
        else:
            self.dx = self.dr = self.dg = self.db = 0

    def step(self):
        """向下移动一行"""
        self.x += self.dx
        self.r += self.dr
        self.g += self.dg
        self.b += self.db

def rasterize_triangle_gouraud(p1, c1, p2, c2, p3, c3):
    """
    Gouraud 着色三角形光栅化算法。
    
    Args:
        p1, p2, p3: QPointF, 顶点坐标
        c1, c2, c3: QColor, 顶点颜色
        
    Returns:
        spans: list of tuples 
               [(y, x_start, x_end, c_start, c_end), ...]
               其中 c_start 和 c_end 是 QColor 对象
    """
    # 1. 按 Y 坐标排序 (p1.y <= p2.y <= p3.y)
    vertices = [(p1, c1), (p2, c2), (p3, c3)]
    vertices.sort(key=lambda v: v[0].y())
    
    p1, c1 = vertices[0]
    p2, c2 = vertices[1]
    p3, c3 = vertices[2]
    
    spans = []
    
    # 转换为整数 Y 边界
    y1 = int(round(p1.y()))
    y2 = int(round(p2.y()))
    y3 = int(round(p3.y()))
    
    if y3 == y1: return [] # 面积为 0 的三角形
    
    # 2. 初始化长边 (p1 -> p3)
    long_edge = _EdgeWalker(p1, c1, p3, c3)
    
    # 3. 初始化短边 (首先是 p1 -> p2)
    short_edge = _EdgeWalker(p1, c1, p2, c2)
    
    # 4. 遍历每一行扫描线
    # 将三角形分为上半部分 (y1 -> y2) 和下半部分 (y2 -> y3)
    
    for y in range(y1, y3):
        # 如果到达了中间点 y2，切换短边为 (p2 -> p3)
        if y == y2:
            short_edge = _EdgeWalker(p2, c2, p3, c3)
            
        # 确定左右边界
        # 判断由 x 坐标决定，而不是由边的类型决定
        if long_edge.x < short_edge.x:
            x_start, x_end = int(long_edge.x), int(short_edge.x)
            r_s, g_s, b_s = long_edge.r, long_edge.g, long_edge.b
            r_e, g_e, b_e = short_edge.r, short_edge.g, short_edge.b
        else:
            x_start, x_end = int(short_edge.x), int(long_edge.x)
            r_s, g_s, b_s = short_edge.r, short_edge.g, short_edge.b
            r_e, g_e, b_e = long_edge.r, long_edge.g, long_edge.b
            
        # 确保 x_end > x_start，且在这一行内生成 Span
        if x_end > x_start:
            # 构造颜色对象
            # 限制范围 0-255，防止溢出
            c_start = QColor(
                max(0, min(255, int(r_s))),
                max(0, min(255, int(g_s))),
                max(0, min(255, int(b_s)))
            )
            c_end = QColor(
                max(0, min(255, int(r_e))),
                max(0, min(255, int(g_e))),
                max(0, min(255, int(b_e)))
            )
            
            spans.append((y, x_start, x_end, c_start, c_end))
        
        # 步进
        long_edge.step()
        short_edge.step()
        
    return spans
def evaluate_bicubic_point(u, v, points):
    """
    计算双三次贝塞尔曲面上 (u, v) 位置的坐标。
    points: 16个控制点列表 (行优先)
    """
    # 辅助：计算 4 个控制点的贝塞尔插值
    def bezier_interp(t, p0, p1, p2, p3):
        u_val = 1 - t
        tt = t * t
        uu = u_val * u_val
        u3 = uu * u_val
        t3 = tt * t
        x = u3 * p0.x() + 3 * uu * t * p1.x() + 3 * u_val * tt * p2.x() + t3 * p3.x()
        y = u3 * p0.y() + 3 * uu * t * p1.y() + 3 * u_val * tt * p2.y() + t3 * p3.y()
        return QPointF(x, y)

    # 1. 在 v 方向上，计算 4 个临时控制点 (q0, q1, q2, q3)
    # 这 4 个点构成了 u 方向的贝塞尔曲线
    q = []
    for i in range(4):
        p0 = points[i * 4 + 0]
        p1 = points[i * 4 + 1]
        p2 = points[i * 4 + 2]
        p3 = points[i * 4 + 3]
        q.append(bezier_interp(v, p0, p1, p2, p3))
    
    # 2. 在 u 方向上插值得到最终点
    return bezier_interp(u, q[0], q[1], q[2], q[3])

def tessellate_bezier_surface(points, steps=20):
    """
    将贝塞尔曲面细分为三角形列表，用于 Gouraud 着色。
    
    Args:
        points: 16个控制点
        steps: 细分密度 (越大越平滑，但越慢)
    
    Returns:
        list of tuples: [(p1, c1, p2, c2, p3, c3), ...]
    """
    triangles = []
    
    # 预计算网格点，避免重复计算
    # grid[row][col] = (QPointF, QColor)
    grid = []
    
    for r in range(steps + 1):
        row_data = []
        v = r / steps
        for c in range(steps + 1):
            u = c / steps
            
            # 计算几何坐标
            pos = evaluate_bicubic_point(u, v, points)
            
            # 计算伪彩色 (根据 UV 坐标)
            # U -> Red, V -> Green, Blue 固定 150
            color = QColor(int(u * 255), int(v * 255), 150)
            
            row_data.append((pos, color))
        grid.append(row_data)
        
    # 生成三角形
    for r in range(steps):
        for c in range(steps):
            # 获取当前方格的四个顶点
            # p1 -- p2
            # |  /  |
            # p3 -- p4
            pt1, col1 = grid[r][c]
            pt2, col2 = grid[r][c+1]
            pt3, col3 = grid[r+1][c]
            pt4, col4 = grid[r+1][c+1]
            
            # 拆分为两个三角形: (1, 2, 3) 和 (2, 4, 3)
            triangles.append((pt1, col1, pt2, col2, pt3, col3))
            triangles.append((pt2, col2, pt4, col4, pt3, col3))
            
    return triangles