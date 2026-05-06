from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame, QToolButton, QSizePolicy, QApplication
from PyQt6.QtCore import Qt, QMimeData, QPoint
from PyQt6.QtGui import QDrag, QPixmap, QPainter, QRegion # Moved QRegion here

from src.pipeline.pipeline_architecture import modules, Module # Import the global modules dictionary and base Module class
# from src.gui.module_item import ModuleItem # ModuleItem is not directly used here, only its name for drag

class DraggableModuleLabel(QLabel):
    def __init__(self, module_class, module_name, parent=None):
        super().__init__(module_name, parent)
        self.module_class = module_class
        self.module_name = module_name
        self.setFrameShape(QFrame.Shape.StyledPanel) # Use StyledPanel for a more modern look
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setContentsMargins(8, 8, 8, 8) # More padding
        self.setStyleSheet("""
            DraggableModuleLabel {
                background-color: #F0F0F0;
                border: 1px solid #CCCCCC;
                border-radius: 5px;
                padding: 5px;
            }
            DraggableModuleLabel:hover {
                background-color: #E0E0E0;
                border: 1px solid #AAAAAA;
            }
        """)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and (event.pos() - self.drag_start_position).manhattanLength() > QApplication.startDragDistance():
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(f"module_drag:{self.module_name}:{self.module_class.__name__}") # Store module info

            # Create a pixmap for the drag visual
            pixmap = QPixmap(self.size())
            pixmap.fill(Qt.GlobalColor.transparent) # Fill with transparent background
            painter = QPainter(pixmap)
            painter.setOpacity(0.7) # Make it slightly transparent
            self.render(painter, QPoint(), QRegion(self.rect())) # Render the widget onto the pixmap
            painter.end()

            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())

            drag.setMimeData(mime_data)
            drag.exec(Qt.DropAction.CopyAction)
        super().mouseMoveEvent(event)


class CollapsibleSection(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
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

        self.content_area = QScrollArea(self)
        self.content_area.setStyleSheet("QScrollArea { border: none; background-color: #F8F8F8; }")
        self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        self.content_area.setWidgetResizable(True)

        self.toggle_button.clicked.connect(self.toggle_content)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.toggle_button)
        self.main_layout.addWidget(self.content_area)

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_widget = QWidget()
        self.content_widget.setLayout(self.content_layout)
        self.content_area.setWidget(self.content_widget)

    def toggle_content(self):
        if self.toggle_button.isChecked():
            self.toggle_button.setArrowType(Qt.ArrowType.DownArrow)
            # Calculate the required height of the content
            self.content_area.setMaximumHeight(self.content_layout.sizeHint().height() + self.content_area.contentsMargins().top() + self.content_area.contentsMargins().bottom())
            self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding) # Allow expansion
        else:
            self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
            self.content_area.setMaximumHeight(0)
            self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed) # Fix size when collapsed
        self.parentWidget().updateGeometry() # Request parent to re-layout

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)


class ModuleSelectionPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modules")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(5)

        self._populate_modules()
        self.main_layout.addStretch() # Push content to the top

    def _populate_modules(self):
        for section_name, module_classes in modules.items():
            section = CollapsibleSection(section_name, self)
            for module_class in module_classes:
                # Instantiate the module to get its default name
                try:
                    temp_module_instance = module_class()
                    module_display_name = temp_module_instance.name
                except Exception:
                    # Fallback if instantiation fails (e.g., missing required args)
                    module_display_name = module_class.__name__

                draggable_label = DraggableModuleLabel(module_class, module_display_name, section)
                section.add_widget(draggable_label)
            self.main_layout.addWidget(section)
