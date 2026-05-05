from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QGridLayout, QFrame,
    QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class MetricsData:
    psnr: float
    time_sec: float
    size_deviation_pct: float
    algorithm: str
    carrier_size_mb: float
    result_size_mb: float
    original_path: Optional[Path] = None
    result_path: Optional[Path] = None
    success: bool = True
    format_id: str = "—"
    integrity_ok: bool = True


class MetricsPanel(QWidget):
    """
    Панель метрик — collapsed / expanded.

    Collapsed: одна строка с ключевыми показателями + кнопка [▼ Expand].
    Expanded : полное окно с превью до/после и детальными метриками.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._data: Optional[MetricsData] = None
        self._build_ui()
        self.setVisible(False)


    def _build_ui(self):
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)

        # Collapsed bar
        self._bar = self._build_collapsed_bar()
        self._root.addWidget(self._bar)

        # Expanded area
        self._expanded_widget = self._build_expanded_area()
        self._expanded_widget.setVisible(False)
        self._root.addWidget(self._expanded_widget)

    def _build_collapsed_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(
            "background-color: #1a2a1a; border-top: 1px solid #3a5a3a;"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 6, 10, 6)

        self.lbl_status = QLabel("[ !!! Operation Complete ]")
        self.lbl_status.setStyleSheet("color: #4aaa4a; font-weight: bold;")
        layout.addWidget(self.lbl_status)

        layout.addSpacing(20)

        self.lbl_psnr = QLabel("PSNR: — dB")
        layout.addWidget(self.lbl_psnr)

        layout.addSpacing(12)
        self.lbl_time = QLabel("Time: —")
        layout.addWidget(self.lbl_time)

        layout.addSpacing(12)
        self.lbl_size = QLabel("Size: —")
        layout.addWidget(self.lbl_size)

        layout.addStretch()

        self.btn_toggle = QPushButton("[ ▼ Expand ]")
        self.btn_toggle.setStyleSheet(
            "border: 1px solid #4a4a4a; padding: 2px 10px;"
            "background: #2a2a2a; color: #d4d4d4;"
        )
        self.btn_toggle.clicked.connect(self._toggle_expand)
        layout.addWidget(self.btn_toggle)

        return bar

    def _build_expanded_area(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet(
            "background-color: #1a1a1a; border-top: 1px solid #3a3a3a;"
        )
        root = QVBoxLayout(widget)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Image/Audio Preview
        preview_group = QGroupBox("Image/Audio Preview")
        preview_layout = QHBoxLayout(preview_group)

        # Оригинал
        left_col = QVBoxLayout()
        self.lbl_orig_title = QLabel("[Original]")
        self.lbl_orig_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_orig_title.setStyleSheet("color: #888888;")
        left_col.addWidget(self.lbl_orig_title)

        self.lbl_orig_image = QLabel()
        self.lbl_orig_image.setFixedSize(200, 150)
        self.lbl_orig_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_orig_image.setStyleSheet(
            "border: 1px solid #4a4a4a; background: #2a2a2a; color: #666666;"
        )
        self.lbl_orig_image.setText("No preview")
        left_col.addWidget(self.lbl_orig_image)

        self.lbl_orig_info = QLabel("Original: — MB")
        self.lbl_orig_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_orig_info.setStyleSheet("color: #888888; font-size: 12px;")
        left_col.addWidget(self.lbl_orig_info)
        preview_layout.addLayout(left_col)

        # Стрелка
        arrow = QLabel("→")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setStyleSheet("font-size: 24px; color: #888888;")
        preview_layout.addWidget(arrow)

        # Результат
        right_col = QVBoxLayout()
        self.lbl_result_title = QLabel("[Stego Result]")
        self.lbl_result_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_result_title.setStyleSheet("color: #888888;")
        right_col.addWidget(self.lbl_result_title)

        self.lbl_result_image = QLabel()
        self.lbl_result_image.setFixedSize(200, 150)
        self.lbl_result_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_result_image.setStyleSheet(
            "border: 1px solid #4a4a4a; background: #2a2a2a; color: #666666;"
        )
        self.lbl_result_image.setText("No preview")
        right_col.addWidget(self.lbl_result_image)

        self.lbl_result_info = QLabel("Result: — MB")
        self.lbl_result_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_result_info.setStyleSheet("color: #888888; font-size: 12px;")
        right_col.addWidget(self.lbl_result_info)
        preview_layout.addLayout(right_col)

        # Отступ
        preview_layout.addStretch()

        # Summary
        summary_col = QVBoxLayout()
        self.lbl_summary = QLabel("SUMMARY: SUCCESS (100%)")
        self.lbl_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_summary.setStyleSheet(
            "color: #4aaa4a; font-weight: bold; font-size: 15px;"
        )
        summary_col.addWidget(self.lbl_summary)
        self.lbl_summary_detail = QLabel("File-in-File concealed internally.")
        self.lbl_summary_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_summary_detail.setStyleSheet("color: #888888; font-size: 12px;")
        summary_col.addWidget(self.lbl_summary_detail)

        checkmark = QLabel("✔")
        checkmark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkmark.setStyleSheet("color: #4aaa4a; font-size: 36px;")
        summary_col.addWidget(checkmark)
        preview_layout.addLayout(summary_col)

        root.addWidget(preview_group)

        # Нижняя строка: метрики + DTO
        bottom_row = QHBoxLayout()

        # Performance Metrics
        metrics_group = QGroupBox("Performance Metrics")
        metrics_grid = QGridLayout(metrics_group)
        self.lbl_psnr_val = QLabel("PSNR Ratio: —")
        self.lbl_time_val = QLabel("Processing Time: —")
        self.lbl_dev_val = QLabel("Size Deviation: —")
        self.lbl_carrier_val = QLabel("Total Carrier Size: —")
        for i, lbl in enumerate([
            self.lbl_psnr_val, self.lbl_time_val,
            self.lbl_dev_val, self.lbl_carrier_val
        ]):
            metrics_grid.addWidget(lbl, i, 0)
        bottom_row.addWidget(metrics_group)

        # DTO Status
        dto_group = QGroupBox("Final Data DTO Status")
        dto_grid = QGridLayout(dto_group)
        self.lbl_format_id = QLabel("Datatype Magic Bytes: —")
        self.lbl_integrity = QLabel("Data Integrity Check: —")
        dto_grid.addWidget(self.lbl_format_id, 0, 0)
        dto_grid.addWidget(self.lbl_integrity, 1, 0)
        bottom_row.addWidget(dto_group)

        root.addLayout(bottom_row)

        # Кнопка Collapse
        collapse_row = QHBoxLayout()
        collapse_row.addStretch()
        btn_collapse = QPushButton("[ ▲ Collapse ]")
        btn_collapse.setStyleSheet(
            "border: 1px solid #4a4a4a; padding: 2px 10px;"
            "background: #2a2a2a; color: #d4d4d4;"
        )
        btn_collapse.clicked.connect(self._toggle_expand)
        collapse_row.addWidget(btn_collapse)
        root.addLayout(collapse_row)

        return widget


    def _toggle_expand(self):
        self._expanded = not self._expanded
        self._expanded_widget.setVisible(self._expanded)
        self.btn_toggle.setText("[ ▲ Collapse ]" if self._expanded else "[ ▼ Expand ]")

    def _psnr_color(self, psnr: float) -> str:
        if psnr >= 50:
            return "#4aaa4a"
        elif psnr >= 40:
            return "#aaaa4a"
        return "#aa4a4a"

    def _load_preview(self, label: QLabel, path: Optional[Path]):
        if path and path.exists():
            px = QPixmap(str(path)).scaled(
                200, 150,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            label.setPixmap(px)
        else:
            label.setText("No preview")


    def show_results(self, data: MetricsData):
        """Принять данные из StegoResponse и отобразить панель."""
        self._data = data

        # Свернутый таб
        color = self._psnr_color(data.psnr)
        self.lbl_psnr.setText(
            f'PSNR: <span style="color:{color}">{data.psnr:.1f} dB</span>'
        )
        self.lbl_psnr.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_time.setText(f"Time: {data.time_sec:.2f}s")
        sign = "+" if data.size_deviation_pct >= 0 else ""
        self.lbl_size.setText(f"Size: {sign}{data.size_deviation_pct:.0f}%")

        # Для развернутого
        self.lbl_orig_info.setText(f"Original: {data.carrier_size_mb:.1f} MB")
        self.lbl_result_info.setText(
            f"Result: {data.result_size_mb:.1f} MB  "
            f"({sign}{data.size_deviation_pct:.0f}%)"
        )

        self.lbl_psnr_val.setText(
            f"PSNR Ratio: {data.psnr:.1f} dB  "
            f"({'!!!' if data.psnr >= 40 else '???'}  т.к. {'>' if data.psnr >= 40 else '<'}40)"
        )
        self.lbl_time_val.setText(f"Processing Time: {data.time_sec:.2f} sec")
        self.lbl_dev_val.setText(
            f"Size Deviation: {sign}{data.size_deviation_pct:.0f}%  "
            f"{'!!!' if data.size_deviation_pct <= 30 else '???'}"
        )
        self.lbl_carrier_val.setText(f"Total Carrier Size: {data.carrier_size_mb:.1f} MB")
        self.lbl_format_id.setText(f"Datatype Magic Bytes (Identity: {data.format_id})")
        self.lbl_integrity.setText(
            f"Data Integrity Check: {'!!! Passed' if data.integrity_ok else '??? Failed'}"
        )

        self._load_preview(self.lbl_orig_image, data.original_path)
        self._load_preview(self.lbl_result_image, data.result_path)

        if data.success:
            self.lbl_summary.setText("SUMMARY: SUCCESS (100%)")
            self.lbl_summary.setStyleSheet(
                "color: #4aaa4a; font-weight: bold; font-size: 15px;"
            )
            self.lbl_summary_detail.setText(
                f"File-in-File concealed internally.\n"
                f"Spreading bits ({data.format_id}/{data.algorithm})"
            )
        else:
            self.lbl_summary.setText("SUMMARY: FAILED")
            self.lbl_summary.setStyleSheet(
                "color: #aa4a4a; font-weight: bold; font-size: 15px;"
            )

        self.setVisible(True)