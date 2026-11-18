"""Unit tests for StegoService in stego_service.py.

Tests isolate the service from core components via mocks. The full cycle is covered in test_smoke_pipeline.py — here we check
only orchestration, branching, and error handling.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from stegambit.core.exceptions import CompatibilityError
from stegambit.models.dto import StegoTaskRequest, CapacityReport
from stegambit.services.stego_service import StegoService
from stegambit.core.exceptions import InvalidFrameError


@pytest.fixture
def service():
    return StegoService()


@pytest.fixture
def png_request(tmp_path):
    """Minimal valid StegoTaskRequest for PNG.

    Creates stub files only so __post_init__ validation passes.
    The contents are NOT decoded as PNG. Tests that need real
    PNG decoding use the global png_medium fixture from conftest.py.
    """
    carrier = tmp_path / "carrier.png"
    payload = tmp_path / "payload.bin"
    carrier.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    payload.write_bytes(b"X" * 100)

    return StegoTaskRequest(
        carrier_path=carrier,
        payload_path=payload,
        output_path=tmp_path / "stego.png",
        password="secret",
    )

@pytest.fixture
def payload_file(tmp_path):
    p = tmp_path / "payload.bin"
    p.write_bytes(b"X" * 100)
    return p

@pytest.fixture
def carrier_png(tmp_path):
    """Path to a fake PNG file for DTO validation.

    Contents are only the PNG magic bytes, not a valid PNG for decoding.
    Used in analyze_capacity tests where PngFormat is mocked.
    """
    path = tmp_path / "carrier.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return path

@pytest.fixture
def mock_png_handler():
    """Mock PngFormat class that returns a stub ndarray."""
    handler_instance = MagicMock()
    handler_instance.load.return_value = np.zeros(100_000, dtype=np.uint8)
    handler_cls = MagicMock(return_value=handler_instance)
    return handler_cls, handler_instance


class TestAntiConversionPolicy:
    """Anti-conversion policy: the carrier format must match the extension of the output."""

    def test_png_carrier_to_jpeg_output_raises(self, service, png_request, tmp_path):
        """Negative case: PNG → .jpeg is forbidden."""
        modified = StegoTaskRequest(
            carrier_path=png_request.carrier_path,
            payload_path=png_request.payload_path,
            output_path=tmp_path / "stego.jpeg",
            password=png_request.password,
        )
        with patch.object(service._identifier, "identify", return_value="PNG"):
            with pytest.raises(CompatibilityError, match="анти-конверсии"):
                service.hide_data(modified)

    def test_jpeg_carrier_to_png_output_raises(self, service, tmp_path):
        """Negative case: JPEG → .png is forbidden."""
        carrier = tmp_path / "carrier.jpg"
        payload = tmp_path / "payload.bin"
        carrier.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
        payload.write_bytes(b"data")

        request = StegoTaskRequest(
            carrier_path=carrier,
            payload_path=payload,
            output_path=tmp_path / "stego.png",
            password="x",
        )
        with patch.object(service._identifier, "identify", return_value="JPEG"):
            with pytest.raises(CompatibilityError, match="анти-конверсии"):
                service.hide_data(request)

    @pytest.mark.parametrize("fmt, ext", [
        ("PNG", ".png"),
        ("JPEG", ".jpg"),
        ("JPEG", ".jpeg"),
        ("WAV", ".wav"),
    ])
    def test_matching_format_and_extension_pass_policy(self, service, fmt, ext, tmp_path):
        """Positive case: a matching format and extension passes the policy.

        We check that the error is NOT caused by anti-conversion, but later by the absence of a real file.
        """
        carrier = tmp_path / f"carrier{ext}"
        payload = tmp_path / "payload.bin"
        carrier.write_bytes(b"fake content")
        payload.write_bytes(b"data")

        request = StegoTaskRequest(
            carrier_path=carrier,
            payload_path=payload,
            output_path=tmp_path / f"stego{ext}",
            password="x",
        )
        with patch.object(service._identifier, "identify", return_value=fmt):
            with pytest.raises(Exception) as exc_info:
                service.hide_data(request)
            assert "анти-конверсии" not in str(exc_info.value)


class TestUnsupportedFormat:
    """Negative case: format is not in _FORMAT_REGISTRY."""

    def test_hide_unsupported_format_raises(self, service, tmp_path):
        carrier = tmp_path / "x.bmp"
        payload = tmp_path / "p.bin"
        carrier.write_bytes(b"BM" + b"\x00" * 100)
        payload.write_bytes(b"data")

        request = StegoTaskRequest(
            carrier_path=carrier,
            payload_path=payload,
            output_path=tmp_path / "out.bmp",
            password="x",
        )
        with patch.object(service._identifier, "identify", return_value="BMP"):
            with pytest.raises(CompatibilityError, match="Нарушение анти-конверсии"):
                service.hide_data(request)

    def test_extract_unsupported_format_raises(self, service, tmp_path):
        carrier = tmp_path / "x.bmp"
        payload = tmp_path / "p.bin"
        carrier.write_bytes(b"BM" + b"\x00" * 100)
        payload.write_bytes(b"data")

        request = StegoTaskRequest(
            carrier_path=carrier,
            payload_path=payload,
            output_path=tmp_path / "out.bin",
            password="x",
        )
        with patch.object(service._identifier, "identify", return_value="BMP"):
            with pytest.raises(CompatibilityError, match="не поддержан"):
                service.extract_data(request)


class TestExtractDataErrors:
    """Negative cases for extract_data."""

    def test_missing_magic_raises_invalid_frame(self, service, png_request):
        """Negative case: a header without MAGIC -> InvalidFrameError."""
        with patch.object(service._identifier, "identify", return_value="PNG"), \
             patch("stegambit.services.stego_service._FORMAT_REGISTRY") as mock_registry:
            mock_handler = MagicMock()
            mock_handler.load.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
            mock_registry.__getitem__.return_value = lambda: mock_handler
            mock_registry.__contains__.return_value = True

            with patch.object(service._processor, "extract", return_value=b"\x00" * 57), \
                 patch.object(service._lsb_spreader, "generate_coords",
                              return_value=np.arange(10000, dtype=np.int64)):
                with pytest.raises(InvalidFrameError, match="MAGIC"):
                    service.extract_data(png_request)


class TestGetAlgorithmForFormat:
    """The get_algorithm_for_format helper — a decision table."""

    @pytest.mark.parametrize("fmt, expected", [
        ("PNG", "LSB"),
        ("WAV", "LSB"),
        ("JPEG", "DCT"),
    ])
    def test_known_formats(self, service, fmt, expected):
        """Equivalence: each known format maps to its own algorithm."""
        assert service.get_algorithm_for_format(fmt) == expected

    @pytest.mark.parametrize("unknown", ["BMP", "GIF", "", "png", "unknown"])
    def test_unknown_format_returns_question_mark(self, service, unknown):
        """Negative case: an unknown format."""
        assert service.get_algorithm_for_format(unknown) == "?"


class TestIdentifyFormat:
    """Public wrapper over FormatIdentifier.identify."""

    def test_delegates_to_identifier(self, service, tmp_path):
        """identify_format delegates to FormatIdentifier."""
        fake_path = tmp_path / "test.png"
        with patch.object(service._identifier, "identify", return_value="PNG") as mock_id:
            result = service.identify_format(fake_path)
            assert result == "PNG"
            mock_id.assert_called_once_with(fake_path)


class TestBuildPool:
    """Tests of private _build_pool: LSB and DCT branching."""

    def test_lsb_pool_is_arange(self, service):
        """The LSB pool is np.arange(container.size)."""
        container = np.zeros((10, 10, 3), dtype=np.uint8)
        pool, processor = service._build_pool("LSB", container)
        np.testing.assert_array_equal(pool, np.arange(container.size))
        assert processor is service._processor

    def test_dct_pool_delegates_to_dct_processor(self, service):
        """The DCT pool is built via DctProcessor.get_embeddable_positions."""
        fake_container = MagicMock()
        expected_pool = np.array([10, 20, 30], dtype=np.int64)
        with patch.object(service._dct, "get_embeddable_positions",
                          return_value=expected_pool) as mock_get:
            pool, processor = service._build_pool("DCT", fake_container)
            mock_get.assert_called_once_with(fake_container)
            np.testing.assert_array_equal(pool, expected_pool)
            assert processor is service._dct

    def test_unknown_processor_kind_raises(self, service):
        """Negative case: an unknown processor kind raises RuntimeError."""
        with pytest.raises(RuntimeError, match="Неизвестный тип процессора"):
            service._build_pool("UNKNOWN", np.zeros(10))


class TestAnalyzeCapacity:
    """Tests of analyze_capacity — a preliminary capacity estimate without hiding."""

    def test_returns_capacity_report(self, service, payload_file, carrier_png, tmp_path, mock_png_handler):
        """analyze_capacity returns a CapacityReport."""
        png_cls, _ = mock_png_handler
        request = StegoTaskRequest(
            carrier_path=carrier_png,
            payload_path=payload_file,
            output_path=tmp_path / "out.png",
            password="x",
        )
        with patch.object(service._identifier, "identify", return_value="PNG"), \
             patch.dict("stegambit.services.stego_service._FORMAT_REGISTRY", {"PNG": png_cls}), \
             patch.object(service._lsb_spreader, "get_max_capacity_bits", return_value=80000):

            report = service.analyze_capacity(request)
            assert isinstance(report, CapacityReport)

    def test_fits_true_when_capacity_sufficient(self, service, payload_file, carrier_png, tmp_path, mock_png_handler):
        """Positive case: capacity > required -> fits=True."""
        png_cls, _ = mock_png_handler
        request = StegoTaskRequest(
            carrier_path=carrier_png,
            payload_path=payload_file,
            output_path=tmp_path / "out.png",
            password="x",
        )
        with patch.object(service._identifier, "identify", return_value="PNG"), \
             patch.dict("stegambit.services.stego_service._FORMAT_REGISTRY", {"PNG": png_cls}), \
             patch.object(service._lsb_spreader, "get_max_capacity_bits", return_value=80_000):

            report = service.analyze_capacity(request)
            assert report.fits is True
            assert report.format == "PNG"
            assert report.algorithm == "LSB"

    def test_fits_false_on_overflow(self, service, payload_file, carrier_png, tmp_path, mock_png_handler):
        """Negative case: required > capacity -> fits=False."""
        png_cls, handler = mock_png_handler
        handler.load.return_value = np.zeros(100, dtype=np.uint8)
        request = StegoTaskRequest(
            carrier_path=carrier_png,
            payload_path=payload_file,
            output_path=tmp_path / "out.png",
            password="x",
        )
        with patch.object(service._identifier, "identify", return_value="PNG"), \
             patch.dict("stegambit.services.stego_service._FORMAT_REGISTRY", {"PNG": png_cls}), \
             patch.object(service._lsb_spreader, "get_max_capacity_bits", return_value=100):

            report = service.analyze_capacity(request)
            assert report.fits is False
            assert report.utilization_percent > 100.0

    def test_utilization_zero_when_capacity_is_zero(self, service, payload_file, carrier_png, tmp_path, mock_png_handler):
        """Boundary case: capacity=0 -> utilization=0 — guards against division by zero."""
        png_cls, handler = mock_png_handler
        handler.load.return_value = np.zeros(10, dtype=np.uint8)
        request = StegoTaskRequest(
            carrier_path=carrier_png,
            payload_path=payload_file,
            output_path=tmp_path / "out.png",
            password="x",
        )
        with patch.object(service._identifier, "identify", return_value="PNG"), \
             patch.dict("stegambit.services.stego_service._FORMAT_REGISTRY", {"PNG": png_cls}), \
             patch.object(service._lsb_spreader, "get_max_capacity_bits", return_value=0):

            report = service.analyze_capacity(request)
            assert report.utilization_percent == 0.0
            assert report.fits is False

    def test_jpeg_delegates_to_dct_spreader(self, service, payload_file, tmp_path):
        """For JPEG, capacity is computed via DctSpreader."""
        carrier = tmp_path / "c.jpg"
        carrier.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

        request = StegoTaskRequest(
            carrier_path=carrier,
            payload_path=payload_file,
            output_path=tmp_path / "out.jpg",
            password="x",
        )
        fake_container = MagicMock()
        jpeg_handler = MagicMock()
        jpeg_handler.load.return_value = fake_container
        jpeg_cls = MagicMock(return_value=jpeg_handler)

        with patch.object(service._identifier, "identify", return_value="JPEG"), \
             patch.dict("stegambit.services.stego_service._FORMAT_REGISTRY", {"JPEG": jpeg_cls}), \
             patch.object(service._dct_spreader, "get_max_capacity_bits",
                          return_value=50_000) as mock_get:

            report = service.analyze_capacity(request)
            mock_get.assert_called_once_with(fake_container)
            assert report.algorithm == "DCT"
            assert report.capacity_bits == 50_000

    def test_unsupported_format_raises(self, service, payload_file, tmp_path):
        """Negative case: an unsupported format -> CompatibilityError."""
        carrier = tmp_path / "c.bmp"
        carrier.write_bytes(b"BM" + b"\x00" * 100)

        request = StegoTaskRequest(
            carrier_path=carrier,
            payload_path=payload_file,
            output_path=tmp_path / "out.bmp",
            password="x",
        )
        with patch.object(service._identifier, "identify", return_value="BMP"):
            with pytest.raises(CompatibilityError, match="не поддержан"):
                service.analyze_capacity(request)

    def test_required_bits_includes_header_and_payload(self, service, payload_file, carrier_png, tmp_path, mock_png_handler):
        """required_bits = (header + payload) * 8."""
        from stegambit.core.crypto.engine import CryptoEngine
        png_cls, handler = mock_png_handler
        handler.load.return_value = np.zeros(1_000_000, dtype=np.uint8)
        request = StegoTaskRequest(
            carrier_path=carrier_png,
            payload_path=payload_file,
            output_path=tmp_path / "out.png",
            password="x",
        )
        with patch.object(service._identifier, "identify", return_value="PNG"), \
             patch.dict("stegambit.services.stego_service._FORMAT_REGISTRY", {"PNG": png_cls}), \
             patch.object(service._lsb_spreader, "get_max_capacity_bits", return_value=1_000_000):

            report = service.analyze_capacity(request)
            expected = (CryptoEngine.header_size() + 100) * 8
            assert report.required_bits == expected
            assert report.payload_size_bytes == 100
            assert report.header_size_bytes == CryptoEngine.header_size()