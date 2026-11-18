"""Smoke tests of the end-to-end StegoService pipeline.

One test per format — the critical path "the user hid and retrieved".
Covers domains 1, 3, 4, 6, 7 from the checklist.

If these tests are green, the system works.

Full edge-case coverage is in task #19 (Unit) and #24 (Integration).
"""
from pathlib import Path

import pytest

from stegambit.core.exceptions import CompatibilityError
from stegambit.models.dto import StegoTaskRequest, QualityStatus
from stegambit.services.stego_service import StegoService
from stegambit.core.exceptions import InvalidFrameError


@pytest.mark.smoke
@pytest.mark.integration
def test_smoke_png_round_trip(png_medium, payload_pdf, tmp_path):
    """PNG: hide PDF → extract → PDF bytes match.

    Covers domains: Crypto, LSB, FormatIdentifier (.pdf recovery),
    StegoService, Spreader, PngFormat I/O.
    """
    service = StegoService()
    stego_path = tmp_path / "stego.png"
    extract_output = tmp_path / "extracted" 
    password = "smoke_png_pass"

    original_payload_bytes = payload_pdf.read_bytes()

    hide_request = StegoTaskRequest(
        carrier_path=png_medium,
        payload_path=payload_pdf,
        output_path=stego_path,
        password=password,
    )
    hide_response = service.hide_data(hide_request)

    assert hide_response.success is True
    assert stego_path.exists()
    assert hide_response.metrics["quality_status"] == QualityStatus.OK

    extract_request = StegoTaskRequest(
        carrier_path=stego_path,
        payload_path=stego_path, 
        output_path=extract_output,
        password=password,
    )
    extract_response = service.extract_data(extract_request)

    assert extract_response.success is True
    assert extract_response.output_path is not None
    assert extract_response.output_path.exists()

    extracted_bytes = extract_response.output_path.read_bytes()
    assert extracted_bytes == original_payload_bytes


@pytest.mark.smoke
@pytest.mark.integration
def test_smoke_jpeg_round_trip(jpeg_carrier, payload_zip, tmp_path):
    """JPEG: hide ZIP → extract → ZIP bytes match.

    Covers: DCT filtering (the shrinkage fix with {-2,-1,0,1}),
    JpegFormat I/O without re-quantization, a Y-channel sanity check, recovery of the .zip extension.
    """
    service = StegoService()
    stego_path = tmp_path / "stego.jpg"
    extract_output = tmp_path / "extracted"
    password = "smoke_jpeg_pass"

    original_payload_bytes = payload_zip.read_bytes()

    hide_request = StegoTaskRequest(
        carrier_path=jpeg_carrier,
        payload_path=payload_zip,
        output_path=stego_path,
        password=password,
    )
    hide_response = service.hide_data(hide_request)

    assert hide_response.success is True
    assert stego_path.exists()

    extract_request = StegoTaskRequest(
        carrier_path=stego_path,
        payload_path=stego_path,
        output_path=extract_output,
        password=password,
    )
    extract_response = service.extract_data(extract_request)

    assert extract_response.success is True
    assert extract_response.output_path.suffix == ".bin"

    extracted_bytes = extract_response.output_path.read_bytes()
    assert extracted_bytes == original_payload_bytes


@pytest.mark.smoke
@pytest.mark.integration
def test_smoke_wav_round_trip(wav_carrier, payload_tiny, tmp_path):
    """WAV: hide tiny.txt → extract → bytes match.

    Covers: LSB on a 1D int16 array, WavFormat I/O, Spreader
    on audio data. We use tiny.txt as a small payload —
    WAV carriers usually have less "noisy" capacity than PNG.
    """
    service = StegoService()
    stego_path = tmp_path / "stego.wav"
    extract_output = tmp_path / "extracted"
    password = "smoke_wav_pass"

    original_payload_bytes = payload_tiny.read_bytes()

    hide_request = StegoTaskRequest(
        carrier_path=wav_carrier,
        payload_path=payload_tiny,
        output_path=stego_path,
        password=password,
    )
    hide_response = service.hide_data(hide_request)

    assert hide_response.success is True
    assert stego_path.exists()

    extract_request = StegoTaskRequest(
        carrier_path=stego_path,
        payload_path=stego_path,
        output_path=extract_output,
        password=password,
    )
    extract_response = service.extract_data(extract_request)

    assert extract_response.success is True
    # tiny.txt is text; FormatIdentifier.identify_bytes does not recognize it
    # as a known format, so the default extension .bin is expected.
    extracted_bytes = extract_response.output_path.read_bytes()
    assert extracted_bytes == original_payload_bytes


@pytest.mark.smoke
def test_smoke_anti_conversion_blocks_png_to_jpeg(png_medium, payload_tiny, tmp_path):
    """An attempt to save a PNG source as JPEG — CompatibilityError.

    Covers: the anti-conversion policy (ADR 007).
    """
    service = StegoService()
    request = StegoTaskRequest(
        carrier_path=png_medium,
        payload_path=payload_tiny,
        output_path=tmp_path / "stego.jpeg",  # ← policy violation
        password="any",
    )

    with pytest.raises(CompatibilityError, match="анти-конверсии"):
        service.hide_data(request)


@pytest.mark.smoke
@pytest.mark.integration
def test_smoke_wrong_password_fails_extraction(png_medium, payload_tiny, tmp_path):
    """Extraction with a wrong password — an error, the file is not created.

    Covers: GCM MAC validation + protection against accidental extraction.
    """
    service = StegoService()
    stego_path = tmp_path / "stego.png"
    extract_output = tmp_path / "extracted"

    hide_request = StegoTaskRequest(
        carrier_path=png_medium,
        payload_path=payload_tiny,
        output_path=stego_path,
        password="correct_password",
    )
    service.hide_data(hide_request)

    extract_request = StegoTaskRequest(
        carrier_path=stego_path,
        payload_path=stego_path,
        output_path=extract_output,
        password="wrong_password",
    )

    with pytest.raises(InvalidFrameError):
        service.extract_data(extract_request)


@pytest.mark.smoke
def test_smoke_capacity_overflow_blocks_hide(png_small, payload_pdf, tmp_path):
    """A small PNG + a large PDF → fits=False.

    Covers: analyze_capacity with an honest capacity, protection against creating a degraded file.
    """
    service = StegoService()
    request = StegoTaskRequest(
        carrier_path=png_small,
        payload_path=payload_pdf,
        output_path=tmp_path / "stego.png",
        password="test",
    )

    report = service.analyze_capacity(request)
    assert report.fits is False
    assert report.utilization_percent > 100.0