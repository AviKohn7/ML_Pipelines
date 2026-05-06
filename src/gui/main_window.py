from PyQt6.QtWidgets import QMainWindow, QToolBar, QGraphicsScene, QGraphicsView, QMessageBox, QDialog, QDockWidget
from PyQt6.QtCore import Qt, QRectF, QPointF, QMimeData
from PyQt6.QtGui import QAction, QColor, QBrush

from .module_item import ModuleItem, PortItem
from .connection_item import ConnectionItem
from .settings_dialog import SettingsDialog
from .module_selection_panel import ModuleSelectionPanel
from src.pipeline.pipeline_architecture import modules # Import the global modules dictionary

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pipeline Creator")
        self.setGeometry(100, 100, 1200, 800)

        self.settings = {
            "pipeline_name": "My Pipeline",
            "default_module_color": "#ADD8E6" # Light Blue
        }

        self._create_toolbar()
        self._create_canvas()
        self._create_status_bar()
        self._create_module_panel() # New method to create and dock the module panel

        self.current_connection = None
        self.start_port = None

    def _create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        # Removed 'Add Module' action as it's replaced by the drag-and-drop panel

        run_action = QAction("Run Pipeline", self)
        run_action.triggered.connect(self._run_pipeline)
        toolbar.addAction(run_action)

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._open_settings)
        toolbar.addAction(settings_action)

    def _create_canvas(self):
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(QRectF(0, 0, 4000, 4000)) # Large scene rect for ample space
        self.view = QGraphicsView(self.scene)
        self.setCentralWidget(self.view)

        # Enable mouse events for connection drawing
        self.view.setMouseTracking(True)
        self.view.mousePressEvent = self._view_mouse_press_event
        self.view.mouseMoveEvent = self._view_mouse_move_event
        self.view.mouseReleaseEvent = self._view_mouse_release_event

        # Enable drag and drop for the canvas
        self.view.setAcceptDrops(True)
        self.view.dragEnterEvent = self._view_drag_enter_event
        self.view.dragMoveEvent = self._view_drag_move_event
        self.view.dropEvent = self._view_drop_event

    def _create_status_bar(self):
        self.statusBar().showMessage("Ready")

    def _create_module_panel(self):
        self.module_panel = ModuleSelectionPanel(self)
        dock_widget = QDockWidget("Modules", self)
        dock_widget.setWidget(self.module_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_widget)

    def _add_module(self, module_class, pos):
        # Instantiate the module class passed from the drag event
        try:
            module = ModuleItem(module_class, pos.x(), pos.y())
            module.setBrush(QBrush(QColor(self.settings["default_module_color"])))
            self.scene.addItem(module)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create module: {e}")


    def _run_pipeline(self):
        # Simulate pipeline execution
        import random
        if random.random() < 0.3: # 30% chance of error
            error_message = "Simulated pipeline error: Module 'X' failed to process data."
            QMessageBox.critical(self, "Pipeline Error", error_message)
            self.statusBar().showMessage("Pipeline failed!")
        else:
            QMessageBox.information(self, "Run Pipeline", f"Pipeline '{self.settings['pipeline_name']}' executed successfully!")
            self.statusBar().showMessage("Pipeline ran successfully.")

    def _open_settings(self):
        settings_dialog = SettingsDialog(self)
        settings_dialog.set_settings(self.settings) # Pass current settings to the dialog
        if settings_dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = settings_dialog.get_settings() # Update settings from dialog
            self.statusBar().showMessage("Settings updated.")
            # Optionally, update existing modules with new color
            for item in self.scene.items():
                if isinstance(item, ModuleItem):
                    item.setBrush(QBrush(QColor(self.settings["default_module_color"])))
        else:
            self.statusBar().showMessage("Settings not changed.")

    def _view_mouse_press_event(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.view.itemAt(event.pos())
            if isinstance(item, PortItem):
                self.start_port = item
                self.current_connection = ConnectionItem(self.start_port)
                self.scene.addItem(self.current_connection)
                self.current_connection.end_point = self.start_port.scenePos() # Initialize end_point
            else:
                # Allow default drag behavior for modules
                super(QGraphicsView, self.view).mousePressEvent(event)
        else:
            super(QGraphicsView, self.view).mousePressEvent(event)

    def _view_mouse_move_event(self, event):
        if self.current_connection:
            self.current_connection.end_point = self.view.mapToScene(event.pos())
            self.current_connection.update_path() # Use update_path for the new logic
        super(QGraphicsView, self.view).mouseMoveEvent(event)

    def _view_mouse_release_event(self, event):
        if self.current_connection and event.button() == Qt.MouseButton.LeftButton:
            end_item = self.view.itemAt(event.pos())
            
            # Assume connection is invalid by default
            is_valid_connection = False

            if isinstance(end_item, PortItem) and end_item != self.start_port:
                # Check if it's a valid connection (output to input)
                # An output port (is_input=False) can connect to an input port (is_input=True)
                if not self.start_port.is_input and end_item.is_input:
                    # Check if the input port already has a connection
                    if not end_item.connections: # Assuming input ports only accept one connection
                        self.current_connection.end_port = end_item
                        self.current_connection.update_path() # Use update_path for the new logic
                        self.start_port.connections.append(self.current_connection)
                        end_item.connections.append(self.current_connection)
                        print(f"Connected {self.start_port.parent_module.title_item.toPlainText()}'s {self.start_port.name} to {end_item.parent_module.title_item.toPlainText()}'s {end_item.name}")
                        is_valid_connection = True
                # Allow input to output connection as well, if desired, but typically it's output to input
                elif self.start_port.is_input and not end_item.is_input:
                    if not self.start_port.connections: # Assuming input ports only accept one connection
                        self.current_connection.end_port = end_item
                        self.current_connection.update_path()
                        self.start_port.connections.append(self.current_connection)
                        end_item.connections.append(self.current_connection)
                        print(f"Connected {self.start_port.parent_module.title_item.toPlainText()}'s {self.start_port.name} to {end_item.parent_module.title_item.toPlainText()}'s {end_item.name}")
                        is_valid_connection = True

            if not is_valid_connection:
                # Remove the connection if it's invalid or dropped on nothing
                if self.current_connection in self.start_port.connections:
                    self.start_port.connections.remove(self.current_connection)
                self.scene.removeItem(self.current_connection)

            self.current_connection = None
            self.start_port = None
        super(QGraphicsView, self.view).mouseReleaseEvent(event)

    def _view_drag_enter_event(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("module_drag:"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _view_drag_move_event(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("module_drag:"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _view_drop_event(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("module_drag:"):
            mime_data_text = event.mimeData().text()
            parts = mime_data_text.split(':')
            if len(parts) == 3 and parts[0] == "module_drag":
                module_name = parts[1]
                module_class_name = parts[2]
                
                # Find the actual module class from the global 'modules' dictionary
                module_class = None
                for section_name, module_classes_in_section in modules.items():
                    for cls in module_classes_in_section:
                        if cls.__name__ == module_class_name:
                            module_class = cls
                            break
                    if module_class:
                        break

                if module_class:
                    scene_pos = self.view.mapToScene(event.position().toPoint()) # Use event.position() and convert to QPoint
                    self._add_module(module_class, scene_pos)
                    event.acceptProposedAction()
                else:
                    QMessageBox.critical(self, "Error", f"Unknown module class: {module_class_name}")
                    event.ignore()
            else:
                event.ignore()
        else:
            event.ignore()