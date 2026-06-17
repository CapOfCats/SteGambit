"""Unit-тесты для core/crypto по ADR 006.

Покрывают:
- KeyManager: детерминизм, валидация соли.
- CryptoEngine: round-trip, negative cases, структура фрейма, сжатие.
"""
import os
import struct

import pytest

from stegambit.core.exceptions import InvalidFrameError
from stegambit.core.crypto.engine import (
    CryptoEngine,
    FrameLayout,
    Flags,
)
from stegambit.core.crypto.key_manager import KeyManager

class TestKeyManager:
    """Деривация ключа и генерация соли."""

    def test_salt_has_correct_length(self):
        """Соль должна быть ровно 16 байт (ADR 006)."""
        salt = KeyManager.generate_salt()
        assert len(salt) == KeyManager.SALT_LENGTH_BYTES == 16

    def test_salt_is_random(self):
        """Две подряд сгенерированные соли не должны совпадать."""
        # Здесь уточнение - вероятность коллизии 2^-128 — считаем невозможной.
        assert KeyManager.generate_salt() != KeyManager.generate_salt()

    def test_derive_key_is_deterministic(self):
        """Одинаковые (password, salt) -> одинаковый ключ."""
        salt = b"\x00" * 16
        key1 = KeyManager.derive_key("hunter2", salt)
        key2 = KeyManager.derive_key("hunter2", salt)
        assert key1 == key2

    def test_derive_key_length_is_32_bytes(self):
        """AES-256 требует ровно 32 байта ключа."""
        key = KeyManager.derive_key("any_password", b"\x00" * 16)
        assert len(key) == 32

    def test_different_passwords_give_different_keys(self):
        """Лавинный эффект: даже близкие пароли дают разные ключи."""
        salt = b"\x00" * 16
        key_a = KeyManager.derive_key("password", salt)
        key_b = KeyManager.derive_key("Password", salt)
        assert key_a != key_b

    def test_different_salts_give_different_keys(self):
        """Защита от радужных таблиц: разная соль -> разный ключ."""
        key_a = KeyManager.derive_key("same_password", b"\x00" * 16)
        key_b = KeyManager.derive_key("same_password", b"\xff" * 16)
        assert key_a != key_b

    def test_invalid_salt_length_raises(self):
        """Соль неверной длины -> ValueError, а не тихий баг."""
        with pytest.raises(ValueError):
            KeyManager.derive_key("pwd", b"\x00" * 8)  # 8 вместо 16


class TestCryptoEngineRoundTrip:
    """Шифруем и сразу расшифровываем — результат должен совпадать с исходником."""

    @pytest.mark.parametrize("payload", [
        b"A",
        b"Hello, stego!",
        b"X" * 1000,
        b"Y" * (1024 * 1024),
        bytes(range(256)),
    ], ids=["1_byte", "short_string", "1kb", "1mb", "all_byte_values"])
    def test_encrypt_decrypt_preserves_data(self, payload):
        """encrypt -> decrypt == исходник для разных размеров payload."""
        frame = CryptoEngine.encrypt(payload, "test_pwd")
        recovered = CryptoEngine.decrypt(frame, "test_pwd")
        assert recovered == payload

    def test_empty_payload(self):
        """Пустые данные — валидный кейс (шифруем 0 байт)."""
        frame = CryptoEngine.encrypt(b"", "pwd")
        assert CryptoEngine.decrypt(frame, "pwd") == b""

    def test_unicode_password(self):
        """Пароли с нелатинскими символами работают (UTF-8)."""
        frame = CryptoEngine.encrypt(b"data", "☺пароль☺")
        assert CryptoEngine.decrypt(frame, "☺пароль☺") == b"data"


class TestCryptoEngineNegative:
    """Атаки, повреждения, неверные пароли — всё должно падать InvalidFrameError."""

    def test_wrong_password_fails(self):
        """Неверный пароль -> InvalidFrameError (MAC mismatch)."""
        frame = CryptoEngine.encrypt(b"secret", "correct")
        with pytest.raises(InvalidFrameError):
            CryptoEngine.decrypt(frame, "wrong")

    def test_tampered_ciphertext_fails(self):
        """Поменяли байт в ciphertext -> MAC не сходится."""
        frame = CryptoEngine.encrypt(b"secret data", "pwd")
        # Ломаем первый байт ciphertext (он идёт сразу после 57-байтного заголовка).
        tampered = bytearray(frame)
        tampered[FrameLayout.HEADER_LEN] ^= 0xFF
        with pytest.raises(InvalidFrameError):
            CryptoEngine.decrypt(bytes(tampered), "pwd")

    def test_tampered_mac_fails(self):
        """Поменяли байт в MAC -> InvalidFrameError."""
        frame = CryptoEngine.encrypt(b"data", "pwd")
        tampered = bytearray(frame)
        # MAC лежит в заголовке в позиции 41..57 (см. FrameLayout в ADR 006).
        tampered[41] ^= 0x01
        with pytest.raises(InvalidFrameError):
            CryptoEngine.decrypt(bytes(tampered), "pwd")

    def test_invalid_magic_fails(self):
        """Чужой/повреждённый MAGIC -> ранняя ошибка, без попытки расшифровки."""
        garbage = b"XXXX" + b"\x00" * (FrameLayout.HEADER_LEN - 4) + b"payload"
        with pytest.raises(InvalidFrameError, match="MAGIC"):
            CryptoEngine.decrypt(garbage, "pwd")

    def test_truncated_frame_fails(self):
        """Фрейм короче 57 байт -> ошибка."""
        with pytest.raises(InvalidFrameError):
            CryptoEngine.decrypt(b"too_short", "pwd")

    def test_lying_length_field_fails(self):
        """Length говорит 1000 байт, а реально их нет -> ошибка парсинга."""
        frame = CryptoEngine.encrypt(b"short", "pwd")
        tampered = bytearray(frame)
        # Поле LENGTH лежит в позиции 33..41 (big-endian uint64).
        tampered[33:41] = struct.pack(">Q", 999999)
        with pytest.raises(InvalidFrameError):
            CryptoEngine.decrypt(bytes(tampered), "pwd")


class TestFrameStructure:
    """Проверяем, что CryptoEngine формирует фрейм строго по ADR 006."""

    def test_frame_starts_with_magic(self):
        """Первые 4 байта — всегда MAGIC = b'SGB1'."""
        frame = CryptoEngine.encrypt(b"data", "pwd")
        assert frame[:4] == FrameLayout.MAGIC == b"SGB1"

    def test_frame_header_is_57_bytes(self):
        """Заголовок ADR 006 — ровно 57 байт."""
        assert FrameLayout.HEADER_LEN == 57
        frame = CryptoEngine.encrypt(b"", "pwd")
        # Пустой payload -> весь фрейм = только заголовок.
        assert len(frame) == FrameLayout.HEADER_LEN

    def test_frame_total_size_matches_payload(self):
        """len(frame) == HEADER_LEN + len(ciphertext). Ciphertext == len(plaintext) для GCM."""
        payload = b"X" * 100
        frame = CryptoEngine.encrypt(payload, "pwd")
        # GCM не добавляет padding -> размер ciphertext = размер plaintext.
        # Но может быть сжатие — тогда размер меньше. Проверим нижнюю границу.
        assert len(frame) >= FrameLayout.HEADER_LEN
        assert len(frame) <= FrameLayout.HEADER_LEN + len(payload)

    def test_two_encryptions_produce_different_frames(self):
        """Одинаковый payload + пароль -> разные фреймы (случайные salt и nonce)."""
        frame1 = CryptoEngine.encrypt(b"same", "same")
        frame2 = CryptoEngine.encrypt(b"same", "same")
        assert frame1 != frame2
        # Но оба расшифровываются в оригинал.
        assert CryptoEngine.decrypt(frame1, "same") == b"same"
        assert CryptoEngine.decrypt(frame2, "same") == b"same"


class TestCompression:
    """Эвристика zlib-сжатия и корректность флага COMPRESSED."""

    def test_compressible_data_sets_flag(self):
        """Сильно сжимаемые данные (1000 одинаковых байт) -> флаг COMPRESSED = 1."""
        payload = b"A" * 1000
        frame = CryptoEngine.encrypt(payload, "pwd")
        flags_byte = frame[4]  # FLAGS — 5-й байт заголовка
        assert flags_byte & Flags.COMPRESSED

    def test_random_data_does_not_compress(self):
        """Случайные данные не сжимаются -> флаг COMPRESSED = 0."""
        payload = os.urandom(1000)
        frame = CryptoEngine.encrypt(payload, "pwd")
        flags_byte = frame[4]
        assert not (flags_byte & Flags.COMPRESSED)

    def test_small_data_skips_compression(self):
        """Данные меньше порога (256 байт) — сжатие не пытается."""
        payload = b"A" * 100  # сжалось бы, но слишком мало
        frame = CryptoEngine.encrypt(payload, "pwd")
        flags_byte = frame[4]
        assert not (flags_byte & Flags.COMPRESSED)

    def test_compressed_roundtrip(self):
        """Сжатые данные корректно распаковываются при decrypt."""
        payload = b"repeating pattern " * 500
        frame = CryptoEngine.encrypt(payload, "pwd")
        assert CryptoEngine.decrypt(frame, "pwd") == payload

    def test_custom_flags_preserved(self):
        """Пользовательские флаги (IS_DECOY) не затираются логикой сжатия."""
        payload = b"A" * 1000  # будет сжато
        frame = CryptoEngine.encrypt(payload, "pwd", flags=Flags.IS_DECOY)
        flags_byte = frame[4]
        assert flags_byte & Flags.IS_DECOY      # пользовательский флаг сохранён
        assert flags_byte & Flags.COMPRESSED    # авто-флаг тоже выставлен