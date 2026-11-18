from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QLabel, QLineEdit,
    QPushButton, QGridLayout, QFileDialog
)
from PyQt6.QtCore import pyqtSignal
from pathlib import Path


class FileSelectionPanel(QWidget):
    """File selection panel for the ENCODE tab.
    
    After a cover file is chosen, synchronously detects the format via FormatIdentifier
    and shows the algorithm label (LSB/DCT).
    FormatIdentifier is imported inside the method so the backend
    dependency is not pulled in at widget-module level.
    """

    cover_changed = pyqtSignal(Path)
    payload_changed = pyqtSignal(Path)

    # Algorithm description by format, in human-readable form
    _ALGO_LABELS = {
        "PNG":  "LSB  (Least Significant Bit — spatial domain)",
        "WAV":  "LSB  (Least Significant Bit — temporal domain)",
        "JPEG": "DCT  (Discrete Cosine Transform — frequency domain)",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        group = QGroupBox("File Selection")
        layout = QGridLayout(group)
        layout.setColumnStretch(1, 1)

        # Cover file
        layout.addWidget(QLabel("Cover File (Image/Audio):"), 0, 0)
        self.edit_cover = QLineEdit()
        self.edit_cover.setPlaceholderText("Select container file...")
        layout.addWidget(self.edit_cover, 0, 1)
        btn_cover = QPushButton("📁 Browse")
        btn_cover.clicked.connect(self._browse_cover)
        layout.addWidget(btn_cover, 0, 2)

        # Algorithm label — appears after the cover is selected
        self.lbl_algorithm = QLabel("Algorithm: —")
        self.lbl_algorithm.setStyleSheet(
            "color: #888888; font-size: 12px; padding-left: 4px;"
        )
        layout.addWidget(self.lbl_algorithm, 1, 1, 1, 2)

        # Payload file
        layout.addWidget(QLabel("Payload File (Data to Hide):"), 2, 0)
        self.edit_payload = QLineEdit()
        self.edit_payload.setPlaceholderText("Select file to hide...")
        layout.addWidget(self.edit_payload, 2, 1)
        btn_payload = QPushButton("📁 Browse")
        btn_payload.clicked.connect(self._browse_payload)
        layout.addWidget(btn_payload, 2, 2)

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
            p = Path(path)
            self._update_algorithm_label(p)
            self.cover_changed.emit(p)

    def _browse_payload(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Payload File", "",
            "All files (*)"
        )
        if path:
            self.edit_payload.setText(path)
            self.payload_changed.emit(Path(path))


    def _update_algorithm_label(self, path: Path) -> None:
        """Synchronously detects the format from magic bytes and updates the label.

        The backend import is local — the core dependency stays in one place.
        If FormatIdentifier raises ValueError (unknown format) —
        show a warning in the label instead of crashing the UI.
        """
        try:
            from stegambit.core.common.format_id import FormatIdentifier
            fmt = FormatIdentifier().identify(path)
            algo = self._ALGO_LABELS.get(fmt, f"Unknown format: {fmt}")
            self.lbl_algorithm.setText(f"Algorithm: {algo}")
            self.lbl_algorithm.setStyleSheet(
                "color: #4aaa4a; font-size: 12px; padding-left: 4px;"
            )
        except ValueError as e:
            self.lbl_algorithm.setText(f"Algorithm: {e}")
            self.lbl_algorithm.setStyleSheet(
                "color: #aa6a2a; font-size: 12px; padding-left: 4px;"
            )
        except Exception:
            # Backend unavailable (for example, in isolated UI tests)
            self.lbl_algorithm.setText("Algorithm: — (backend unavailable)")
            self.lbl_algorithm.setStyleSheet(
                "color: #888888; font-size: 12px; padding-left: 4px;"
            )

    def reset_algorithm_label(self) -> None:
        """Resets the label to its initial state (needed when the form is cleared)."""
        self.lbl_algorithm.setText("Algorithm: —")
        self.lbl_algorithm.setStyleSheet(
            "color: #888888; font-size: 12px; padding-left: 4px;"
        )


    def get_cover_path(self) -> Path | None:
        t = self.edit_cover.text().strip()
        return Path(t) if t else None

    def get_payload_path(self) -> Path | None:
        t = self.edit_payload.text().strip()
        return Path(t) if t else None

    def get_detected_format(self) -> str | None:
        """Returns the last detected format (PNG/WAV/JPEG) or None."""
        text = self.lbl_algorithm.text()
        for fmt in ("PNG", "WAV", "JPEG"):
            if fmt in text:
                return fmt
        return None