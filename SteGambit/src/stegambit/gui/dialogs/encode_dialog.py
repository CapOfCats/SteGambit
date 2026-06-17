from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton,
    QCheckBox, QTextEdit, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class EncodeDialogResult:
    password: str
    derive_seed_from_password: bool
    output_path: Path


class EncodeDialog(QDialog):
    """
    Диалог Configure Protection — появляется поверх MainWindow
    при нажатии HIDE DATA, до запуска операции.
    """

    confirmed = pyqtSignal(EncodeDialogResult)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SteGambit — Encode: Spreading and Hiding Data")
        self.setModal(True)
        self.setMinimumWidth(620)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        lbl_header = QLabel("Processing Data — configure protection after files are validated.")
        lbl_header.setObjectName("lbl_encode_header")
        root.addWidget(lbl_header)

        self.lbl_step1 = QLabel(
            "Step 1: [ — Source Files Pending ] (Magic Bytes not yet identified)"
        )
        self.lbl_step1.setObjectName("lbl_step1_pending")
        root.addWidget(self.lbl_step1)

        group2 = QGroupBox("Step 2: Configure Protection")
        g2_layout = QGridLayout(group2)
        g2_layout.setColumnStretch(1, 1)

        g2_layout.addWidget(QLabel("Encryption Passphrase:"), 0, 0)

        pass_row = QHBoxLayout()

        self.edit_pass1 = QLineEdit()
        self.edit_pass1.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_pass1.setPlaceholderText("[********]")
        pass_row.addWidget(self.edit_pass1)

        self.edit_pass2 = QLineEdit()
        self.edit_pass2.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_pass2.setPlaceholderText("[********]")
        pass_row.addWidget(self.edit_pass2)

        self.btn_toggle_pass = QPushButton("👁")
        self.btn_toggle_pass.setObjectName("btn_toggle_pass")
        self.btn_toggle_pass.setFixedWidth(32)
        self.btn_toggle_pass.setCheckable(True)
        self.btn_toggle_pass.setToolTip("Show / hide passphrase")
        self.btn_toggle_pass.clicked.connect(self._toggle_pass_visibility)
        pass_row.addWidget(self.btn_toggle_pass)

        self.lbl_match = QLabel("Match!!!")
        self.lbl_match.setObjectName("lbl_pass_match")
        self.lbl_match.setVisible(False)
        pass_row.addWidget(self.lbl_match)

        g2_layout.addLayout(pass_row, 0, 1)

        self.lbl_match_row = QLabel("")
        self.lbl_match_row.setObjectName("lbl_pass_match_row")
        self.lbl_match_row.setAlignment(Qt.AlignmentFlag.AlignRight)
        g2_layout.addWidget(self.lbl_match_row, 1, 1)

        self.edit_pass1.textChanged.connect(self._check_passwords)
        self.edit_pass2.textChanged.connect(self._check_passwords)

        self.chk_derive_seed = QCheckBox("Derive Coordinate Seed from Passphrase")
        self.chk_derive_seed.setChecked(True)
        g2_layout.addWidget(self.chk_derive_seed, 1, 0, 1, 2)

        lbl_prng = QLabel("— PRNG initialization will use passphrase hash as seed")
        lbl_prng.setObjectName("lbl_prng_hint")
        g2_layout.addWidget(lbl_prng, 2, 0, 1, 2)

        root.addWidget(group2)

        step3_row = QHBoxLayout()
        step3_row.addWidget(QLabel("Step 3: Output Location"))
        self.edit_output = QLineEdit()
        self.edit_output.setPlaceholderText("[D:\\OutputFiles\\covered_secret.png]")
        step3_row.addWidget(self.edit_output)
        btn_new = QPushButton("💾 New File")
        btn_new.clicked.connect(self._browse_output)
        step3_row.addWidget(btn_new)
        root.addLayout(step3_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_start = QPushButton("🔒 Start Spreading Bits (File-in-File) 🔒")
        self.btn_start.setObjectName("btn_hide")
        self.btn_start.setMinimumWidth(300)
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._on_start)
        btn_row.addWidget(self.btn_start)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(100)
        self.log_box.setPlaceholderText(
            "Process Log (Placeholder):\n"
            "Spreading algorithm: LSB\n"
            "Coordinates generated.\n"
            "Bit insertion..."
        )
        root.addWidget(self.log_box)

    def _toggle_pass_visibility(self, checked: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self.edit_pass1.setEchoMode(mode)
        self.edit_pass2.setEchoMode(mode)
        # Qt dynamic property → QSS [active="true"] перерисует кнопку без inline-стилей
        self.btn_toggle_pass.setProperty("active", "true" if checked else "false")
        self.btn_toggle_pass.style().unpolish(self.btn_toggle_pass)
        self.btn_toggle_pass.style().polish(self.btn_toggle_pass)

    def _check_passwords(self):
        p1 = self.edit_pass1.text()
        p2 = self.edit_pass2.text()
        match = p1 == p2
        # Индикатор "Match" — только если реально что-то введено и совпадает
        self.lbl_match.setVisible(match and len(p1) > 0)
        # Пустой пароль разрешён — дефолт "secret" подставится в _on_start
        self.btn_start.setEnabled(
            match and bool(self.edit_output.text().strip())
        )

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Stego File", "",
            "PNG (*.png);;WAV (*.wav);;JPEG (*.jpg);;All files (*)"
        )
        if path:
            self.edit_output.setText(path)
            self._check_passwords()

    def _on_start(self):
        raw_password = self.edit_pass1.text()
        result = EncodeDialogResult(
            self.edit_pass1.text(),
            derive_seed_from_password=self.chk_derive_seed.isChecked(),
            output_path=Path(self.edit_output.text()),
        )
        self.confirmed.emit(result)
        self.accept()


    def set_step1_valid(self, valid: bool, format_id: str = ""):
        if valid:
            self.lbl_step1.setText(
                f"Step 1: [!!! Source Files Valid] (Magic Bytes identified: {format_id})"
            )
            self.lbl_step1.setObjectName("lbl_step1_valid")
        else:
            self.lbl_step1.setText(
                "Step 1: [??? Source Files Invalid] (Check file selection)"
            )
            self.lbl_step1.setObjectName("lbl_step1_invalid")
        # Форсируем перерисовку после смены objectName
        self.lbl_step1.style().unpolish(self.lbl_step1)
        self.lbl_step1.style().polish(self.lbl_step1)

    def append_log(self, text: str):
        self.log_box.append(text)