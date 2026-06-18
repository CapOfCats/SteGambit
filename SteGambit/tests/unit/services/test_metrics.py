"""Смоки для метрик качества и analyze_capacity.

Покрывают:
    * calculate_ssim — новая метрика структурного сходства.
    * calculate_size_deviation — процентный прирост размера файла.
    * evaluate_quality — триггеры качества OK/WARNING/ANOMALY.
    * StegoService.analyze_capacity — DTO CapacityReport.
    * Интеграция: hide_data возвращает все новые поля в metrics.
"""

import numpy as np
import pytest

from stegambit.core.exceptions import CompatibilityError
from stegambit.models.dto import (
    StegoTaskRequest,
    CapacityReport,
    QualityStatus,
)
from stegambit.services.analytics.metrics import (
    calculate_ssim,
    calculate_size_deviation,
    evaluate_quality,
    PSNR_OK_THRESHOLD,
)
from stegambit.services.stego_service import StegoService


class TestSSIM:
    """SSIM — структурное сходство."""

    def test_identical_images_give_ssim_1(self, random_image):
        """Идентичные изображения -> SSIM == 1.0."""
        ssim = calculate_ssim(random_image, random_image.copy())
        assert ssim == pytest.approx(1.0, abs=1e-6)

    def test_lsb_modified_image_has_high_ssim(self, random_image):
        """После LSB-модификации SSIM остаётся >0.99 (визуально неотличимо)."""
        modified = random_image.copy()
        modified.flat[::2] ^= 1
        ssim = calculate_ssim(random_image, modified)
        assert ssim > 0.99

    def test_completely_different_image_has_low_ssim(self, random_image):
        """Инвертированное изображение -> низкий SSIM."""
        inverted = 255 - random_image
        ssim = calculate_ssim(random_image, inverted)
        assert ssim < 0.5

    def test_shape_mismatch_raises(self, random_image):
        """Разные размеры -> ValueError."""
        other = np.zeros((32, 32, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            calculate_ssim(random_image, other)

    def test_1d_audio_returns_nan(self):
        """Для 1D-аудио SSIM возвращает NaN (метрика неприменима)."""
        audio = np.random.randint(-32768, 32767, size=1000, dtype=np.int16)
        result = calculate_ssim(audio, audio.copy())
        assert np.isnan(result)


class TestSizeDeviation:
    """Процентное отклонение размера файла."""

    def test_identical_files_zero_deviation(self, tmp_path):
        """Файлы одинакового размера -> отклонение 0%."""
        a = tmp_path / "a.bin"
        b = tmp_path / "b.bin"
        a.write_bytes(b"X" * 1000)
        b.write_bytes(b"X" * 1000)
        assert calculate_size_deviation(a, b) == 0.0

    def test_positive_growth(self, tmp_path):
        """Файл вырос на 10% -> deviation == 10.0."""
        a = tmp_path / "orig.bin"
        b = tmp_path / "stego.bin"
        a.write_bytes(b"X" * 1000)
        b.write_bytes(b"X" * 1100)
        assert calculate_size_deviation(a, b) == pytest.approx(10.0)

    def test_negative_shrinkage(self, tmp_path):
        """Stego меньше оригинала -> отрицательное значение."""
        a = tmp_path / "orig.bin"
        b = tmp_path / "stego.bin"
        a.write_bytes(b"X" * 1000)
        b.write_bytes(b"X" * 900)
        assert calculate_size_deviation(a, b) == pytest.approx(-10.0)

    def test_empty_original_safe(self, tmp_path):
        """Деление на ноль обработано: пустой оригинал -> 0%."""
        a = tmp_path / "empty.bin"
        b = tmp_path / "non_empty.bin"
        a.write_bytes(b"")
        b.write_bytes(b"X" * 100)
        assert calculate_size_deviation(a, b) == 0.0


class TestEvaluateQuality:
    """Триггеры качества."""

    def test_high_psnr_low_deviation_ok(self):
        """PSNR >= 40 + deviation <= 30% -> OK."""
        assert evaluate_quality(psnr=45.0, size_deviation=5.0) == QualityStatus.OK

    def test_mid_psnr_warning(self):
        """30 <= PSNR < 40 -> WARNING."""
        assert evaluate_quality(psnr=35.0, size_deviation=5.0) == QualityStatus.WARNING

    def test_low_psnr_anomaly(self):
        """PSNR < 30 -> ANOMALY."""
        assert evaluate_quality(psnr=25.0, size_deviation=5.0) == QualityStatus.ANOMALY

    def test_high_deviation_anomaly(self):
        """deviation > 30% -> ANOMALY даже при хорошем PSNR."""
        assert evaluate_quality(psnr=50.0, size_deviation=50.0) == QualityStatus.ANOMALY

    def test_negative_deviation_within_limit_ok(self):
        """Отрицательное отклонение (файл уменьшился) — нормально, если |dev| <= 30%."""
        assert evaluate_quality(psnr=45.0, size_deviation=-15.0) == QualityStatus.OK

    def test_psnr_only_no_deviation(self):
        """Если deviation=None — решение по одному PSNR."""
        assert evaluate_quality(psnr=45.0, size_deviation=None) == QualityStatus.OK
        assert evaluate_quality(psnr=35.0, size_deviation=None) == QualityStatus.WARNING

    def test_deviation_only_no_psnr(self):
        """Если psnr=None в DCT — решение по deviation."""

        assert evaluate_quality(psnr=None, size_deviation=10.0) == QualityStatus.OK

        assert evaluate_quality(psnr=None, size_deviation=50.0) == QualityStatus.ANOMALY

    def test_thresholds_exact_values(self):
        """Граничные значения: PSNR ровно на пороге - это OK."""
        assert evaluate_quality(psnr=PSNR_OK_THRESHOLD, size_deviation=0.0) == QualityStatus.OK
        # Граничное ниже порога OK -> WARNING.
        assert evaluate_quality(psnr=PSNR_OK_THRESHOLD - 0.01, size_deviation=0.0) == QualityStatus.WARNING


class TestAnalyzeCapacity:
    """StegoService.analyze_capacity — публичный метод для UI."""

    def test_returns_capacity_report(self, png_carrier, small_payload, tmp_path):
        """Возвращает CapacityReport с заполненными полями."""
        service = StegoService()
        request = StegoTaskRequest(
            carrier_path=png_carrier,
            payload_path=small_payload,
            output_path=tmp_path / "out.png",
            password="test",
        )
        report = service.analyze_capacity(request)

        assert isinstance(report, CapacityReport)
        assert report.format == "PNG"
        assert report.algorithm == "LSB"
        assert report.capacity_bits > 0
        assert report.required_bits > 0
        assert report.payload_size_bytes == 200
        assert report.header_size_bytes == 57
        assert 0.0 <= report.utilization_percent <= 100.0

    def test_small_payload_fits(self, png_carrier, small_payload, tmp_path):
        """200 байт в PNG 64x64 -> fits=True."""
        service = StegoService()
        request = StegoTaskRequest(
            carrier_path=png_carrier,
            payload_path=small_payload,
            output_path=tmp_path / "out.png",
            password="test",
        )
        report = service.analyze_capacity(request)
        assert report.fits is True

    def test_huge_payload_does_not_fit(self, png_carrier, tmp_path):
        """Payload больше ёмкости -> fits=False, но без исключения.
           Задаем PNG 64x64 RGB = 12_288 пикселей = 12_288 бит ёмкости.
           Пытаемся скрыть пэйлоад, который заведомо не поместится.
        """
        huge = tmp_path / "huge.bin"
        huge.write_bytes(b"Y" * 10_000)

        service = StegoService()
        request = StegoTaskRequest(
            carrier_path=png_carrier,
            payload_path=huge,
            output_path=tmp_path / "out.png",
            password="test",
        )
        report = service.analyze_capacity(request)
        assert report.fits is False
        assert report.required_bits > report.capacity_bits

    def test_unsupported_format_raises(self, tmp_path, small_payload):
        """Неподдержанный формат -> CompatibilityError или ValueError."""
        bogus = tmp_path / "bogus.xyz"
        bogus.write_bytes(b"NOT_A_MEDIA_FILE")

        service = StegoService()
        request = StegoTaskRequest(
            carrier_path=bogus,
            payload_path=small_payload,
            output_path=tmp_path / "out.xyz",
            password="test",
        )
        with pytest.raises((CompatibilityError, ValueError)):
            service.analyze_capacity(request)


class TestHideDataMetrics:
    """После hide_data в response.metrics должны быть все новые поля."""

    def test_lsb_response_contains_all_metrics(
        self, png_carrier, small_payload, tmp_path
    ):
        """PNG-encode c compute_visual_metrics=True - в metrics все поля включая ssim.

        После оптимизации #25 SSIM считается опционально. Тест явно запрашивает
        визуальные метрики, чтобы проверить полный набор полей в response.
        """
        service = StegoService()
        output = tmp_path / "stego.png"
        request = StegoTaskRequest(
            carrier_path=png_carrier,
            payload_path=small_payload,
            output_path=output,
            password="test",
            compute_visual_metrics=True,
        )
        response = service.hide_data(request)

        assert response.success is True
        assert response.metrics is not None

        metrics = response.metrics
        assert "psnr" in metrics
        assert "ssim" in metrics
        assert "size_deviation" in metrics
        assert "quality_status" in metrics
        assert "time" in metrics

        # Для PNG LSB на 200 байт PSNR должен быть очень высоким
        assert metrics["psnr"] > 40.0
        assert metrics["ssim"] > 0.99
        # Статус - Enum
        assert isinstance(metrics["quality_status"], QualityStatus)
        assert metrics["quality_status"] == QualityStatus.OK

    def test_lsb_response_without_visual_metrics_omits_ssim(
        self, png_carrier, small_payload, tmp_path
    ):
        """По умолчанию compute_visual_metrics=False - ssim отсутствует в metrics.

        Архитектурное решение #25: SSIM не должен попадать мандаторно в hide_data.
        Защитный тест от случайного возврата к старому поведению.
        """
        service = StegoService()
        output = tmp_path / "stego.png"
        request = StegoTaskRequest(
            carrier_path=png_carrier,
            payload_path=small_payload,
            output_path=output,
            password="test",
            # compute_visual_metrics не указан - дефолт False
        )
        response = service.hide_data(request)

        assert response.success is True
        metrics = response.metrics

        # Обязательный набор остаётся.
        assert "psnr" in metrics
        assert "size_deviation" in metrics
        assert "quality_status" in metrics
        assert "time" in metrics
        # SSIM пропущен.
        assert "ssim" not in metrics, (
            "SSIM не должен считаться без явного запроса - это оптимизация #25."
        )