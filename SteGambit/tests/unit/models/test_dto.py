"""Unit-тесты для DTO-слоя (models/dto.py).

В модуле не покрыты:
    * Валидация Path - возложена на pathlib.
    * Логика fits=True/False - определена в StegoService.
"""
from dataclasses import FrozenInstanceError
from pathlib import Path
from stegambit.models.dto import QualityStatus

import pytest

from stegambit.models.dto import (
    QualityStatus,
    StegoTaskRequest,
    StegoResponse,
    CapacityReport,
)

@pytest.fixture
def request_base_kwargs(tmp_path):
    """Создаёт временные файлы для прохождения валидации __post_init__."""
    carrier = tmp_path / "carrier.png"
    payload = tmp_path / "payload.txt"
    carrier.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # mock
    payload.write_text("secret data")
    return {
        "carrier_path": carrier,
        "payload_path": payload,
        "output_path": tmp_path / "stego.png",  # parent существует, сам файл - нет
        "password": "secret",
    }

@pytest.fixture
def capacity_base_kwargs():
    return {
        "fits": True,
        "format": "PNG",
        "algorithm": "LSB",
        "capacity_bits": 10000,
        "required_bits": 5000,
        "payload_size_bytes": 500,
        "header_size_bytes": 57,
        "utilization_percent": 50.0,
    }

class TestQualityStatus:
    """Триггер качества операции — str-Enum с тремя значениями."""

    def test_has_three_values(self):
        assert len(QualityStatus) == 3

    @pytest.mark.parametrize("status, expected_str", [
        (QualityStatus.OK, "OK"),
        (QualityStatus.WARNING, "WARNING"),
        (QualityStatus.ANOMALY, "ANOMALY"),
    ])

    def test_string_values_match_spec(self, status, expected_str):
        assert status.value == expected_str

    def test_str_enum_comparable_with_plain_string(self):
        """Enum должен работать в сравнении == "OK" """
        assert QualityStatus.OK == "OK"
        assert QualityStatus.WARNING == "WARNING"

    def test_construction_from_string(self):
        """QualityStatus('OK') должен восстанавливать enum."""
        assert QualityStatus("OK") is QualityStatus.OK


class TestStegoTaskRequest:
    """Тестирование модели класса стего-запроса с валидацией в __post_init__."""

    def test_creation_with_valid_kwargs(self, request_base_kwargs):
        """Happy path: все поля валидны - DTO создаётся."""
        req = StegoTaskRequest(**request_base_kwargs)
        assert req.password == "secret"
        assert req.carrier_path.exists()
        assert req.payload_path.exists()

    def test_paths_are_resolved_to_absolute(self, request_base_kwargs):
        """Пути нормализуются к абсолютным."""
        req = StegoTaskRequest(**request_base_kwargs)
        assert req.carrier_path.is_absolute()
        assert req.payload_path.is_absolute()
        assert req.output_path.is_absolute()

    def test_empty_password_is_allowed(self, request_base_kwargs):
        """Пустой пароль допустим и используется в analyze_capacity."""
        request_base_kwargs["password"] = ""
        req = StegoTaskRequest(**request_base_kwargs)
        assert req.password == ""

    def test_missing_carrier_raises(self, request_base_kwargs, tmp_path):
        """Негативный кейз: carrier_path не существует - FileNotFoundError."""
        request_base_kwargs["carrier_path"] = tmp_path / "ghost.png"
        with pytest.raises(FileNotFoundError, match="Carrier not found"):
            StegoTaskRequest(**request_base_kwargs)

    def test_missing_payload_raises(self, request_base_kwargs, tmp_path):
        """Негативный кейз: payload_path не существует - FileNotFoundError."""
        request_base_kwargs["payload_path"] = tmp_path / "ghost.txt"
        with pytest.raises(FileNotFoundError, match="Payload not found"):
            StegoTaskRequest(**request_base_kwargs)

    def test_carrier_is_directory_raises(self, request_base_kwargs, tmp_path):
        """Негативный кейз: carrier - директория, не файл - ValueError."""
        a_dir = tmp_path / "some_dir"
        a_dir.mkdir()
        request_base_kwargs["carrier_path"] = a_dir
        with pytest.raises(ValueError, match="Carrier is not a file"):
            StegoTaskRequest(**request_base_kwargs)

    def test_output_parent_missing_raises(self, request_base_kwargs, tmp_path):
        """Негативный кейз: родитель output_path не существует - FileNotFoundError."""
        request_base_kwargs["output_path"] = tmp_path / "ghost_dir" / "out.png"
        with pytest.raises(FileNotFoundError, match="Output directory does not exist"):
            StegoTaskRequest(**request_base_kwargs)

    def test_non_string_password_raises(self, request_base_kwargs):
        """Негативный кейз: пароль не строка - TypeError."""
        request_base_kwargs["password"] = 12345
        with pytest.raises(TypeError, match="Password must be str"):
            StegoTaskRequest(**request_base_kwargs)

    def test_frozen_blocks_field_mutation(self, request_base_kwargs):
        """Негативный кейз: попытка изменить поле frozen-dataclass - FrozenInstanceError."""
        req = StegoTaskRequest(**request_base_kwargs)
        with pytest.raises(FrozenInstanceError):
            req.password = "new_password"

    def test_frozen_blocks_path_replacement(self, request_base_kwargs, tmp_path):
        """Замена пути на другой Path также блокируется frozen-атрибутом."""
        req = StegoTaskRequest(**request_base_kwargs)
        with pytest.raises(FrozenInstanceError):
            req.carrier_path = tmp_path / "other.png"


class TestStegoResponse:
    """Тестирование модели класса стего-ответа."""

    def test_success_only_response(self):
        """Optional поля по умолчанию None."""
        resp = StegoResponse(success=True)
        assert resp.success is True
        assert resp.output_path is None
        assert resp.metrics is None
        assert resp.error is None

    def test_full_response(self, tmp_path):
        metrics = {"psnr": 51.2, "time": 0.5}
        resp = StegoResponse(
            success=True,
            output_path=tmp_path / "out.png",
            metrics=metrics,
            error=None,
        )
        assert resp.metrics["psnr"] == 51.2
        assert resp.output_path == tmp_path / "out.png"

    def test_failure_response(self):
        """Ошибочный ответ - success=False + сообщение об ошибке"""
        resp = StegoResponse(success=False, error="Capacity overflow")
        assert resp.success is False
        assert resp.error == "Capacity overflow"

    def test_metrics_accepts_heterogeneous_dict(self):
        """metrics: Dict[str, Any] — допустимы разные типы значений."""
        metrics = {
            "psnr": 51.2,
            "time": 0.5,
            "quality_status": QualityStatus.OK,
            "algorithm": "LSB",
        }
        resp = StegoResponse(success=True, metrics=metrics)
        assert resp.metrics["quality_status"] is QualityStatus.OK

    def test_frozen_blocks_mutation(self):
        resp = StegoResponse(success=True)
        with pytest.raises(FrozenInstanceError):
            resp.success = False


class TestCapacityReport:

    def test_full_creation(self, capacity_base_kwargs):
        report = CapacityReport(**capacity_base_kwargs)
        assert report.fits is True
        assert report.format == "PNG"
        assert report.algorithm == "LSB"

    @pytest.mark.parametrize("util", [0.0, 50.0, 99.9, 100.0, 150.0])
    def test_utilization_boundary_values(self, capacity_base_kwargs, util):
        """Граничный кейз: utilization может быть 0, 50, 100, >100 — DTO не валидирует."""
        capacity_base_kwargs["utilization_percent"] = util
        report = CapacityReport(**capacity_base_kwargs)
        assert report.utilization_percent == util

    def test_negative_fits_when_overflow(self, capacity_base_kwargs):
        """fits=False — допустимое состояние при переполнении буфера."""
        capacity_base_kwargs["fits"] = False
        capacity_base_kwargs["required_bits"] = 20000
        capacity_base_kwargs["utilization_percent"] = 200.0
        report = CapacityReport(**capacity_base_kwargs)
        assert report.fits is False
        assert report.utilization_percent == 200.0

    def test_all_fields_required(self):
        """Негативный кейз: CapacityReport не имеет дефолтов - пропуск поля -> TypeError."""
        with pytest.raises(TypeError):
            CapacityReport(fits=True, format="PNG")

    def test_frozen_blocks_mutation(self, capacity_base_kwargs):
        """Запрещенная мутация frozen-атрибутом."""
        report = CapacityReport(**capacity_base_kwargs)
        with pytest.raises(FrozenInstanceError):
            report.fits = False