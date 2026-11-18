from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QGridLayout,
    QSlider, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
import wave
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from stegambit.models.dto import QualityStatus

_STATUS_COLOR: dict[QualityStatus, str] = {
    QualityStatus.OK:      "#4aaa4a",   # GREEN
    QualityStatus.WARNING: "#aaaa4a",   # YELLOW
    QualityStatus.ANOMALY: "#aa4a4a",   # RED
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

def _render_waveform(path: Path, w: int, h: int, color: str = "#4aaa4a") -> Optional[QPixmap]:
    """WAV → waveform QPixmap. stdlib wave + numpy only."""
    try:
        with wave.open(str(path), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth  = wf.getsampwidth()
            n_frames   = wf.getnframes()
            raw        = wf.readframes(n_frames)

        dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}
        dtype     = dtype_map.get(sampwidth, np.int16)
        samples   = np.frombuffer(raw, dtype=dtype)

        if n_channels > 1:
            samples = samples[::n_channels]  # stereo → mono

        max_val = np.iinfo(dtype).max
        samples = samples.astype(np.float32) / max_val

        if len(samples) > w:
            step    = len(samples) / w
            indices = (np.arange(w) * step).astype(int)
            samples = samples[indices]

        pixmap = QPixmap(w, h)
        pixmap.fill(QColor("#2a2a2a"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(color))
        pen.setWidth(1)
        painter.setPen(pen)

        mid    = h / 2
        x_step = w / len(samples)
        for i, s in enumerate(samples):
            x = int(i * x_step)
            painter.drawLine(x, int(mid), x, int(mid - s * mid * 0.9))

        # center axis
        painter.setPen(QPen(QColor("#3a5a3a")))
        painter.drawLine(0, int(mid), w, int(mid))
        painter.end()
        return pixmap

    except Exception:
        return None

class ZoomablePreview(QWidget):
    """Preview of one file: image / WAV waveform + zoom slider."""

    _ZOOM_MIN  = 50
    _ZOOM_MAX  = 300
    _ZOOM_STEP = 10

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title    = title
        self._raw_px: Optional[QPixmap] = None
        self._base_w   = 200
        self._base_h   = 150
        self._zoom_pct = 100
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.lbl_title = QLabel(self._title)
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setStyleSheet("color: #888888;")
        layout.addWidget(self.lbl_title)

        self._scroll = QScrollArea()
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setWidgetResizable(False)
        self._scroll.setFixedSize(self._base_w + 16, self._base_h + 16)
        self._scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4a4a4a; background: #2a2a2a; }"
            "QScrollBar:horizontal { height: 6px; background: #1a1a1a; }"
            "QScrollBar:vertical   { width:  6px; background: #1a1a1a; }"
            "QScrollBar::handle    { background: #4a7a4a; border-radius: 3px; }"
        )
        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setStyleSheet("background: #2a2a2a; color: #666666;")
        self.lbl_image.setText("No preview")
        self._scroll.setWidget(self.lbl_image)
        layout.addWidget(self._scroll, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.lbl_info = QLabel("— MB")
        self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_info.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(self.lbl_info)

        zoom_row = QHBoxLayout()
        zoom_row.setSpacing(6)

        btn_minus = QPushButton("[ − ]")
        btn_minus.setFixedWidth(46)
        btn_minus.setStyleSheet(self._btn_style())
        btn_minus.clicked.connect(self._zoom_out)
        zoom_row.addWidget(btn_minus)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(self._ZOOM_MIN, self._ZOOM_MAX)
        self._slider.setValue(100)
        self._slider.setSingleStep(self._ZOOM_STEP)
        self._slider.setPageStep(self._ZOOM_STEP * 2)
        self._slider.setFixedWidth(120)
        self._slider.setStyleSheet(self._slider_style())
        self._slider.valueChanged.connect(self._on_slider)
        zoom_row.addWidget(self._slider)

        btn_plus = QPushButton("[ + ]")
        btn_plus.setFixedWidth(46)
        btn_plus.setStyleSheet(self._btn_style())
        btn_plus.clicked.connect(self._zoom_in)
        zoom_row.addWidget(btn_plus)

        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(38)
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_zoom.setStyleSheet("color: #4a9a4a; font-size: 11px;")
        zoom_row.addWidget(self.lbl_zoom)

        layout.addLayout(zoom_row)


    def load(self, path: Optional[Path], info_text: str = ""):
        """Load a file. Auto-detect: image / WAV / placeholder."""
        self.lbl_info.setText(info_text)
        self._raw_px   = None
        self._zoom_pct = 100
        self._slider.setValue(100)
        self.lbl_zoom.setText("100%")

        if path and path.exists():
            suffix = path.suffix.lower()
            if suffix == ".wav":
                px = _render_waveform(path, self._base_w * 2, self._base_h * 2)
                if px:
                    self._raw_px = px
                    self._apply_zoom()
                    return
            else:
                px = QPixmap(str(path))
                if not px.isNull():
                    self._raw_px = px
                    self._apply_zoom()
                    return

        self.lbl_image.setPixmap(QPixmap())
        self.lbl_image.setText("No preview")
        self.lbl_image.setFixedSize(self._base_w, self._base_h)

    def reset(self):
        self.load(None)
        self.lbl_info.setText("— MB")

    def _zoom_in(self):
        self._slider.setValue(min(self._zoom_pct + self._ZOOM_STEP, self._ZOOM_MAX))

    def _zoom_out(self):
        self._slider.setValue(max(self._zoom_pct - self._ZOOM_STEP, self._ZOOM_MIN))

    def _on_slider(self, value: int):
        self._zoom_pct = value
        self.lbl_zoom.setText(f"{value}%")
        self._apply_zoom()

    def _apply_zoom(self):
        if self._raw_px is None:
            return
        scale  = self._zoom_pct / 100.0
        new_w  = int(self._base_w * scale)
        new_h  = int(self._base_h * scale)
        scaled = self._raw_px.scaled(
            QSize(new_w, new_h),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.lbl_image.setPixmap(scaled)
        self.lbl_image.setFixedSize(scaled.width(), scaled.height())

    @staticmethod
    def _btn_style() -> str:
        return (
            "QPushButton {"
            "  border: 1px solid #4a7a4a; padding: 1px 4px;"
            "  background: #1a2a1a; color: #4aaa4a; font-size: 11px;"
            "}"
            "QPushButton:hover  { background: #2a3a2a; }"
            "QPushButton:pressed{ background: #0a1a0a; }"
        )

    @staticmethod
    def _slider_style() -> str:
        return (
            "QSlider::groove:horizontal {"
            "  height: 4px; background: #2a3a2a;"
            "  border: 1px solid #3a5a3a; border-radius: 2px;"
            "}"
            "QSlider::handle:horizontal {"
            "  width: 12px; height: 12px; margin: -4px 0;"
            "  background: #4aaa4a; border: 1px solid #2a7a2a;"
            "  border-radius: 6px;"
            "}"
            "QSlider::sub-page:horizontal {"
            "  background: #3a7a3a; border-radius: 2px;"
            "}"
        )


@dataclass
class MetricsData:
    time_sec: float
    size_deviation_pct: float
    algorithm: str
    carrier_size_mb: float
    result_size_mb: float
    quality_status: QualityStatus = QualityStatus.OK

    # PSNR/SSIM: None for the DCT pipeline
    psnr: Optional[float] = None
    ssim: Optional[float] = None

    original_path: Optional[Path] = None
    result_path: Optional[Path] = None
    success: bool = True
    format_id: str = "—"
    integrity_ok: bool = True



class MetricsPanel(QWidget):
    """
    Metrics panel — collapsed / expanded.

    Collapsed: one row of key figures + [▼ Expand] button.
    Expanded: full view with before/after previews and detailed metrics.
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
        self.btn_toggle.setObjectName("btn_metrics_toggle")

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

        preview_group = QGroupBox("Image / Audio Preview")
        preview_outer = QHBoxLayout(preview_group)
        preview_outer.setContentsMargins(8, 8, 8, 8)
        preview_outer.setSpacing(0)

        preview_outer.addStretch(1)                          # ← pin to center

        self._preview_orig = ZoomablePreview("[Original]")
        preview_outer.addWidget(self._preview_orig)

        arrow = QLabel("→")
        arrow.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        arrow.setStyleSheet("font-size: 24px; color: #888888; padding: 0 16px;")
        arrow.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        preview_outer.addWidget(arrow)

        self._preview_result = ZoomablePreview("[Stego Result]")
        preview_outer.addWidget(self._preview_result)

        preview_outer.addStretch(1)                          # ← pin to center

        preview_outer.addSpacing(32)
        summary_col = QVBoxLayout()
        summary_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

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

        preview_outer.addLayout(summary_col)
        preview_outer.addSpacing(12)

        root.addWidget(preview_group)

        bottom_row = QHBoxLayout()

        metrics_group = QGroupBox("Performance Metrics")
        metrics_grid = QGridLayout(metrics_group)

        self.lbl_psnr_val   = QLabel("PSNR Ratio: —")
        self.lbl_ssim_val   = QLabel("SSIM Index: —")
        self.lbl_time_val   = QLabel("Processing Time: —")
        self.lbl_dev_val    = QLabel("Size Deviation: —")
        self.lbl_carrier_val = QLabel("Total Carrier Size: —")
        self.lbl_algorithm_val = QLabel("Algorithm: —")

        for i, lbl in enumerate([
            self.lbl_psnr_val,
            self.lbl_ssim_val,
            self.lbl_time_val,
            self.lbl_dev_val,
            self.lbl_carrier_val,
            self.lbl_algorithm_val,
        ]):
            metrics_grid.addWidget(lbl, i, 0)

        bottom_row.addWidget(metrics_group)

        dto_group = QGroupBox("Final Data DTO Status")
        dto_grid = QGridLayout(dto_group)
        self.lbl_format_id  = QLabel("Datatype Magic Bytes: —")
        self.lbl_integrity  = QLabel("Data Integrity Check: —")
        self.lbl_quality_badge = QLabel("Quality Gate: —")     # new field #13
        dto_grid.addWidget(self.lbl_format_id, 0, 0)
        dto_grid.addWidget(self.lbl_integrity, 1, 0)
        dto_grid.addWidget(self.lbl_quality_badge, 2, 0)
        bottom_row.addWidget(dto_group)

        root.addLayout(bottom_row)

        # Collapse
        collapse_row = QHBoxLayout()
        collapse_row.addStretch()
        btn_collapse = QPushButton("[ ▲ Collapse ]")
        btn_collapse.setObjectName("btn_metrics_toggle")
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
        """Single mapping point from status → color.
        The old _psnr_color() was removed; color now comes from backend QualityStatus.
        """
        return _STATUS_COLOR.get(status, "#888888")


    def show_results(self, data: MetricsData):
        """Accept data and display the panel.

        Color indication is fully driven by data.quality_status.
        """
        self._data = data
        color = self._status_color(data.quality_status)

        self.lbl_status.setText(_STATUS_LABEL.get(data.quality_status, "[ Operation Complete ]"))
        self.lbl_status.setStyleSheet(f"color: {color}; font-weight: bold;")

        # PSNR — may be None
        if data.psnr is not None:
            self.lbl_psnr.setText(
                f'PSNR: <span style="color:{color}">{data.psnr:.1f} dB</span>'
            )
            self.lbl_psnr.setTextFormat(Qt.TextFormat.RichText)
        else:
            self.lbl_psnr.setText("PSNR: N/A (DCT)")
            self.lbl_psnr.setTextFormat(Qt.TextFormat.PlainText)

        # SSIM — may be None
        if data.ssim is not None:
            self.lbl_ssim.setText(
                f'SSIM: <span style="color:{color}">{data.ssim:.4f}</span>'
            )
            self.lbl_ssim.setTextFormat(Qt.TextFormat.RichText)
        else:
            is_dct = "DCT" in (data.algorithm or "").upper()
            self.lbl_ssim.setText("SSIM: N/A (DCT)" if is_dct else "SSIM: N/A (disabled)")
            self.lbl_ssim.setTextFormat(Qt.TextFormat.PlainText)

        self.lbl_time.setText(f"Time: {data.time_sec:.2f}s")

        sign = "+" if data.size_deviation_pct >= 0 else ""
        self.lbl_size.setText(f"Size: {sign}{data.size_deviation_pct:.1f}%")

        self._preview_orig.load(
            data.original_path,
            f"Original: {data.carrier_size_mb:.1f} MB"
        )
        self._preview_result.load(
            data.result_path,
            f"Result: {data.result_size_mb:.1f} MB  ({sign}{data.size_deviation_pct:.1f}%)"
        )

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
            is_dct = "DCT" in (data.algorithm or "").upper()
            if is_dct:
                self.lbl_ssim_val.setText("SSIM Index: N/A (DCT — frequency domain)")
            else:
                self.lbl_ssim_val.setText(
                    "SSIM Index: N/A — disabled in Settings "
                    "(Performance & Logs → Calculate Heavy Visual Metrics)"
        )

        self.lbl_time_val.setText(f"Processing Time: {data.time_sec:.2f} sec")
        dev_badge = "!!!" if abs(data.size_deviation_pct) <= 30 else "???"
        self.lbl_dev_val.setText(
            f"Size Deviation: {sign}{data.size_deviation_pct:.1f}%  [{dev_badge}]"
        )
        self.lbl_carrier_val.setText(
            f"Total Carrier Size: {data.carrier_size_mb:.1f} MB"
        )

        self.lbl_algorithm_val.setText(f"Algorithm: {data.algorithm}")

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