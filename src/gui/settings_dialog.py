from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QColorDialog
from PyQt6.QtGui import QColor

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setGeometry(200, 200, 400, 300)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Example setting: Pipeline Name
        self.layout.addWidget(QLabel("Pipeline Name:"))
        self.pipeline_name_input = QLineEdit("My Pipeline")
        self.layout.addWidget(self.pipeline_name_input)

        # Example setting: Default Module Color
        self.layout.addWidget(QLabel("Default Module Color:"))
        self.default_module_color_label = QLabel("#ADD8E6") # Light Blue
        self.layout.addWidget(self.default_module_color_label)
        self.change_color_button = QPushButton("Change Color")
        self.change_color_button.clicked.connect(self._change_default_module_color)
        self.layout.addWidget(self.change_color_button)

        # Save and Cancel buttons
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.accept)
        self.layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.layout.addWidget(self.cancel_button)

    def _change_default_module_color(self):
        color = QColorDialog.getColor(QColor(self.default_module_color_label.text()), self)
        if color.isValid():
            self.default_module_color_label.setText(color.name())

    def get_settings(self):
        return {
            "pipeline_name": self.pipeline_name_input.text(),
            "default_module_color": self.default_module_color_label.text()
        }

    def set_settings(self, settings):
        self.pipeline_name_input.setText(settings.get("pipeline_name", "My Pipeline"))
        self.default_module_color_label.setText(settings.get("default_module_color", "#ADD8E6"))
