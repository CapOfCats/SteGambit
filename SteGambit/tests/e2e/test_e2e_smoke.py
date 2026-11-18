"""E2E smoke tests: fast black-box scenarios.

Principle:
    ↕ Only the public StegoService API: hide_data, extract_data / analyze_capacity / identify_format.
    ↕ Real artifacts from disk.
    ↕ Full roundtrip: hide -- file on disk -- extract -- diff against the original.
    ↕ Boundary conditions: capacity overflow, wrong password, corrupted files, anti-conversion violation.

Expected runtime: <30 seconds for the whole group.
"""
from pathlib import Path

import pytest

from stegambit.models.dto import StegoTaskRequest, QualityStatus
from stegambit.services.stego_service import StegoService
from stegambit.core.exceptions import (
    CompatibilityError, InvalidFrameError, InvalidPasswordError,
)

from .conftest import assert_bytes_equal_to_file


class TestE2EHappyPath:
    """Full roundtrip for every supported format."""

    def test_png_text_roundtrip(self, png_medium: Path, payload_tiny: Path, tmp_path: Path):
        """PNG + text payload: hide -> extract -> exact byte match."""
        service = StegoService()
        output = tmp_path / "stego.png"

        hide_req = StegoTaskRequest(
            carrier_path=png_medium,
            payload_path=payload_tiny,
            output_path=output,
            password="e2e_password",
        )
        hide_resp = service.hide_data(hide_req)

        assert hide_resp.success is True
        assert hide_resp.output_path.exists()
        assert hide_resp.metrics is not None

        extracted_target = tmp_path / "extracted.bin"
        extract_req = StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,  # ignored for extract
            output_path=extracted_target,
            password="e2e_password",
        )
        extract_resp = service.extract_data(extract_req)

        assert extract_resp.success is True
        assert extract_resp.output_path.exists()
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), payload_tiny)

    def test_wav_pdf_roundtrip(self, wav_carrier: Path, payload_pdf: Path, tmp_path: Path):
        """WAV + PDF payload: hide -- extract -- exact byte match."""
        service = StegoService()
        output = tmp_path / "stego.wav"

        hide_req = StegoTaskRequest(
            carrier_path=wav_carrier,
            payload_path=payload_pdf,
            output_path=output,
            password="wav_pwd",
        )
        hide_resp = service.hide_data(hide_req)
        assert hide_resp.success is True

        extract_req = StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="wav_pwd",
        )
        extract_resp = service.extract_data(extract_req)
        assert extract_resp.success is True
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), payload_pdf)

    def test_jpeg_text_roundtrip(self, jpeg_carrier: Path, payload_tiny: Path, tmp_path: Path):
        """JPEG + text payload: hide -- extract -- diff == 0."""
        service = StegoService()
        output = tmp_path / "stego.jpg"

        hide_req = StegoTaskRequest(
            carrier_path=jpeg_carrier,
            payload_path=payload_tiny,
            output_path=output,
            password="jpeg_pwd",
        )
        hide_resp = service.hide_data(hide_req)
        assert hide_resp.success is True

        extract_req = StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="jpeg_pwd",
        )
        extract_resp = service.extract_data(extract_req)
        assert extract_resp.success is True
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), payload_tiny)

    def test_png_with_visual_metrics(self, png_medium: Path, payload_tiny: Path, tmp_path: Path):
        """PNG hide with compute_visual_metrics=True: the response must contain ssim."""
        service = StegoService()
        hide_req = StegoTaskRequest(
            carrier_path=png_medium,
            payload_path=payload_tiny,
            output_path=tmp_path / "stego.png",
            password="metrics_pwd",
            compute_visual_metrics=True,
        )
        resp = service.hide_data(hide_req)
        assert resp.success is True
        assert "psnr" in resp.metrics
        assert "ssim" in resp.metrics
        assert resp.metrics["psnr"] > 40.0
        assert resp.metrics["ssim"] > 0.99


class TestE2EMetrics:
    """Checks of metrics in response.metrics."""

    def test_png_psnr_above_threshold(self, png_medium: Path, payload_tiny: Path, tmp_path: Path):
        """PNG: PSNR must be >= 40 dB."""
        service = StegoService()
        req = StegoTaskRequest(
            carrier_path=png_medium,
            payload_path=payload_tiny,
            output_path=tmp_path / "stego.png",
            password="pwd",
        )
        resp = service.hide_data(req)
        assert resp.success is True
        assert resp.metrics["psnr"] >= 40.0
        assert resp.metrics["quality_status"] == QualityStatus.OK

    def test_metrics_contain_required_keys(
        self, png_medium: Path, payload_tiny: Path, tmp_path: Path
    ):
        """Minimum set of keys in metrics for PNG."""
        service = StegoService()
        req = StegoTaskRequest(
            carrier_path=png_medium,
            payload_path=payload_tiny,
            output_path=tmp_path / "stego.png",
            password="pwd",
        )
        resp = service.hide_data(req)

        for key in ("psnr", "size_deviation", "quality_status", "time"):
            assert key in resp.metrics, f"missing key {key}"



class TestE2EEdgeCases:
    """Boundary conditions: overflow, wrong password, corrupted files, anti-conversion."""

    def test_capacity_overflow_raises_compatibility(
        self, png_small: Path, payload_pdf: Path, tmp_path: Path
    ):
        """small.png (64x64) cannot hold a PDF of several KB -- CompatibilityError."""
        service = StegoService()
        req = StegoTaskRequest(
            carrier_path=png_small,
            payload_path=payload_pdf,
            output_path=tmp_path / "stego.png",
            password="pwd",
        )
        with pytest.raises((CompatibilityError, ValueError)) as exc_info:
            service.hide_data(req)
        msg = str(exc_info.value).lower()
        assert "ёмкости" in msg or "capacity" in msg or "недостаточно" in msg

    def test_wrong_password_on_extract_raises(
        self, png_medium: Path, payload_tiny: Path, tmp_path: Path
    ):
        """Hide with one password -- extract with another -- InvalidFrameError or InvalidPasswordError."""
        service = StegoService()

        hide_resp = service.hide_data(StegoTaskRequest(
            carrier_path=png_medium,
            payload_path=payload_tiny,
            output_path=tmp_path / "stego.png",
            password="Pravilno",
        ))

        extract_req = StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="AYaNepravilnyi",
        )
        with pytest.raises((InvalidFrameError, InvalidPasswordError)):
            service.extract_data(extract_req)

    def test_corrupted_carrier_fails_gracefully(
        self, corrupted_png: Path, tmp_path: Path
    ):
        """A corrupted PNG on extract -- an exception, not a segfault."""
        service = StegoService()
        req = StegoTaskRequest(
            carrier_path=corrupted_png,
            payload_path=corrupted_png,
            output_path=tmp_path / "extracted.bin",
            password="any",
        )
        with pytest.raises(Exception):
            # Any exception is accepted — PIL may raise different things,
            # InvalidFrameError, or OSError on load. What matters is that
            # the interpreter does not crash.
            service.extract_data(req)

    def test_empty_password_allowed(
        self, png_medium: Path, payload_tiny: Path, tmp_path: Path
    ):
        """An empty password is allowed."""
        service = StegoService()
        req = StegoTaskRequest(
            carrier_path=png_medium,
            payload_path=payload_tiny,
            output_path=tmp_path / "stego.png",
            password="",
        )
        resp = service.hide_data(req)
        assert resp.success is True

    def test_anticonversion_png_to_wav_blocked(
        self, png_medium: Path, payload_tiny: Path, tmp_path: Path
    ):
        """PNG carrier -- an attempt to save with a .wav extension -- CompatibilityError."""
        service = StegoService()
        req = StegoTaskRequest(
            carrier_path=png_medium,
            payload_path=payload_tiny,
            output_path=tmp_path / "stego.wav",  # wrong extension
            password="pwd",
        )
        with pytest.raises(CompatibilityError) as exc_info:
            service.hide_data(req)
        assert "анти-конверсии" in str(exc_info.value).lower() or "conversion" in str(exc_info.value).lower()

    def test_payload_format_detection_known_format(
        self, png_medium: Path, tmp_path: Path
    ):
        """Hide a minimal valid WAV inside a PNG - extract - the output must get a .wav extension.

        We build the WAV by hand with a minimal header so it is guaranteed
        to fit in the png_medium capacity and still let FormatIdentifier recognize the format by magic bytes.
        """
        minimal_wav = (
            b"RIFF"
            b"\x24\x00\x00\x00"   # file size minus 8
            b"WAVE"
            b"fmt "
            b"\x10\x00\x00\x00"   # PCM header size
            b"\x01\x00"           # PCM format
            b"\x01\x00"           # 1 channel
            b"\x44\xac\x00\x00"   # 44100 Hz
            b"\x88\x58\x01\x00"   # byte rate
            b"\x02\x00"           # block align
            b"\x10\x00"           # 16 bits per sample
            b"data"
            b"\x00\x00\x00\x00"   # 0 bytes of audio data
        )
        wav_payload = tmp_path / "minimal.wav"
        wav_payload.write_bytes(minimal_wav)

        service = StegoService()
        hide_resp = service.hide_data(StegoTaskRequest(
            carrier_path=png_medium,
            payload_path=wav_payload,
            output_path=tmp_path / "stego.png",
            password="pwd",
        ))
        assert hide_resp.success is True

        extract_resp = service.extract_data(StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="pwd",
        ))
        assert extract_resp.success is True
        assert extract_resp.output_path.suffix.lower() == ".wav"

    def test_payload_format_unknown_falls_back_to_bin(
        self, png_medium: Path, payload_pdf: Path, tmp_path: Path
    ):
        """Hide a PDF (unsupported format) -- extract -- extension .bin.

        PDF is not in the list of formats FormatIdentifier detects by magic bytes; that list is only PNG/WAV/JPEG.
        The backend defaults unrecognized formats to .bin — this is documented behavior.
        """
        service = StegoService()
        hide_resp = service.hide_data(StegoTaskRequest(
            carrier_path=png_medium,
            payload_path=payload_pdf,
            output_path=tmp_path / "stego.png",
            password="pwd",
        ))
        extract_resp = service.extract_data(StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="pwd",
        ))
        assert extract_resp.success is True
        assert extract_resp.output_path.suffix.lower() == ".bin"
        assert_bytes_equal_to_file(
            extract_resp.output_path.read_bytes(), payload_pdf
        )


class TestE2ECapacityReport:
    """analyze_capacity must correctly predict fit/no-fit."""

    def test_capacity_fits_for_small_payload(
        self, png_medium: Path, payload_tiny: Path, tmp_path: Path
    ):
        """A tiny payload in a medium PNG -> fits=True."""
        service = StegoService()
        req = StegoTaskRequest(
            carrier_path=png_medium,
            payload_path=payload_tiny,
            output_path=tmp_path / "stego.png",
            password="pwd",
        )
        report = service.analyze_capacity(req)
        assert report.fits is True
        assert report.required_bits < report.capacity_bits

    def test_capacity_no_fit_warns_before_hide(
        self, png_small: Path, payload_pdf: Path, tmp_path: Path
    ):
        """A PDF in a small PNG -- fits=False, hide_data has not been called yet."""
        service = StegoService()
        req = StegoTaskRequest(
            carrier_path=png_small,
            payload_path=payload_pdf,
            output_path=tmp_path / "stego.png",
            password="pwd",
        )
        report = service.analyze_capacity(req)
        assert report.fits is False
        assert report.required_bits > report.capacity_bits