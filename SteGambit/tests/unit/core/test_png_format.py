"""Unit/IO tests for PngFormat — png.py."""
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
    """Loading a PNG from a file."""

    def test_load_returns_ndarray(self, png_format, png_small):
        """load returns an np.ndarray."""
        arr = png_format.load(png_small)
        assert isinstance(arr, np.ndarray)

    def test_load_returns_3d_rgb(self, png_format, png_small):
        """A PNG (RGB) loads as a 3D ndarray with 3 channels."""
        arr = png_format.load(png_small)
        assert arr.ndim == 3
        assert arr.shape[2] == 3

    def test_load_dtype_is_uint8(self, png_format, png_small):
        """The result dtype is uint8."""
        arr = png_format.load(png_small)
        assert arr.dtype == np.uint8

    def test_load_missing_file_raises(self, png_format, tmp_path):
        """Negative case: a file that does not exist -> FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            png_format.load(tmp_path / "ghost.png")

    def test_load_corrupt_file_raises(self, png_format, tmp_path):
        """Negative case: a corrupted file -> an exception from PIL."""
        broken = tmp_path / "broken.png"
        broken.write_bytes(b"\x89PNG\r\n\x1a\nNOT_A_REAL_PNG")
        with pytest.raises(Exception):
            png_format.load(broken)

    def test_rgba_converts_to_rgb(self, png_format, tmp_path):
        """Property: an RGBA PNG is automatically converted to RGB."""
        rgba_path = tmp_path / "rgba.png"
        Image.new("RGBA", (10, 10), (255, 0, 0, 128)).save(rgba_path)
        arr = png_format.load(rgba_path)
        assert arr.shape[2] == 3


@pytest.mark.io
class TestSave:
    """Saving a PNG to a file."""

    def test_save_creates_file(self, png_format, rng, tmp_path):
        """save creates a file at the given path."""
        arr = rng.integers(0, 256, size=(20, 20, 3), dtype=np.uint8)
        out = tmp_path / "out.png"
        png_format.save(arr, out)
        assert out.exists()
        assert out.stat().st_size > 0


@pytest.mark.io
class TestRoundTrip:
    """save -> load restores the array byte for byte."""

    def test_round_trip_random_image(self, png_format, rng, tmp_path):
        """PNG is lossless; the round-trip must be exact."""
        original = rng.integers(0, 256, size=(30, 40, 3), dtype=np.uint8)
        out = tmp_path / "rt.png"
        png_format.save(original, out)
        loaded = png_format.load(out)
        np.testing.assert_array_equal(original, loaded)

    def test_round_trip_preserves_shape(self, png_format, rng, tmp_path):
        """shape is preserved on round-trip."""
        original = rng.integers(0, 256, size=(15, 25, 3), dtype=np.uint8)
        out = tmp_path / "rt.png"
        png_format.save(original, out)
        loaded = png_format.load(out)
        assert loaded.shape == original.shape


class TestMagic:
    """Magic property."""

    def test_magic_is_png_signature(self, png_format):
        """magic matches the start of the ISO PNG signature."""
        assert png_format.magic == b"\x89PNG"