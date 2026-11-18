"""Checks of carrier capacity boundary conditions.

Covers CompatibilityError on overflow and the analyze_capacity contract:
numbers in CapacityReport must agree with a real embed attempt.
"""
import pytest

from stegambit.core.exceptions import CompatibilityError
from stegambit.models.dto import StegoTaskRequest
from stegambit.services.stego_service import StegoService


pytestmark = [pytest.mark.integration]


def test_capacity_overflow_raises(png_small, payload_zip, tmp_path):
    """A payload larger than the carrier capacity -> refusal BEFORE the actual embed.

    small.png (64x64) physically cannot hold archive.zip (~10.5 KB).
    The service must catch this and raise CompatibilityError from Spreader.
    """
    service = StegoService()
    stego_path = tmp_path / "stego.png"

    with pytest.raises((CompatibilityError, ValueError)) as exc_info:
        service.hide_data(StegoTaskRequest(
            carrier_path=png_small,
            payload_path=payload_zip,
            output_path=stego_path,
            password="pwd",
        ))

    # The error message should be specific — how much is missing.
    msg = str(exc_info.value).lower()
    assert any(word in msg for word in ("ёмкост", "недостаточно", "бит", "байт")), (
        f"Сообщение об ошибке должно содержать численные детали, получено: {exc_info.value!r}"
    )

    # The file must not be created when validation fails.
    assert not stego_path.exists(), (
        "Стего-файл создан несмотря на отказ - значит, ошибка возникла "
        "после save(), а должна была до."
    )


def test_analyze_capacity_fits_for_tiny_payload(png_medium, payload_tiny):
    """analyze_capacity for a small payload in a medium carrier — fits=True."""
    service = StegoService()
    report = service.analyze_capacity(StegoTaskRequest(
        carrier_path=png_medium,
        payload_path=payload_tiny,
        output_path=png_medium,  # unused in analyze
        password="pwd",
    ))

    assert report.fits is True
    assert report.format == "PNG"
    assert report.algorithm == "LSB"
    assert report.capacity_bits > 0
    assert report.required_bits > 0
    assert report.capacity_bits >= report.required_bits
    assert 0.0 < report.utilization_percent < 100.0
    assert report.payload_size_bytes == payload_tiny.stat().st_size
    assert report.header_size_bytes == 57  # FrameLayout.HEADER_LEN


def test_analyze_capacity_does_not_fit_for_large_payload(png_small, payload_zip):
    """analyze_capacity for a large payload in a small carrier — fits=False."""
    service = StegoService()
    report = service.analyze_capacity(StegoTaskRequest(
        carrier_path=png_small,
        payload_path=payload_zip,
        output_path=png_small,
        password="pwd",
    ))

    assert report.fits is False
    assert report.required_bits > report.capacity_bits
    assert report.utilization_percent > 100.0


def test_analyze_capacity_matches_real_embed_behavior(
    png_medium, payload_tiny, tmp_path,
):
    """Contract: if analyze says fits=True, a real embed must succeed."""
    service = StegoService()
    req = StegoTaskRequest(
        carrier_path=png_medium,
        payload_path=payload_tiny,
        output_path=tmp_path / "stego.png",
        password="pwd",
    )

    report = service.analyze_capacity(req)
    assert report.fits is True, "Тест-данные подобраны неверно - payload не должен переполнять носитель"

    # Since analyze allows it, embed must succeed.
    resp = service.hide_data(req)
    assert resp.success


def test_analyze_capacity_jpeg_reports_dct_algorithm(jpeg_carrier, payload_tiny):
    """A JPEG carrier -> the DCT algorithm in the report."""
    service = StegoService()
    report = service.analyze_capacity(StegoTaskRequest(
        carrier_path=jpeg_carrier,
        payload_path=payload_tiny,
        output_path=jpeg_carrier,
        password="pwd",
    ))

    assert report.format == "JPEG"
    assert report.algorithm == "DCT"
    assert report.capacity_bits > 0


def test_analyze_capacity_wav_reports_lsb_algorithm(wav_carrier, payload_tiny):
    """A WAV carrier -> the LSB algorithm in the report."""
    service = StegoService()
    report = service.analyze_capacity(StegoTaskRequest(
        carrier_path=wav_carrier,
        payload_path=payload_tiny,
        output_path=wav_carrier,
        password="pwd",
    ))

    assert report.format == "WAV"
    assert report.algorithm == "LSB"
    assert report.capacity_bits > 0