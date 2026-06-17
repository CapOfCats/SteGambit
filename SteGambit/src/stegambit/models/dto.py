"""DTO-слой SteGambit.

Все DTO неизменяемы (frozen=True) и валидируют входные данные
через __post_init__. Архитектурное обоснование: см. ADR 009.
"""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any


class QualityStatus(str, Enum):
    """Триггер качества операции. Используется UI для цветовой индикации результата:
        OK       (PSNR >= 40 dB, deviation <= 30%).
        WARNING  (30 <= PSNR < 40, потенциально обнаружимо).
        ANOMALY  (PSNR < 30 или deviation > 30%).
    """
    OK = "OK"
    WARNING = "WARNING"
    ANOMALY = "ANOMALY"


@dataclass(frozen=True)
class StegoTaskRequest:
    """Запрос на сокрытие или извлечение данных.

    Поля валидируются в __post_init__:
        * carrier_path - должен существовать и быть файлом.
        * payload_path - должен существовать и быть файлом.
        * output_path  - родительская директория должна существовать.
        * password     - допустима пустая строка.

    Пути нормализуются через Path(...).resolve().

    Raises:
        FileNotFoundError: Если output_path.parent отсутствуют.
        ValueError:        Если carrier/payload не являются файлами.
        TypeError:         Если password не строка.
    """
    carrier_path: Path
    payload_path: Path
    output_path: Path
    password: str

    def __post_init__(self):
        carrier = Path(self.carrier_path).resolve()
        if not carrier.exists():
            raise FileNotFoundError(f"Carrier not found: {carrier}")
        if not carrier.is_file():
            raise ValueError(f"Carrier is not a file: {carrier}")
        object.__setattr__(self, "carrier_path", carrier)

        payload = Path(self.payload_path).resolve()
        if not payload.exists():
            raise FileNotFoundError(f"Payload not found: {payload}")
        if not payload.is_file():
            raise ValueError(f"Payload is not a file: {payload}")
        object.__setattr__(self, "payload_path", payload)

        output = Path(self.output_path).resolve()
        if not output.parent.exists():
            raise FileNotFoundError(
                f"Output directory does not exist: {output.parent}"
            )
        object.__setattr__(self, "output_path", output)

        if not isinstance(self.password, str):
            raise TypeError(
                f"Password must be str, got {type(self.password).__name__}"
            )


@dataclass(frozen=True)
class StegoResponse:
    """Результат операции."""
    success: bool
    output_path: Optional[Path] = None
    metrics: Optional[Dict[str, Any]] = None  # PSNR, время и т.д.
    error: Optional[str] = None


@dataclass(frozen=True)
class CapacityReport:
    """Отчёт о пропускной способности контейнера для предварительной валидации.

    Возвращается StegoService.analyze_capacity() до фактической операции сокрытия.
    """
    fits: bool
    format: str
    algorithm: str
    capacity_bits: int
    required_bits: int
    payload_size_bytes: int
    header_size_bytes: int
    utilization_percent: float