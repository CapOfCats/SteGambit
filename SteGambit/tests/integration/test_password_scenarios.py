"""Password scenarios: empty, unicode, long, wrong, ciphertext non-determinism.

Covers the crypto layer through the public service API. Guarantees that
the seed scheme (SHA-256 of the password) works on any string, and that GCM catches
a password mismatch on extract.
"""
import pytest

from stegambit.core.exceptions import InvalidFrameError
from stegambit.models.dto import StegoTaskRequest
from stegambit.services.stego_service import StegoService


pytestmark = [pytest.mark.integration]


def _hide_and_extract(carrier, payload, tmp_path, *, encode_pwd, decode_pwd):
    """Helper: encode with one password, decode with another. Returns the response."""
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
        "",                              # empty — regression for a recent GUI bug
        "x",                             # 1 character
        "simple_password_123",           # plain ASCII
        "пароль_с_кириллицей",           # unicode Cyrillic
        "♂♀♪",                       # emoji
        "пароль🔐mixed_123",             # mixed string
        "a" * 500,                       # very long
        "!@#$%^&*()_+-={}[]|\\:;\"'<>?,./",  # special characters
        "   ",                           # spaces only
        "\n\t\r",                        # non-printable whitespace
    ],
    ids=[
        "empty", "single_char", "simple_ascii",
        "cyrillic", "emoji", "mixed_unicode",
        "very_long_500", "special_chars",
        "spaces_only", "whitespace_escapes",
    ],
)
def test_password_roundtrip_succeeds(password, png_small, payload_tiny, tmp_path):
    """Any valid str password gives a correct round-trip when encode == decode."""
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
        ("пароль", "пapoль"),           # look-alike characters (Latin vs Cyrillic)
    ],
    ids=[
        "wrong_password", "empty_vs_nonempty", "nonempty_vs_empty",
        "different_strings", "case_sensitive", "look_alike_unicode",
    ],
)
def test_wrong_password_raises_invalid_frame(
    encode_pwd, decode_pwd, png_small, payload_tiny, tmp_path,
):
    """A password mismatch -> InvalidFrameError.

    This is the first line of defense: a different coordinate pool -> garbage
    bits are read -> MAGIC bytes are not found before the GCM MAC is even checked.
    """
    with pytest.raises(InvalidFrameError):
        _hide_and_extract(
            png_small, payload_tiny, tmp_path,
            encode_pwd=encode_pwd, decode_pwd=decode_pwd,
        )


def test_non_determinism_of_ciphertext(png_medium, payload_tiny, tmp_path):
    """The same payload + password -> DIFFERENT stego files (random nonce).

    A cryptographic guarantee: a repeated encode does not create an identical
    stego container, even with identical inputs. This protects against detect-by-comparison attacks.
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

    # Both must decode to the same payload.
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
    """Regression for a GUI bug: encode with "" -> decode with "" must be consistent.

    Duplicates one case from the parametrization, but is split out as its own
    test so it is easy to read in CI reports.
    """
    resp = _hide_and_extract(
        png_small, payload_tiny, tmp_path,
        encode_pwd="", decode_pwd="",
    )
    assert resp.success
    assert resp.output_path.read_bytes() == payload_tiny.read_bytes()