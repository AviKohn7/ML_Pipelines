from math import atan2, cos, sin, pi
from PyQt6.QtWidgets import QGraphicsPathItem
from PyQt6.QtGui import QPen, QPainterPath, QColor, QPolygonF, QBrush
from PyQt6.QtCore import Qt, QPointF, QRectF

class ConnectionItem(QGraphicsPathItem):
    def __init__(self, start_port, end_port=None):
        super().__init__()
        self.start_port = start_port
        self.end_port = end_port
        self.setPen(QPen(QColor("#4CAF50"), 3)) # Green color, thickness 3
        self.setBrush(QBrush(QColor("#4CAF50")))
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

        start_pos = self.start_port.connection_scene_pos()
        end_pos = self.end_port.connection_scene_pos() if self.end_port else self.end_point_temp

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

        x_start_bend = start_pos.x() + start_h_dir * port_extension
        x_end_bend = end_pos.x() + end_h_dir * port_extension

        if start_h_dir == 1 and end_h_dir == -1 and x_start_bend > x_end_bend:
            mid_x = (start_pos.x() + end_pos.x()) / 2
            x_start_bend = mid_x
            x_end_bend = mid_x
        elif start_h_dir == -1 and end_h_dir == 1 and x_start_bend < x_end_bend:
            mid_x = (start_pos.x() + end_pos.x()) / 2
            x_start_bend = mid_x
            x_end_bend = mid_x

        if (start_h_dir == 1 and end_h_dir == 1 and x_start_bend > x_end_bend) or \
           (start_h_dir == -1 and end_h_dir == -1 and x_start_bend < x_end_bend):
            if start_h_dir == 1:
                x_start_bend = max(x_start_bend, end_pos.x() + port_extension)
                x_end_bend = max(x_start_bend, end_pos.x() + port_extension)
            else:
                x_start_bend = min(x_start_bend, end_pos.x() - port_extension)
                x_end_bend = min(x_start_bend, end_pos.x() - port_extension)

        if abs(x_start_bend - x_end_bend) < radius * 2:
            if x_start_bend < x_end_bend:
                x_start_bend -= radius
                x_end_bend += radius
            else:
                x_start_bend += radius
                x_end_bend -= radius

        p1 = QPointF(x_start_bend, start_pos.y())
        p2 = QPointF(x_end_bend, end_pos.y())

        if abs(start_pos.x() - p1.x()) > radius:
            self.path.lineTo(p1.x() - start_h_dir * radius, p1.y())
            rect1 = QRectF(p1.x() - radius, p1.y() - radius, radius * 2, radius * 2)
            start_angle1 = 0
            sweep_angle1 = 90

            if start_h_dir == 1:
                if p1.y() < p2.y():
                    start_angle1 = 180
                    sweep_angle1 = -90
                else:
                    start_angle1 = 90
                    sweep_angle1 = 90
            else:
                if p1.y() < p2.y():
                    start_angle1 = 0
                    sweep_angle1 = 90
                else:
                    start_angle1 = 270
                    sweep_angle1 = 90

            self.path.arcTo(rect1, start_angle1, sweep_angle1)
        else:
            self.path.lineTo(p1)

        if abs(p1.y() - p2.y()) > radius:
            self.path.lineTo(p2.x(), p2.y() - (1 if p1.y() < p2.y() else -1) * radius)
            rect2 = QRectF(p2.x() - radius, p2.y() - radius, radius * 2, radius * 2)
            start_angle2 = 0
            sweep_angle2 = 90

            if p1.y() < p2.y():
                if p2.x() < end_pos.x():
                    start_angle2 = 270
                    sweep_angle2 = -90
                else:
                    start_angle2 = 180
                    sweep_angle2 = -90
            else:
                if p2.x() < end_pos.x():
                    start_angle2 = 0
                    sweep_angle2 = -90
                else:
                    start_angle2 = 90
                    sweep_angle2 = -90

            self.path.arcTo(rect2, start_angle2, sweep_angle2)
        else:
            self.path.lineTo(p2)

        self.path.lineTo(end_pos)
        self.setPath(self.path)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        end_pos = self.end_port.connection_scene_pos() if self.end_port else self.end_point_temp
        if not end_pos:
            return

        if self.path.elementCount() < 2:
            return

        prev_element = self.path.elementAt(self.path.elementCount() - 2)
        prev_point = QPointF(prev_element.x, prev_element.y)
        direction = end_pos - prev_point
        if direction.manhattanLength() < 0.1:
            return

        angle = atan2(direction.y(), direction.x())
        arrow_size = 10
        arrow_p1 = end_pos - QPointF(cos(angle - pi / 6) * arrow_size, sin(angle - pi / 6) * arrow_size)
        arrow_p2 = end_pos - QPointF(cos(angle + pi / 6) * arrow_size, sin(angle + pi / 6) * arrow_size)
        arrow_head = QPolygonF([end_pos, arrow_p1, arrow_p2])

        painter.setBrush(QBrush(self.pen().color()))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(arrow_head)

    def update_position(self):
        self.update_path()
