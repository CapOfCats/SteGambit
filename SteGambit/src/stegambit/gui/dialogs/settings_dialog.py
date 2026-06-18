from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QComboBox, QPushButton,
    QCheckBox, QLineEdit, QSlider, QDialogButtonBox,
    QFileDialog
)
from PyQt6.QtCore import Qt
from dataclasses import dataclass


@dataclass
class AppSettings:
    encryption_type: str = "AES-GCM-256"
    kdf: str = "SHA-256 (PBKDF2)"
    spreading_algorithm: str = "LSB (Spatial)"
    enable_analytics: bool = True
    use_default_prng: bool = True
    logging_level: int = 3
    compute_visual_metrics: bool = False


class SettingsDialog(QDialog):
    """Окно Platform Configuration (кнопка ⚙ Settings)."""

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("[ ⚙ ] Settings — Platform Configuration")
        self.setModal(True)
        self.setMinimumWidth(640)
        self._settings = settings
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        top_row = QHBoxLayout()

        # Default Formats
        fmt_group = QGroupBox("Default Formats")
        fmt_layout = QGridLayout(fmt_group)
        fmt_layout.addWidget(QLabel("Image:"), 0, 0)
        fmt_layout.addWidget(QLabel("Audio:"), 0, 1)
        self.chk_png = QCheckBox("PNG")
        self.chk_png.setChecked(True)
        self.chk_jpg = QCheckBox("JPEG")
        self.chk_jpg.setChecked(True)
        self.chk_wav = QCheckBox("WAV")
        self.chk_wav.setChecked(True)
        fmt_layout.addWidget(self.chk_png, 1, 0)
        fmt_layout.addWidget(self.chk_jpg, 2, 0)
        fmt_layout.addWidget(self.chk_wav, 1, 1)
        fmt_layout.addWidget(QLabel("File formats allowed..."), 3, 0, 1, 2)
        top_row.addWidget(fmt_group)

        # Cryptographic Protection
        crypto_group = QGroupBox("Cryptographic Protection")
        crypto_layout = QGridLayout(crypto_group)
        crypto_layout.addWidget(QLabel("Encryption Type:"), 0, 0)
        self.combo_enc = QComboBox()
        self.combo_enc.addItems(["AES-GCM-256"])
        crypto_layout.addWidget(self.combo_enc, 0, 1)
        btn_keys = QPushButton("📁 Manage keys")
        crypto_layout.addWidget(btn_keys, 0, 2)
        crypto_layout.addWidget(QLabel("Key Derivation Function:"), 1, 0)
        self.combo_kdf = QComboBox()
        self.combo_kdf.addItems(["SHA-256 (PBKDF2)"])
        crypto_layout.addWidget(self.combo_kdf, 1, 1)
        crypto_layout.addWidget(QLabel("Password Seed (for coordinates):"), 2, 0)
        self.edit_seed = QLineEdit()
        crypto_layout.addWidget(self.edit_seed, 2, 1, 1, 2)
        top_row.addWidget(crypto_group)

        root.addLayout(top_row)

        # Obfuscation & Spreading
        spread_group = QGroupBox("Obfuscation & Spreading")
        spread_layout = QGridLayout(spread_group)
        self.chk_default_prng = QCheckBox("Default PRNG (numpy)")
        self.chk_default_prng.setChecked(True)
        self.chk_custom_prng = QCheckBox("Customized")
        spread_layout.addWidget(self.chk_default_prng, 0, 0)
        spread_layout.addWidget(self.chk_custom_prng, 1, 0)
        spread_layout.addWidget(QLabel("Spreading Algorithm:"), 0, 1)
        self.combo_spread = QComboBox()
        self.combo_spread.addItems(["LSB (Spatial)", "DCT (Frequency)"])
        spread_layout.addWidget(self.combo_spread, 0, 2)
        spread_layout.addWidget(QLabel("Coords Storage:"), 1, 1)
        self.edit_coords = QLineEdit()
        self.edit_coords.setPlaceholderText("D:\\StegoProject\\coord_data\\coords.bin")
        spread_layout.addWidget(self.edit_coords, 1, 2)
        btn_load = QPushButton("📋 Load Seed")
        spread_layout.addWidget(btn_load, 1, 3)
        root.addWidget(spread_group)

        # Performance & Logs
        perf_group = QGroupBox("Performance & Logs")
        perf_layout = QGridLayout(perf_group)
        self.chk_analytics = QCheckBox("Enable Analytics (metrics)")
        self.chk_analytics.setChecked(True)
        perf_layout.addWidget(self.chk_analytics, 0, 0)
        perf_layout.addWidget(QLabel("Logging Level:"), 0, 1)
        lbl_min = QLabel("[Min.]")
        lbl_min.setStyleSheet("color: #888888;")
        perf_layout.addWidget(lbl_min, 0, 2)
        self.slider_log = QSlider(Qt.Orientation.Horizontal)
        self.slider_log.setRange(0, 10)
        self.slider_log.setValue(3)
        self.slider_log.setMaximumWidth(180)
        perf_layout.addWidget(self.slider_log, 0, 3)
        self.chk_compute_ssim = QCheckBox(
            "Calculate Heavy Visual Metrics (SSIM) — affects performance"
        )
        self.chk_compute_ssim.setChecked(False)
        self.chk_compute_ssim.setToolTip(
            "Включает расчёт психовизуальной метрики SSIM.\n"
            "Добавляет ~1 секунду к операции на больших изображениях.\n"
            "Рекомендуется только для детального отчёта качества."
        )
        perf_layout.addWidget(self.chk_compute_ssim, 1, 0, 1, 5)
        lbl_max = QLabel("[Max.]")
        lbl_max.setStyleSheet("color: #888888;")
        perf_layout.addWidget(lbl_max, 0, 4)
        root.addWidget(perf_group)

        # OK / Cancel
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
        self.combo_spread.setCurrentText(self._settings.spreading_algorithm)
        self.chk_analytics.setChecked(self._settings.enable_analytics)
        self.chk_default_prng.setChecked(self._settings.use_default_prng)
        self.slider_log.setValue(self._settings.logging_level)
        self.chk_compute_ssim.setChecked(self._settings.compute_visual_metrics)

    def _on_ok(self):
        self._settings.encryption_type = self.combo_enc.currentText()
        self._settings.compute_visual_metrics = self.chk_compute_ssim.isChecked()
        self._settings.kdf = self.combo_kdf.currentText()
        self._settings.spreading_algorithm = self.combo_spread.currentText()
        self._settings.enable_analytics = self.chk_analytics.isChecked()
        self._settings.use_default_prng = self.chk_default_prng.isChecked()
        self._settings.logging_level = self.slider_log.value()
        self.accept()

    def get_settings(self) -> AppSettings:
        return self._settings