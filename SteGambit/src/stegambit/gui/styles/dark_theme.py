DARK_QSS = """
QMainWindow, QDialog {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: "Courier New", monospace;
}

QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: "Courier New", monospace;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #3a3a3a;
    background-color: #1e1e1e;
}

QTabBar::tab {
    background-color: #2a2a2a;
    color: #888888;
    padding: 8px 40px;
    border: 1px solid #3a3a3a;
    font-family: "Courier New", monospace;
    font-size: 13px;
    font-weight: bold;
}

QTabBar::tab:selected {
    background-color: #1e1e1e;
    color: #d4d4d4;
    border-bottom: 2px solid #d4d4d4;
    background-image: repeating-linear-gradient(
        45deg,
        transparent,
        transparent 3px,
        rgba(255,255,255,0.03) 3px,
        rgba(255,255,255,0.03) 6px
    );
}

QGroupBox {
    border: 1px solid #4a4a4a;
    border-radius: 2px;
    margin-top: 8px;
    padding-top: 8px;
    color: #d4d4d4;
    font-family: "Courier New", monospace;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}

QLineEdit {
    background-color: #2a2a2a;
    border: 1px solid #4a4a4a;
    color: #d4d4d4;
    padding: 4px 6px;
    font-family: "Courier New", monospace;
    selection-background-color: #4a4a6a;
}

QLineEdit:focus {
    border: 1px solid #6a6a9a;
}

QLineEdit:disabled {
    color: #555555;
    background-color: #242424;
}

QPushButton {
    background-color: #2a2a2a;
    color: #d4d4d4;
    border: 1px solid #4a4a4a;
    padding: 5px 14px;
    font-family: "Courier New", monospace;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #333333;
    border-color: #6a6a6a;
}

QPushButton:pressed {
    background-color: #222222;
}

QPushButton:disabled {
    color: #555555;
    border-color: #333333;
}

QPushButton#btn_hide {
    background-color: #2a2a2a;
    border: 1px solid #888855;
    color: #d4d4d4;
    font-weight: bold;
    padding: 8px 20px;
    font-size: 14px;
}

QPushButton#btn_hide:enabled:hover {
    background-color: #3a3a2a;
    border-color: #aaaa66;
}

QPushButton#btn_hide:disabled {
    color: #555555;
    border-color: #444433;
}

QPushButton#btn_extract {
    background-color: #2a2a2a;
    border: 1px solid #555588;
    color: #d4d4d4;
    font-weight: bold;
    padding: 8px 20px;
    font-size: 14px;
}

QPushButton#btn_extract:hover {
    background-color: #2a2a3a;
    border-color: #7777aa;
}

QPushButton#btn_check {
    background-color: #2a2a2a;
    border: 1px solid #4a4a4a;
    color: #d4d4d4;
    padding: 6px 24px;
}

QPushButton#btn_check:hover {
    background-color: #2a3a2a;
    border-color: #6a8a6a;
}

QProgressBar {
    background-color: #2a2a2a;
    border: 1px solid #4a4a4a;
    color: #d4d4d4;
    text-align: center;
    font-family: "Courier New", monospace;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #555533;
    background-image: repeating-linear-gradient(
        45deg,
        transparent,
        transparent 4px,
        rgba(0,0,0,0.3) 4px,
        rgba(0,0,0,0.3) 8px
    );
}

QStatusBar {
    background-color: #161616;
    color: #888888;
    border-top: 1px solid #3a3a3a;
    font-family: "Courier New", monospace;
    font-size: 12px;
}

QTextEdit, QPlainTextEdit {
    background-color: #161616;
    border: 1px solid #3a3a3a;
    color: #aaaaaa;
    font-family: "Courier New", monospace;
    font-size: 12px;
}

QCheckBox {
    color: #d4d4d4;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #4a4a4a;
    background-color: #2a2a2a;
}

QCheckBox::indicator:checked {
    background-color: #4a8a4a;
    border-color: #6aaa6a;
}

QComboBox {
    background-color: #2a2a2a;
    border: 1px solid #4a4a4a;
    color: #d4d4d4;
    padding: 3px 6px;
    font-family: "Courier New", monospace;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #2a2a2a;
    border: 1px solid #4a4a4a;
    color: #d4d4d4;
    selection-background-color: #3a3a5a;
}

QSlider::groove:horizontal {
    height: 4px;
    background-color: #3a3a3a;
    border: 1px solid #4a4a4a;
}

QSlider::handle:horizontal {
    background-color: #888888;
    border: 1px solid #aaaaaa;
    width: 12px;
    height: 12px;
    margin: -5px 0;
    border-radius: 6px;
}

QLabel#label_indicator_green {
    color: #4aaa4a;
    font-weight: bold;
}

QLabel#label_indicator_red {
    color: #aa4a4a;
    font-weight: bold;
}

QPushButton#btn_metrics_toggle {
    border: 1px solid #4a4a4a;
    padding: 2px 10px;
    background: #2a2a2a;
    color: #d4d4d4;
}

QPushButton#btn_metrics_toggle:hover {
    background-color: #333333;
    border-color: #6a6a6a;
}
"""


def apply_dark_theme(app) -> None:
    """Применить тёмную тему к QApplication."""
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_QSS)