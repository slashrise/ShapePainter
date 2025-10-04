from PyQt6.QtCore import QRect

class Aligner:
    @staticmethod
    def align(shapes, mode):
        """
        Calculates the required movement (dx, dy) for each shape to align them.
        Returns a list of tuples: [(shape, dx, dy), ...].
        """
        if len(shapes) < 2:
            return []

        # Use the first selected shape as the reference for alignment
        # This is a common and intuitive approach
        reference_bbox = shapes[0].get_transformed_bounding_box()
        moves = []

        for shape in shapes[1:]:
            bbox = shape.get_transformed_bounding_box()
            dx, dy = 0, 0

            if mode == 'left':
                dx = reference_bbox.left() - bbox.left()
            elif mode == 'right':
                dx = reference_bbox.right() - bbox.right()
            elif mode == 'top':
                dy = reference_bbox.top() - bbox.top()
            elif mode == 'bottom':
                dy = reference_bbox.bottom() - bbox.bottom()
            elif mode == 'center_h':
                dx = reference_bbox.center().x() - bbox.center().x()
            elif mode == 'center_v':
                dy = reference_bbox.center().y() - bbox.center().y()
            
            if dx != 0 or dy != 0:
                moves.append((shape, dx, dy))
        
        return moves