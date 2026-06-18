"""Integration-тесты на Unicode-пути файлов.

Покрывает: read/write через open(rb)/open(wb) handle вместо строкового пути.
Покрывает случаи взаимодействий с путями в системе и кодировками.
"""
import pytest

from stegambit.models.dto import StegoTaskRequest
from stegambit.services.stego_service import StegoService


pytestmark = [pytest.mark.integration]


# Каталоги, имитирующие реальные пользовательские сценарии.
UNICODE_DIR_NAMES = [
    "кириллица",
    "中文目录",
    "日本語",
    "Ελληνικά",
    "papka s probelami",
    "emoji_🔐_dir",
    "смешанный_dir_中",
]


@pytest.fixture
def service():
    return StegoService()


class TestUnicodeDirectories:
    """Кириллица и не-ASCII в каталоге назначения.

    Техника: эквивалентность - один класс "не-ASCII путь",
    но представителей берём из разных языковых групп на возможные локаль-зависимые баги Windows.
    """

    @pytest.mark.parametrize("dir_name", UNICODE_DIR_NAMES)
    def test_png_roundtrip_in_unicode_dir(
        self, service, dir_name, png_medium, payload_tiny, tmp_path,
    ):
        """PNG round-trip в каталоге с не-ASCII именем."""
        work_dir = tmp_path / dir_name
        work_dir.mkdir()
        stego_path = work_dir / "stego.png"
        extract_out = work_dir / "extracted"

        service.hide_data(StegoTaskRequest(
            carrier_path=png_medium,
            payload_path=payload_tiny,
            output_path=stego_path,
            password="pwd",
        ))
        resp = service.extract_data(StegoTaskRequest(
            carrier_path=stego_path,
            payload_path=stego_path,
            output_path=extract_out,
            password="pwd",
        ))

        assert resp.success
        assert resp.output_path.read_bytes() == payload_tiny.read_bytes()

    @pytest.mark.parametrize("dir_name", UNICODE_DIR_NAMES)
    def test_wav_roundtrip_in_unicode_dir(
        self, service, dir_name, wav_carrier, payload_tiny, tmp_path,
    ):
        """WAV round-trip в каталоге с не-ASCII именем (регресс по scipy.io.wavfile)."""
        work_dir = tmp_path / dir_name
        work_dir.mkdir()
        stego_path = work_dir / "stego.wav"
        extract_out = work_dir / "extracted"

        service.hide_data(StegoTaskRequest(
            carrier_path=wav_carrier,
            payload_path=payload_tiny,
            output_path=stego_path,
            password="pwd",
        ))
        resp = service.extract_data(StegoTaskRequest(
            carrier_path=stego_path,
            payload_path=stego_path,
            output_path=extract_out,
            password="pwd",
        ))

        assert resp.success
        assert resp.output_path.read_bytes() == payload_tiny.read_bytes()

    @pytest.mark.parametrize("dir_name", UNICODE_DIR_NAMES)
    def test_jpeg_roundtrip_in_unicode_dir(
        self, service, dir_name, jpeg_carrier, payload_tiny, tmp_path,
    ):
        """JPEG round-trip в каталоге с не-ASCII именем."""
        work_dir = tmp_path / dir_name
        work_dir.mkdir()
        stego_path = work_dir / "stego.jpg"
        extract_out = work_dir / "extracted"

        service.hide_data(StegoTaskRequest(
            carrier_path=jpeg_carrier,
            payload_path=payload_tiny,
            output_path=stego_path,
            password="pwd",
        ))
        resp = service.extract_data(StegoTaskRequest(
            carrier_path=stego_path,
            payload_path=stego_path,
            output_path=extract_out,
            password="pwd",
        ))

        assert resp.success
        assert resp.output_path.read_bytes() == payload_tiny.read_bytes()


class TestUnicodeFilenames:
    """Не-ASCII в самом имени файла.

    Граничный кейс: пользователь именует стего-файл "секретик.png"
    напрямую в Save Dialog. Должно работать на всех форматах.
    """

    @pytest.mark.parametrize(
        "filename, carrier_fixture",
        [
            ("секретик.png", "png_medium"),
            ("стего_файл.png", "png_medium"),
            ("музыка.wav", "wav_carrier"),
            ("фото_中文.jpg", "jpeg_carrier"),
            ("🔐stego.png", "png_medium"),
        ],
        ids=[
            "cyrillic_png", "cyrillic_underscore_png",
            "cyrillic_wav", "mixed_cyrillic_chinese_jpg",
            "emoji_png",
        ],
    )
    def test_unicode_filename_roundtrip(
        self, request, service, filename, carrier_fixture,
        payload_tiny, tmp_path,
    ):
        """Round-trip когда не-ASCII символы в имени стего-файла."""
        carrier = request.getfixturevalue(carrier_fixture)
        stego_path = tmp_path / filename
        extract_out = tmp_path / "extracted"

        service.hide_data(StegoTaskRequest(
            carrier_path=carrier,
            payload_path=payload_tiny,
            output_path=stego_path,
            password="pwd",
        ))
        resp = service.extract_data(StegoTaskRequest(
            carrier_path=stego_path,
            payload_path=stego_path,
            output_path=extract_out,
            password="pwd",
        ))

        assert resp.success
        assert resp.output_path.read_bytes() == payload_tiny.read_bytes()


class TestUnicodeCarrierAndPayload:
    """Не-ASCII в путях входных файлов.

    И cover, и payload, и output - все в кириллице.
    """

    def test_all_paths_unicode_png(
        self, service, png_medium, payload_tiny, tmp_path,
    ):
        """Все три пути (carrier, payload, output) содержат кириллицу."""
        unicode_dir = tmp_path / "блаблабла"
        unicode_dir.mkdir()

        # Копируем артефакты в unicode-каталог под unicode-именами.
        carrier_uni = unicode_dir / "носитель.png"
        carrier_uni.write_bytes(png_medium.read_bytes())

        payload_uni = unicode_dir / "секрет.txt"
        payload_uni.write_bytes(payload_tiny.read_bytes())

        stego_path = unicode_dir / "результат.png"
        extract_out = unicode_dir / "извлечено"

        service.hide_data(StegoTaskRequest(
            carrier_path=carrier_uni,
            payload_path=payload_uni,
            output_path=stego_path,
            password="пароль",
        ))
        resp = service.extract_data(StegoTaskRequest(
            carrier_path=stego_path,
            payload_path=stego_path,
            output_path=extract_out,
            password="пароль",
        ))

        assert resp.success
        assert resp.output_path.read_bytes() == payload_tiny.read_bytes()