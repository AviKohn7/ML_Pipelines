from PyQt6.QtWidgets import QMainWindow, QSizePolicy, QToolBar, QGraphicsScene, QGraphicsView, QMessageBox, QDialog, QDockWidget, QWidget, QHBoxLayout, QLabel, QToolButton
from PyQt6.QtCore import QSize, Qt, QRectF, QPointF, QMimeData, QEvent, QTimer
from PyQt6.QtGui import QAction, QColor, QBrush, QFont

from .module_item import ModuleItem, PortItem
from .connection_item import ConnectionItem
from .settings_dialog import SettingsDialog
from .module_selection_panel import ModuleSelectionPanel
from src.pipeline.pipeline_architecture import modules, Pipeline
try:
    import src.pipeline.default_modules
except Exception as e:
    print(f"Warning: default modules failed to load: {e}")

class DropEnabledGraphicsView(QGraphicsView):
    """Custom QGraphicsView that handles drag and drop for modules"""
    def __init__(self, scene, main_window, *args, **kwargs):
        super().__init__(scene, *args, **kwargs)
        self.main_window = main_window
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("module_drag:"):
            event.acceptProposedAction()
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("module_drag:"):
            event.acceptProposedAction()
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("module_drag:"):
            mime_data_text = event.mimeData().text()
            module_class_name = mime_data_text.split(':', 1)[1]

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
                pos = event.position().toPoint()
                if not self.viewport().rect().contains(pos):
                    pos = self.viewport().mapFromGlobal(event.globalPosition().toPoint())
                scene_pos = self.mapToScene(pos)
                event.setDropAction(Qt.DropAction.CopyAction)
                self.main_window._add_module(module_class, scene_pos)
                event.acceptProposedAction()
                event.accept()
            else:
                QMessageBox.critical(self.main_window, "Error", f"Unknown module class: {module_class_name}")
                event.ignore()
        else:
            event.ignore()

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.DragEnter:
            self.dragEnterEvent(event)
            return True
        if event.type() == QEvent.Type.DragMove:
            self.dragMoveEvent(event)
            return True
        if event.type() == QEvent.Type.Drop:
            self.dropEvent(event)
            return True
        return super().viewportEvent(event)

class MainWindow(QMainWindow):
    _dock_minimized_width = 24
    _dock_expanded_width = 180
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
        self.view = DropEnabledGraphicsView(self.scene, self)
        self.setCentralWidget(self.view)

        # Enable mouse events for connection drawing on the view
        self.view.setMouseTracking(True)
        self.view.mousePressEvent = self._view_mouse_press_event
        self.view.mouseMoveEvent = self._view_mouse_move_event
        self.view.mouseReleaseEvent = self._view_mouse_release_event

    def _create_status_bar(self):
        self.statusBar().showMessage("Ready")

    def _create_module_panel(self):
        self.module_panel = ModuleSelectionPanel(self._on_panel_layout_changed)
        dock_widget = QDockWidget("Modules", self)
        dock_widget.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        dock_widget.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        dock_widget.setWidget(self.module_panel)
        self._module_dock = dock_widget

        title_bar = QWidget(self)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(5, 0, 5, 0)
        title_layout.setSpacing(4)

        title_label = QLabel("Modules", title_bar)
        title_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        self._module_panel_toggle = QToolButton(title_bar)
        self._module_panel_toggle.setText("▾")
        self._module_panel_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._module_panel_toggle.clicked.connect(self._toggle_module_panel)
        title_layout.addWidget(self._module_panel_toggle)

        self._module_panel_float = QToolButton(title_bar)
        self._module_panel_float.setText("⇱")
        self._module_panel_float.setCursor(Qt.CursorShape.PointingHandCursor)
        self._module_panel_float.clicked.connect(lambda: dock_widget.setFloating(not dock_widget.isFloating()))
        title_layout.addWidget(self._module_panel_float)

        dock_widget.setTitleBarWidget(title_bar)
        dock_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_widget)
        self._normal_title_bar = title_bar

        self._collapsed_title_bar = QWidget()
        self._collapsed_title_bar.setFixedSize(self._dock_minimized_width, 12)
        self._collapsed_title_bar.setStyleSheet("""
            background: #DDDDDD;
            border: none;
        """)
        self._module_panel_collapsed_width = self._dock_minimized_width
        self._module_panel_expanded_width = self._dock_expanded_width
        self._module_panel_minimized = False
        self._module_dock.setCursor(Qt.CursorShape.ArrowCursor)
        dock_widget.topLevelChanged.connect(self._on_dock_float_changed)
        dock_widget.installEventFilter(self)
        QTimer.singleShot(0, self._initialize_module_dock)
    
    def get_natural_width(self):
        return max(
            self._module_panel_expanded_width,
            self.module_panel.sizeHint().width() + 20
        )
    
    def _initialize_module_dock(self):
        natural_width = self.get_natural_width()

        self.resizeDocks(
            [self._module_dock],
            [natural_width],
            Qt.Orientation.Horizontal
        )

    def _on_dock_float_changed(self, floating):
        if not floating and not self._module_panel_minimized:
            # When redocking, ensure dock is visible and recalculate width after repositioning
            self._module_dock.show()
            self.module_panel.show()
            # Defer longer to let QMainWindow finish repositioning the dock
            #QTimer.singleShot(200, self._force_dock_width)
        if not floating:
            QTimer.singleShot(0, self._refresh_dock_layout)
    
    def _refresh_dock_layout(self):
        self._module_dock.updateGeometry()
        self.module_panel.updateGeometry()

        self.layout().activate()

        self._recalculate_dock_width()

    def _force_dock_width(self):
        print("forced")
        """Force dock to proper width after redocking"""
        if self._module_dock.isFloating():
            return  # Don't adjust floating dock
        QTimer.singleShot(50, lambda: self._module_dock.setMaximumWidth(16777215))

    def _toggle_module_panel(self):
        self._set_module_panel_minimized(not self._module_panel_minimized)

    def _on_panel_layout_changed(self):
        if not self._module_panel_minimized:
            self._recalculate_dock_width()

    def _recalculate_dock_width(self):
        if self._module_panel_minimized:
            return

        natural_width = self.get_natural_width()

        self.module_panel.updateGeometry()
        self._module_dock.updateGeometry()

        if self._module_dock.isFloating():
            self._module_dock.resize(
                natural_width,
                self._module_dock.height()
            )
        else:
            # temporarily force desired width
            self._module_dock.setMinimumWidth(natural_width)
            self._module_dock.setMaximumWidth(natural_width)

            # allow dynamic resizing again immediately after layout pass
            QTimer.singleShot(
                0,
                lambda: (
                    self._module_dock.setMinimumWidth(0),
                    self._module_dock.setMaximumWidth(16777215),
                )
            )
            
    def _set_module_panel_minimized(self, minimized: bool):
        self._module_panel_minimized = minimized

        if minimized:
            self.module_panel.toggle_content(False)

            self.module_panel.setMinimumWidth(0)
            self.module_panel.setMaximumWidth(0)

            self._module_dock.setTitleBarWidget(self._collapsed_title_bar)

            # keep minimized dock visible/clickable
            self._module_dock.setMinimumWidth(self._dock_minimized_width)

            self.resizeDocks(
                [self._module_dock],
                [self._dock_minimized_width],
                Qt.Orientation.Horizontal
            )

        else:
            self.module_panel.toggle_content(True)

            self.module_panel.setMinimumWidth(0)
            self.module_panel.setMaximumWidth(16777215)

            self._module_dock.setTitleBarWidget(self._normal_title_bar)

            # clear minimized constraints
            self._module_dock.setMinimumWidth(0)
            self._module_dock.setMaximumWidth(16777215)

            self.module_panel.updateGeometry()
            self._module_dock.updateGeometry()

            QTimer.singleShot(0, self._recalculate_dock_width)

        self.module_panel.updateGeometry()
        self._module_dock.updateGeometry()

    def _add_module(self, module_class, pos):
        # Instantiate the module class passed from the drag event
        try:
            module = ModuleItem(module_class, pos.x(), pos.y())
            module.setBrush(QBrush(QColor(self.settings["default_module_color"])))
            self.scene.addItem(module)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create module: {e}")

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonPress and self._module_panel_minimized:
            if watched == self._module_dock:
                self._toggle_module_panel()
                return True
        return super().eventFilter(watched, event)

    def _run_pipeline(self):
        module_items = [item for item in self.scene.items() if isinstance(item, ModuleItem)]
        if not module_items:
            QMessageBox.warning(self, "Run Pipeline", "Add at least one module before running the pipeline.")
            return

        pipeline = Pipeline()
        added_modules = {}
        remaining = set(module_items)
        error_message = None

        while remaining:
            progress = False
            for module_item in list(remaining):
                config = module_item.current_configuration
                if len(module_item.input_ports) == 0:
                    try:
                        pipeline.add_configuration(config)
                        added_modules[module_item] = config
                        remaining.remove(module_item)
                        progress = True
                    except Exception as e:
                        error_message = f"Pipeline error for '{module_item.module_instance.name}': {e}"
                        remaining.remove(module_item)
                        progress = True
                        break
                    continue

                input_edges = []
                ready = True
                for port in module_item.input_ports:
                    if len(port.connections) != 1:
                        ready = False
                        break

                    connection = port.connections[0]
                    source_port = connection.start_port if not connection.start_port.is_input else connection.end_port
                    if source_port.is_input:
                        ready = False
                        break

                    source_module = source_port.parent_module
                    if source_module not in added_modules:
                        ready = False
                        break

                    input_edges.append((port.index, added_modules[source_module]))

                if ready:
                    try:
                        pipeline.add_configuration(config, *input_edges)
                        added_modules[module_item] = config
                        remaining.remove(module_item)
                        progress = True
                    except Exception as e:
                        error_message = f"Pipeline error for '{module_item.module_instance.name}': {e}"
                        remaining.remove(module_item)
                        progress = True
                        break

            if not progress:
                error_message = error_message or "Could not resolve pipeline graph. There may be missing connections or a cycle."
                break

        if error_message:
            QMessageBox.critical(self, "Pipeline Error", error_message)
            self.statusBar().showMessage("Pipeline failed!")
            return

        try:
            if pipeline.has_cycle():
                raise ValueError("Cycle detected in pipeline connections.")
            if not pipeline.all_inputs_filled():
                raise ValueError("Some module inputs are not connected.")

            QMessageBox.information(self, "Run Pipeline", f"Pipeline '{self.settings['pipeline_name']}' validated successfully!")
            self.statusBar().showMessage("Pipeline ran successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Pipeline Error", str(e))
            self.statusBar().showMessage("Pipeline failed!")

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
                self.current_connection.end_point_temp = self.start_port.connection_scene_pos() # Initialize temporary end point
            else:
                # Allow default drag behavior for modules
                super(QGraphicsView, self.view).mousePressEvent(event)
        else:
            super(QGraphicsView, self.view).mousePressEvent(event)

    def _view_mouse_move_event(self, event):
        if self.current_connection:
            self.current_connection.end_point_temp = self.view.mapToScene(event.pos())
            self.current_connection.update_path() # Use update_path for the new logic
        super(QGraphicsView, self.view).mouseMoveEvent(event)

    def _view_mouse_release_event(self, event):
        if self.current_connection and event.button() == Qt.MouseButton.LeftButton:
            end_item = self.view.itemAt(event.pos())
            
            # Assume connection is invalid by default
            is_valid_connection = False

            if isinstance(end_item, PortItem) and end_item != self.start_port:
                start_port = self.start_port
                end_port = end_item

                if start_port.is_input and not end_port.is_input:
                    # Swap so that output becomes the connection start and input becomes the end.
                    if self.current_connection in start_port.connections:
                        start_port.connections.remove(self.current_connection)
                    self.current_connection.start_port = end_port
                    self.current_connection.start_port.connections.append(self.current_connection)
                    end_port = start_port
                    start_port = self.current_connection.start_port

                if not start_port.is_input and end_port.is_input:
                    if not end_port.connections: # input can accept only one connection
                        self.current_connection.end_port = end_port
                        self.current_connection.update_path()
                        end_port.connections.append(self.current_connection)
                        is_valid_connection = True
                        print(f"Connected {start_port.parent_module.title_item.toPlainText()}'s {start_port.name} to {end_port.parent_module.title_item.toPlainText()}'s {end_port.name}")

            if not is_valid_connection:
                # Remove the connection if it's invalid or dropped on nothing
                if self.current_connection in self.start_port.connections:
                    self.start_port.connections.remove(self.current_connection)
                self.scene.removeItem(self.current_connection)

            self.current_connection = None
            self.start_port = None
        super(QGraphicsView, self.view).mouseReleaseEvent(event)

    def _handle_drag_enter(self, event, original_handler):
        if event.mimeData().hasText() and event.mimeData().text().startswith("module_drag:"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _handle_drag_move(self, event, original_handler):
        if event.mimeData().hasText() and event.mimeData().text().startswith("module_drag:"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _handle_drop(self, event, original_handler):
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
                    scene_pos = self.view.mapToScene(event.position().toPoint())
                    self._add_module(module_class, scene_pos)
                    event.acceptProposedAction()
                else:
                    QMessageBox.critical(self, "Error", f"Unknown module class: {module_class_name}")
                    event.ignore()
            else:
                event.ignore()
        else:
            event.ignore()