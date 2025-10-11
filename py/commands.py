from PyQt6.QtGui import QColor
from shapes import ShapeGroup
class Command:
    def undo(self): raise NotImplementedError
    def redo(self): raise NotImplementedError

# --- 图层操作命令 ---
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

# --- 图形操作命令 (现在需要知道图层) ---
class AddShapeCommand(Command):
    def __init__(self, layer, shape):
        self.layer, self.shape = layer, shape
    def undo(self): self.layer.shapes.remove(self.shape)
    def redo(self): self.layer.shapes.append(self.shape)

class RemoveShapesCommand(Command):
    def __init__(self, layer, shapes):
        self.layer, self.shapes = layer, list(shapes)
    def undo(self): self.layer.shapes.extend(self.shapes)
    def redo(self):
        self.layer.shapes = [s for s in self.layer.shapes if s not in self.shapes]

class MoveShapesCommand(Command):
    def __init__(self, shapes, dx, dy):
        self.shapes, self.dx, self.dy = list(shapes), dx, dy
    def undo(self):
        for shape in self.shapes: shape.move(-self.dx, -self.dy)
    def redo(self):
        for shape in self.shapes: shape.move(self.dx, self.dy)

class ChangePropertiesCommand(Command):
    def __init__(self, shapes, new_properties):
        self.shapes = list(shapes)
        self.new_properties = new_properties
        self.old_properties = {}
        # 预先记录旧值
        for shape in self.shapes:
            self.old_properties[shape] = {}
            for prop_name in self.new_properties.keys():
                self.old_properties[shape][prop_name] = getattr(shape, prop_name)

    def undo(self):
        for shape in self.shapes:
            for prop_name, value in self.old_properties[shape].items():
                setattr(shape, prop_name, value)
    def redo(self):
        for shape in self.shapes:
            for prop_name, value in self.new_properties.items():
                setattr(shape, prop_name, value)

class GroupCommand(Command):
    def __init__(self, layer, shapes_to_group):
        self.layer = layer
        self.shapes_to_group = list(shapes_to_group)
        self.group = ShapeGroup(self.shapes_to_group)

    def undo(self):
        self.layer.shapes.remove(self.group)
        self.layer.shapes.extend(self.shapes_to_group)

    def redo(self):
        for shape in self.shapes_to_group:
            self.layer.shapes.remove(shape)
        self.layer.shapes.append(self.group)

class UngroupCommand(Command):
    def __init__(self, layer, group_to_ungroup):
        self.layer = layer
        self.group = group_to_ungroup
        self.shapes_inside = list(group_to_ungroup.shapes)

    def undo(self):
        for shape in self.shapes_inside:
            self.layer.shapes.remove(shape)
        self.layer.shapes.append(self.group)

    def redo(self):
        self.layer.shapes.remove(self.group)
        self.layer.shapes.extend(self.shapes_inside)

class ScaleCommand(Command):
    def __init__(self, shapes, factor, center):
        self.shapes = list(shapes)
        self.factor = factor
        self.center = center

    def undo(self):
        if self.factor == 0: return # Avoid division by zero
        inverse_factor = 1.0 / self.factor
        for shape in self.shapes:
            shape.scale(inverse_factor, self.center)

    def redo(self):
        for shape in self.shapes:
            shape.scale(self.factor, self.center)
class RotateCommand(Command):
    def __init__(self, shapes, rotation_delta):
        self.shapes = list(shapes)
        self.rotation_delta = rotation_delta

    def undo(self):
        for shape in self.shapes:
            shape.rotate(-self.rotation_delta)
    
    def redo(self):
        for shape in self.shapes:
            shape.rotate(self.rotation_delta)

class FlipCommand(Command):
    def __init__(self, shapes, direction):
        self.shapes = list(shapes)
        self.direction = direction # 'horizontal' or 'vertical'

    def undo(self):
        # 翻转操作是自身的逆操作，所以 undo 和 redo 是一样的
        self.redo()

    def redo(self):
        for shape in self.shapes:
            if self.direction == 'horizontal':
                shape.flip_horizontal()
            elif self.direction == 'vertical':
                shape.flip_vertical()

class ModifyNodeCommand(Command):
    def __init__(self, shape, node_index, old_pos, new_pos):
        self.shape = shape
        self.node_index = node_index
        self.old_pos = old_pos
        self.new_pos = new_pos

    def undo(self):
        self.shape.set_node_at(self.node_index, self.old_pos)

    def redo(self):
        self.shape.set_node_at(self.node_index, self.new_pos)

class AddShapesCommand(Command):
    def __init__(self, layer, shapes):
        self.layer = layer
        self.shapes = list(shapes)  # 确保我们操作的是列表副本

    def undo(self):
        # 从图层中移除这些刚刚添加的图形
        self.layer.shapes = [s for s in self.layer.shapes if s not in self.shapes]

    def redo(self):
        # 将这些图形重新添加到图层中
        self.layer.shapes.extend(self.shapes)

class CompositeCommand(Command):
    """A command that groups other commands into a single undo/redo operation."""
    def __init__(self, commands):
        self.commands = commands

    def undo(self):
        # Undo commands in reverse order
        for cmd in reversed(self.commands):
            cmd.undo()

    def redo(self):
        # Redo commands in normal order
        for cmd in self.commands:
            cmd.redo()

class ModifyPathCommand(Command):
    """
    一个用于修改 Path 对象内部结构的命令（如添加/删除节点）。
    它通过保存整个 sub_paths 列表的快照来实现撤销/重做。
    """
    def __init__(self, path_shape, old_sub_paths, new_sub_paths):
        self.path_shape = path_shape
        # 使用深拷贝确保我们保存的是值的快照，而不是引用
        self.old_sub_paths = [
            [seg.clone() for seg in sp] for sp in old_sub_paths
        ]
        self.new_sub_paths = [
            [seg.clone() for seg in sp] for sp in new_sub_paths
        ]

    def undo(self):
        self.path_shape.sub_paths = self.old_sub_paths

    def redo(self):
        self.path_shape.sub_paths = self.new_sub_paths