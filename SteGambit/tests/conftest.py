"""Глобальные фикстуры для всего test suite."""
import pytest
import numpy as np
import shutil

from pathlib import Path
from PIL import Image


ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
CARRIERS_DIR = ARTIFACTS_DIR / "carriers"
PAYLOADS_DIR = ARTIFACTS_DIR / "payloads"


def _copy_artifact(src: Path, tmp_path: Path) -> Path:
    """Копирует артефакт в tmp_path и возвращает путь к копии.

    Защита от случайной мутации артефакта тестом. Каждый тест работает с собственной копией.
    """
    if not src.exists():
        pytest.fail(
            f"Артефакт отсутствует: {src}\n"
            f"Положи файл в tests/artifacts/ согласно README.md."
        )
    dst = tmp_path / src.name
    shutil.copy2(src, dst)
    return dst


@pytest.fixture
def png_small(tmp_path: Path) -> Path:
    """Маленький PNG (64x64). Подходит для проверок малой ёмкости."""
    return _copy_artifact(CARRIERS_DIR / "small.png", tmp_path)


@pytest.fixture
def png_medium(tmp_path: Path) -> Path:
    """Средний PNG (256x256). Основной носитель smoke-тестов."""
    return _copy_artifact(CARRIERS_DIR / "medium.png", tmp_path)


@pytest.fixture
def jpeg_carrier(tmp_path: Path) -> Path:
    """JPEG-носитель для DCT-пайплайна (512x512, baseline)."""
    return _copy_artifact(CARRIERS_DIR / "photo.jpg", tmp_path)


@pytest.fixture
def wav_carrier(tmp_path: Path) -> Path:
    """WAV-носитель (16-bit PCM, 44.1 kHz)."""
    return _copy_artifact(CARRIERS_DIR / "music.wav", tmp_path)


@pytest.fixture
def payload_tiny(tmp_path: Path) -> Path:
    """Очень маленький payload (100 байт текста)."""
    return _copy_artifact(PAYLOADS_DIR / "tiny.txt", tmp_path)


@pytest.fixture
def payload_pdf(tmp_path: Path) -> Path:
    """Реалистичный payload - PDF-документ."""
    return _copy_artifact(PAYLOADS_DIR / "secret.pdf", tmp_path)


@pytest.fixture
def payload_zip(tmp_path: Path) -> Path:
    """Реалистичный payload - ZIP-архив."""
    return _copy_artifact(PAYLOADS_DIR / "archive.zip", tmp_path)

@pytest.fixture
def random_image() -> np.ndarray:
    """Случайное RGB-изображение 64x64.

    Используется в test_metrics.py. Будет заменено на png_medium.
    """
    rng = np.random.default_rng(seed=42)
    return rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8)


@pytest.fixture
def png_carrier(tmp_path: Path, random_image: np.ndarray) -> Path:
    """Сгенерированный PNG. Будет заменено на png_small."""
    path = tmp_path / "carrier.png"
    Image.fromarray(random_image).save(path)
    return path


@pytest.fixture
def small_payload(tmp_path: Path) -> Path:
    """Payload 200 байт. Будет заменено на payload_tiny."""
    path = tmp_path / "secret.bin"
    path.write_bytes(b"X" * 200)
    return path