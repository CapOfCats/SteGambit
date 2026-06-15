"""Метрики качества стего-контейнеров.

Этот модуль — чистый "счётный движок". Не знает ни про DTO, ни про сервисы,
ни про GUI. На вход — ndarray и пути, на выход — числа и enum'ы.
Использование решает StegoService (фасад) и MetricsPanel (фронт).

Метрики:
    * PSNR — пиковое отношение сигнала к шуму (dB), стандарт визуальной
             прозрачности.
    * SSIM — индекс структурного сходства [0..1], более точная оценка
             восприятия искажений человеком.
    * Size Deviation — процентный прирост размера файла на диске
             (триггер защиты от структурного стегоанализа).

Триггеры качества (из отчёта, Глава 5.2):
    * OK       — PSNR >= 40 dB и Deviation <= 30%.
    * WARNING  — 30 dB <= PSNR < 40 dB.
    * ANOMALY  — PSNR < 30 dB или Deviation > 30%.
"""
from pathlib import Path
from typing import Optional

import numpy as np
from skimage.metrics import structural_similarity as _ssim

from stegambit.models.dto import QualityStatus


# Пороги — общие константы модуля, чтобы не размазывать magic numbers
# по коду. При смене политики качества меняем только здесь.
PSNR_OK_THRESHOLD = 40.0       # dB, ниже — WARNING
PSNR_ANOMALY_THRESHOLD = 30.0  # dB, ниже — ANOMALY
SIZE_DEVIATION_LIMIT = 30.0    # %, выше — ANOMALY


def calculate_psnr(original: np.ndarray, stego: np.ndarray) -> float:
    """Вычисляет Peak Signal-to-Noise Ratio между двумя контейнерами.

    PSNR — стандартная метрика качества в lossless-стеганографии.
    Чем выше PSNR, тем менее заметны искажения от встраивания payload.
    Значения >40 dB считаются визуально неразличимыми.

    Args:
        original: Исходный контейнер до встраивания (np.ndarray, dtype=uint8).
                  Для изображений shape=(H, W, C), для аудио shape=(N,) или (N, 2).
        stego:    Контейнер после встраивания payload, той же формы и dtype.

    Returns:
        PSNR в децибелах (dB). float('inf') — если массивы идентичны
        (MSE == 0, что означает нулевое искажение).

    Raises:
        ValueError: Если shape массивов не совпадает.
    """
    if original.shape != stego.shape:
        raise ValueError(
            f"Shape mismatch: original={original.shape}, stego={stego.shape}"
        )

    diff = original.astype(np.float64) - stego.astype(np.float64)
    mse = np.mean(diff ** 2)
    if mse == 0:
        return float("inf")
    return float(20.0 * np.log10(255.0 / np.sqrt(mse)))


def calculate_ssim(original: np.ndarray, stego: np.ndarray) -> float:
    """Вычисляет Structural Similarity Index между контейнерами.

    SSIM — современная метрика воспринимаемого качества изображений.
    В отличие от PSNR (работающего попиксельно), оценивает структурное
    сходство в локальных окнах. Диапазон [-1, 1], где 1 — идентичность.
    Значения >0.95 для LSB-стеганографии считаются неотличимыми визуально.

    Args:
        original: Исходный контейнер (np.ndarray, dtype=uint8).
                  Поддерживаются: 2D grayscale, 3D RGB, 1D/2D audio (без SSIM).
        stego:    Стего-контейнер той же формы.

    Returns:
        SSIM в диапазоне [-1, 1]. float nan — если SSIM неприменим
        к данному типу контейнера (например, 1D-аудио).

    Raises:
        ValueError: Если shape массивов не совпадает.
    """
    if original.shape != stego.shape:
        raise ValueError(
            f"Shape mismatch: original={original.shape}, stego={stego.shape}"
        )

    # SSIM пока сделан для 2D/3D-изображений. Для 1D-аудио возвращаем NaN
    if original.ndim < 2:
        return float("nan")

    if original.ndim == 3:
        return float(_ssim(original, stego, channel_axis=-1, data_range=255))
    return float(_ssim(original, stego, data_range=255))


def calculate_size_deviation(original_path: Path, stego_path: Path) -> float:
    """Вычисляет процентный прирост размера файла после внедрения payload.

    Триггер защиты от структурного стегоанализа: если итоговый файл
    значительно больше оригинала, это явная аномалия, видимая DLP-системами.

    Args:
        original_path: Путь к исходному контейнеру до операции.
        stego_path:    Путь к итоговому стего-файлу после операции.

    Returns:
        Процентное отклонение в процентах.
    """
    size_orig = original_path.stat().st_size
    size_stego = stego_path.stat().st_size
    if size_orig == 0:
        return 0.0
    return float((size_stego - size_orig) / size_orig * 100.0)


def evaluate_quality(
    psnr: Optional[float],
    size_deviation: Optional[float],
) -> QualityStatus:
    """Определяет статус качества операции по триггерам.

    Реализует политику PSNR в проекте:
        * PSNR >= 40 dB и Deviation <= 30%  -> OK
        * 30 dB <= PSNR < 40 dB               -> WARNING
        * PSNR < 30 dB или Deviation > 30%  -> ANOMALY

    Args:
        psnr:           PSNR в dB или None (метрика недоступна).
        size_deviation: Прирост размера в % или None.

    Returns:
        QualityStatus: OK / WARNING / ANOMALY.
    """
    if size_deviation is not None and abs(size_deviation) > SIZE_DEVIATION_LIMIT:
        return QualityStatus.ANOMALY
    if psnr is not None and psnr < PSNR_ANOMALY_THRESHOLD:
        return QualityStatus.ANOMALY

    if psnr is not None and psnr < PSNR_OK_THRESHOLD:
        return QualityStatus.WARNING

    return QualityStatus.OK