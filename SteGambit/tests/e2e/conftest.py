"""Локальные фикстуры для E2E-тестов.

Содержит:
    - Носители для нагрузочных тестов (large PNG/WAV/JPEG из artifacts/).
    - Генераторы payload'ов произвольного размера (на лету, без коммита в репо).
    - Хелперы для проверки байтового равенства файлов.
    - Битый PNG для граничных тестов.

Архитектурный принцип:
    Фикстуры этого conftest НЕ дублируют фикстуры из tests/conftest.py.
    Здесь только то, что нужно именно для E2E
"""
import shutil
import hashlib
from pathlib import Path

import numpy as np
import pytest


ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
CARRIERS_DIR = ARTIFACTS_DIR / "carriers"


def _copy_artifact(src: Path, tmp_path: Path) -> Path:
    """Копирует артефакт в tmp_path. Если файла нет — пропускает тест
    с понятным сообщением, а не падает с FileNotFoundError."""
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
    """Большой PNG (20 МБ, 6K×6K RGB). Носитель для PNG load-тестов."""
    return _copy_artifact(CARRIERS_DIR / "large.png", tmp_path)


@pytest.fixture
def wav_long(tmp_path: Path) -> Path:
    """Длинный WAV (68 МБ, 16-bit/44.1kHz). Носитель для WAV load-тестов."""
    return _copy_artifact(CARRIERS_DIR / "long.wav", tmp_path)


@pytest.fixture
def jpeg_large(tmp_path: Path) -> Path:
    """Большой JPEG (8 МБ, высокое разрешение). Носитель для JPEG load-тестов."""
    return _copy_artifact(CARRIERS_DIR / "large_photo.jpg", tmp_path)


def _make_random_payload(path: Path, size_bytes: int, seed: int = 42) -> Path:
    """Создаёт файл фиксированного размера, заполненный псевдослучайными
    байтами. Детерминирован через seed для воспроизводимости diff'а.
    """
    rng = np.random.default_rng(seed=seed)
    path.write_bytes(rng.bytes(size_bytes))
    return path


@pytest.fixture
def payload_100kb(tmp_path: Path) -> Path:
    """100 КБ случайных байт."""
    return _make_random_payload(tmp_path / "payload_100kb.bin", 100 * 1024)

@pytest.fixture
def payload_250kb(tmp_path: Path) -> Path:
    """250 КБ случайных байт. Реалистичный payload для PNG-load на 3.5MB носителе."""
    return _make_random_payload(tmp_path / "payload_250kb.bin", 250 * 1024)


@pytest.fixture
def payload_350kb(tmp_path: Path) -> Path:
    """350 КБ случайных байт. На границе capacity для PNG-load."""
    return _make_random_payload(tmp_path / "payload_350kb.bin", 350 * 1024)


@pytest.fixture
def payload_300kb(tmp_path: Path) -> Path:
    """300 КБ случайных байт. Для тяжёлого JPEG-кейса."""
    return _make_random_payload(tmp_path / "payload_300kb.bin", 300 * 1024)


@pytest.fixture
def payload_500kb(tmp_path: Path) -> Path:
    """500 КБ случайных байт. Реалистичный потолок для JPEG-load."""
    return _make_random_payload(tmp_path / "payload_500kb.bin", 500 * 1024)

@pytest.fixture
def payload_750kb(tmp_path: Path) -> Path:
    """750 КБ случайных байт. На границе capacity для WAV-load."""
    return _make_random_payload(tmp_path / "payload_750kb.bin", 750 * 1024)

@pytest.fixture
def payload_1mb(tmp_path: Path) -> Path:
    """1 МБ случайных байт."""
    return _make_random_payload(tmp_path / "payload_1mb.bin", 1024 * 1024)


@pytest.fixture
def payload_2mb(tmp_path: Path) -> Path:
    """2 МБ случайных байт. Реалистичный максимум для WAV-load."""
    return _make_random_payload(tmp_path / "payload_2mb.bin", 2 * 1024 * 1024)


@pytest.fixture
def payload_5mb(tmp_path: Path) -> Path:
    """5 МБ случайных байт. Тяжёлый payload для PNG-load."""
    return _make_random_payload(tmp_path / "payload_5mb.bin", 5 * 1024 * 1024)


@pytest.fixture
def corrupted_png(tmp_path: Path, png_medium: Path) -> Path:
    """PNG с порченым содержимым.

    Сигнатура PNG в начале остаётся валидной - FormatIdentifier пропустит,
    но IDAT-чанки повреждены. Используется для проверки graceful failure при попытке загрузки/извлечения.
    """
    data = bytearray(png_medium.read_bytes())
    if len(data) < 200:
        pytest.skip("png_medium слишком мал для коррупции, нужен ≥200 байт.")
    # портим всё остальное от смещения 100 до 200.
    for i in range(100, 200):
        data[i] = 0xFF
    corrupted = tmp_path / "corrupted.png"
    corrupted.write_bytes(bytes(data))
    return corrupted


@pytest.fixture
def random_garbage_file(tmp_path: Path) -> Path:
    """Файл со случайными байтами без валидной сигнатуры формата.

    Используется для проверки FormatIdentifier - должен бросать ValueError.
    """
    path = tmp_path / "garbage.dat"
    path.write_bytes(b"\x00\x01\x02\x03" + b"X" * 1000)
    return path


def assert_files_byte_equal(actual: Path, expected: Path) -> None:
    """Сравнивает два файла побайтово."""
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
    """То же что assert_files_byte_equal, но один из аргументов - bytes."""
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