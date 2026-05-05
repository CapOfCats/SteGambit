from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton,
    QCheckBox, QTextEdit, QFileDialog
)
from PyQt6.QtCore import pyqtSignal, Qt
from pathlib import Path


class DecodePanel(QWidget):
    """Вкладка DECODE главного окна."""

    request_extract = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(10, 10, 10, 10)

        # Группа File to Extract
        group = QGroupBox("File to Extract Data From:")
        grid = QGridLayout(group)
        grid.setColumnStretch(1, 1)

        # Stego-файл
        grid.addWidget(QLabel("File to Extract Data From:"), 0, 0)
        self.edit_stego = QLineEdit()
        self.edit_stego.setPlaceholderText("Select stego file...")
        grid.addWidget(self.edit_stego, 0, 1)
        btn_stego = QPushButton("📁 Browse")
        btn_stego.clicked.connect(self._browse_stego)
        grid.addWidget(btn_stego, 0, 2)

        # Пароль
        grid.addWidget(QLabel("Enter Decryption Password:"), 1, 0)
        pass_row = QHBoxLayout()
        self.edit_password = QLineEdit()
        self.edit_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_password.setPlaceholderText("[********]")
        pass_row.addWidget(self.edit_password)
        self.chk_use_coords = QCheckBox("Use Password-derived Coordinates")
        self.chk_use_coords.setChecked(True)
        pass_row.addWidget(self.chk_use_coords)
        grid.addLayout(pass_row, 1, 1, 1, 2)

        # Папка сохранения
        grid.addWidget(QLabel("Save Extracted Payload To:"), 2, 0)
        self.edit_output = QLineEdit()
        self.edit_output.setPlaceholderText("Select output directory...")
        grid.addWidget(self.edit_output, 2, 1)
        btn_output = QPushButton("📁 Browse")
        btn_output.clicked.connect(self._browse_output)
        grid.addWidget(btn_output, 2, 2)

        root.addWidget(group)

        # Кнопка Extract
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_extract = QPushButton("🔓 EXTRACT & RECOVER DATA")
        self.btn_extract.setObjectName("btn_extract")
        self.btn_extract.setMinimumWidth(280)
        self.btn_extract.clicked.connect(self.request_extract)
        btn_row.addWidget(self.btn_extract)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # Лог метрик
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText(
            "Processing Metrics:\n"
            "'Decrypted DTO Format: Magic identified correctly.\n"
            "'Recovered Format: %FormatID%'\n"
            "'Data Integrity [✅ Valid CRC]\n"
            "'Extraction Time: %Time% sec.'"
        )
        root.addWidget(self.log_box)

    # ── Браузеры ──────────────────────────────────────────────────────────

    def _browse_stego(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Stego File", "",
            "Media files (*.png *.jpg *.jpeg *.wav);;All files (*)"
        )
        if path:
            self.edit_stego.setText(path)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self.edit_output.setText(path)

    # ── Публичное API ─────────────────────────────────────────────────────

    def set_log(self, text: str):
        self.log_box.setPlainText(text)

    def get_stego_path(self) -> Path | None:
        t = self.edit_stego.text().strip()
        return Path(t) if t else None

    def get_password(self) -> str:
        return self.edit_password.text()

    def get_output_dir(self) -> Path | None:
        t = self.edit_output.text().strip()
        return Path(t) if t else None

    def use_password_coords(self) -> bool:
        return self.chk_use_coords.isChecked()