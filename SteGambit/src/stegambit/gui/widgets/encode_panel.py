from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QProgressBar, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QPalette

from .file_panel import FileSelectionPanel


class EncodePanel(QWidget):
    """Вкладка ENCODE главного окна."""

    request_check = pyqtSignal()
    request_hide = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(10, 10, 10, 10)

        # Файловая панель
        self.file_panel = FileSelectionPanel()
        root.addWidget(self.file_panel)

        # Кнопка Check Compatibility
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_check = QPushButton("● Check Compatibility")
        self.btn_check.setObjectName("btn_check")
        self.btn_check.setMinimumWidth(220)
        self.btn_check.clicked.connect(self.request_check)
        btn_row.addWidget(self.btn_check)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # Блок результатов совместимости
        self.compatibility_box = QTextEdit()
        self.compatibility_box.setReadOnly(True)
        self.compatibility_box.setMaximumHeight(90)
        self.compatibility_box.setPlaceholderText(
            "Format Identity: —\n"
            "Container Capacity: —\n"
            "Payload Size (Encrypted): —\n"
            "Estimation: —"
        )
        self.compatibility_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.compatibility_box)

        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3a3a3a;")
        root.addWidget(sep)

        # Кнопка HIDE DATA
        hide_row = QHBoxLayout()
        hide_row.addStretch()
        self.btn_hide = QPushButton("🔒 HIDE DATA (File-in-File)")
        self.btn_hide.setObjectName("btn_hide")
        self.btn_hide.setMinimumWidth(280)
        self.btn_hide.setEnabled(False)
        self.btn_hide.clicked.connect(self.request_hide)
        hide_row.addWidget(self.btn_hide)
        hide_row.addStretch()
        root.addLayout(hide_row)

        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        # Лейбл текущего действия
        self.label_action = QLabel("")
        self.label_action.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_action.setStyleSheet("color: #888888; font-size: 12px;")
        root.addWidget(self.label_action)

        root.addStretch()


    def set_compatibility_result(self, text: str):
        self.compatibility_box.setPlainText(text)

    def set_hide_enabled(self, enabled: bool):
        self.btn_hide.setEnabled(enabled)

    def set_progress(self, value: int, action: str = ""):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(value)
        self.label_action.setText(f"Current Action: {action}" if action else "")

    def reset_progress(self):
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.label_action.setText("")

    def get_cover_path(self):
        return self.file_panel.get_cover_path()

    def get_payload_path(self):
        return self.file_panel.get_payload_path()