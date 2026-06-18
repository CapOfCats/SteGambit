"""Проверки граничных условий ёмкости носителя.

Покрывает CompatibilityError при переполнении и контракт analyze_capacity:
числа в CapacityReport должны быть согласованы с реальной попыткой embed.
"""
import pytest

from stegambit.core.exceptions import CompatibilityError
from stegambit.models.dto import StegoTaskRequest
from stegambit.services.stego_service import StegoService


pytestmark = [pytest.mark.integration]


def test_capacity_overflow_raises(png_small, payload_zip, tmp_path):
    """Payload крупнее ёмкости носителя -> отказ ДО фактического embed.

    small.png (64x64) физически не вместит archive.zip (~10.5 KB).
    Сервис должен это поймать и кинуть CompatibilityError  из Spreader.
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

    # В сообщении ошибки должна быть конкретика - сколько не хватает.
    msg = str(exc_info.value).lower()
    assert any(word in msg for word in ("ёмкост", "недостаточно", "бит", "байт")), (
        f"Сообщение об ошибке должно содержать численные детали, получено: {exc_info.value!r}"
    )

    # Файл не должен быть создан при провале валидации.
    assert not stego_path.exists(), (
        "Стего-файл создан несмотря на отказ - значит, ошибка возникла "
        "после save(), а должна была до."
    )


def test_analyze_capacity_fits_for_tiny_payload(png_medium, payload_tiny):
    """analyze_capacity для маленького payload в среднем носителе - fits=True."""
    service = StegoService()
    report = service.analyze_capacity(StegoTaskRequest(
        carrier_path=png_medium,
        payload_path=payload_tiny,
        output_path=png_medium,  # не используется в analyze
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
    """analyze_capacity для крупного payload в маленьком носителе - fits=False."""
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
    """Контракт: если analyze говорит fits=True, real embed должен пройти."""
    service = StegoService()
    req = StegoTaskRequest(
        carrier_path=png_medium,
        payload_path=payload_tiny,
        output_path=tmp_path / "stego.png",
        password="pwd",
    )

    report = service.analyze_capacity(req)
    assert report.fits is True, "Тест-данные подобраны неверно - payload не должен переполнять носитель"

    # Раз analyze разрешает - embed должен пройти.
    resp = service.hide_data(req)
    assert resp.success


def test_analyze_capacity_jpeg_reports_dct_algorithm(jpeg_carrier, payload_tiny):
    """JPEG-носитель -> алгоритм DCT в отчёте."""
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
    """WAV-носитель -> алгоритм LSB в отчёте."""
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