import os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


# TODO: Not sure yet why this is a class; for now everything is static. It may change in the future.
class KeyManager:
    """Symmetric key derivation from a password.

    Uses PBKDF2-HMAC-SHA256, 480000 iterations.
    Split into its own module so that a KDF upgrade changes only this file and leaves CryptoEngine untouched.
    """

    PBKDF2_ITERATIONS = 480_000
    KEY_LENGTH_BYTES = 32  # as prescribed by AES-256
    SALT_LENGTH_BYTES = 16

    @staticmethod
    def generate_salt() -> bytes:
        """Cryptographically strong salt for a new encryption session."""
        return os.urandom(KeyManager.SALT_LENGTH_BYTES)

    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        """Builds a 32-byte AES key from password + salt.

        Args:
            password: user password (any length).
            salt: 16 bytes of salt; must match between encrypt and decrypt.

        Returns:
            32-byte key for AES-256.

        Raises:
            ValueError: if the salt has the wrong length.
        """
        if len(salt) != KeyManager.SALT_LENGTH_BYTES:
            raise ValueError(
                f"Salt must be {KeyManager.SALT_LENGTH_BYTES} bytes, got {len(salt)}"
            )
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KeyManager.KEY_LENGTH_BYTES,
            salt=salt,
            iterations=KeyManager.PBKDF2_ITERATIONS,
        )
        return kdf.derive(password.encode("utf-8"))
