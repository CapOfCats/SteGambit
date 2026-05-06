"""Идентификация файла по "магическим" байтам по ADR 007."""
from pathlib import Path

_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "PNG"),
    (b"RIFF", "WAV"),   # доп. проверка WAVE ниже
    (b"\xff\xd8\xff", "JPEG"),
)


class FormatIdentifier:
    """Определяет реальный формат файла по Magic Bytes, игнорируя расширение."""

    _READ_BYTES = 12 # договоренность насчет длины nonce

    def identify(self, file_path: Path) -> str:
        """Читает заголовок файла и возвращает 'PNG' | 'WAV' | 'JPEG'.

        Raises:
            ValueError: если формат не распознан или не поддерживается.
            FileNotFoundError: если файл отсутствует.
        """
        with open(file_path, "rb") as f:
            header = f.read(self._READ_BYTES)

        for magic, fmt in _SIGNATURES:
            if header.startswith(magic):
                # Для RIFF нужна доп. проверка, что это именно WAVE, а не AVI и т.п.
                if fmt == "WAV" and header[8:12] != b"WAVE":
                    continue
                return fmt

        raise ValueError(f"Unsupported or unknown format: {file_path.name}")