import os
import struct
import zlib
from dataclasses import dataclass
from enum import IntFlag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from stegambit.core.exceptions import InvalidFrameError, InvalidPasswordError
from .key_manager import KeyManager


class FrameLayout:
    """Layout of the 57-byte frame."""
    MAGIC = b"SGB1"
    MAGIC_LEN = 4
    FLAGS_LEN = 1
    SALT_LEN = 16
    NONCE_LEN = 12
    LENGTH_LEN = 8
    MAC_LEN = 16
    HEADER_LEN = MAGIC_LEN + FLAGS_LEN + SALT_LEN + NONCE_LEN + LENGTH_LEN + MAC_LEN

class Flags(IntFlag):
    """Bit masks of the FLAGS field."""
    COMPRESSED = 0x01
    IS_DECOY = 0x02

class HeuristicCompression:
    """Heuristic for enabling compression."""
    COMPRESSION_MIN_SIZE = 256        # below this, compressing is pointless
    COMPRESSION_RATIO_THRESHOLD = 0.9  # compress only if the gain is > 10%
    COMPRESSION_LEVEL = 9


@dataclass(frozen=True)
class _ParsedFrame:
    """Parsed 57-byte header plus ciphertext."""
    flags: int
    salt: bytes
    nonce: bytes
    length: int
    mac: bytes
    ciphertext: bytes


class CryptoEngine:
    """AES-256-GCM encryption packed into a 57-byte frame per ADR 006.

    All methods are static and stateless — safe to call from any thread.
    """

    @staticmethod
    def _should_compress(data: bytes) -> tuple[bytes, bool]:
        """Compresses data with zlib when that yields a gain greater than 10%.

        Returns:
            (compressed data, whether_zlib_was_applied).
        """
        if len(data) < HeuristicCompression.COMPRESSION_MIN_SIZE:
            return data, False
        compressed = zlib.compress(data, level=HeuristicCompression.COMPRESSION_LEVEL)
        if len(compressed) < len(data) * HeuristicCompression.COMPRESSION_RATIO_THRESHOLD:
            return compressed, True
        return data, False

    @staticmethod
    def encrypt(data: bytes, password: str, /, *, flags: int = 0) -> bytes:
        """Encrypts data and packs it into a crypto-frame per ADR 006.

        Pipeline:
            1. Optional zlib compression (per the _should_compress heuristic).
            2. Generation of a random SALT (16 bytes) and NONCE (12 bytes).
            3. PBKDF2(password, salt) -> AES key.
            4. AES-GCM(nonce, key) -> ciphertext + 16-byte MAC.
            5. Frame assembly: MAGIC | FLAGS | SALT | NONCE | LENGTH | MAC | DATA.

        Args:
            data:     Original payload bytes.
            password: User password (any string, including the empty one).
            flags:    Extra FLAGS bits (for example, IS_DECOY).
                      The COMPRESSED bit is set automatically — it cannot be
                      controlled from the outside.

        Returns:
            Binary blob: HEADER_LEN (57 bytes) + ciphertext.
            The ciphertext size equals len(data) after possible zlib compression.

        Note:
            Each call generates a new SALT and NONCE — two encrypt calls
            with the same (data, password) produce DIFFERENT outputs. This is by design.
        """
        processed, compressed = CryptoEngine._should_compress(data)
        if compressed:
            flags |= Flags.COMPRESSED

        salt = KeyManager.generate_salt()
        nonce = os.urandom(FrameLayout.NONCE_LEN)
        key = KeyManager.derive_key(password, salt)

        aesgcm = AESGCM(key)
        ct_with_tag = aesgcm.encrypt(nonce, processed, associated_data=None)
        ciphertext, mac = ct_with_tag[:-FrameLayout.MAC_LEN], ct_with_tag[-FrameLayout.MAC_LEN:] # always the last 16 bytes

        length = len(processed)
        header = (
            FrameLayout.MAGIC
            + struct.pack("B", flags & 0xFF) # pack one byte, plus a guard in case the value accidentally exceeds 255
            + salt
            + nonce
            + struct.pack(">Q", length) # Pack into an 8-byte unsigned type. A provision for cross-platform use
            + mac
        )
        return header + ciphertext

    @staticmethod
    def _parse_frame(frame: bytes) -> _ParsedFrame:
        """Parses the 57-byte header plus ciphertext. Validates MAGIC and the sizes."""
        if len(frame) < FrameLayout.HEADER_LEN:
            raise InvalidFrameError(
                f"Frame too short: {len(frame)} < {FrameLayout.HEADER_LEN}"
            )
        if frame[:FrameLayout.MAGIC_LEN] != FrameLayout.MAGIC: # magic flag. Byte-wise read of the first 4 — if this triggers, the user is trying to decode a file with no steganography
            raise InvalidFrameError("Invalid MAGIC - wrong password or corrupted data")

        offset = FrameLayout.MAGIC_LEN
        flags = frame[offset] # read the byte at position (4)
        offset += FrameLayout.FLAGS_LEN # append this byte to the offset (5)
        salt = frame[offset:offset + FrameLayout.SALT_LEN] # next, 16 salt bytes [5:21]
        offset += FrameLayout.SALT_LEN # append to the offset (21)
        nonce = frame[offset:offset + FrameLayout.NONCE_LEN] # nonce — 12 bytes [21:33]
        offset += FrameLayout.NONCE_LEN # the value is added to the offset (33)
        length = struct.unpack(">Q", frame[offset:offset + FrameLayout.LENGTH_LEN])[0] # unpack 8 length bytes, converting out of the tuple
        offset += FrameLayout.LENGTH_LEN # append the length to the offset (41)
        mac = frame[offset:offset + FrameLayout.MAC_LEN] # last 16 bytes of the header
        offset += FrameLayout.MAC_LEN # append the last 16 bytes
        ciphertext = frame[offset:offset + length]

        if len(ciphertext) != length:
            raise InvalidFrameError(
                f"Ciphertext truncated: expected {length}, got {len(ciphertext)}" # check for garbage
            )
        return _ParsedFrame(flags, salt, nonce, length, mac, ciphertext)

    @staticmethod
    def decrypt(frame: bytes, password: str) -> bytes:
        """Decrypts a crypto-frame and returns the original payload bytes.

        Pipeline (mirror of encrypt):
            1. Frame parsing (MAGIC validation, FLAGS, SALT, NONCE, LENGTH, MAC).
            2. PBKDF2(password, salt) -> AES key.
            3. AES-GCM.decrypt -> plaintext plus a MAC check.
            4. Optional zlib decompression if the COMPRESSED flag is set.

        Args:
            frame:    Binary blob in exactly the format returned by encrypt().
            password: User password.

        Returns:
            Original payload bytes, identical to those passed to encrypt.

        Raises:
            InvalidFrameError:    Corrupt header or wrong MAGIC
                                  (the file contains no SteGambit data).
            InvalidPasswordError: Wrong password OR the data was altered
                                  after embed (MAC mismatch). These two
                                  cases cannot be distinguished cryptographically.
        """
        parsed = CryptoEngine._parse_frame(frame)
        key = KeyManager.derive_key(password, parsed.salt)

        try:
            plaintext = AESGCM(key).decrypt(
                parsed.nonce,
                parsed.ciphertext + parsed.mac,
                associated_data=None,
            )
        except InvalidTag as e:
            raise InvalidPasswordError(
                "Неверный пароль или данные повреждены. "
                "Проверьте пароль и убедитесь, что файл действительно содержит скрытые данные."
            ) from e

        if parsed.flags & Flags.COMPRESSED:
            plaintext = zlib.decompress(plaintext)
        return plaintext

    @staticmethod
    def header_size() -> int:
        """Returns the crypto-frame size WITHOUT the payload, in bytes.

        Used by CapacityAnalyzer and StegoService to compute the real
        carrier capacity (= total capacity minus overhead bytes).

        Returns:
            Fixed HEADER_LEN size (57 bytes per ADR 006)."""
        return FrameLayout.HEADER_LEN
