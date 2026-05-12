import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QTabWidget, QPushButton, QStatusBar,
    QHBoxLayout, QLabel
)
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from stegambit.models.dto import StegoTaskRequest
from stegambit.services.async_worker import StegoWorker
from stegambit.services.stego_service import StegoService
from .widgets.encode_panel import EncodePanel
from .widgets.decode_panel import DecodePanel
from .widgets.metrics_panel import MetricsPanel
from .dialogs.encode_dialog import EncodeDialog, EncodeDialogResult
from .dialogs.settings_dialog import SettingsDialog, AppSettings


class MainWindow(QMainWindow):
    """
    Главное окно SteGambit.
    Содержит: TabWidget (ENCODE/DECODE), MetricsPanel (collapsed/expanded), StatusBar, кнопку Settings.
    Не содержит бизнес-логики, UI+ делегация в контроллер (TODO #17).
    """

    def __init__(self):
        super().__init__()
        self._settings = AppSettings()
        self._service = StegoService()
        self._setup_window()
        self._build_ui()
        self._connect_signals()
        self._set_status("Idle")


    def _setup_window(self):
        self.setWindowTitle("[ 🔒 ] SteGambit — Multi-format Steganography Tool")
        self.setMinimumSize(760, 520)
        self.resize(860, 580)


    def _build_ui(self):
        # Центральный виджет
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Шапка с кнопкой Settings
        header = self._build_header()
        layout.addWidget(header)

        # Tab: ENCODE / DECODE
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)

        self.encode_panel = EncodePanel()
        self.decode_panel = DecodePanel()

        self.tabs.addTab(self.encode_panel, "[ ENCODE ]")
        self.tabs.addTab(self.decode_panel, "[ DECODE ]")
        layout.addWidget(self.tabs, stretch=1)

        # MetricsPanel (скрыта до завершения операции)
        self.metrics_panel = MetricsPanel()
        layout.addWidget(self.metrics_panel)

        # StatusBar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _build_header(self) -> QWidget:
        """Верхняя полоска с кнопкой Settings (имитирует titlebar из макета)."""
        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet(
            "background-color: #161616; border-bottom: 1px solid #3a3a3a;"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 0, 10, 0)

        lbl_title = QLabel("[ 🔒 ] SteGambit")
        lbl_title.setStyleSheet("color: #888888; font-size: 12px;")
        h_layout.addWidget(lbl_title)

        h_layout.addStretch()

        self.btn_settings = QPushButton("⚙ Settings")
        self.btn_settings.setStyleSheet(
            "border: none; color: #aaaaaa; background: transparent;"
            "font-size: 13px; padding: 2px 8px;"
        )
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        h_layout.addWidget(self.btn_settings)

        return header

    def _connect_signals(self):
        self.btn_settings.clicked.connect(self._open_settings)
        self.encode_panel.request_check.connect(self._on_check_compatibility)
        self.encode_panel.request_hide.connect(self._on_hide_requested)
        self.decode_panel.request_extract.connect(self._on_extract_requested)

    def _open_settings(self):
        dlg = SettingsDialog(self._settings, parent=self)
        if dlg.exec():
            self._settings = dlg.get_settings()
            self._set_status("Settings saved.")

    def _on_check_compatibility(self):
        cover = self.encode_panel.get_cover_path()
        payload = self.encode_panel.get_payload_path()

        if not cover or not payload:
            self._set_status("Select both files first.")
            return

        self._set_status("Checking compatibility...")

        try:
            fmt = self._service.identify_format(cover)
            algo = self._service.get_algorithm_for_format(fmt)

            cover_mb = cover.stat().st_size / (1024 * 1024)
            payload_kb = payload.stat().st_size / 1024

            with open(cover, "rb") as f:
                magic_raw = f.read(8).hex(" ").upper()

            self.encode_panel.set_compatibility_result(
                f"Format Identity: {fmt}  (Magic: {magic_raw})\n"
                f"Algorithm Selected: {algo}\n"
                f"Container Size: {cover_mb:.2f} MB\n"
                f"Payload Size: {payload_kb:.1f} KB\n"
                f"Estimation: [Capacity check — TODO #17]"
            )
            self.encode_panel.set_hide_enabled(True)
            self._set_status(f"Compatibility check passed. Format: {fmt} → {algo}. Ready to hide.")

        except ValueError as e:
            self.encode_panel.set_compatibility_result(
                f"⚠ Format not supported:\n{e}\n\nSupported: PNG, WAV, JPEG"
            )
            self.encode_panel.set_hide_enabled(False)
            self._set_status(f"Compatibility check failed: {e}")

        except FileNotFoundError:
            self.encode_panel.set_compatibility_result("⚠ File not found. Check the path.")
            self.encode_panel.set_hide_enabled(False)
            self._set_status("File not found.")

        except Exception as e:
            self.encode_panel.set_compatibility_result(
                f"⚠ Unexpected error:\n{type(e).__name__}: {e}"
            )
            self.encode_panel.set_hide_enabled(False)
            self._set_status(f"Error: {type(e).__name__}")

    def _on_hide_requested(self):
        """Открывает EncodeDialog для ввода пароля и пути."""
        cover = self.encode_panel.get_cover_path()
        if not cover:
            self._set_status("Cover не выбран.")
            return
        try:
            fmt = self._service.identify_format(cover)
        except Exception:
            fmt = "?"

        dlg = EncodeDialog(parent=self)
        dlg.set_step1_valid(True, format_id=fmt)
        dlg.confirmed.connect(self._on_encode_confirmed)
        dlg.exec()


    def _on_encode_confirmed(self, result: EncodeDialogResult):
        """Запуск Encode через StegoWorker."""
        cover = self.encode_panel.get_cover_path()
        payload = self.encode_panel.get_payload_path()

        if not cover or not payload:
            self._set_status("Cover/Payload не выбраны.")
            return

        self._set_status(f"Processing... | Output: {result.output_path.name}")
        self.encode_panel.set_progress(50, "Spreading bits...")

        request = StegoTaskRequest(
            carrier_path=cover,
            payload_path=payload,
            output_path=result.output_path,
            password=result.password,
        )

        # Хранится в self, чтобы воркер не был собран сборщиком мусора
        # до доставки сигналов (важно при будущей миграции на QThread).
        self._worker = StegoWorker(request, mode="encode")
        self._worker.finished.connect(self._on_encode_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()
    

    def _on_encode_finished(self, response):
        """Обработчик результата Encode."""
        if response.success:
            self.encode_panel.set_progress(100, "Done.")
            metrics_text = ""
            if response.metrics:
                psnr = response.metrics.get("psnr")
                t = response.metrics.get("time")
                if psnr is not None:
                    metrics_text += f"PSNR: {psnr:.1f} dB  "
                if t is not None:
                    metrics_text += f"Time: {t:.2f}s"
            self._set_status(f"Готово. {metrics_text}")
        else:
            self.encode_panel.reset_progress()
            self._set_status(f"Ошибка: {response.error}")

    def _on_extract_requested(self):
        """Запуск Decode через StegoWorker."""
        stego = self.decode_panel.get_stego_path()
        output_dir = self.decode_panel.get_output_dir()
        password = self.decode_panel.get_password()

        if not stego:
            self._set_status("Stego-файл не выбран.")
            return
        if not output_dir:
            self._set_status("Папка для сохранения не выбрана.")
            return
        if not password:
            self._set_status("Введите пароль.")
            return

        output_path = Path(output_dir) / f"extracted_{stego.stem}.bin"
        self._set_status("Extracting...")

        request = StegoTaskRequest(
            carrier_path=stego,
            payload_path=stego,
            output_path=output_path,
            password=password,
        )

        self._worker = StegoWorker(request, mode="decode")
        self._worker.finished.connect(self._on_decode_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    def _on_decode_finished(self, response):
        """Обработчик результата Decode."""
        if response.success:
            t = response.metrics.get("time", 0) if response.metrics else 0
            size = response.metrics.get("extracted_bytes", 0) if response.metrics else 0
            self.decode_panel.set_log(
                f"Извлечение успешно!\n"
                f"Saved to: {response.output_path}\n"
                f"Size: {size} bytes\n"
                f"Time: {t:.2f}s\n"
                f"Data Integrity: !!! Valid (AES-GCM tag verified)"
            )
            self._set_status(f"Извлечено в {response.output_path.name}")
        else:
            self.decode_panel.set_log(f"Ошибка: {response.error}")
            self._set_status(f"Ошибка: {response.error}")
    
    
    def _on_worker_error(self, message: str):
        """Обработчик неожиданных ошибок воркера."""
        self.encode_panel.reset_progress()
        self._set_status(f"Critical: {message}")


    def _set_status(self, message: str):
        self.status_bar.showMessage(
            f"System Status: {message}  |  Version AlphaCentavra"
        )


    def show_metrics(self, data):
        """Планируется для AsyncWorker по завершении операции."""
        self.metrics_panel.show_results(data)
        self._set_status(
            f"Processing complete. | Time Elapsed: {data.time_sec:.2f}s | Version AlphaCentavra"
        )