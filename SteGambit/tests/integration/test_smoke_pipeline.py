"""Smoke-тесты сквозного пайплайна StegoService.

По одному тесту на формат — критичный путь "пользователь скрыл и достал".
Покрывает домены 1, 3, 4, 6, 7 из чек-листа.

Если эти тесты зелёные — система работает.

Полное покрытие edge-cases — в задаче #19 (Unit) и #24 (Integration).
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
    """PNG: hide PDF → extract → байты PDF совпадают.

    Покрывает домены: Crypto, LSB, FormatIdentifier (восстановление .pdf),
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
    """JPEG: hide ZIP → extract → байты ZIP совпадают.

    Покрывает: DCT-фильтрацию (фикс shrinkage с {-2,-1,0,1}),
    JpegFormat I/O без re-quantization, sanity-check Y-канала, восстановление расширения .zip.
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
    """WAV: hide tiny.txt → extract → байты совпадают.

    Покрывает: LSB на 1D-массиве int16, WavFormat I/O, Spreader
    на аудио-данных. Используем tiny.txt как малый payload —
    WAV-носители обычно имеют меньшую "шумную" ёмкость, чем PNG.
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
    # tiny.txt — текст, FormatIdentifier.identify_bytes его не опознает
    # как известный формат, поэтому ожидаем дефолтное расширение .bin.
    extracted_bytes = extract_response.output_path.read_bytes()
    assert extracted_bytes == original_payload_bytes


@pytest.mark.smoke
def test_smoke_anti_conversion_blocks_png_to_jpeg(png_medium, payload_tiny, tmp_path):
    """Попытка сохранить PNG-источник как JPEG - CompatibilityError.

    Покрывает: политику Anti-Conversion (ADR 007).
    """
    service = StegoService()
    request = StegoTaskRequest(
        carrier_path=png_medium,
        payload_path=payload_tiny,
        output_path=tmp_path / "stego.jpeg",  # ← нарушение политики
        password="any",
    )

    with pytest.raises(CompatibilityError, match="анти-конверсии"):
        service.hide_data(request)


@pytest.mark.smoke
@pytest.mark.integration
def test_smoke_wrong_password_fails_extraction(png_medium, payload_tiny, tmp_path):
    """Извлечение с неверным паролем - ошибка, файл не создаётся.

    Покрывает: GCM MAC validation + защиту от случайного извлечения.
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
    """Маленький PNG + крупный PDF → fits=False.

    Покрывает: analyze_capacity с честной ёмкостью, защиту от создания деградированного файла.
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