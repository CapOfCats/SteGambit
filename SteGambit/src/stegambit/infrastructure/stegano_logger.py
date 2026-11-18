"""Global logging setup for SteGambit.

Used by the core and the GUI to record important events and errors.
Output is duplicated to the console and a file rotated at 5 files of 1 MB so the log does not grow without bound.
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional


_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DATE_FORMAT = "%H:%M:%S"
_DEFAULT_LOG_FILE = "stegambit.log"

# Rotation: up to 5 files of 1 MB.
_LOG_MAX_BYTES = 1 * 1024 * 1024
_LOG_BACKUP_COUNT = 5

# Keep the active log path so the GUI can open it.
_active_log_path: Optional[Path] = None


def setup_logging(
    level: int = logging.INFO,
    log_file: str | Path = _DEFAULT_LOG_FILE,
) -> None:
    """Initializes the root logger: console + rotating file.

    Called once at application startup.
    Idempotent: a repeated call does not duplicate handlers.

    Args:
        level: Minimum logging level.
        log_file: Path to the log file. Resolved to an absolute path.
    """
    global _active_log_path

    root = logging.getLogger()

    # Guard against double initialization (relevant on IDE restarts).
    if getattr(root, "_stegambit_configured", False):
        return

    root.setLevel(level)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    # Console handler.
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Rotating file handler.
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
    """Returns the absolute path to the active log file.

    Returns:
        Path to the log file after setup_logging(), or None if setup_logging has not been called yet.
    """
    return _active_log_path


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. A thin wrapper for consistent imports."""
    return logging.getLogger(name)