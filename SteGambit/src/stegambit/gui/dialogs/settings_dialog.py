from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout,
    QGroupBox, QLabel, QComboBox,
    QCheckBox, QSlider, QDialogButtonBox,
)
from PyQt6.QtCore import Qt
from dataclasses import dataclass


@dataclass
class AppSettings:
    encryption_type: str = "AES-GCM-256"
    kdf: str = "SHA-256 (PBKDF2)"
    logging_level: int = 3
    compute_visual_metrics: bool = False


class SettingsDialog(QDialog):
    """Окно Platform Configuration (кнопка ⚙ Settings)."""

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("[ ⚙ ] Settings — Platform Configuration")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._settings = settings
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # ── Cryptographic Protection (информационный блок) ──────────────────
        crypto_group = QGroupBox("Cryptographic Protection")
        crypto_layout = QGridLayout(crypto_group)
        crypto_layout.setColumnStretch(1, 1)

        crypto_layout.addWidget(QLabel("Encryption Type:"), 0, 0)
        self.combo_enc = QComboBox()
        self.combo_enc.addItems(["AES-GCM-256"])
        self.combo_enc.setEnabled(False)
        self.combo_enc.setToolTip("Only AES-GCM-256 is supported in this version.")
        crypto_layout.addWidget(self.combo_enc, 0, 1)

        crypto_layout.addWidget(QLabel("Key Derivation Function:"), 1, 0)
        self.combo_kdf = QComboBox()
        self.combo_kdf.addItems(["SHA-256 (PBKDF2)"])
        self.combo_kdf.setEnabled(False)
        self.combo_kdf.setToolTip("Only SHA-256 (PBKDF2) is supported in this version.")
        crypto_layout.addWidget(self.combo_kdf, 1, 1)

        root.addWidget(crypto_group)

        # ── Performance & Logs ───────────────────────────────────────────────
        perf_group = QGroupBox("Performance & Logs")
        perf_layout = QGridLayout(perf_group)

        perf_layout.addWidget(QLabel("Logging Level:"), 0, 0)

        lbl_min = QLabel("[Min.]")
        lbl_min.setStyleSheet("color: #888888;")
        perf_layout.addWidget(lbl_min, 0, 1)

        self.slider_log = QSlider(Qt.Orientation.Horizontal)
        self.slider_log.setRange(0, 10)
        self.slider_log.setValue(3)
        self.slider_log.setMaximumWidth(180)
        perf_layout.addWidget(self.slider_log, 0, 2)

        lbl_max = QLabel("[Max.]")
        lbl_max.setStyleSheet("color: #888888;")
        perf_layout.addWidget(lbl_max, 0, 3)

        self.chk_compute_ssim = QCheckBox(
            "Calculate Heavy Visual Metrics (SSIM) — affects performance"
        )
        self.chk_compute_ssim.setChecked(False)
        self.chk_compute_ssim.setToolTip(
            "Включает расчёт психовизуальной метрики SSIM.\n"
            "Добавляет ~1 секунду к операции на больших изображениях.\n"
            "Рекомендуется только для детального отчёта качества."
        )
        perf_layout.addWidget(self.chk_compute_ssim, 1, 0, 1, 4)

        root.addWidget(perf_group)

        # ── OK / Cancel ──────────────────────────────────────────────────────
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_ok)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    def _load_settings(self):
        self.combo_enc.setCurrentText(self._settings.encryption_type)
        self.combo_kdf.setCurrentText(self._settings.kdf)
        self.slider_log.setValue(self._settings.logging_level)
        self.chk_compute_ssim.setChecked(self._settings.compute_visual_metrics)

    def _on_ok(self):
        self._settings.encryption_type = self.combo_enc.currentText()
        self._settings.kdf = self.combo_kdf.currentText()
        self._settings.logging_level = self.slider_log.value()
        self._settings.compute_visual_metrics = self.chk_compute_ssim.isChecked()
        self.accept()

    def get_settings(self) -> AppSettings:
        return self._settings