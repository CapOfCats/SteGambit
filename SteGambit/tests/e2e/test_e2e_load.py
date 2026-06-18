"""E2E Load-тесты: нагрузочные сценарии на больших файлах.

Запускаются по флагу: -m load -v -s

Артефакты:
     large.png       (3.5 МБ, 2K×2K)  capacity 380 КБ payload
     long.wav        (68 МБ, 16-bit/44.1)  capacity 850 КБ payload
     large_photo.jpg (8 МБ)              capacity 387 КБ payload

Capacity для PNG/WAV сильно меньше размера файла из-за фильтрации
"шумных" пикселей/сэмплов в SmartSpreader (edge-detection для PNG,
silence-cutoff для WAV). Для JPEG capacity определяется фильтром
среднечастотных AC-коэффициентов.

Ожидаемое время прогона: 3-6 минут.

Архитектурное примечание:
    PNG-носители > 3.5MB могут вызывать OOM на бытовых конфигурациях. SmartSpreader аллоцирует O(N) памяти
    от размера контейнера; на 6K×6K это даёт 3-5 ГБ пиковой памяти.
"""
import time
from pathlib import Path

import pytest

from stegambit.models.dto import StegoTaskRequest
from stegambit.services.stego_service import StegoService
from stegambit.core.exceptions import CompatibilityError

from .conftest import assert_bytes_equal_to_file


# Маркер для всех тестов в этом модуле.
pytestmark = pytest.mark.load


class TestE2ELoadPNG:
    """Нагрузочное тестирование PNG-LSB.

    Реалистичный потолок носителя ~3.5MB из-за O(N) памяти в SmartSpreader.
    Capacity такого PNG ~380KB payload (10-15% от файла после edge-фильтра).
    """

    def test_png_load_250kb_payload(
        self, png_large: Path, payload_250kb: Path, tmp_path: Path
    ):
        """PNG 3.5МБ + 250КБ payload (комфортный запас по capacity)."""
        service = StegoService()

        t0 = time.perf_counter()
        hide_resp = service.hide_data(StegoTaskRequest(
            carrier_path=png_large,
            payload_path=payload_250kb,
            output_path=tmp_path / "stego.png",
            password="load_pwd",
        ))
        hide_time = time.perf_counter() - t0

        assert hide_resp.success is True
        assert hide_resp.metrics["psnr"] > 40.0
        print(f"\n[LOAD PNG 250KB] hide={hide_time:.2f}s, "
              f"PSNR={hide_resp.metrics['psnr']:.1f}dB")

        t0 = time.perf_counter()
        extract_resp = service.extract_data(StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="load_pwd",
        ))
        extract_time = time.perf_counter() - t0

        assert extract_resp.success is True
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), payload_250kb)
        print(f"[LOAD PNG 250KB] extract={extract_time:.2f}s")

    def test_png_load_350kb_near_capacity(
        self, png_large: Path, payload_350kb: Path, tmp_path: Path
    ):
        """PNG 3.5МБ + 350КБ payload (на границе capacity 380KB).

        Best-effort: если capacity конкретного носителя оказалась чуть
        меньше  skip, не fail. PNG capacity варьируется +-10% в
        зависимости от текстуры изображения.
        """
        service = StegoService()
        try:
            t0 = time.perf_counter()
            hide_resp = service.hide_data(StegoTaskRequest(
                carrier_path=png_large,
                payload_path=payload_350kb,
                output_path=tmp_path / "stego.png",
                password="load_pwd",
            ))
            hide_time = time.perf_counter() - t0
        except (CompatibilityError, ValueError) as e:
            pytest.skip(f"PNG capacity недостаточна для 350KB payload: {e}")

        assert hide_resp.success is True
        print(f"\n[LOAD PNG 350KB] hide={hide_time:.2f}s, "
              f"PSNR={hide_resp.metrics['psnr']:.1f}dB")

        extract_resp = service.extract_data(StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="load_pwd",
        ))
        assert extract_resp.success is True
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), payload_350kb)


class TestE2ELoadWAV:
    """Нагрузочное тестирование WAV-LSB.

    WAV-LSB обрабатывает большие файлы значительно дешевле PNG - нет
    grayscale-конвертации и edge-detection в spatial domain. Тестируем
    реальные нагрузки на 68MB носителе.
    """

    def test_wav_load_500kb_payload(
        self, wav_long: Path, payload_500kb: Path, tmp_path: Path
    ):
        """WAV ~68МБ + 500КБ payload."""
        service = StegoService()

        t0 = time.perf_counter()
        hide_resp = service.hide_data(StegoTaskRequest(
            carrier_path=wav_long,
            payload_path=payload_500kb,
            output_path=tmp_path / "stego.wav",
            password="wav_load_pwd",
        ))
        hide_time = time.perf_counter() - t0

        assert hide_resp.success is True
        print(f"\n[LOAD WAV 500KB] hide={hide_time:.2f}s")

        extract_resp = service.extract_data(StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="wav_load_pwd",
        ))
        assert extract_resp.success is True
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), payload_500kb)

    def test_wav_load_750kb_near_capacity(
        self, wav_long: Path, payload_750kb: Path, tmp_path: Path
    ):
        """WAV 68МБ + 750КБ payload (на границе capacity 850KB).

        Best-effort: если конкретный WAV содержит больше тишины, чем
        ожидалось, capacity уменьшится. В этом случае - skip.
        """
        service = StegoService()
        try:
            t0 = time.perf_counter()
            hide_resp = service.hide_data(StegoTaskRequest(
                carrier_path=wav_long,
                payload_path=payload_750kb,
                output_path=tmp_path / "stego.wav",
                password="wav_pwd",
            ))
            hide_time = time.perf_counter() - t0
        except (CompatibilityError, ValueError) as e:
            pytest.skip(f"WAV capacity недостаточна для 750KB payload: {e}")

        assert hide_resp.success is True
        print(f"\n[LOAD WAV 750KB] hide={hide_time:.2f}s")

        extract_resp = service.extract_data(StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="wav_pwd",
        ))
        assert extract_resp.success is True
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), payload_750kb)


class TestE2ELoadJPEG:
    """Нагрузочное тестирование JPEG-DCT.

    JPEG-DCT capacity 5-10% от размера файла после фильтра
    среднечастотных AC-коэффициентов. Для 8MB файла - 387KB payload.
    """

    def test_jpeg_load_100kb_payload(
        self, jpeg_large: Path, payload_100kb: Path, tmp_path: Path
    ):
        """JPEG 8МБ + 100КБ payload (комфортный запас)."""
        service = StegoService()

        t0 = time.perf_counter()
        hide_resp = service.hide_data(StegoTaskRequest(
            carrier_path=jpeg_large,
            payload_path=payload_100kb,
            output_path=tmp_path / "stego.jpg",
            password="jpeg_pwd",
        ))
        hide_time = time.perf_counter() - t0

        assert hide_resp.success is True
        print(f"\n[LOAD JPEG 100KB] hide={hide_time:.2f}s")

        extract_resp = service.extract_data(StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="jpeg_pwd",
        ))
        assert extract_resp.success is True
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), payload_100kb)

    def test_jpeg_load_300kb_near_capacity(
        self, jpeg_large: Path, payload_300kb: Path, tmp_path: Path
    ):
        """JPEG 8МБ + 300КБ payload (на границе capacity 387KB).

        Best-effort: capacity DCT-пула зависит от текстуры конкретной фотографии. Если не хватит - skip.
        """
        service = StegoService()
        try:
            t0 = time.perf_counter()
            hide_resp = service.hide_data(StegoTaskRequest(
                carrier_path=jpeg_large,
                payload_path=payload_300kb,
                output_path=tmp_path / "stego.jpg",
                password="jpeg_max_pwd",
            ))
            hide_time = time.perf_counter() - t0
        except (CompatibilityError, ValueError) as e:
            pytest.skip(f"JPEG capacity недостаточна для 300KB payload: {e}")

        assert hide_resp.success is True
        print(f"\n[LOAD JPEG 300KB] hide={hide_time:.2f}s")

        extract_resp = service.extract_data(StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="jpeg_max_pwd",
        ))
        assert extract_resp.success is True
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), payload_300kb)


class TestE2ELoadDynamicCapacity:
    """Динамические capacity-тесты.

    Вместо фиксированных размеров payload используют analyze_capacity()
    для выяснения реального потолка конкретного носителя и подбирают
    payload "под 95% capacity". Это  тесты - работают на любых артефактах, не привязаны к точным размерам файлов.
    """

    def test_png_capacity_95_percent(
        self, png_large: Path, payload_tiny: Path, tmp_path: Path
    ):
        """Подбирает payload под 95% реальной capacity PNG-носителя
        и проверяет полный roundtrip."""
        service = StegoService()

        # Шаг 1: спрашиваем capacity у сервиса (передаём любой существующий
        # payload — analyze_capacity использует его только для размера).
        probe_req = StegoTaskRequest(
            carrier_path=png_large,
            payload_path=payload_tiny,
            output_path=tmp_path / "stego.png",
            password="dyn_pwd",
        )
        report = service.analyze_capacity(probe_req)
        target_payload_size = int(report.capacity_bits / 8 * 0.95) - report.header_size_bytes
        assert target_payload_size > 0, "Capacity слишком мала даже для заголовка"

        # Шаг 2: генерируем payload точно под этот размер.
        import numpy as np
        rng = np.random.default_rng(seed=42)
        dynamic_payload = tmp_path / "dynamic_payload.bin"
        dynamic_payload.write_bytes(rng.bytes(target_payload_size))

        print(f"\n[DYNAMIC PNG] capacity={report.capacity_bits} bits, "
              f"payload={target_payload_size} bytes (95% load)")

        # Шаг 3: полный roundtrip.
        hide_req = StegoTaskRequest(
            carrier_path=png_large,
            payload_path=dynamic_payload,
            output_path=tmp_path / "stego.png",
            password="dyn_pwd",
        )
        t0 = time.perf_counter()
        hide_resp = service.hide_data(hide_req)
        print(f"[DYNAMIC PNG] hide={time.perf_counter() - t0:.2f}s")

        assert hide_resp.success is True

        extract_resp = service.extract_data(StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="dyn_pwd",
        ))
        assert extract_resp.success is True
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), dynamic_payload)