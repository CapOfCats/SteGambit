"""Сценарии паролей: пустой, юникод, длинный, неверный, не-определимость шифра.

Покрывает crypto-слой через публичный API сервиса. Гарантирует, что
seed-схема (SHA-256 от пароля) работает на любых строках, а GCM ловит
несовпадение пароля при extract.
"""
import pytest

from stegambit.core.exceptions import InvalidFrameError
from stegambit.models.dto import StegoTaskRequest
from stegambit.services.stego_service import StegoService


pytestmark = [pytest.mark.integration]


def _hide_and_extract(carrier, payload, tmp_path, *, encode_pwd, decode_pwd):
    """Хелпер: encode с одним паролем, decode с другим. Возвращает response."""
    service = StegoService()
    stego_path = tmp_path / "stego.png"
    extract_out = tmp_path / "extracted"

    service.hide_data(StegoTaskRequest(
        carrier_path=carrier,
        payload_path=payload,
        output_path=stego_path,
        password=encode_pwd,
    ))
    return service.extract_data(StegoTaskRequest(
        carrier_path=stego_path,
        payload_path=stego_path,
        output_path=extract_out,
        password=decode_pwd,
    ))


@pytest.mark.parametrize(
    "password",
    [
        "",                              # пустой - регресс на свежий GUI-баг
        "x",                             # 1 символ
        "simple_password_123",           # обычный ASCII
        "пароль_с_кириллицей",           # юникод-кириллица
        "♂♀♪",                       # эмодзи
        "пароль🔐mixed_123",             # смешанная строка
        "a" * 500,                       # очень длинный
        "!@#$%^&*()_+-={}[]|\\:;\"'<>?,./",  # спец-символы
        "   ",                           # только пробелы
        "\n\t\r",                        # whitespace-непечатные
    ],
    ids=[
        "empty", "single_char", "simple_ascii",
        "cyrillic", "emoji", "mixed_unicode",
        "very_long_500", "special_chars",
        "spaces_only", "whitespace_escapes",
    ],
)
def test_password_roundtrip_succeeds(password, png_small, payload_tiny, tmp_path):
    """Любой валидный str-пароль даёт корректный round-trip, если encode == decode."""
    resp = _hide_and_extract(
        png_small, payload_tiny, tmp_path,
        encode_pwd=password, decode_pwd=password,
    )
    assert resp.success
    assert resp.output_path.read_bytes() == payload_tiny.read_bytes()


@pytest.mark.parametrize(
    "encode_pwd, decode_pwd",
    [
        ("correct", "wrong"),
        ("", "non_empty"),
        ("non_empty", ""),
        ("password1", "password2"),
        ("Password", "password"),       # case-sensitivity
        ("пароль", "пapoль"),           # визуально похожие символы (латинские vs кириллица)
    ],
    ids=[
        "wrong_password", "empty_vs_nonempty", "nonempty_vs_empty",
        "different_strings", "case_sensitive", "look_alike_unicode",
    ],
)
def test_wrong_password_raises_invalid_frame(
    encode_pwd, decode_pwd, png_small, payload_tiny, tmp_path,
):
    """Несовпадение пароля -> InvalidFrameError.

    Это первая линия защиты: пул координат разный -> читаются мусорные
    биты -> MAGIC bytes не найдены до того, как GCM-MAC даже проверится.
    """
    with pytest.raises(InvalidFrameError):
        _hide_and_extract(
            png_small, payload_tiny, tmp_path,
            encode_pwd=encode_pwd, decode_pwd=decode_pwd,
        )


def test_non_determinism_of_ciphertext(png_medium, payload_tiny, tmp_path):
    """Один и тот же payload + пароль -> РАЗНЫЕ stego-файлы (рандомный nonce).

    Гарантия криптостойкости: повторный encode не создаёт идентичный
    стего-контейнер, даже при идентичных входах. Это защищает от detect-by-comparison атак.
    """
    service = StegoService()

    stego1 = tmp_path / "stego1.png"
    stego2 = tmp_path / "stego2.png"

    for out in (stego1, stego2):
        service.hide_data(StegoTaskRequest(
            carrier_path=png_medium,
            payload_path=payload_tiny,
            output_path=out,
            password="fixed_password",
        ))

    bytes1 = stego1.read_bytes()
    bytes2 = stego2.read_bytes()

    assert bytes1 != bytes2, (
        "Stego-файлы идентичны после двух encode - nonce не рандомизируется. "
        "Это критическая уязвимость."
    )

    # Оба должны декодиться в тот же payload.
    extract1 = tmp_path / "extract1"
    extract2 = tmp_path / "extract2"

    r1 = service.extract_data(StegoTaskRequest(
        carrier_path=stego1, payload_path=stego1,
        output_path=extract1, password="fixed_password",
    ))
    r2 = service.extract_data(StegoTaskRequest(
        carrier_path=stego2, payload_path=stego2,
        output_path=extract2, password="fixed_password",
    ))

    payload_bytes = payload_tiny.read_bytes()
    assert r1.output_path.read_bytes() == payload_bytes
    assert r2.output_path.read_bytes() == payload_bytes


def test_empty_password_encode_empty_decode(png_small, payload_tiny, tmp_path):
    """Регресс на GUI-баг: encode с "" -> decode с "" должны быть консистентны.

    Дублирует один кейс из параметризации, но вынесен отдельным
    тестом для явной читаемости в отчётах CI.
    """
    resp = _hide_and_extract(
        png_small, payload_tiny, tmp_path,
        encode_pwd="", decode_pwd="",
    )
    assert resp.success
    assert resp.output_path.read_bytes() == payload_tiny.read_bytes()