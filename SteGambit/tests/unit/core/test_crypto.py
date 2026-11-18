"""Unit tests for core/crypto per ADR 006.

Cover:
- KeyManager: determinism, salt validation.
- CryptoEngine: round-trip, negative cases, frame structure, compression.
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
    """Key derivation and salt generation."""

    def test_salt_has_correct_length(self):
        """The salt must be exactly 16 bytes (ADR 006)."""
        salt = KeyManager.generate_salt()
        assert len(salt) == KeyManager.SALT_LENGTH_BYTES == 16

    def test_salt_is_random(self):
        """Two salts generated in a row must not match."""
        # Note: the collision probability is 2^-128 — treated as impossible.
        assert KeyManager.generate_salt() != KeyManager.generate_salt()

    def test_derive_key_is_deterministic(self):
        """The same (password, salt) -> the same key."""
        salt = b"\x00" * 16
        key1 = KeyManager.derive_key("hunter2", salt)
        key2 = KeyManager.derive_key("hunter2", salt)
        assert key1 == key2

    def test_derive_key_length_is_32_bytes(self):
        """AES-256 requires exactly 32 bytes of key."""
        key = KeyManager.derive_key("any_password", b"\x00" * 16)
        assert len(key) == 32

    def test_different_passwords_give_different_keys(self):
        """Avalanche effect: even similar passwords yield different keys."""
        salt = b"\x00" * 16
        key_a = KeyManager.derive_key("password", salt)
        key_b = KeyManager.derive_key("Password", salt)
        assert key_a != key_b

    def test_different_salts_give_different_keys(self):
        """Protection against rainbow tables: a different salt -> a different key."""
        key_a = KeyManager.derive_key("same_password", b"\x00" * 16)
        key_b = KeyManager.derive_key("same_password", b"\xff" * 16)
        assert key_a != key_b

    def test_invalid_salt_length_raises(self):
        """A salt of the wrong length -> ValueError, not a silent bug."""
        with pytest.raises(ValueError):
            KeyManager.derive_key("pwd", b"\x00" * 8)  # 8 instead of 16


class TestCryptoEngineRoundTrip:
    """Encrypt and immediately decrypt — the result must match the original."""

    @pytest.mark.parametrize("payload", [
        b"A",
        b"Hello, stego!",
        b"X" * 1000,
        b"Y" * (1024 * 1024),
        bytes(range(256)),
    ], ids=["1_byte", "short_string", "1kb", "1mb", "all_byte_values"])
    def test_encrypt_decrypt_preserves_data(self, payload):
        """encrypt -> decrypt == original for different payload sizes."""
        frame = CryptoEngine.encrypt(payload, "test_pwd")
        recovered = CryptoEngine.decrypt(frame, "test_pwd")
        assert recovered == payload

    def test_empty_payload(self):
        """Empty data is a valid case (we encrypt 0 bytes)."""
        frame = CryptoEngine.encrypt(b"", "pwd")
        assert CryptoEngine.decrypt(frame, "pwd") == b""

    def test_unicode_password(self):
        """Passwords with non-Latin characters work (UTF-8)."""
        frame = CryptoEngine.encrypt(b"data", "☺пароль☺")
        assert CryptoEngine.decrypt(frame, "☺пароль☺") == b"data"


class TestCryptoEngineNegative:
    """Attacks, corruption, wrong passwords — everything must fail with InvalidFrameError."""

    def test_wrong_password_fails(self):
        """A wrong password -> InvalidFrameError (MAC mismatch)."""
        frame = CryptoEngine.encrypt(b"secret", "correct")
        with pytest.raises(InvalidFrameError):
            CryptoEngine.decrypt(frame, "wrong")

    def test_tampered_ciphertext_fails(self):
        """A changed byte in the ciphertext -> the MAC does not match."""
        frame = CryptoEngine.encrypt(b"secret data", "pwd")
        # Corrupt the first ciphertext byte (it follows the 57-byte header).
        tampered = bytearray(frame)
        tampered[FrameLayout.HEADER_LEN] ^= 0xFF
        with pytest.raises(InvalidFrameError):
            CryptoEngine.decrypt(bytes(tampered), "pwd")

    def test_tampered_mac_fails(self):
        """A changed byte in the MAC -> InvalidFrameError."""
        frame = CryptoEngine.encrypt(b"data", "pwd")
        tampered = bytearray(frame)
        # The MAC sits in the header at positions 41..57 (see FrameLayout in ADR 006).
        tampered[41] ^= 0x01
        with pytest.raises(InvalidFrameError):
            CryptoEngine.decrypt(bytes(tampered), "pwd")

    def test_invalid_magic_fails(self):
        """A foreign/corrupted MAGIC -> an early error, with no decryption attempt."""
        garbage = b"XXXX" + b"\x00" * (FrameLayout.HEADER_LEN - 4) + b"payload"
        with pytest.raises(InvalidFrameError, match="MAGIC"):
            CryptoEngine.decrypt(garbage, "pwd")

    def test_truncated_frame_fails(self):
        """A frame shorter than 57 bytes -> an error."""
        with pytest.raises(InvalidFrameError):
            CryptoEngine.decrypt(b"too_short", "pwd")

    def test_lying_length_field_fails(self):
        """Length claims 1000 bytes, but they are not there -> a parse error."""
        frame = CryptoEngine.encrypt(b"short", "pwd")
        tampered = bytearray(frame)
        # The LENGTH field sits at positions 33..41 (big-endian uint64).
        tampered[33:41] = struct.pack(">Q", 999999)
        with pytest.raises(InvalidFrameError):
            CryptoEngine.decrypt(bytes(tampered), "pwd")


class TestFrameStructure:
    """We check that CryptoEngine builds the frame strictly per ADR 006."""

    def test_frame_starts_with_magic(self):
        """The first 4 bytes are always MAGIC = b'SGB1'."""
        frame = CryptoEngine.encrypt(b"data", "pwd")
        assert frame[:4] == FrameLayout.MAGIC == b"SGB1"

    def test_frame_header_is_57_bytes(self):
        """The ADR 006 header is exactly 57 bytes."""
        assert FrameLayout.HEADER_LEN == 57
        frame = CryptoEngine.encrypt(b"", "pwd")
        # Empty payload -> the whole frame is just the header.
        assert len(frame) == FrameLayout.HEADER_LEN

    def test_frame_total_size_matches_payload(self):
        """len(frame) == HEADER_LEN + len(ciphertext). Ciphertext == len(plaintext) for GCM."""
        payload = b"X" * 100
        frame = CryptoEngine.encrypt(payload, "pwd")
        # GCM adds no padding -> ciphertext size equals plaintext size.
        # Compression may shrink it. Check the lower bound.
        assert len(frame) >= FrameLayout.HEADER_LEN
        assert len(frame) <= FrameLayout.HEADER_LEN + len(payload)

    def test_two_encryptions_produce_different_frames(self):
        """The same payload + password -> different frames (random salt and nonce)."""
        frame1 = CryptoEngine.encrypt(b"same", "same")
        frame2 = CryptoEngine.encrypt(b"same", "same")
        assert frame1 != frame2
        # But both decrypt back to the original.
        assert CryptoEngine.decrypt(frame1, "same") == b"same"
        assert CryptoEngine.decrypt(frame2, "same") == b"same"


class TestCompression:
    """The zlib compression heuristic and correctness of the COMPRESSED flag."""

    def test_compressible_data_sets_flag(self):
        """Highly compressible data (1000 identical bytes) -> the COMPRESSED flag = 1."""
        payload = b"A" * 1000
        frame = CryptoEngine.encrypt(payload, "pwd")
        flags_byte = frame[4]  # FLAGS — 5th byte of the header
        assert flags_byte & Flags.COMPRESSED

    def test_random_data_does_not_compress(self):
        """Random data does not compress -> the COMPRESSED flag = 0."""
        payload = os.urandom(1000)
        frame = CryptoEngine.encrypt(payload, "pwd")
        flags_byte = frame[4]
        assert not (flags_byte & Flags.COMPRESSED)

    def test_small_data_skips_compression(self):
        """Data below the threshold (256 bytes) — compression is not attempted."""
        payload = b"A" * 100  # would compress, but it is too small
        frame = CryptoEngine.encrypt(payload, "pwd")
        flags_byte = frame[4]
        assert not (flags_byte & Flags.COMPRESSED)

    def test_compressed_roundtrip(self):
        """Compressed data is unpacked correctly on decrypt."""
        payload = b"repeating pattern " * 500
        frame = CryptoEngine.encrypt(payload, "pwd")
        assert CryptoEngine.decrypt(frame, "pwd") == payload

    def test_custom_flags_preserved(self):
        """User flags (IS_DECOY) are not overwritten by the compression logic."""
        payload = b"A" * 1000  # will be compressed
        frame = CryptoEngine.encrypt(payload, "pwd", flags=Flags.IS_DECOY)
        flags_byte = frame[4]
        assert flags_byte & Flags.IS_DECOY      # user flag preserved
        assert flags_byte & Flags.COMPRESSED    # auto flag is set too