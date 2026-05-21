from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QSizePolicy, QApplication, QComboBox
from PyQt6.QtCore import QSize, Qt, QMimeData, QPoint, QTimer, QRect
from PyQt6.QtGui import QDrag, QPixmap, QPainter, QRegion, QPen, QColor, QFont

from src.pipeline.pipeline_architecture import modules, Module

class PortPreview(QWidget):
    def __init__(self, name, is_input=True, parent=None):
        super().__init__(parent)
        self.name = name
        self.is_input = is_input
        self.setMinimumHeight(24)
        self.setMaximumHeight(24)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        radius = 10

        if self.is_input:
            circle_x = 0
            text_rect = QRect(radius + 8, 0, rect.width() - radius - 8, rect.height())
            circle_color = QColor(Qt.GlobalColor.darkGreen)
            text_align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        else:
            circle_x = rect.width() - 2 * radius
            text_rect = QRect(0, 0, rect.width() - radius - 8, rect.height())
            circle_color = QColor(Qt.GlobalColor.darkRed)
            text_align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight

        painter.setBrush(circle_color)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        if self.is_input:
            painter.drawPie(circle_x, (rect.height() - 2 * radius) // 2, 2 * radius, 2 * radius, 90 * 16, 180 * 16)
        else:
            painter.drawPie(circle_x, (rect.height() - 2 * radius) // 2, 2 * radius, 2 * radius, -90 * 16, 180 * 16)

        painter.setPen(QPen(Qt.GlobalColor.black))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(text_rect, text_align, self.name)
        painter.end()


class DraggableModulePreview(QWidget):
    def __init__(self, module_class, module_name, parent=None):
        super().__init__(parent)
        self.module_class = module_class
        self.module_name = module_name
        self.setObjectName("DraggableModulePreview")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self.setStyleSheet("QWidget#DraggableModulePreview { background-color: #ADD8E6; border: 1px solid #000000; border-radius: 6px; }")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(6)

        self.title_label = QLabel(module_name, self)
        self.title_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.layout.addWidget(self.title_label)

        self.config_dropdown = QComboBox(self)
        try:
            module_instance = module_class()
            self.configurations = module_instance.get_configurations()
            self.config_dropdown.addItems([config.name for config in self.configurations])
        except Exception:
            self.configurations = []
        self.config_dropdown.setCurrentIndex(0)
        self.config_dropdown.setEnabled(False)
        self.layout.addWidget(self.config_dropdown)

        self.ports_layout = QVBoxLayout()
        self.ports_layout.setSpacing(4)
        self.layout.addLayout(self.ports_layout)

        self._update_ports()
        self.config_dropdown.currentIndexChanged.connect(self._update_ports)

    def _update_ports(self):
        while self.ports_layout.count():
            item = self.ports_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.configurations:
            return

        config = self.configurations[self.config_dropdown.currentIndex()]
        for i, input_type in enumerate(config.input_types):
            self.ports_layout.addWidget(PortPreview(f"Input {i+1} ({input_type.__name__})", is_input=True, parent=self))

        if config.output:
            self.ports_layout.addWidget(PortPreview(f"Output ({config.output.__name__})", is_input=False, parent=self))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, 'drag_start_position') and (event.pos() - self.drag_start_position).manhattanLength() > QApplication.startDragDistance():
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(f"module_drag:{self.module_class.__name__}:{self.drag_start_position.x()}:{self.drag_start_position.y()}")

            pixmap = QPixmap(self.size())
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setOpacity(0.9)
            self.render(painter, QPoint(), QRegion(self.rect()))
            painter.end()

            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())
            drag.setMimeData(mime_data)
            drag.exec(Qt.DropAction.CopyAction)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)


class CollapsibleSection(QWidget):
    def __init__(self, title="", on_layout_changed=None, parent=None):
        super().__init__(parent)
        self._on_layout_changed = on_layout_changed
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.toggle_button = QToolButton(self)
        self.toggle_button.setStyleSheet("""
            QToolButton {
                border: none;
                background-color: #E0E0E0;
                padding: 5px;
                text-align: left;
                font-weight: bold;
                border-radius: 3px;
            }
            QToolButton:hover {
                background-color: #D0D0D0;
            }
        """)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)

        self.content_area = QWidget(self)
        self.content_area.setStyleSheet("background-color: #F8F8F8;")
        self.content_area.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.content_area.setVisible(False)

        self.toggle_button.clicked.connect(self.toggle_content)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.toggle_button)
        self.main_layout.addWidget(self.content_area)

        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_layout.setSpacing(5)

    def toggle_content(self):
        visible = not self.content_area.isVisible()
        self.content_area.setVisible(visible)
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow)
        self.updateGeometry()
        self.adjustSize()
        parent = self.parentWidget()
        if parent is not None:
            parent.adjustSize()
        if self._on_layout_changed:
            self._on_layout_changed()

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)


class ModuleSelectionPanel(QWidget):
    def __init__(self, on_layout_changed=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modules")
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(0)
        self._on_layout_changed = on_layout_changed

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(5)

        self.content_container = QWidget(self)
        self.content_container.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(5)

        self.loading_label = QLabel("Loading modules...")
        self.loading_label.setStyleSheet("color: #555; padding: 8px;")
        self.content_layout.addWidget(self.loading_label)
        self.content_layout.addStretch()

        self.main_layout.addWidget(self.content_container)
        self.main_layout.addStretch()

        QTimer.singleShot(0, self._populate_modules)

    def sizeHint(self):
        return self.main_layout.sizeHint()

    def minimumSizeHint(self):
        return self.main_layout.minimumSize()

    def toggle_content(self, visible=None):
        if visible is None:
            visible = not self.content_container.isVisible()
        self.content_container.setVisible(visible)
        self.adjustSize()
        self.updateGeometry()

    def is_content_visible(self):
        return self.content_container.isVisible()

    def set_minimized(self, minimized: bool):
        self._minimized = minimized

        if minimized:
            self.setMinimumWidth(24)
            self.setMaximumWidth(24)
        else:
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)

        self.updateGeometry()

    def sizeHint(self):
        hint = super().sizeHint()

        if getattr(self, "_minimized", False):
            return QSize(24, hint.height())

        return hint
    
    def _populate_modules(self):
        try:
            import src.pipeline.default_modules
        except Exception as e:
            self.loading_label.setText(f"Failed to load modules: {e}")
            return

        self.loading_label.hide()

        for section_name, module_classes in modules.items():
            section = CollapsibleSection(section_name, self._on_layout_changed, self)
            for module_class in module_classes:
                # Instantiate the module to get its default name
                try:
                    temp_module_instance = module_class()
                    module_display_name = temp_module_instance.name
                except Exception:
                    # Fallback if instantiation fails (e.g., missing required args)
                    module_display_name = module_class.__name__

                draggable_label = DraggableModulePreview(module_class, module_display_name, section)
                section.add_widget(draggable_label)
            self.content_layout.insertWidget(self.content_layout.count() - 1, section)
