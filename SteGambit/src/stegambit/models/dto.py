from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class StegoTaskRequest:
    """Запрос на сокрытие данных"""
    carrier_path: Path      # Путь к контейнеру
    payload_path: Path      # Путь к файлу для сокрытия
    output_path: Path       # Куда сохранить результат
    password: str           # Для шифрования
    algorithm: str = "LSB"  # Какой алгоритм использовать


@dataclass(frozen=True)
class StegoResponse:
    """Результат операции"""
    success: bool
    output_path: Optional[Path] = None
    metrics: Optional[Dict[str, float]] = None  # PSNR, время и т.д.
    error: Optional[str] = None