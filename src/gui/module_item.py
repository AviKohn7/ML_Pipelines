from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem, QGraphicsProxyWidget, QComboBox, QGraphicsDropShadowEffect, QGraphicsPathItem
from PyQt6.QtCore import Qt, QRectF, QPointF, QSizeF
from PyQt6.QtGui import QBrush, QColor, QPen, QFont, QPainterPath
from typing import Type, List, Optional

from src.pipeline.pipeline_architecture import Module, Configuration # Import Module and Configuration

class PortItem(QGraphicsPathItem):
    def __init__(self, parent_module, is_input, index, name="", port_type=None):
        super().__init__(parent_module)
        self.parent_module = parent_module
        self.is_input = is_input
        self.index = index
        self.name = name
        self.port_type = port_type # Store the type for display

        self.port_radius = 6
        self.setPen(QPen(Qt.GlobalColor.black, 1))
        self.setBrush(QBrush(QColor(Qt.GlobalColor.gray))) # Default color
        self.setZValue(2)

        self.connections = []

        self.label = QGraphicsTextItem(name, self)
        self.label.setFont(QFont("Arial", 7))
        self.label.setDefaultTextColor(QColor(Qt.GlobalColor.black))

        self.setAcceptHoverEvents(True)
        self.update_path() # Initial path drawing

    def update_path(self):
        path = QPainterPath()
        if self.is_input:
            # Semicircle on the left
            path.arcMoveTo(QRectF(-self.port_radius, -self.port_radius, self.port_radius * 2, self.port_radius * 2), 90)
            path.arcTo(QRectF(-self.port_radius, -self.port_radius, self.port_radius * 2, self.port_radius * 2), 90, 180)
            path.closeSubpath()
        else:
            # Semicircle on the right
            path.arcMoveTo(QRectF(-self.port_radius, -self.port_radius, self.port_radius * 2, self.port_radius * 2), -90)
            path.arcTo(QRectF(-self.port_radius, -self.port_radius, self.port_radius * 2, self.port_radius * 2), -90, 180)
            path.closeSubpath()
        self.setPath(path)

        # Position label
        if self.is_input:
            self.label.setPos(-self.label.boundingRect().width() - self.port_radius - 5, -self.label.boundingRect().height() / 2)
        else:
            self.label.setPos(self.port_radius + 5, -self.label.boundingRect().height() / 2)

    def connection_scene_pos(self):
        # Return the center of the flat edge of the semicircle
        if self.is_input:
            return self.parent_module.mapToScene(self.pos() + QPointF(-self.port_radius, 0))
        else:
            return self.parent_module.mapToScene(self.pos() + QPointF(self.port_radius, 0))

    def hoverEnterEvent(self, event):
        if self.is_input:
            self.setBrush(QBrush(QColor(Qt.GlobalColor.green)))
        else:
            self.setBrush(QBrush(QColor(Qt.GlobalColor.red)))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if self.is_input:
            self.setBrush(QBrush(QColor(Qt.GlobalColor.darkGreen)))
        else:
            self.setBrush(QBrush(QColor(Qt.GlobalColor.darkRed)))
        super().hoverLeaveEvent(event)


class ModuleItem(QGraphicsRectItem):
    def __init__(self, module_class: Type[Module], x=0, y=0, width=150, height=100):
        super().__init__(0, 0, width, height) # Initialize rect at (0,0) within the item's local coordinates
        self.setPos(x, y) # Set the item's position in the scene
        self.setBrush(QBrush(QColor("lightblue")))
        self.setPen(QPen(Qt.GlobalColor.black))
        self.setFlags(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(1)

        self.module_instance = module_class()
        self.configurations = self.module_instance.get_configurations()
        self.current_configuration: Optional[Configuration] = None

        self.setGraphicsEffect(QGraphicsDropShadowEffect(blurRadius=5, xOffset=3, yOffset=3))

        self.title_item = QGraphicsTextItem(self.module_instance.name, self)
        self.title_item.setDefaultTextColor(QColor(Qt.GlobalColor.black))
        self.title_item.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.title_item.setPos(10, 10)

        self.config_dropdown = QComboBox()
        self.config_dropdown.addItems([config.name for config in self.configurations])
        self.config_dropdown.setCurrentIndex(0)
        self.config_dropdown.currentIndexChanged.connect(self._config_changed)

        self.config_proxy = QGraphicsProxyWidget(self)
        self.config_proxy.setWidget(self.config_dropdown)
        self.config_proxy.setZValue(2)

        self.input_ports: List[PortItem] = []
        self.output_port: Optional[PortItem] = None

        self._update_ports_and_size() # Initial port creation and size adjustment

    def _update_ports_and_size(self):
        # Clear existing ports and their connections
        scene = self.scene()
        for port in self.input_ports:
            for connection in list(port.connections): # Iterate over a copy
                if scene:
                    scene.removeItem(connection)
                if connection.start_port == port and connection.end_port:
                    connection.end_port.connections.remove(connection)
                elif connection.end_port == port and connection.start_port:
                    connection.start_port.connections.remove(connection)
            port.connections.clear()
            if scene:
                scene.removeItem(port)
        self.input_ports.clear()

        if self.output_port:
            for connection in list(self.output_port.connections):
                if scene:
                    scene.removeItem(connection)
                if connection.start_port == self.output_port and connection.end_port:
                    connection.end_port.connections.remove(connection)
                elif connection.end_port == self.output_port and connection.start_port:
                    connection.start_port.connections.remove(connection)
            self.output_port.connections.clear()
            if scene:
                scene.removeItem(self.output_port)
            self.output_port = None

        # Set current configuration
        self.current_configuration = self.configurations[self.config_dropdown.currentIndex()]

        # Calculate new size based on ports
        max_input_label_width = 0
        if self.current_configuration.input_types:
            for i, input_type in enumerate(self.current_configuration.input_types):
                temp_label = QGraphicsTextItem(f"Input {i+1} ({input_type.__name__})")
                max_input_label_width = max(max_input_label_width, temp_label.boundingRect().width())

        output_label_width = 0
        if self.current_configuration.output:
            temp_label = QGraphicsTextItem(f"Output ({self.current_configuration.output.__name__})")
            output_label_width = temp_label.boundingRect().width()

        port_spacing = 20
        port_radius = 6 # Must match PortItem's port_radius

        # Calculate required height for ports
        num_inputs = len(self.current_configuration.input_types)
        ports_height = max(num_inputs, 1) * port_spacing + 10 # At least one port height

        # Calculate required width
        min_width = 150
        required_width = max(min_width, self.title_item.boundingRect().width() + 20,
                             max_input_label_width + output_label_width + 2 * port_radius + 40) # 40 for padding

        # Calculate required height
        min_height = 100
        required_height = max(min_height, self.title_item.boundingRect().height() + self.config_dropdown.sizeHint().height() + ports_height + 30) # 30 for padding

        self.setRect(0, 0, required_width, required_height)

        # Position title and dropdown
        self.title_item.setPos(10, 10)
        self.config_proxy.setPos(10, self.title_item.pos().y() + self.title_item.boundingRect().height() + 5)
        self.config_proxy.setWidget(self.config_dropdown) # Re-set widget to update position

        # Create new ports
        config_proxy_size_hint = self.config_proxy.sizeHint(Qt.SizeHint.PreferredSize, QSizeF())
        start_y_ports = self.config_proxy.pos().y() + config_proxy_size_hint.height() + 10

        # Input ports
        for i, input_type in enumerate(self.current_configuration.input_types):
            port = PortItem(self, True, i, f"Input {i+1} ({input_type.__name__})", input_type)
            port.setPos(0, start_y_ports + i * port_spacing)
            self.input_ports.append(port)
            port.setBrush(QBrush(QColor(Qt.GlobalColor.darkGreen))) # Green for input

        # Output port
        if self.current_configuration.output:
            self.output_port = PortItem(self, False, 0, f"Output ({self.current_configuration.output.__name__})", self.current_configuration.output)
            self.output_port.setPos(self.rect().width(), start_y_ports + (max(num_inputs, 1) - 1) * port_spacing / 2) # Center vertically
            self.output_port.setBrush(QBrush(QColor(Qt.GlobalColor.darkRed))) # Red for output

    def _config_changed(self, index):
        self._update_ports_and_size()
        print(f"Module '{self.module_instance.name}' config changed to: {self.config_dropdown.currentText()}")

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionHasChanged:
            for port in self.input_ports:
                for connection in port.connections:
                    connection.update_path()
            if self.output_port:
                for connection in self.output_port.connections:
                    connection.update_path()
        return super().itemChange(change, value)
