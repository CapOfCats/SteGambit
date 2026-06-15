"""Настройка глобального логирования для SteGambit.

Используется ядром (StegoService, CryptoEngine) и GUI (MainWindow, Worker)
для записи важных событий и ошибок. Вывод дублируется в консоль и файл.
"""
import logging
import sys
from pathlib import Path


_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DATE_FORMAT = "%H:%M:%S"
_DEFAULT_LOG_FILE = "stegambit.log"


def setup_logging(
    level: int = logging.INFO,
    log_file: str | Path = _DEFAULT_LOG_FILE,
) -> None:
    """Инициализирует root-логгер: консоль + файл.

    Вызывается один раз на старте приложения (в main.py).
    Идемпотентна: повторный вызов не дублирует хендлеры.

    Args:
        level: Минимальный уровень логирования (logging.INFO/DEBUG/...).
        log_file: Путь к файлу логов. Будет создан рядом с main.py.
    """
    root = logging.getLogger()

    # Защита от двойной инициализации (актуально при перезапусках в IDE).
    if getattr(root, "_stegambit_configured", False):
        return

    root.setLevel(level)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    # Консольный хендлер
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Файловый хендлер
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    root._stegambit_configured = True  # type: ignore[attr-defined]
    logging.getLogger(__name__).info("Logging initialized")


def get_logger(name: str) -> logging.Logger:
    """Получить именованный логгер. Просто обёртка для единообразия импортов."""
    return logging.getLogger(name)