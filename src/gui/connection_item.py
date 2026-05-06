from PyQt6.QtWidgets import QGraphicsPathItem
from PyQt6.QtGui import QPen, QPainterPath, QColor
from PyQt6.QtCore import Qt, QPointF, QRectF

class ConnectionItem(QGraphicsPathItem):
    def __init__(self, start_port, end_port=None):
        super().__init__()
        self.start_port = start_port
        self.end_port = end_port
        self.setPen(QPen(QColor("#4CAF50"), 3)) # Green color, thickness 3
        self.setZValue(0) # Connections are behind modules

        self.start_port.connections.append(self)
        if self.end_port:
            self.end_port.connections.append(self)

        self.path = QPainterPath()
        self.end_point_temp = None # Used when dragging a new connection
        self.update_path()

    def update_path(self):
        if not self.start_port:
            return

        start_pos = self.start_port.scenePos()
        end_pos = self.end_port.scenePos() if self.end_port else self.end_point_temp

        if not end_pos:
            return

        self.path = QPainterPath()
        self.path.moveTo(start_pos)

        radius = 10 # Radius for rounded corners
        # Minimum horizontal extension from port to ensure the bend is outside the module
        port_extension = 30

        # Determine the direction of the connection from the start port
        # 1 for output (right), -1 for input (left)
        start_h_dir = 1 if not self.start_port.is_input else -1
        # Determine the direction of the connection to the end port
        end_h_dir = 1 if not (self.end_port and self.end_port.is_input) else -1

        # Calculate the x-coordinates for the first and second horizontal segments
        # These are the x-coordinates where the path will turn vertically
        x_start_bend = start_pos.x() + start_h_dir * port_extension
        x_end_bend = end_pos.x() + end_h_dir * port_extension

        # Adjust x_start_bend and x_end_bend if they cross or are too close
        # This ensures the vertical segment has enough space and doesn't overlap modules
        if start_h_dir == 1 and end_h_dir == -1: # Output to Input (left side)
            # If the start bend is to the right of the end bend, they are crossing
            if x_start_bend > x_end_bend:
                mid_x = (start_pos.x() + end_pos.x()) / 2
                x_start_bend = mid_x
                x_end_bend = mid_x
        elif start_h_dir == -1 and end_h_dir == 1: # Input (left side) to Output
            # If the start bend is to the left of the end bend, they are crossing
            if x_start_bend < x_end_bend:
                mid_x = (start_pos.x() + end_pos.x()) / 2
                x_start_bend = mid_x
                x_end_bend = mid_x
        
        # If both ports are on the same side (e.g., output to output, or input to input)
        # or if they are on opposite sides but the modules are very close,
        # we might need to push the intermediate horizontal segments further out.
        if (start_h_dir == 1 and end_h_dir == 1 and x_start_bend > x_end_bend) or \
           (start_h_dir == -1 and end_h_dir == -1 and x_start_bend < x_end_bend):
            # Both outputs or both inputs, and they are "crossing"
            # Push the intermediate x further out
            if start_h_dir == 1: # Both outputs
                x_start_bend = max(x_start_bend, end_pos.x() + port_extension)
                x_end_bend = max(x_start_bend, end_pos.x() + port_extension)
            else: # Both inputs
                x_start_bend = min(x_start_bend, end_pos.x() - port_extension)
                x_end_bend = min(x_start_bend, end_pos.x() - port_extension)

        # Ensure x_start_bend and x_end_bend are distinct enough if they are too close
        if abs(x_start_bend - x_end_bend) < radius * 2: # Minimum horizontal separation for two bends
            if x_start_bend < x_end_bend:
                x_start_bend -= radius
                x_end_bend += radius
            else:
                x_start_bend += radius
                x_end_bend -= radius

        # Define the key points for the H-V-H path
        # p1: end of first horizontal segment, start of first vertical segment
        # p2: end of first vertical segment, start of second horizontal segment
        p1 = QPointF(x_start_bend, start_pos.y())
        p2 = QPointF(x_end_bend, end_pos.y())

        # Draw first horizontal segment and first bend
        if abs(start_pos.x() - p1.x()) > radius:
            self.path.lineTo(p1.x() - start_h_dir * radius, p1.y())
            # Determine arc direction for the first bend
            rect1 = QRectF(p1.x() - radius, p1.y() - radius, radius * 2, radius * 2)
            start_angle1 = 0
            sweep_angle1 = 90

            if start_h_dir == 1: # Going right
                if p1.y() < p2.y(): # Bending down
                    start_angle1 = 180
                    sweep_angle1 = -90
                else: # Bending up
                    start_angle1 = 90
                    sweep_angle1 = 90
            else: # Going left
                if p1.y() < p2.y(): # Bending down
                    start_angle1 = 0
                    sweep_angle1 = 90
                else: # Bending up
                    start_angle1 = 270
                    sweep_angle1 = 90
            
            self.path.arcTo(rect1, start_angle1, sweep_angle1)
        else:
            self.path.lineTo(p1)

        # Draw vertical segment and second bend
        if abs(p1.y() - p2.y()) > radius:
            self.path.lineTo(p2.x(), p2.y() - (1 if p1.y() < p2.y() else -1) * radius)
            # Determine arc direction for the second bend
            rect2 = QRectF(p2.x() - radius, p2.y() - radius, radius * 2, radius * 2)
            start_angle2 = 0
            sweep_angle2 = 90

            if p1.y() < p2.y(): # Going down
                if p2.x() < end_pos.x(): # Bending right
                    start_angle2 = 270
                    sweep_angle2 = -90
                else: # Bending left
                    start_angle2 = 180
                    sweep_angle2 = -90
            else: # Going up
                if p2.x() < end_pos.x(): # Bending right
                    start_angle2 = 0
                    sweep_angle2 = -90
                else: # Bending left
                    start_angle2 = 90
                    sweep_angle2 = -90
            
            self.path.arcTo(rect2, start_angle2, sweep_angle2)
        else:
            self.path.lineTo(p2)

        # Draw final horizontal segment to end_pos
        self.path.lineTo(end_pos)

        self.setPath(self.path)

    def update_position(self):
        self.update_path()
