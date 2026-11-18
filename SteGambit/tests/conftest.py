"""Global fixtures for the entire test suite."""
import pytest
import numpy as np
import shutil

from pathlib import Path
from PIL import Image


ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
CARRIERS_DIR = ARTIFACTS_DIR / "carriers"
PAYLOADS_DIR = ARTIFACTS_DIR / "payloads"


def _copy_artifact(src: Path, tmp_path: Path) -> Path:
    """Copies an artifact into tmp_path and returns the path to the copy.

    Guards against a test accidentally mutating the artifact. Each test works with its own copy.
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
    """Small PNG (64x64). Suitable for low-capacity checks."""
    return _copy_artifact(CARRIERS_DIR / "small.png", tmp_path)


@pytest.fixture
def png_medium(tmp_path: Path) -> Path:
    """Medium PNG (256x256). The main carrier for smoke tests."""
    return _copy_artifact(CARRIERS_DIR / "medium.png", tmp_path)


@pytest.fixture
def jpeg_carrier(tmp_path: Path) -> Path:
    """JPEG carrier for the DCT pipeline (512x512, baseline)."""
    return _copy_artifact(CARRIERS_DIR / "photo.jpg", tmp_path)


@pytest.fixture
def wav_carrier(tmp_path: Path) -> Path:
    """WAV carrier (16-bit PCM, 44.1 kHz)."""
    return _copy_artifact(CARRIERS_DIR / "music.wav", tmp_path)


@pytest.fixture
def payload_tiny(tmp_path: Path) -> Path:
    """Very small payload (100 bytes of text)."""
    return _copy_artifact(PAYLOADS_DIR / "tiny.txt", tmp_path)


@pytest.fixture
def payload_pdf(tmp_path: Path) -> Path:
    """Realistic payload — a PDF document."""
    return _copy_artifact(PAYLOADS_DIR / "secret.pdf", tmp_path)


@pytest.fixture
def payload_zip(tmp_path: Path) -> Path:
    """Realistic payload — a ZIP archive."""
    return _copy_artifact(PAYLOADS_DIR / "archive.zip", tmp_path)

@pytest.fixture
def random_image() -> np.ndarray:
    """Random RGB image, 64x64.

    Used in test_metrics.py. Will be replaced with png_medium.
    """
    rng = np.random.default_rng(seed=42)
    return rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8)


@pytest.fixture
def png_carrier(tmp_path: Path, random_image: np.ndarray) -> Path:
    """Generated PNG. Will be replaced with png_small."""
    path = tmp_path / "carrier.png"
    Image.fromarray(random_image).save(path)
    return path


@pytest.fixture
def small_payload(tmp_path: Path) -> Path:
    """200-byte payload. Will be replaced with payload_tiny."""
    path = tmp_path / "secret.bin"
    path.write_bytes(b"X" * 200)
    return path