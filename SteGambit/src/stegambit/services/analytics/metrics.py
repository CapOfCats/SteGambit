"""Метрики качества контейнеров."""
import numpy as np


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