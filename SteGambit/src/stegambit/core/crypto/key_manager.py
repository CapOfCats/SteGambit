import os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


# TODO: Пока не знаю, зачем здесь класс, предварительно - всё статика. Может измениться в будущем.
class KeyManager:
    """Деривация симметричных ключей из пароля.

    Используем PBKDF2-HMAC-SHA256, 480000 итераций.
    Выделено отдельным модулем — чтобы при апгрейде KDF менять только здесь, не трогая CryptoEngine.
    """

    PBKDF2_ITERATIONS = 480_000
    KEY_LENGTH_BYTES = 32  # по заветам AES-256
    SALT_LENGTH_BYTES = 16

    @staticmethod
    def generate_salt() -> bytes:
        """Криптостойкая соль для новой сессии шифрования."""
        return os.urandom(KeyManager.SALT_LENGTH_BYTES)

    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        """На основе Password + Salt генерирует 32-байтный AES-ключ.

        Args:
            password: пользовательский пароль (любая длина).
            salt: 16 байт "соли"; должна совпадать при encrypt/decrypt.

        Returns:
            32 байта ключа для AES-256.

        Raises:
            ValueError: если соль неверной длины.
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