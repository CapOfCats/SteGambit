import os
import struct
import zlib
from dataclasses import dataclass
from enum import IntFlag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .key_manager import KeyManager


class FrameLayout:
    """Структура 57-байтного фрейма."""
    MAGIC = b"SGB1"
    MAGIC_LEN = 4
    FLAGS_LEN = 1
    SALT_LEN = 16
    NONCE_LEN = 12
    LENGTH_LEN = 8
    MAC_LEN = 16
    HEADER_LEN = MAGIC_LEN + FLAGS_LEN + SALT_LEN + NONCE_LEN + LENGTH_LEN + MAC_LEN

class Flags(IntFlag):
    """Битовые маски поля FLAGS."""
    COMPRESSED = 0x01
    IS_DECOY = 0x02

class HeuristicCompression:
    """Эвристика включения сжатия."""
    COMPRESSION_MIN_SIZE = 256        # меньше — сжимать нет смысла
    COMPRESSION_RATIO_THRESHOLD = 0.9  # сжимаем, только если выигрыш > 10%
    COMPRESSION_LEVEL = 9


@dataclass(frozen=True)
class _ParsedFrame:
    """Распарсенный 57-байтный заголовок + ciphertext."""
    flags: int
    salt: bytes
    nonce: bytes
    length: int
    mac: bytes
    ciphertext: bytes


class InvalidFrameError(RuntimeError):
    """Невалидный magic, повреждение заголовка или неверный пароль."""
    pass


class CryptoEngine:
    """AES-256-GCM шифрование с упаковкой в 57-байтный фрейм по ADR 006.

    Все методы статические и stateless — безопасно звать из любого потока.
    """

    @staticmethod
    def _should_compress(data: bytes) -> tuple[bytes, bool]:
        """Сжимает data через zlib, если это даёт выигрыш > 10%.

        Returns:
            (сжатые данные, был_ли_применён_zlib).
        """
        if len(data) < HeuristicCompression.COMPRESSION_MIN_SIZE:
            return data, False
        compressed = zlib.compress(data, level=HeuristicCompression.COMPRESSION_LEVEL)
        if len(compressed) < len(data) * HeuristicCompression.COMPRESSION_RATIO_THRESHOLD:
            return compressed, True
        return data, False

    @staticmethod
    def encrypt(data: bytes, password: str, /, *, flags: int = 0) -> bytes:
        """Шифрует data и упаковывает в 57-байтный фрейм по - ADR 006.

        Как работает:
            1. Опциональное zlib-сжатие (эвристика).
            2. Генерация случайных SALT (16) и NONCE (12).
            3. PBKDF2 -> AES-ключ.
            4. AES-GCM -> ciphertext + MAC.
            5. Сборка фрейма MAGIC|FLAGS|SALT|NONCE|LENGTH|MAC|DATA

        Args:
            data: исходные байты payload.
            password: пароль пользователя.
            flags: дополнительные биты FLAGS (например, IS_DECOY). Бит COMPRESSED выставляется автоматически.

        Returns:
            Готовый к внедрению бинарный блоб.
        """
        processed, compressed = CryptoEngine._should_compress(data)
        if compressed:
            flags |= Flags.COMPRESSED

        salt = KeyManager.generate_salt()
        nonce = os.urandom(FrameLayout.NONCE_LEN)
        key = KeyManager.derive_key(password, salt)

        aesgcm = AESGCM(key)
        ct_with_tag = aesgcm.encrypt(nonce, processed, associated_data=None)
        ciphertext, mac = ct_with_tag[:-FrameLayout.MAC_LEN], ct_with_tag[-FrameLayout.MAC_LEN:] # всегда равен 16 байтам в конце

        length = len(processed)
        header = (
            FrameLayout.MAGIC
            + struct.pack("B", flags & 0xFF) # тут упаковка одного байта + страховка на случай, если случайно будет выход за значение 255
            + salt
            + nonce
            + struct.pack(">Q", length) # Упаковка в 8-байтовый беззнаковый тип. Задел под кроссплатформенность
            + mac
        )
        assert len(header) == FrameLayout.HEADER_LEN, "Header size mismatch (ADR 006)" # TODO: Вырезать в проде.
        return header + ciphertext

    @staticmethod
    def _parse_frame(frame: bytes) -> _ParsedFrame:
        """Разбор 57-байтного заголовка + ciphertext. Валидирует MAGIC и размеры."""
        if len(frame) < FrameLayout.HEADER_LEN:
            raise InvalidFrameError(
                f"Frame too short: {len(frame)} < {FrameLayout.HEADER_LEN}"
            )
        if frame[:FrameLayout.MAGIC_LEN] != FrameLayout.MAGIC: # флаг меджика. Побайтовое чтение первых 4 - юзер пытается декодировать файл без стеганографии, если триггерится
            raise InvalidFrameError("Invalid MAGIC - wrong password or corrupted data")

        offset = FrameLayout.MAGIC_LEN
        flags = frame[offset] # чтение байта на позиции (4)
        offset += FrameLayout.FLAGS_LEN # append этого байта в отступ (5)
        salt = frame[offset:offset + FrameLayout.SALT_LEN] # далее - 16 байт соли [5:21]
        offset += FrameLayout.SALT_LEN # append в отступ (21)
        nonce = frame[offset:offset + FrameLayout.NONCE_LEN] # nonce - 12 байт [21:33]
        offset += FrameLayout.NONCE_LEN # прибавляется значение в отступ (33)
        length = struct.unpack(">Q", frame[offset:offset + FrameLayout.LENGTH_LEN])[0] # распаковка 8 байт длины, конверт из кортежа
        offset += FrameLayout.LENGTH_LEN # append длины к оффсету (41)
        mac = frame[offset:offset + FrameLayout.MAC_LEN] # последние 16 байт заголовка
        offset += FrameLayout.MAC_LEN # append последних 16 байт
        ciphertext = frame[offset:offset + length]

        if len(ciphertext) != length:
            raise InvalidFrameError(
                f"Ciphertext truncated: expected {length}, got {len(ciphertext)}" # проверка на "мусор"
            )
        return _ParsedFrame(flags, salt, nonce, length, mac, ciphertext)

    @staticmethod
    def decrypt(frame: bytes, password: str) -> bytes:
        """Расшифровывает фрейм, валидирует MAC, опционально распаковывает zlib.

        Raises:
            InvalidFrameError: если битый заголовок, неверный MAGIC, повреждение данных или неверный пароль.
        """
        parsed = CryptoEngine._parse_frame(frame)
        key = KeyManager.derive_key(password, parsed.salt)

        try:
            plaintext = AESGCM(key).decrypt(
                parsed.nonce,
                parsed.ciphertext + parsed.mac,
                associated_data=None,
            )
        except Exception as e:
            # cryptography.InvalidTag и всё, что летит из hazmat.
            raise InvalidFrameError("Decryption failed: wrong password or tampered data") from e

        if parsed.flags & Flags.COMPRESSED:
            plaintext = zlib.decompress(plaintext)
        return plaintext

    @staticmethod
    def header_size() -> int:
        """Размер фрейма без payload - нужен CapacityAnalyzer."""
        return FrameLayout.HEADER_LEN