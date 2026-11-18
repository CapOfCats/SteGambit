"""Integration tests of Unicode file paths.

Covers: read/write via an open(rb)/open(wb) handle instead of a string path.
Covers interactions with paths in the OS and with encodings.
"""
import pytest

from stegambit.models.dto import StegoTaskRequest
from stegambit.services.stego_service import StegoService


pytestmark = [pytest.mark.integration]


# Directories that mimic real user scenarios.
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
    """Cyrillic and non-ASCII in the destination directory.

    Technique: equivalence — one class "non-ASCII path",
    but we take representatives from different language groups for possible locale-dependent Windows bugs.
    """

    @pytest.mark.parametrize("dir_name", UNICODE_DIR_NAMES)
    def test_png_roundtrip_in_unicode_dir(
        self, service, dir_name, png_medium, payload_tiny, tmp_path,
    ):
        """PNG round-trip in a directory with a non-ASCII name."""
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
        """WAV round-trip in a directory with a non-ASCII name (regression for scipy.io.wavfile)."""
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
        """JPEG round-trip in a directory with a non-ASCII name."""
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
    """Non-ASCII in the file name itself.

    Boundary case: the user names the stego file with a Cyrillic name
    directly in the Save Dialog. It must work for every format.
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
        """Round-trip when the stego file name contains non-ASCII characters."""
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
    """Non-ASCII in the paths of the input files.

    The cover, the payload, and the output are all in Cyrillic.
    """

    def test_all_paths_unicode_png(
        self, service, png_medium, payload_tiny, tmp_path,
    ):
        """All three paths (carrier, payload, output) contain Cyrillic."""
        unicode_dir = tmp_path / "блаблабла"
        unicode_dir.mkdir()

        # Copy artifacts into the unicode directory under unicode names.
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