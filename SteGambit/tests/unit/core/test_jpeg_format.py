"""Unit/IO тесты для JpegFormat и JpegContainer - jpeg.py.

Тесты используют реальный jpeglib для загрузки и сохранения. Если артефакта нет - тест пропускается через pytest.skip.
"""
from pathlib import Path

import numpy as np
import pytest
import shutil

from stegambit.core.formats.jpeg import JpegFormat, JpegContainer


@pytest.fixture
def jpeg_format():
    return JpegFormat()



@pytest.mark.io
class TestLoad:

    def test_load_returns_container(self, jpeg_format, jpeg_carrier):
        """load возвращает JpegContainer."""
        container = jpeg_format.load(jpeg_carrier)
        assert isinstance(container, JpegContainer)

    def test_container_has_coef_arrays(self, jpeg_format, jpeg_carrier):
        """container.coef_arrays - непустой список ndarray."""
        container = jpeg_format.load(jpeg_carrier)
        assert len(container.coef_arrays) >= 1
        for arr in container.coef_arrays:
            assert isinstance(arr, np.ndarray)

    def test_y_channel_is_int16(self, jpeg_format, jpeg_carrier):
        """Y-канал - int16."""
        container = jpeg_format.load(jpeg_carrier)
        assert container.coef_arrays[0].dtype == np.int16

    def test_y_channel_shape_is_blocks_8x8(self, jpeg_format, jpeg_carrier):
        """Y-канал (Hb, Wb, 8, 8)."""
        container = jpeg_format.load(jpeg_carrier)
        y = container.coef_arrays[0]
        assert y.ndim == 4
        assert y.shape[2] == 8
        assert y.shape[3] == 8

    def test_dimensions_are_set(self, jpeg_format, jpeg_carrier):
        """container.dimensions - кортеж (H, W) > 0."""
        container = jpeg_format.load(jpeg_carrier)
        assert isinstance(container.dimensions, tuple)
        assert len(container.dimensions) == 2
        assert all(d > 0 for d in container.dimensions)

    def test_color_jpeg_has_three_channels(self, jpeg_format,jpeg_carrier):
        """Эквивалентность: цветной JPEG - 3 канала (Y, Cb, Cr)."""
        container = jpeg_format.load(jpeg_carrier)
        assert len(container.coef_arrays) == 3

    def test_load_missing_file_raises(self, jpeg_format, tmp_path):
        """Негативный кейз: несуществующий файл."""
        with pytest.raises((FileNotFoundError, Exception)):
            jpeg_format.load(tmp_path / "ghost.jpg")


@pytest.mark.io
class TestSave:

    def test_save_creates_file(self, jpeg_format, tmp_path, jpeg_carrier):
        """save создаёт JPEG-файл."""
        container = jpeg_format.load(jpeg_carrier)
        out = tmp_path / "out.jpg"
        jpeg_format.save(container, out)
        assert out.exists()
        assert out.stat().st_size > 0


@pytest.mark.io
class TestRoundTrip:

    def test_round_trip_preserves_coefficients(self, jpeg_format, tmp_path, jpeg_carrier):
        """Неизменённые DCT-коэффициенты восстанавливаются точно."""
        original = jpeg_format.load(jpeg_carrier)
        y_before = original.coef_arrays[0].copy()

        out = tmp_path / "rt.jpg"
        jpeg_format.save(original, out)
        reloaded = jpeg_format.load(out)

        np.testing.assert_array_equal(reloaded.coef_arrays[0], y_before)

    def test_round_trip_preserves_modification(self, jpeg_format, tmp_path, jpeg_carrier):
        """Модификация Y - save - load — модификации сохранены."""
        container = jpeg_format.load(jpeg_carrier)
        container.coef_arrays[0][0, 0, 1, 1] ^= 1

        y_modified = container.coef_arrays[0].copy()
        out = tmp_path / "mod.jpg"
        jpeg_format.save(container, out)
        reloaded = jpeg_format.load(out)

        np.testing.assert_array_equal(reloaded.coef_arrays[0], y_modified)

    def test_round_trip_preserves_dimensions(self, jpeg_format, tmp_path, jpeg_carrier):
        """Размеры сохраняются."""
        original = jpeg_format.load(jpeg_carrier)
        out = tmp_path / "rt.jpg"
        jpeg_format.save(original, out)
        reloaded = jpeg_format.load(out)
        assert reloaded.dimensions == original.dimensions