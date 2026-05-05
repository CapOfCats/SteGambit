import sys
from PyQt6.QtWidgets import QApplication
from stegambit.gui.main_window import MainWindow
from stegambit.gui.styles.dark_theme import apply_dark_theme


def main():
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()