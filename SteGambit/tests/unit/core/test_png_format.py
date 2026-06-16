"""Unit/IO тесты для PngFormat - png.py."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from stegambit.core.formats.png import PngFormat


@pytest.fixture
def png_format():
    return PngFormat()


@pytest.mark.io
class TestLoad:
    """Загрузка PNG из файла."""

    def test_load_returns_ndarray(self, png_format, png_small):
        """load возвращает np.ndarray."""
        arr = png_format.load(png_small)
        assert isinstance(arr, np.ndarray)

    def test_load_returns_3d_rgb(self, png_format, png_small):
        """PNG (RGB) грузится как 3D ndarray с 3 каналами."""
        arr = png_format.load(png_small)
        assert arr.ndim == 3
        assert arr.shape[2] == 3

    def test_load_dtype_is_uint8(self, png_format, png_small):
        """dtype результата - uint8."""
        arr = png_format.load(png_small)
        assert arr.dtype == np.uint8

    def test_load_missing_file_raises(self, png_format, tmp_path):
        """Негативный кейз: несуществующий файл -> FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            png_format.load(tmp_path / "ghost.png")

    def test_load_corrupt_file_raises(self, png_format, tmp_path):
        """Негативный кейз: битый файл -> исключение от PIL."""
        broken = tmp_path / "broken.png"
        broken.write_bytes(b"\x89PNG\r\n\x1a\nNOT_A_REAL_PNG")
        with pytest.raises(Exception):
            png_format.load(broken)

    def test_rgba_converts_to_rgb(self, png_format, tmp_path):
        """Property: RGBA PNG автоматически конвертируется в RGB."""
        rgba_path = tmp_path / "rgba.png"
        Image.new("RGBA", (10, 10), (255, 0, 0, 128)).save(rgba_path)
        arr = png_format.load(rgba_path)
        assert arr.shape[2] == 3


@pytest.mark.io
class TestSave:
    """Сохранение PNG в файл."""

    def test_save_creates_file(self, png_format, rng, tmp_path):
        """save создаёт файл по указанному пути."""
        arr = rng.integers(0, 256, size=(20, 20, 3), dtype=np.uint8)
        out = tmp_path / "out.png"
        png_format.save(arr, out)
        assert out.exists()
        assert out.stat().st_size > 0


@pytest.mark.io
class TestRoundTrip:
    """save -> load восстанавливает массив байт-в-байт."""

    def test_round_trip_random_image(self, png_format, rng, tmp_path):
        """PNG - lossless, round-trip должен быть точным."""
        original = rng.integers(0, 256, size=(30, 40, 3), dtype=np.uint8)
        out = tmp_path / "rt.png"
        png_format.save(original, out)
        loaded = png_format.load(out)
        np.testing.assert_array_equal(original, loaded)

    def test_round_trip_preserves_shape(self, png_format, rng, tmp_path):
        """shape сохраняется при round-trip."""
        original = rng.integers(0, 256, size=(15, 25, 3), dtype=np.uint8)
        out = tmp_path / "rt.png"
        png_format.save(original, out)
        loaded = png_format.load(out)
        assert loaded.shape == original.shape


class TestMagic:
    """Magic property."""

    def test_magic_is_png_signature(self, png_format):
        """magic совпадает с началом ISO PNG сигнатурой."""
        assert png_format.magic == b"\x89PNG"