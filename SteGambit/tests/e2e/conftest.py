"""Local fixtures for E2E tests.

Contains:
    - Carriers for load tests (large PNG/WAV/JPEG from artifacts/).
    - Generators of payloads of arbitrary size (on the fly, not committed to the repo).
    - Helpers for checking byte equality of files.
    - A corrupted PNG for boundary tests.

Architectural principle:
    Fixtures in this conftest do NOT duplicate fixtures from tests/conftest.py.
    Only what E2E specifically needs lives here.
"""
import shutil
import hashlib
from pathlib import Path

import numpy as np
import pytest


ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
CARRIERS_DIR = ARTIFACTS_DIR / "carriers"


def _copy_artifact(src: Path, tmp_path: Path) -> Path:
    """Copies an artifact into tmp_path. If the file is missing, skips the test
    with a clear message instead of failing with FileNotFoundError."""
    if not src.exists():
        pytest.skip(
            f"Артефакт отсутствует: {src.name}. "
            f"См. tests/artifacts/README.md для инструкций по добавлению."
        )
    dst = tmp_path / src.name
    shutil.copy2(src, dst)
    return dst


@pytest.fixture
def png_large(tmp_path: Path) -> Path:
    """Large PNG (20 MB, 6K×6K RGB). Carrier for PNG load tests."""
    return _copy_artifact(CARRIERS_DIR / "large.png", tmp_path)


@pytest.fixture
def wav_long(tmp_path: Path) -> Path:
    """Long WAV (68 MB, 16-bit/44.1kHz). Carrier for WAV load tests."""
    return _copy_artifact(CARRIERS_DIR / "long.wav", tmp_path)


@pytest.fixture
def jpeg_large(tmp_path: Path) -> Path:
    """Large JPEG (8 MB, high resolution). Carrier for JPEG load tests."""
    return _copy_artifact(CARRIERS_DIR / "large_photo.jpg", tmp_path)


def _make_random_payload(path: Path, size_bytes: int, seed: int = 42) -> Path:
    """Creates a fixed-size file filled with pseudorandom
    bytes. Deterministic via seed so the diff is reproducible.
    """
    rng = np.random.default_rng(seed=seed)
    path.write_bytes(rng.bytes(size_bytes))
    return path


@pytest.fixture
def payload_100kb(tmp_path: Path) -> Path:
    """100 KB of random bytes."""
    return _make_random_payload(tmp_path / "payload_100kb.bin", 100 * 1024)

@pytest.fixture
def payload_250kb(tmp_path: Path) -> Path:
    """250 KB of random bytes. A realistic payload for a PNG load on a 3.5MB carrier."""
    return _make_random_payload(tmp_path / "payload_250kb.bin", 250 * 1024)


@pytest.fixture
def payload_350kb(tmp_path: Path) -> Path:
    """350 KB of random bytes. At the capacity boundary for a PNG load."""
    return _make_random_payload(tmp_path / "payload_350kb.bin", 350 * 1024)


@pytest.fixture
def payload_300kb(tmp_path: Path) -> Path:
    """300 KB of random bytes. For a heavy JPEG case."""
    return _make_random_payload(tmp_path / "payload_300kb.bin", 300 * 1024)


@pytest.fixture
def payload_500kb(tmp_path: Path) -> Path:
    """500 KB of random bytes. A realistic ceiling for a JPEG load."""
    return _make_random_payload(tmp_path / "payload_500kb.bin", 500 * 1024)

@pytest.fixture
def payload_750kb(tmp_path: Path) -> Path:
    """750 KB of random bytes. At the capacity boundary for a WAV load."""
    return _make_random_payload(tmp_path / "payload_750kb.bin", 750 * 1024)

@pytest.fixture
def payload_1mb(tmp_path: Path) -> Path:
    """1 MB of random bytes."""
    return _make_random_payload(tmp_path / "payload_1mb.bin", 1024 * 1024)


@pytest.fixture
def payload_2mb(tmp_path: Path) -> Path:
    """2 MB of random bytes. A realistic maximum for a WAV load."""
    return _make_random_payload(tmp_path / "payload_2mb.bin", 2 * 1024 * 1024)


@pytest.fixture
def payload_5mb(tmp_path: Path) -> Path:
    """5 MB of random bytes. A heavy payload for a PNG load."""
    return _make_random_payload(tmp_path / "payload_5mb.bin", 5 * 1024 * 1024)


@pytest.fixture
def corrupted_png(tmp_path: Path, png_medium: Path) -> Path:
    """PNG with corrupted contents.

    The PNG signature at the start stays valid — FormatIdentifier will accept it,
    but the IDAT chunks are damaged. Used to check graceful failure on load/extraction.
    """
    data = bytearray(png_medium.read_bytes())
    if len(data) < 200:
        pytest.skip("png_medium слишком мал для коррупции, нужен ≥200 байт.")
    # Corrupt everything else from offset 100 through 200.
    for i in range(100, 200):
        data[i] = 0xFF
    corrupted = tmp_path / "corrupted.png"
    corrupted.write_bytes(bytes(data))
    return corrupted


@pytest.fixture
def random_garbage_file(tmp_path: Path) -> Path:
    """A file of random bytes with no valid format signature.

    Used to check FormatIdentifier — it must raise ValueError.
    """
    path = tmp_path / "garbage.dat"
    path.write_bytes(b"\x00\x01\x02\x03" + b"X" * 1000)
    return path


def assert_files_byte_equal(actual: Path, expected: Path) -> None:
    """Compares two files byte by byte."""
    actual_bytes = actual.read_bytes()
    expected_bytes = expected.read_bytes()

    if actual_bytes == expected_bytes:
        return

    actual_hash = hashlib.sha256(actual_bytes).hexdigest()[:16]
    expected_hash = hashlib.sha256(expected_bytes).hexdigest()[:16]
    pytest.fail(
        f"Файлы не совпадают.\n"
        f"  Actual:   {actual.name} ({len(actual_bytes):,} bytes, sha256={actual_hash})\n"
        f"  Expected: {expected.name} ({len(expected_bytes):,} bytes, sha256={expected_hash})"
    )


def assert_bytes_equal_to_file(actual_bytes: bytes, expected_path: Path) -> None:
    """Same as assert_files_byte_equal, but one of the arguments is bytes."""
    expected_bytes = expected_path.read_bytes()
    if actual_bytes == expected_bytes:
        return
    actual_hash = hashlib.sha256(actual_bytes).hexdigest()[:16]
    expected_hash = hashlib.sha256(expected_bytes).hexdigest()[:16]
    pytest.fail(
        f"Байты не совпадают с файлом.\n"
        f"  Actual:   {len(actual_bytes):,} bytes, sha256={actual_hash}\n"
        f"  Expected: {expected_path.name} ({len(expected_bytes):,} bytes, sha256={expected_hash})"
    )