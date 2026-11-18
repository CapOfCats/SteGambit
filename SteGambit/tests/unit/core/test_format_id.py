"""Unit tests for FormatIdentifier.

Test data:
    * Valid files — from tests/artifacts/, read-only.
    * Invalid files — generated in tmp_path.
"""
from pathlib import Path
import pytest
from stegambit.core.common.format_id import FormatIdentifier, get_default_extension


ARTIFACTS = Path(__file__).resolve().parents[2] / "artifacts" / "carriers"


@pytest.fixture
def identifier():
    return FormatIdentifier()


class TestIdentifyValidFiles:
    """Positive scenarios: each supported format is its own equivalence class."""

    @pytest.mark.parametrize("filename, expected_fmt", [
        ("small.png", "PNG"),
        ("photo.jpg", "JPEG"),
        ("music.wav", "WAV"),
    ])
    def test_identify_real_artifact(self, identifier, filename, expected_fmt):
        path = ARTIFACTS / filename
        assert identifier.identify(path) == expected_fmt


class TestIdentifyInvalidFiles:
    """Negative scenarios for identify() — every exception from the documentation."""

    def test_file_not_found_raises(self, identifier, tmp_path):
        non_existent = tmp_path / "ghost.png"
        with pytest.raises(FileNotFoundError):
            identifier.identify(non_existent)

    def test_garbage_bytes_raise_value_error(self, identifier, tmp_path):
        """A file of random bytes — the format is unrecognizable."""
        broken = tmp_path / "garbage.bin"
        broken.write_bytes(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b")
        with pytest.raises(ValueError, match="Unsupported or unknown format"):
            identifier.identify(broken)

    def test_riff_but_not_wave_raises(self, identifier, tmp_path):
        """RIFF is a container. We check the guard against AVI/WebP disguised as WAV."""
        fake_avi = tmp_path / "fake.wav"
        fake_avi.write_bytes(b"RIFF\x00\x00\x00\x00AVI \x00\x00")
        with pytest.raises(ValueError, match="RIFF контейнер не является WAVE"):
            identifier.identify(fake_avi)

    def test_empty_file_raises(self, identifier, tmp_path):
        """An empty file — the header is empty, magic does not match."""
        empty = tmp_path / "empty.bin"
        empty.write_bytes(b"")
        with pytest.raises(ValueError, match="Unsupported or unknown format"):
            identifier.identify(empty)


class TestErrorMessages:
    """UX contract: identify() appends the file name to the error, identify_bytes does not."""

    def test_identify_appends_filename_to_error(self, identifier, tmp_path):
        broken = tmp_path / "weird_name_42.bin"
        broken.write_bytes(b"NOT_A_VALID_HEADER!!")
        with pytest.raises(ValueError, match="weird_name_42.bin"):
            identifier.identify(broken)

    def test_identify_bytes_does_not_include_filename(self, identifier):
        """identify_bytes works on a buffer — no file name."""
        with pytest.raises(ValueError) as exc_info:
            identifier.identify_bytes(b"NOT_VALID_DATA")
        assert ".bin" not in str(exc_info.value)
        assert ".png" not in str(exc_info.value)


class TestIdentifyBytes:
    """Tests for identify_bytes."""

    @pytest.mark.parametrize("header, expected_fmt", [
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 4, "PNG"),
        (b"\xff\xd8\xff\xe0" + b"\x00" * 8, "JPEG"),
        (b"RIFF\x00\x00\x00\x00WAVE", "WAV"),
    ])
    def test_valid_magic_bytes(self, identifier, header, expected_fmt):
        assert identifier.identify_bytes(header) == expected_fmt

    def test_unknown_magic_raises(self, identifier):
        with pytest.raises(ValueError, match="Unsupported"):
            identifier.identify_bytes(b"NOT_A_MAGIC_BYTE_SEQUENCE")

    def test_riff_without_wave_raises(self, identifier):
        with pytest.raises(ValueError, match="RIFF"):
            identifier.identify_bytes(b"RIFF\x00\x00\x00\x00AVI ")


class TestIdentifyBytesBoundary:
    """Boundary tests of identify_bytes: what happens at the edges of 0, 4, 8, 11, 12, 13 bytes."""

    def test_empty_buffer_raises(self, identifier):
        """0 bytes — the smallest edge of the boundary."""
        with pytest.raises(ValueError):
            identifier.identify_bytes(b"")

    def test_short_buffer_padded_with_zeros(self, identifier):
        """A short 8-byte magic — the function must pad with zeros to 12 and recognize it."""
        png_magic_only = b"\x89PNG\r\n\x1a\n"
        assert identifier.identify_bytes(png_magic_only) == "PNG"

    def test_exact_read_bytes_size(self, identifier):
        """Exactly 12 bytes — the size from the constant. Zero padding is not needed."""
        data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00"
        assert len(data) == 12
        assert identifier.identify_bytes(data) == "PNG"

    def test_one_byte_short_of_riff_subtype(self, identifier):
        """RIFF + 7 bytes — not enough to check the WAVE subtype. Padded with zeros -> not WAVE."""
        data = b"RIFF\x00\x00\x00"
        with pytest.raises(ValueError, match="RIFF"):
            identifier.identify_bytes(data)

    def test_buffer_larger_than_read_bytes_truncated(self, identifier):
        """A buffer longer than 12 bytes — only the first 12 are taken, the rest is ignored."""
        long_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00" + b"GARBAGE_TAIL" * 100
        assert identifier.identify_bytes(long_data) == "PNG"



class TestGetDefaultExtension:
    """Test of the format-mapping helper."""

    @pytest.mark.parametrize("fmt, expected_ext", [
        ("PNG", ".png"),
        ("JPEG", ".jpg"),
        ("WAV", ".wav"),
    ])
    def test_known_formats(self, fmt, expected_ext):
        assert get_default_extension(fmt) == expected_ext

    @pytest.mark.parametrize("unknown_fmt", [
        "UNKNOWN",
        "TEXT",
        "PDF",
        "",
        "png", # lowercase is also treated as unknown; this check is required too
    ])
    def test_unknown_formats_default_to_bin(self, unknown_fmt):
        assert get_default_extension(unknown_fmt) == ".bin"