"""Integration-тесты политики "запрет конвертации формата".

Покрывает ADR про несменяемость формата носителя. Stego-output должен сохранять исходный формат носителя.
Попытка задать output с другим расширением приведет к CompatibilityError ДО embed.
"""
import pytest

from stegambit.core.exceptions import CompatibilityError
from stegambit.models.dto import StegoTaskRequest
from stegambit.services.stego_service import StegoService


pytestmark = [pytest.mark.integration]


@pytest.fixture
def service():
    return StegoService()


class TestForbiddenConversions:
    """Decision table: пары (carrier_fmt, output_ext), которые ДОЛЖНЫ падать.

    Техника: таблица решений. Каждая строка - запрещённая комбинация
    форматов, проверяем что сервис корректно отказывает.
    """

    @pytest.mark.parametrize(
        "carrier_fixture, forbidden_ext",
        [
            # PNG-носитель нельзя сохранять в чужие форматы.
            ("png_medium", ".jpg"),
            ("png_medium", ".jpeg"),
            ("png_medium", ".wav"),
            ("png_medium", ".bmp"),
            # JPEG-носитель.
            ("jpeg_carrier", ".png"),
            ("jpeg_carrier", ".wav"),
            ("jpeg_carrier", ".bin"),
            # WAV-носитель.
            ("wav_carrier", ".png"),
            ("wav_carrier", ".mp3"),
            ("wav_carrier", ".jpg"),
        ],
        ids=[
            "PNG->jpg", "PNG->jpeg", "PNG->wav", "PNG->bmp",
            "JPEG->png", "JPEG->wav", "JPEG->bin",
            "WAV->png", "WAV->mp3", "WAV->jpg",
        ],
    )
    def test_forbidden_output_extension_raises(
        self, request, service, carrier_fixture, forbidden_ext,
        payload_tiny, tmp_path,
    ):
        """Несовпадение carrier-формата и output-расширения -> CompatibilityError.

        Эквивалентность: все запрещённые расширения - один класс отказа.
        """
        carrier = request.getfixturevalue(carrier_fixture)
        stego_path = tmp_path / f"stego{forbidden_ext}"

        with pytest.raises(CompatibilityError):
            service.hide_data(StegoTaskRequest(
                carrier_path=carrier,
                payload_path=payload_tiny,
                output_path=stego_path,
                password="pwd",
            ))

        # Запрет на конвертацию - файл не должен быть создан.
        assert not stego_path.exists(), (
            "Файл создан, хотя политика запрещает конвертацию формата."
        )


class TestAllowedFormats:
    """Сэнити-блок: положительные кейсы политики должны проходить.

    Техника: позитивные представители классов эквивалентности из таблицы решений.
    """

    @pytest.mark.parametrize(
        "carrier_fixture, allowed_ext",
        [
            ("png_medium", ".png"),
            ("jpeg_carrier", ".jpg"),
            ("jpeg_carrier", ".jpeg"),
            ("wav_carrier", ".wav"),
        ],
        ids=["PNG->png", "JPEG->jpg", "JPEG->jpeg", "WAV->wav"],
    )
    def test_matching_extension_succeeds(
        self, request, service, carrier_fixture, allowed_ext,
        payload_tiny, tmp_path,
    ):
        """Совпадение carrier-формата и output-расширения -> embed успешен."""
        carrier = request.getfixturevalue(carrier_fixture)
        stego_path = tmp_path / f"stego{allowed_ext}"

        resp = service.hide_data(StegoTaskRequest(
            carrier_path=carrier,
            payload_path=payload_tiny,
            output_path=stego_path,
            password="pwd",
        ))

        assert resp.success
        assert stego_path.exists()


class TestCaseSensitivity:
    """Поведение при разных регистрах расширения."""

    @pytest.mark.parametrize(
        "ext_variant",
        [".PNG", ".Png", ".pNg"],
        ids=["upper", "title", "mixed"],
    )
    def test_extension_case_insensitive_for_png(
        self, service, png_medium, payload_tiny, tmp_path, ext_variant,
    ):
        """Расширение должно сравниваться case-insensitive.

        Граничный кейс: пользователь сохраняет в "stego.PNG" из Save Dialog
        на Windows - должно работать так же, как ".png".
        """
        stego_path = tmp_path / f"stego{ext_variant}"

        resp = service.hide_data(StegoTaskRequest(
            carrier_path=png_medium,
            payload_path=payload_tiny,
            output_path=stego_path,
            password="pwd",
        ))

        assert resp.success
        assert stego_path.exists()