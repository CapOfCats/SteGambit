from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QLabel, QLineEdit,
    QPushButton, QGridLayout, QFileDialog
)
from PyQt6.QtCore import pyqtSignal
from pathlib import Path


class FileSelectionPanel(QWidget):
    """Панель выбора файлов для вкладки ENCODE."""

    cover_changed = pyqtSignal(Path)
    payload_changed = pyqtSignal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        group = QGroupBox("File Selection")
        layout = QGridLayout(group)
        layout.setColumnStretch(1, 1)

        # Материнский файл
        layout.addWidget(QLabel("Cover File (Image/Audio):"), 0, 0)
        self.edit_cover = QLineEdit()
        self.edit_cover.setPlaceholderText("Select container file...")
        layout.addWidget(self.edit_cover, 0, 1)
        btn_cover = QPushButton("📁 Browse")
        btn_cover.clicked.connect(self._browse_cover)
        layout.addWidget(btn_cover, 0, 2)

        # Файл для сокрытия
        layout.addWidget(QLabel("Payload File (Data to Hide):"), 1, 0)
        self.edit_payload = QLineEdit()
        self.edit_payload.setPlaceholderText("Select file to hide...")
        layout.addWidget(self.edit_payload, 1, 1)
        btn_payload = QPushButton("📁 Browse")
        btn_payload.clicked.connect(self._browse_payload)
        layout.addWidget(btn_payload, 1, 2)

        outer = QGridLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(group)

    def _browse_cover(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Cover File", "",
            "Media files (*.png *.jpg *.jpeg *.wav);;All files (*)"
        )
        if path:
            self.edit_cover.setText(path)
            self.cover_changed.emit(Path(path))

    def _browse_payload(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Payload File", "",
            "All files (*)"
        )
        if path:
            self.edit_payload.setText(path)
            self.payload_changed.emit(Path(path))

    def get_cover_path(self) -> Path | None:
        t = self.edit_cover.text().strip()
        return Path(t) if t else None

    def get_payload_path(self) -> Path | None:
        t = self.edit_payload.text().strip()
        return Path(t) if t else None