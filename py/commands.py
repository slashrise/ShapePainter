from PyQt6.QtGui import QColor
from shapes import ShapeGroup

class Command:
    def undo(self): raise NotImplementedError
    def redo(self): raise NotImplementedError

# --- 辅助函数，用于从shapes中找到所有受影响的图层 ---
def _get_affected_layers(shapes):
    layers = set()
    for shape in shapes:
        # 假设 shape 对象能够反向引用到它的 layer
        if hasattr(shape, 'layer') and shape.layer:
            layers.add(shape.layer)
    return layers

# --- 图层操作命令 ---
# 对于图层本身的增删改，我们通常需要重绘所有内容，
# 但为了精确，我们可以在canvas层面处理。这些命令本身暂时不标记。
class AddLayerCommand(Command):
    def __init__(self, canvas, layer, index):
        self.canvas, self.layer, self.index = canvas, layer, index
    def undo(self): self.canvas.layers.pop(self.index)
    def redo(self): self.canvas.layers.insert(self.index, self.layer)

class RemoveLayerCommand(Command):
    def __init__(self, canvas, layer, index):
        self.canvas, self.layer, self.index = canvas, layer, index
    def undo(self): self.canvas.layers.insert(self.index, self.layer)
    def redo(self): self.canvas.layers.pop(self.index)

class MoveLayerCommand(Command):
    def __init__(self, canvas, from_index, to_index):
        self.canvas, self.from_index, self.to_index = canvas, from_index, to_index
    def undo(self):
        layer = self.canvas.layers.pop(self.to_index)
        self.canvas.layers.insert(self.from_index, layer)
    def redo(self):
        layer = self.canvas.layers.pop(self.from_index)
        self.canvas.layers.insert(self.to_index, layer)

# --- 图形操作命令 ---
class AddShapeCommand(Command):
    def __init__(self, layer, shape):
        self.layer, self.shape = layer, shape
    def undo(self):
        if self.shape in self.layer.shapes: self.layer.shapes.remove(self.shape)
        self.layer.is_dirty = True
    def redo(self):
        self.layer.shapes.append(self.shape)
        self.layer.is_dirty = True

class AddShapesCommand(Command):
    def __init__(self, layer, shapes):
        self.layer = layer
        self.shapes = list(shapes)
    def undo(self):
        self.layer.shapes = [s for s in self.layer.shapes if s not in self.shapes]
        self.layer.is_dirty = True
    def redo(self):
        self.layer.shapes.extend(self.shapes)
        self.layer.is_dirty = True

class RemoveShapesCommand(Command):
    def __init__(self, layer, shapes):
        self.layer, self.shapes = layer, list(shapes)
    def undo(self):
        self.layer.shapes.extend(self.shapes)
        self.layer.is_dirty = True
    def redo(self):
        self.layer.shapes = [s for s in self.layer.shapes if s not in self.shapes]
        self.layer.is_dirty = True

class MoveShapesCommand(Command):
    def __init__(self, shapes, dx, dy):
        self.shapes, self.dx, self.dy = list(shapes), dx, dy
        # 🔴 预先找出所有受影响的图层
        self.affected_layers = _get_affected_layers(self.shapes)

    def undo(self):
        for shape in self.shapes: shape.move(-self.dx, -self.dy)
        for layer in self.affected_layers: layer.is_dirty = True # 🔴 标记
            
    def redo(self):
        for shape in self.shapes: shape.move(self.dx, self.dy)
        for layer in self.affected_layers: layer.is_dirty = True # 🔴 标记

class ChangePropertiesCommand(Command):
    def __init__(self, shapes, new_properties):
        self.shapes = list(shapes)
        self.new_properties = new_properties
        self.old_properties = {}
        # 🔴 预先找出所有受影响的图层
        self.affected_layers = _get_affected_layers(self.shapes)
        
        for shape in self.shapes:
            self.old_properties[shape] = {}
            for prop_name in self.new_properties.keys():
                # 对于图层属性（如opacity），直接从shape（即layer对象）获取
                if hasattr(shape, prop_name):
                    self.old_properties[shape][prop_name] = getattr(shape, prop_name)

    def undo(self):
        for shape in self.shapes:
            for prop_name, value in self.old_properties[shape].items():
                setattr(shape, prop_name, value)
        # 🔴 如果改变的是图层本身的属性（比如透明度），shape就是layer，也能被正确标记
        for layer in self.affected_layers: layer.is_dirty = True
            
    def redo(self):
        for shape in self.shapes:
            for prop_name, value in self.new_properties.items():
                setattr(shape, prop_name, value)
        for layer in self.affected_layers: layer.is_dirty = True

class GroupCommand(Command):
    def __init__(self, layer, shapes_to_group):
        self.layer = layer
        self.shapes_to_group = list(shapes_to_group)
        self.group = ShapeGroup(self.shapes_to_group)
    def undo(self):
        self.layer.shapes.remove(self.group)
        self.layer.shapes.extend(self.shapes_to_group)
        self.layer.is_dirty = True # 🔴 标记
    def redo(self):
        for shape in self.shapes_to_group:
            if shape in self.layer.shapes: self.layer.shapes.remove(shape)
        self.layer.shapes.append(self.group)
        self.layer.is_dirty = True # 🔴 标记

class UngroupCommand(Command):
    def __init__(self, layer, group_to_ungroup):
        self.layer = layer
        self.group = group_to_ungroup
        self.shapes_inside = list(group_to_ungroup.shapes)
    def undo(self):
        for shape in self.shapes_inside:
            if shape in self.layer.shapes: self.layer.shapes.remove(shape)
        self.layer.shapes.append(self.group)
        self.layer.is_dirty = True # 🔴 标记
    def redo(self):
        self.layer.shapes.remove(self.group)
        self.layer.shapes.extend(self.shapes_inside)
        self.layer.is_dirty = True # 🔴 标记

class ScaleCommand(Command):
    def __init__(self, shapes, factor, center):
        self.shapes = list(shapes); self.factor = factor; self.center = center
        self.affected_layers = _get_affected_layers(self.shapes) # 🔴
    def undo(self):
        if self.factor == 0: return
        inverse_factor = 1.0 / self.factor
        for shape in self.shapes: shape.scale(inverse_factor, self.center)
        for layer in self.affected_layers: layer.is_dirty = True # 🔴
    def redo(self):
        for shape in self.shapes: shape.scale(self.factor, self.center)
        for layer in self.affected_layers: layer.is_dirty = True # 🔴

class RotateCommand(Command):
    def __init__(self, shapes, rotation_delta):
        self.shapes = list(shapes); self.rotation_delta = rotation_delta
        self.affected_layers = _get_affected_layers(self.shapes) # 🔴
    def undo(self):
        for shape in self.shapes: shape.rotate(-self.rotation_delta)
        for layer in self.affected_layers: layer.is_dirty = True # 🔴
    def redo(self):
        for shape in self.shapes: shape.rotate(self.rotation_delta)
        for layer in self.affected_layers: layer.is_dirty = True # 🔴

class FlipCommand(Command):
    def __init__(self, shapes, direction):
        self.shapes = list(shapes); self.direction = direction
        self.affected_layers = _get_affected_layers(self.shapes) # 🔴
    def undo(self): self.redo()
    def redo(self):
        for shape in self.shapes:
            if self.direction == 'horizontal': shape.flip_horizontal()
            elif self.direction == 'vertical': shape.flip_vertical()
        for layer in self.affected_layers: layer.is_dirty = True # 🔴

class ModifyNodeCommand(Command):
    def __init__(self, shape, node_index, old_pos, new_pos):
        self.shape, self.node_index = shape, node_index; self.old_pos, self.new_pos = old_pos, new_pos
        self.affected_layers = _get_affected_layers([self.shape]) # 🔴
    def undo(self):
        self.shape.set_node_at(self.node_index, self.old_pos)
        for layer in self.affected_layers: layer.is_dirty = True # 🔴
    def redo(self):
        self.shape.set_node_at(self.node_index, self.new_pos)
        for layer in self.affected_layers: layer.is_dirty = True # 🔴

class CompositeCommand(Command):
    def __init__(self, commands):
        self.commands = commands
    def undo(self):
        for cmd in reversed(self.commands): cmd.undo()
    def redo(self):
        for cmd in self.commands: cmd.redo()

class ModifyPathCommand(Command):
    def __init__(self, path_shape, old_sub_paths, new_sub_paths):
        self.path_shape = path_shape
        self.old_sub_paths = [ [seg.clone() for seg in sp] for sp in old_sub_paths ]
        self.new_sub_paths = [ [seg.clone() for seg in sp] for sp in new_sub_paths ]
        self.affected_layers = _get_affected_layers([self.path_shape]) # 🔴
    def undo(self):
        self.path_shape.sub_paths = self.old_sub_paths
        for layer in self.affected_layers: layer.is_dirty = True # 🔴
    def redo(self):
        self.path_shape.sub_paths = self.new_sub_paths
        for layer in self.affected_layers: layer.is_dirty = True # 🔴