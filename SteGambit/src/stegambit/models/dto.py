from dataclasses import dataclass, field
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
    """Запрос на сокрытие данных"""
    carrier_path: Path      # Путь к контейнеру
    payload_path: Path      # Путь к файлу для сокрытия
    output_path: Path       # Куда сохранить результат
    password: str           # Для шифрования
    # TODO #22: dead field. Алгоритм определяется автоматически в
    # StegoService через _FORMAT_TO_PROCESSOR[carrier_fmt]. Поле
    # оставлено для обратной совместимости с ранними версиями GUI;
    # никем не читается. Удалить в рамках #22 после аудита всех
    # точек создания StegoTaskRequest.
    algorithm: str = "LSB"  # Какой алгоритм использовать


@dataclass(frozen=True)
class StegoResponse:
    """Результат операции"""
    success: bool
    output_path: Optional[Path] = None
    metrics: Optional[Dict[str, Any]] = None  # PSNR, время и т.д.
    error: Optional[str] = None


@dataclass(frozen=True)
class CapacityReport:
    """Отчёт о пропускной способности контейнера для предварительной валидации.

    Возвращается StegoService.analyze_capacity() до фактической операции
    сокрытия. Используется UI (вкладка Encode → Check Compatibility),
    чтобы заранее показать реальные цифры и не запускать невозможную операцию.

    """
    fits: bool                  # Флаг ВОЗМОЖНОСТИ сокрытия
    format: str                 # Один из поддерживаемых форматов
    algorithm: str              # LSB или DCT
    capacity_bits: int          # Доступная ёмкость в битах
    required_bits: int          # Сколько нужно для payload + crypto-frame
    payload_size_bytes: int     # Размер исходного скрываемого файла
    header_size_bytes: int      # Накладные расходы CryptoEngine (57 байт)
    utilization_percent: float  # Процент использования ёмкости