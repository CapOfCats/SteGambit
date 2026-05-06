"""Quality metrics for stego-containers."""
import numpy as np


def calculate_psnr(original: np.ndarray, stego: np.ndarray) -> float:
    """Peak Signal-to-Noise Ratio между оригиналом и stego-контейнером.

    Возвращает float('inf'), если массивы идентичны (MSE == 0).
    Предполагает 8-битный диапазон (MAX=255).
    """
    if original.shape != stego.shape:
        raise ValueError("Shape mismatch between original and stego arrays")

    diff = original.astype(np.float64) - stego.astype(np.float64)
    mse = np.mean(diff ** 2)
    if mse == 0:
        return float("inf")
    return float(20.0 * np.log10(255.0 / np.sqrt(mse)))