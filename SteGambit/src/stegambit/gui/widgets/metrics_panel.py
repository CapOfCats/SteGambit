from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QGridLayout, QFrame,
    QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from stegambit.models.dto import QualityStatus

_STATUS_COLOR: dict[QualityStatus, str] = {
    QualityStatus.OK:      "#4aaa4a",   # ГРИН
    QualityStatus.WARNING: "#aaaa4a",   # ЕЛЛОУ
    QualityStatus.ANOMALY: "#aa4a4a",   # РЭД
}

_STATUS_LABEL: dict[QualityStatus, str] = {
    QualityStatus.OK:      "[ Operation Complete — OK ]",
    QualityStatus.WARNING: "[ Operation Complete — WARNING ]",
    QualityStatus.ANOMALY: "[ Operation Complete — ANOMALY ]",
}

_SUMMARY_TEXT: dict[QualityStatus, str] = {
    QualityStatus.OK:      "SUMMARY: SUCCESS — Quality OK",
    QualityStatus.WARNING: "SUMMARY: SUCCESS — Quality WARNING",
    QualityStatus.ANOMALY: "SUMMARY: SUCCESS — Quality ANOMALY",
}



@dataclass
class MetricsData:
    time_sec: float
    size_deviation_pct: float
    algorithm: str
    carrier_size_mb: float
    result_size_mb: float
    quality_status: QualityStatus = QualityStatus.OK

    # PSNR/SSIM: None для DCT-пайплайна
    psnr: Optional[float] = None
    ssim: Optional[float] = None

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

        self._bar = self._build_collapsed_bar()
        self._root.addWidget(self._bar)

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

        self.lbl_psnr = QLabel("PSNR: —")
        layout.addWidget(self.lbl_psnr)

        layout.addSpacing(12)

        self.lbl_ssim = QLabel("SSIM: —")
        layout.addWidget(self.lbl_ssim)

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

        preview_layout.addStretch()

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

        self.lbl_checkmark = QLabel("✔")
        self.lbl_checkmark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_checkmark.setStyleSheet("color: #4aaa4a; font-size: 36px;")
        summary_col.addWidget(self.lbl_checkmark)
        preview_layout.addLayout(summary_col)

        root.addWidget(preview_group)

        bottom_row = QHBoxLayout()

        metrics_group = QGroupBox("Performance Metrics")
        metrics_grid = QGridLayout(metrics_group)

        self.lbl_psnr_val   = QLabel("PSNR Ratio: —")
        self.lbl_ssim_val   = QLabel("SSIM Index: —")
        self.lbl_time_val   = QLabel("Processing Time: —")
        self.lbl_dev_val    = QLabel("Size Deviation: —")
        self.lbl_carrier_val = QLabel("Total Carrier Size: —")

        for i, lbl in enumerate([
            self.lbl_psnr_val,
            self.lbl_ssim_val,
            self.lbl_time_val,
            self.lbl_dev_val,
            self.lbl_carrier_val,
        ]):
            metrics_grid.addWidget(lbl, i, 0)

        bottom_row.addWidget(metrics_group)

        dto_group = QGroupBox("Final Data DTO Status")
        dto_grid = QGridLayout(dto_group)
        self.lbl_format_id  = QLabel("Datatype Magic Bytes: —")
        self.lbl_integrity  = QLabel("Data Integrity Check: —")
        self.lbl_quality_badge = QLabel("Quality Gate: —")     # новое поле #13
        dto_grid.addWidget(self.lbl_format_id, 0, 0)
        dto_grid.addWidget(self.lbl_integrity, 1, 0)
        dto_grid.addWidget(self.lbl_quality_badge, 2, 0)
        bottom_row.addWidget(dto_group)

        root.addLayout(bottom_row)

        # Collapse
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


    @staticmethod
    def _status_color(status: QualityStatus) -> str:
        """Единственная точка маппинга статус → цвет.
        Убрана старая _psnr_color(), теперь цвет берётся из бэкендового QualityStatus.
        """
        return _STATUS_COLOR.get(status, "#888888")


    def _load_preview(self, label: QLabel, path: Optional[Path]):
        if path and path.exists():
            px = QPixmap(str(path)).scaled(
                200, 150,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            label.setPixmap(px)
        else:
            label.setText("No preview")


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
        """Принять данные и отобразить панель.

        Цветовая индикация полностью управляется data.quality_status.
        """
        self._data = data
        color = self._status_color(data.quality_status)

        self.lbl_status.setText(_STATUS_LABEL.get(data.quality_status, "[ Operation Complete ]"))
        self.lbl_status.setStyleSheet(f"color: {color}; font-weight: bold;")

        # PSNR — может быть None
        if data.psnr is not None:
            self.lbl_psnr.setText(
                f'PSNR: <span style="color:{color}">{data.psnr:.1f} dB</span>'
            )
            self.lbl_psnr.setTextFormat(Qt.TextFormat.RichText)
        else:
            self.lbl_psnr.setText("PSNR: N/A (DCT)")
            self.lbl_psnr.setTextFormat(Qt.TextFormat.PlainText)

        # SSIM — может быть None
        if data.ssim is not None:
            self.lbl_ssim.setText(
                f'SSIM: <span style="color:{color}">{data.ssim:.4f}</span>'
            )
            self.lbl_ssim.setTextFormat(Qt.TextFormat.RichText)
        else:
            self.lbl_ssim.setText("SSIM: N/A (DCT)")
            self.lbl_ssim.setTextFormat(Qt.TextFormat.PlainText)

        self.lbl_time.setText(f"Time: {data.time_sec:.2f}s")

        sign = "+" if data.size_deviation_pct >= 0 else ""
        self.lbl_size.setText(f"Size: {sign}{data.size_deviation_pct:.1f}%")

        self.lbl_orig_info.setText(f"Original: {data.carrier_size_mb:.1f} MB")
        self.lbl_result_info.setText(
            f"Result: {data.result_size_mb:.1f} MB  "
            f"({sign}{data.size_deviation_pct:.1f}%)"
        )
        self._load_preview(self.lbl_orig_image, data.original_path)
        self._load_preview(self.lbl_result_image, data.result_path)

        if data.psnr is not None:
            psnr_badge = "!!!" if data.psnr >= 40 else "???"
            self.lbl_psnr_val.setText(
                f"PSNR Ratio: {data.psnr:.1f} dB  [{psnr_badge}]"
            )
        else:
            self.lbl_psnr_val.setText("PSNR Ratio: N/A (DCT — frequency domain)")

        if data.ssim is not None:
            ssim_badge = "!!!" if data.ssim >= 0.95 else "???"
            self.lbl_ssim_val.setText(
                f"SSIM Index: {data.ssim:.4f}  [{ssim_badge}  т.к. "
                f"{'≥' if data.ssim >= 0.95 else '<'}0.95]"
            )
        else:
            self.lbl_ssim_val.setText("SSIM Index: N/A (DCT — frequency domain)")

        self.lbl_time_val.setText(f"Processing Time: {data.time_sec:.2f} sec")
        dev_badge = "!!!" if abs(data.size_deviation_pct) <= 30 else "???"
        self.lbl_dev_val.setText(
            f"Size Deviation: {sign}{data.size_deviation_pct:.1f}%  [{dev_badge}]"
        )
        self.lbl_carrier_val.setText(
            f"Total Carrier Size: {data.carrier_size_mb:.1f} MB"
        )

        self.lbl_format_id.setText(
            f"Datatype Magic Bytes (Identity: {data.format_id})"
        )
        self.lbl_integrity.setText(
            f"Data Integrity Check: "
            f"{'!!! Passed (AES-GCM tag verified)' if data.integrity_ok else '??? FAILED'}"
        )
        self.lbl_quality_badge.setText(
            f"Quality Gate: {data.quality_status.value}"
        )
        self.lbl_quality_badge.setStyleSheet(f"color: {color}; font-weight: bold;")

        summary_text = _SUMMARY_TEXT.get(data.quality_status, "SUMMARY: COMPLETE")
        if not data.success:
            summary_text = "SUMMARY: FAILED"

        self.lbl_summary.setText(summary_text)
        self.lbl_summary.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 15px;"
        )
        self.lbl_checkmark.setStyleSheet(
            f"color: {color}; font-size: 36px;"
        )
        checkmark_char = "✔" if data.success else "✖"
        self.lbl_checkmark.setText(checkmark_char)

        detail = f"File-in-File concealed.\nSpreading bits ({data.format_id}/{data.algorithm})"
        if data.quality_status == QualityStatus.WARNING:
            detail += "\n⚠ Potentially detectable by advanced steganalysis."
        elif data.quality_status == QualityStatus.ANOMALY:
            detail += "\n✖ High distortion detected — not recommended for covert use."
        self.lbl_summary_detail.setText(detail)

        self.setVisible(True)