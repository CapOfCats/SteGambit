"""Unit-тесты для StegoService stego_service.py.

Тесты изолируют сервис от core-компонентов через моки. Полный цикл покрыт в test_smoke_pipeline.py — здесь проверяем
только оркестрацию, ветвление и обработку ошибок.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from stegambit.models.dto import StegoTaskRequest, CapacityReport
from stegambit.services.stego_service import StegoService, CompatibilityError
from stegambit.core.crypto.engine import InvalidFrameError, CryptoEngine


@pytest.fixture
def service():
    return StegoService()


@pytest.fixture
def png_request(tmp_path):
    """Минимальный валидный StegoTaskRequest для PNG."""
    return StegoTaskRequest(
        carrier_path=tmp_path / "carrier.png",
        payload_path=tmp_path / "payload.bin",
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
    return tmp_path / "carrier.png"

@pytest.fixture
def mock_png_handler():
    """Мок-класс PngFormat, возвращает ndarray-заглушку."""
    handler_instance = MagicMock()
    handler_instance.load.return_value = np.zeros(100_000, dtype=np.uint8)
    handler_cls = MagicMock(return_value=handler_instance)
    return handler_cls, handler_instance


class TestAntiConversionPolicy:
    """Политика анти-конверсии: формат носителя должен совпадать с расширением в выхлопе."""

    def test_png_carrier_to_jpeg_output_raises(self, service, png_request, tmp_path):
        """Негативный кейз: PNG → .jpeg запрещено."""
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
        """Негативный кейз: JPEG → .png запрещено."""
        request = StegoTaskRequest(
            carrier_path=tmp_path / "carrier.jpg",
            payload_path=tmp_path / "payload.bin",
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
        """Положительный кейз: совпадающий формат-расширение проходит политику.

        Проверяем, что ошибка возникает НЕ из-за анти-конверсии а позже при отсутствия реального файла.
        """
        request = StegoTaskRequest(
            carrier_path=tmp_path / f"carrier{ext}",
            payload_path=tmp_path / "payload.bin",
            output_path=tmp_path / f"stego{ext}",
            password="x",
        )
        with patch.object(service._identifier, "identify", return_value=fmt):
            with pytest.raises(Exception) as exc_info:
                service.hide_data(request)
            assert "анти-конверсии" not in str(exc_info.value)


class TestUnsupportedFormat:
    """Негативный кейз: формат не в _FORMAT_REGISTRY."""

    def test_hide_unsupported_format_raises(self, service, tmp_path):
        request = StegoTaskRequest(
            carrier_path=tmp_path / "x.bmp",
            payload_path=tmp_path / "p.bin",
            output_path=tmp_path / "out.bmp",
            password="x",
        )
        with patch.object(service._identifier, "identify", return_value="BMP"):
            with pytest.raises(CompatibilityError, match="Нарушение анти-конверсии"):
                service.hide_data(request)

    def test_extract_unsupported_format_raises(self, service, tmp_path):
        request = StegoTaskRequest(
            carrier_path=tmp_path / "x.bmp",
            payload_path=tmp_path / "p.bin",
            output_path=tmp_path / "out.bin",
            password="x",
        )
        with patch.object(service._identifier, "identify", return_value="BMP"):
            with pytest.raises(CompatibilityError, match="не поддержан"):
                service.extract_data(request)


class TestExtractDataErrors:
    """Негативные кейсы extract_data."""

    def test_missing_magic_raises_invalid_frame(self, service, png_request):
        """Негативный кейз: заголовок без MAGIC -> InvalidFrameError."""
        with patch.object(service._identifier, "identify", return_value="PNG"), \
             patch("stegambit.services.stego_service._FORMAT_REGISTRY") as mock_registry:
            mock_handler = MagicMock()
            mock_handler.load.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
            mock_registry.__getitem__.return_value = lambda: mock_handler
            mock_registry.__contains__.return_value = True

            with patch.object(service._processor, "extract", return_value=b"\x00" * 57):
                with patch("stegambit.services.stego_service.SmartSpreader") as mock_spreader:
                    mock_spreader.return_value.generate_coords.return_value = np.arange(10000, dtype=np.int64)
                    with pytest.raises(InvalidFrameError, match="MAGIC"):
                        service.extract_data(png_request)


class TestGetAlgorithmForFormat:
    """Утилита get_algorithm_for_format - тут Таблица решений."""

    @pytest.mark.parametrize("fmt, expected", [
        ("PNG", "LSB"),
        ("WAV", "LSB"),
        ("JPEG", "DCT"),
    ])
    def test_known_formats(self, service, fmt, expected):
        """Эквивалентность: каждый известный формат - свой алгоритм."""
        assert service.get_algorithm_for_format(fmt) == expected

    @pytest.mark.parametrize("unknown", ["BMP", "GIF", "", "png", "unknown"])
    def test_unknown_format_returns_question_mark(self, service, unknown):
        """Негативный кейз: неизвестный формат."""
        assert service.get_algorithm_for_format(unknown) == "?"


class TestIdentifyFormat:
    """Публичная обёртка над FormatIdentifier.identify."""

    def test_delegates_to_identifier(self, service, tmp_path):
        """identify_format пробрасывает в FormatIdentifier."""
        fake_path = tmp_path / "test.png"
        with patch.object(service._identifier, "identify", return_value="PNG") as mock_id:
            result = service.identify_format(fake_path)
            assert result == "PNG"
            mock_id.assert_called_once_with(fake_path)


class TestBuildPool:
    """Тесты приватного _build_pool: ветвление LSB и DCT."""

    def test_lsb_pool_is_arange(self, service):
        """LSB-пул — np.arange(container.size)."""
        container = np.zeros((10, 10, 3), dtype=np.uint8)
        pool, processor = service._build_pool("LSB", container)
        np.testing.assert_array_equal(pool, np.arange(container.size))
        assert processor is service._processor

    def test_dct_pool_delegates_to_dct_processor(self, service):
        """DCT-пул строится через DctProcessor.get_embeddable_positions."""
        fake_container = MagicMock()
        expected_pool = np.array([10, 20, 30], dtype=np.int64)
        with patch.object(service._dct, "get_embeddable_positions",
                          return_value=expected_pool) as mock_get:
            pool, processor = service._build_pool("DCT", fake_container)
            mock_get.assert_called_once_with(fake_container)
            np.testing.assert_array_equal(pool, expected_pool)
            assert processor is service._dct

    def test_unknown_processor_kind_raises(self, service):
        """Негативный кейз: неизвестный тип процессора - RuntimeError."""
        with pytest.raises(RuntimeError, match="Неизвестный тип процессора"):
            service._build_pool("UNKNOWN", np.zeros(10))


class TestShufflePoolByPassword:
    """Тесты статического _shuffle_pool_by_password."""

    def test_same_password_same_shuffle(self):
        """Один пароль - идентичная перестановка."""
        pool = np.arange(100, dtype=np.int64)
        r1 = StegoService._shuffle_pool_by_password(pool, "secret")
        r2 = StegoService._shuffle_pool_by_password(pool, "secret")
        np.testing.assert_array_equal(r1, r2)

    def test_different_passwords_different_shuffle(self):
        """Пазные пароли - разные перестановки."""
        pool = np.arange(100, dtype=np.int64)
        r1 = StegoService._shuffle_pool_by_password(pool, "secret1")
        r2 = StegoService._shuffle_pool_by_password(pool, "secret2")
        assert not np.array_equal(r1, r2)

    def test_shuffle_preserves_elements(self):
        """Перестановка содержит те же элементы, что и исходный пул."""
        pool = np.arange(100, dtype=np.int64)
        shuffled = StegoService._shuffle_pool_by_password(pool, "x")
        np.testing.assert_array_equal(np.sort(shuffled), pool)

    def test_does_not_mutate_input(self):
        """Исходный пул не мутируется."""
        pool = np.arange(100, dtype=np.int64)
        backup = pool.copy()
        StegoService._shuffle_pool_by_password(pool, "x")
        np.testing.assert_array_equal(pool, backup)


class TestAnalyzeCapacity:
    """Тесты analyze_capacity — предварительная оценка ёмкости без сокрытия."""

    def test_returns_capacity_report(self, service, payload_file, carrier_png, tmp_path, mock_png_handler):
        """analyze_capacity возвращает CapacityReport."""
        png_cls, _ = mock_png_handler
        request = StegoTaskRequest(
            carrier_path=carrier_png,
            payload_path=payload_file,
            output_path=tmp_path / "out.png",
            password="x",
        )
        with patch.object(service._identifier, "identify", return_value="PNG"), \
             patch.dict("stegambit.services.stego_service._FORMAT_REGISTRY", {"PNG": png_cls}), \
             patch("stegambit.services.stego_service.SmartSpreader") as mock_spreader_cls:
            mock_spreader_cls.return_value.get_max_capacity_bits.return_value = 80_000

            report = service.analyze_capacity(request)
            assert isinstance(report, CapacityReport)

    def test_fits_true_when_capacity_sufficient(self, service, payload_file, carrier_png, tmp_path, mock_png_handler):
        """Положительный кейз: capacity > required -> fits=True."""
        png_cls, _ = mock_png_handler
        request = StegoTaskRequest(
            carrier_path=carrier_png,
            payload_path=payload_file,
            output_path=tmp_path / "out.png",
            password="x",
        )
        with patch.object(service._identifier, "identify", return_value="PNG"), \
             patch.dict("stegambit.services.stego_service._FORMAT_REGISTRY", {"PNG": png_cls}), \
             patch("stegambit.services.stego_service.SmartSpreader") as mock_spreader_cls:
            mock_spreader_cls.return_value.get_max_capacity_bits.return_value = 80_000

            report = service.analyze_capacity(request)
            assert report.fits is True
            assert report.format == "PNG"
            assert report.algorithm == "LSB"

    def test_fits_false_on_overflow(self, service, payload_file, carrier_png, tmp_path, mock_png_handler):
        """Негативный кейз: required > capacity -> fits=False."""
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
             patch("stegambit.services.stego_service.SmartSpreader") as mock_spreader_cls:
            mock_spreader_cls.return_value.get_max_capacity_bits.return_value = 100

            report = service.analyze_capacity(request)
            assert report.fits is False
            assert report.utilization_percent > 100.0

    def test_utilization_zero_when_capacity_is_zero(self, service, payload_file, carrier_png, tmp_path, mock_png_handler):
        """Граничный кейз: capacity=0 -> utilization=0 - защита от деления на ноль."""
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
             patch("stegambit.services.stego_service.SmartSpreader") as mock_spreader_cls:
            mock_spreader_cls.return_value.get_max_capacity_bits.return_value = 0

            report = service.analyze_capacity(request)
            assert report.utilization_percent == 0.0
            assert report.fits is False

    def test_jpeg_delegates_to_dct_processor(self, service, payload_file, tmp_path):
        """Жля JPEG ёмкость считается через DctProcessor."""
        request = StegoTaskRequest(
            carrier_path=tmp_path / "c.jpg",
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
             patch.object(service._dct, "get_embeddable_positions",
                          return_value=np.arange(50_000, dtype=np.int64)) as mock_get:

            report = service.analyze_capacity(request)
            mock_get.assert_called_once_with(fake_container)
            assert report.algorithm == "DCT"
            assert report.capacity_bits == 50_000

    def test_unsupported_format_raises(self, service, payload_file, tmp_path):
        """Негативный кейз: неподдерживаемый формат -> CompatibilityError."""
        request = StegoTaskRequest(
            carrier_path=tmp_path / "c.bmp",
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
             patch("stegambit.services.stego_service.SmartSpreader") as mock_spreader_cls:
            mock_spreader_cls.return_value.get_max_capacity_bits.return_value = 1_000_000

            report = service.analyze_capacity(request)
            expected = (CryptoEngine.header_size() + 100) * 8
            assert report.required_bits == expected
            assert report.payload_size_bytes == 100
            assert report.header_size_bytes == CryptoEngine.header_size()