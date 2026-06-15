import pytest
import numpy as np

from pathlib import Path
from PIL import Image

@pytest.fixture
def random_image() -> np.ndarray:
    """Случайное RGB-изображение 64x64 — детерминированное по seed.

    Маленькое, чтобы тесты летали, но достаточно для расчёта SSIM
    (минимум 7x7 пикселей для скользящего окна).
    """
    rng = np.random.default_rng(seed=42)
    return rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8)


@pytest.fixture
def png_carrier(tmp_path: Path, random_image: np.ndarray) -> Path:
    """Реальный PNG-файл на диске для тестов end-to-end."""
    path = tmp_path / "carrier.png"
    Image.fromarray(random_image).save(path)
    return path


@pytest.fixture
def small_payload(tmp_path: Path) -> Path:
    """Небольшой payload-файл (200 байт)."""
    path = tmp_path / "secret.bin"
    path.write_bytes(b"X" * 200)
    return path
