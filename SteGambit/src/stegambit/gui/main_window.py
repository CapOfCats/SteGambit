import sys
from PyQt6.QtWidgets import (
    QMainWindow, QMessageBox, QWidget, QVBoxLayout,
    QTabWidget, QPushButton, QStatusBar,
    QHBoxLayout, QLabel
)
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon

from stegambit.models.dto import StegoTaskRequest
from stegambit.services.async_worker import StegoWorker
from stegambit.services.stego_service import StegoService
from stegambit.models.dto import (
    StegoTaskRequest, StegoResponse, CapacityReport, QualityStatus
)
from stegambit.services.stego_service import CompatibilityError
from .widgets.metrics_panel import MetricsData
from .widgets.encode_panel import EncodePanel
from .widgets.decode_panel import DecodePanel
from .widgets.metrics_panel import MetricsPanel
from .dialogs.encode_dialog import EncodeDialog, EncodeDialogResult
from .dialogs.settings_dialog import SettingsDialog, AppSettings

_CAPACITY_ERROR_MARKERS = (
        "Недостаточно ёмкости",
        "Требуется:",
        "Доступно:",
    )

class MainWindow(QMainWindow):
    """
    Главное окно SteGambit.
    Содержит: TabWidget ENCODE/DECODE, MetricsPanel collapsed/expanded, StatusBar, кнопку Settings.
    """
    _CAPACITY_ERROR_MARKERS = (
        "Недостаточно ёмкости",
        "ёмкости носителя",
        "TOO LARGE",
    )
    def __init__(self):
        super().__init__()
        self._settings = AppSettings()
        self._service = StegoService()
        self._worker: StegoWorker | None = None
        self._progress_timer: QTimer | None = None
        self._progress_value: int = 0
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
        """Проверка совместимости через StegoService.analyze_capacity()."""
        cover = self.encode_panel.get_cover_path()
        payload = self.encode_panel.get_payload_path()

        if not cover or not payload:
            self._set_status("Select both files first.")
            return

        self._set_status("Checking compatibility...")

        request = StegoTaskRequest(
            carrier_path=cover,
            payload_path=payload,
            output_path=cover,
            password="",  
        )

        try:
            report: CapacityReport = self._service.analyze_capacity(request)
        except CompatibilityError as e:
            self.encode_panel.set_compatibility_result(f"⚠ Format not supported:\n{e}")
            self.encode_panel.set_hide_enabled(False)
            self._set_status(f"Compatibility check failed: {e}")
            return
        except FileNotFoundError:
            self.encode_panel.set_compatibility_result("⚠ File not found. Check the path.")
            self.encode_panel.set_hide_enabled(False)
            self._set_status("File not found.")
            return
        except Exception as e:
            self.encode_panel.set_compatibility_result(
                f"⚠ Unexpected error:\n{type(e).__name__}: {e}"
            )
            self.encode_panel.set_hide_enabled(False)
            self._set_status(f"Error: {type(e).__name__}")
            return

        status_line = (
            "FITS — ready to hide" if report.fits
            else "TOO LARGE — choose bigger carrier or smaller payload"
        )
        text = (
            f"Format: {report.format}  |  Algorithm: {report.algorithm}\n"
            f"Container capacity: {report.capacity_bits:,} bits\n"
            f"Required for payload: {report.required_bits:,} bits "
            f"({report.utilization_percent:.1f}%)\n"
            f"Payload size: {report.payload_size_bytes:,} bytes  |  "
            f"Crypto overhead: {report.header_size_bytes} bytes\n"
            f"Status: {status_line}"
        )
        self.encode_panel.set_compatibility_result(text)
        self.encode_panel.set_hide_enabled(report.fits)

        if report.fits:
            self._set_status(
                f"Compatibility check passed. "
                f"Format: {report.format} → {report.algorithm}. "
                f"Utilization: {report.utilization_percent:.1f}%. Ready to hide."
            )
        else:
            self._set_status(
                f"Capacity insufficient: need {report.required_bits:,} bits, "
                f"available {report.capacity_bits:,}."
            )

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

    def _start_fake_progress(self, label: str = "Processing..."):
        self._progress_value = 0
        self.encode_panel.set_progress(0, label)
        if self._progress_timer is not None:
            self._progress_timer.stop()
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._tick_progress)
        self._progress_timer.start(80)

    def _tick_progress(self):
        if self._progress_value < 90:
            step = max(1, (90 - self._progress_value) // 12)
            self._progress_value = min(90, self._progress_value + step)
            label = "Encrypting..." if self._progress_value > 60 else "Spreading bits..."
            self.encode_panel.set_progress(self._progress_value, label)

    def _stop_fake_progress(self):
        if self._progress_timer is not None:
            self._progress_timer.stop()
            self._progress_timer = None

    def _on_encode_confirmed(self, result: EncodeDialogResult):
        """Запуск Encode через StegoWorker."""
        if self._is_worker_running():
            self._set_status("Операция уже выполняется. Подождите...")
            return
        cover = self.encode_panel.get_cover_path()
        payload = self.encode_panel.get_payload_path()

        if not cover or not payload:
            self._set_status("Cover/Payload не выбраны.")
            return

        self._set_status(f"Processing... | Output: {result.output_path.name}")
        self._start_fake_progress("Encrypting payload...")

        request = StegoTaskRequest(
            carrier_path=cover,
            payload_path=payload,
            output_path=result.output_path,
            password=result.password,
        )

        self._worker = self._create_worker(request, mode="encode")
        self._worker.finished.connect(self._on_encode_finished)
        self._worker.error.connect(self._on_worker_error)
        self._set_controls_enabled(False)
        self._worker.start()
    
    def _apply_status_color(self, status: QualityStatus):
        """Окрашивает статус-бар по QualityStatus.

        OK      → зелёный фон
        WARNING → жёлтый фон
        ANOMALY → красный фон
        """
        color_map = {
            QualityStatus.OK:      "background-color: #1a2a1a; color: #4aaa4a;",
            QualityStatus.WARNING: "background-color: #2a2a1a; color: #aaaa4a;",
            QualityStatus.ANOMALY: "background-color: #2a1a1a; color: #aa4a4a;",
        }
        style = color_map.get(status, "")
        self.status_bar.setStyleSheet(style)


    def _on_encode_finished(self, response):
        """Обработчик результата Encode.

        MetricsData собирается здесь и передаётся в MetricsPanel.
        """
        self._stop_fake_progress()
        self._set_controls_enabled(True)
        if not response.success:
            self.encode_panel.reset_progress()
            if self._is_capacity_error(response.error):
                self._show_capacity_error_dialog(response.error or "")
                self._set_status("Not enough capacity — see dialog.")
            else:
                self._set_status(f"Ошибка: {response.error}")
            return

        self.encode_panel.set_progress(100, "Done.")
        metrics = response.metrics or {}

        psnr = metrics.get("psnr")  
        ssim = metrics.get("ssim")            
        time_sec = metrics.get("time", 0.0)
        size_deviation = metrics.get("size_deviation", 0.0)
        quality_status = metrics.get("quality_status", QualityStatus.OK)

        if isinstance(quality_status, str):
            quality_status = QualityStatus(quality_status)

        cover   = self.encode_panel.get_cover_path()
        output  = response.output_path

        carrier_mb = cover.stat().st_size / (1024 * 1024) if cover else 0.0
        result_mb  = output.stat().st_size / (1024 * 1024) if output and output.exists() else 0.0

        data = MetricsData(
            psnr=psnr,
            ssim=ssim,
            time_sec=time_sec,
            size_deviation_pct=size_deviation,
            quality_status=quality_status,
            algorithm=metrics.get("algorithm", "—"),
            carrier_size_mb=carrier_mb,
            result_size_mb=result_mb,
            original_path=cover,
            result_path=output,
            success=True,
            format_id=metrics.get("format_id", "—"),
            integrity_ok=True,
        )

        self.metrics_panel.show_results(data)

        self._apply_status_color(quality_status)

        parts = [f"Time: {time_sec:.2f}s"]
        if psnr is not None:
            parts.append(f"PSNR: {psnr:.1f} dB")
        if ssim is not None:
            parts.append(f"SSIM: {ssim:.4f}")
        parts.append(f"Size Δ: {size_deviation:+.1f}%")
        self._set_status(f"Done. {' | '.join(parts)}")

    def _on_extract_requested(self):
        """Запуск Decode через StegoWorker."""
        if self._is_worker_running():
            self._set_status("Операция уже выполняется. Подождите...")
            return
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

        self._worker = self._create_worker(request, mode="decode")
        self._worker.finished.connect(self._on_decode_finished)
        self._worker.error.connect(self._on_worker_error)
        self._set_controls_enabled(False)
        self._worker.start()

    def _on_decode_finished(self, response):
        self._set_controls_enabled(True)
        if response.success:
            metrics = response.metrics or {}
            t = metrics.get("time", 0)
            size = metrics.get("extracted_bytes", 0)
            fmt = metrics.get("detected_format", "UNKNOWN")
            self.decode_panel.set_log(
                f"Extraction successful!\n"
                f"Saved to: {response.output_path}\n"
                f"Detected format: {fmt}\n"
                f"Note: extension auto-detected from payload magic bytes.\n"
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
        self._set_controls_enabled(True)
        QMessageBox.critical(
            self,
            "SteGambit - внутренняя ошибка",
            f"Неожиданная ошибка ядра:\n\n{message}\n\nПожалуйста, сообщите разработчику",
        )
        self._set_status(f"Critical error — see dialog")

    def _is_worker_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _create_worker(self, request: StegoTaskRequest, mode: str) -> StegoWorker:
        worker = StegoWorker(request, mode=mode)
        worker.finished.connect(worker.deleteLater)
        return worker

    def _set_controls_enabled(self, enabled: bool):
        self.encode_panel.btn_check.setEnabled(enabled)
        self.encode_panel.btn_hide.setEnabled(enabled)
        self.decode_panel.btn_extract.setEnabled(enabled)

    def _is_capacity_error(self, message: str) -> bool:
        """Определяет, является ли сообщение ошибкой нехватки ёмкости."""
        return any(marker in message for marker in self._CAPACITY_ERROR_MARKERS)
    

    def _show_capacity_error_dialog(self, message: str):
        """Показывает попап с деталями ошибки ёмкости и советом."""
        dlg = QMessageBox(self)
        dlg.setWindowTitle("SteGambit — Capacity Error")
        dlg.setIcon(QMessageBox.Icon.Warning)

        dlg.setText(
            "Контейнеру не достаёт емкости для сокрытия выбранного файла."
        )
        dlg.setInformativeText(
            "В контейнере не хватает достаточного кол-ва 'шумных' пикселей "
            "для граничного распределения (порога незаметности).\n\n"
            "Что делать?:\n"
            "  • Другой 'носитель', желательно - потяжелее\n"
            "  • Уменьшить скрываемую нагрузку \n"
        )

        dlg.setDetailedText(message)

        dlg.setStandardButtons(QMessageBox.StandardButton.Ok)
        dlg.setDefaultButton(QMessageBox.StandardButton.Ok)

        dlg.setStyleSheet("""
            QMessageBox {
                background-color: #1e1e1e;
                color: #d4d4d4;
            }
            QMessageBox QLabel {
                color: #d4d4d4;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: #d4d4d4;
                border: 1px solid #4a4a4a;
                padding: 4px 16px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border-color: #6a6a6a;
            }
            QTextEdit {
                background-color: #141414;
                color: #888888;
                border: 1px solid #3a3a3a;
            }
        """)

        dlg.exec()


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