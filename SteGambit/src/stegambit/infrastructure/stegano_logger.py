"""Настройка глобального логирования для SteGambit.

Используется ядром  и GUI для записи важных событий и ошибок. 
Вывод дублируется в консоль и файл с ротацией 5 файлов по 1 МБ, чтобы лог не разрастался бесконечно.
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional


_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DATE_FORMAT = "%H:%M:%S"
_DEFAULT_LOG_FILE = "stegambit.log"

# Ротация: до 5 файлов по 1 МБ.
_LOG_MAX_BYTES = 1 * 1024 * 1024
_LOG_BACKUP_COUNT = 5

# Сохраняем путь к активному лог-файлу, чтобы GUI мог открыть его.
_active_log_path: Optional[Path] = None


def setup_logging(
    level: int = logging.INFO,
    log_file: str | Path = _DEFAULT_LOG_FILE,
) -> None:
    """Инициализирует root-логгер: консоль + ротируемый файл.

    Вызывается один раз на старте приложения.
    Идемпотентна: повторный вызов не дублирует хендлеры.

    Args:
        level: Минимальный уровень логирования.
        log_file: Путь к файлу логов. Резолвится к абсолютному пути.
    """
    global _active_log_path

    root = logging.getLogger()

    # Защита от двойной инициализации (актуально при перезапусках в IDE).
    if getattr(root, "_stegambit_configured", False):
        return

    root.setLevel(level)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    # Консольный хендлер.
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Файловый хендлер с ротацией.
    log_path = Path(log_file).resolve()
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        mode="a",
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _active_log_path = log_path
    root._stegambit_configured = True  # type: ignore[attr-defined]
    logging.getLogger(__name__).info("Logging initialized")


def get_log_path() -> Optional[Path]:
    """Возвращает абсолютный путь к активному лог-файлу.

    Returns:
        Path к файлу логов после setup_logging(), либо None, если setup_logging ещё не был вызван.
    """
    return _active_log_path


def get_logger(name: str) -> logging.Logger:
    """Получить именованный логгер. Просто обёртка для единообразия импортов."""
    return logging.getLogger(name)