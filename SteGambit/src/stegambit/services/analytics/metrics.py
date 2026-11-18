"""Quality metrics for stego containers.

This module is a pure counting engine. It knows nothing about DTOs, services,
or the GUI. Input is ndarrays and paths; output is numbers and enums.
StegoService (the facade) and MetricsPanel (the front end) decide how to use it.

Metrics:
    * PSNR — peak signal-to-noise ratio (dB), the standard of visual
             transparency.
    * SSIM — structural similarity index [0..1], a finer estimate
             of how a human perceives distortion.
    * Size Deviation — percent growth of the file size on disk
             (a trigger against structural steganalysis).

Quality triggers (from the report, Chapter 5.2):
    * OK       — PSNR >= 40 dB and Deviation <= 30%.
    * WARNING  — 30 dB <= PSNR < 40 dB.
    * ANOMALY  — PSNR < 30 dB or Deviation > 30%.
"""
from pathlib import Path
from typing import Optional

import numpy as np
from skimage.metrics import structural_similarity as _ssim

from stegambit.models.dto import QualityStatus


# Thresholds are module-level constants so magic numbers are not scattered
# through the code. Change the quality policy only here.
PSNR_OK_THRESHOLD = 40.0       # dB, below — WARNING
PSNR_ANOMALY_THRESHOLD = 30.0  # dB, below — ANOMALY
SIZE_DEVIATION_LIMIT = 30.0    # %, above — ANOMALY


def calculate_psnr(original: np.ndarray, stego: np.ndarray) -> float:
    """Computes the Peak Signal-to-Noise Ratio between two containers.

    PSNR is the standard quality metric in lossless steganography.
    The higher the PSNR, the less visible the distortion from embedding the payload.
    Values >40 dB are treated as visually indistinguishable.

    Args:
        original: Original container before embedding (np.ndarray, dtype=uint8).
                  For images shape=(H, W, C), for audio shape=(N,) or (N, 2).
        stego:    Container after payload embedding, same shape and dtype.

    Returns:
        PSNR in decibels (dB). float('inf') if the arrays are identical
        (MSE == 0, which means zero distortion).

    Raises:
        ValueError: If the array shapes do not match.
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
    """Computes the Structural Similarity Index between containers.

    SSIM is a modern metric of perceived image quality.
    Unlike PSNR (which works pixel by pixel), it estimates structural
    similarity in local windows. Range [-1, 1], where 1 is identity.
    Values >0.95 for LSB steganography are treated as visually indistinguishable.

    Args:
        original: Original container (np.ndarray, dtype=uint8).
                  Supported: 2D grayscale, 3D RGB, 1D/2D audio (no SSIM).
        stego:    Stego container of the same shape.

    Returns:
        SSIM in the range [-1, 1]. float nan if SSIM does not apply
        to this container type (for example, 1D audio).

    Raises:
        ValueError: If the array shapes do not match.
    """
    if original.shape != stego.shape:
        raise ValueError(
            f"Shape mismatch: original={original.shape}, stego={stego.shape}"
        )

    # SSIM is implemented for 2D/3D images for now. For 1D audio return NaN.
    if original.ndim < 2:
        return float("nan")

    if original.ndim == 3:
        return float(_ssim(original, stego, channel_axis=-1, data_range=255))
    return float(_ssim(original, stego, data_range=255))


def calculate_size_deviation(original_path: Path, stego_path: Path) -> float:
    """Computes the percent growth of the file size after payload embedding.

    A trigger against structural steganalysis: if the result file
    is much larger than the original, that is a clear anomaly visible to DLP systems.

    Args:
        original_path: Path to the original container before the operation.
        stego_path:    Path to the resulting stego file after the operation.

    Returns:
        Percent deviation.
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
    """Determines the operation quality status from the triggers.

    Implements the project PSNR policy:
        * PSNR >= 40 dB and Deviation <= 30%  -> OK
        * 30 dB <= PSNR < 40 dB               -> WARNING
        * PSNR < 30 dB or Deviation > 30%  -> ANOMALY

    Args:
        psnr:           PSNR in dB, or None (metric unavailable).
        size_deviation: Size growth in %, or None.

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