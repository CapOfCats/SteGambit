"""Идентификация файла по "магическим" байтам по ADR 007."""
from pathlib import Path

_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "PNG"),
    (b"RIFF", "WAV"),   # доп. проверка WAVE ниже
    (b"\xff\xd8\xff", "JPEG"),
)

_FORMAT_TO_EXT = {
    "PNG":  ".png",
    "JPEG": ".jpg",
    "WAV":  ".wav",
}

def get_default_extension(fmt: str) -> str:
    """Возвращает расширение по умолчанию для известного формата.

    Returns:
        '.png' / '.jpg' / '.wav' для известных форматов, .bin для всего остального (текст или неподдерживаемый бинарь)
    """
    return _FORMAT_TO_EXT.get(fmt, ".bin")

class FormatIdentifier:
    """Определяет реальный формат файла по Magic Bytes, игнорируя расширение."""

    _READ_BYTES = 12 # договоренность насчет длины nonce

    def _validate_riff_subtype(self, header: bytes) -> bool:
        """RIFF — контейнер-обёртка. Проверяем, что внутри WAVE, а не другой родственник типа AVI/WebP."""
        return header[8:12] == b"WAVE"
    
    def _identify_from_header(self, header: bytes) -> str:
        """Базовая логика определения формата по уже прочитанному буферу.

        Используется и identify, и identify_bytes (работает с готовыми байтами в памяти).
        """
        for magic, fmt in _SIGNATURES:
            if header.startswith(magic):
                # Для RIFF нужна доп. проверка субтипа (WAVE vs AVI/WebP).
                if fmt == "WAV" and not self._validate_riff_subtype(header):
                    # Это RIFF, но НЕ WAVE -> пока не поддержан :((((.
                    raise ValueError(
                        "RIFF контейнер не является WAVE (возможно AVI/WebP)."
                    )
                return fmt
        raise ValueError("Unsupported or unknown format.")

    def identify(self, file_path: Path) -> str:
        """Читает заголовок файла и возвращает 'PNG' | 'WAV' | 'JPEG'.

        Raises:
            ValueError: если формат не распознан или не поддерживается.
            FileNotFoundError: если файл отсутствует.
        """
        with open(file_path, "rb") as f:
            header = f.read(self._READ_BYTES)
        try:
            return self._identify_from_header(header)
        except ValueError as e:
            raise ValueError(f"{e} ({file_path.name})") from e
    

    def identify_bytes(self, data: bytes) -> str:
        """Определяет формат по magic bytes готового буфера в памяти.

        Используется после извлечения payload из стего-контейнера,
        когда файл ещё не сохранён на диск.

        Returns:
            'PNG' | 'WAV' | 'JPEG'.

        Raises:
            ValueError: если формат не распознан или это не WAV-RIFF.
        """
        if len(data) < self._READ_BYTES:
            # Маленький буфер — короткие данные, magic bytes могут не уместиться.
            # Дополняем нулями, чтобы _identify_from_header не вылетел на срез.
            data = data + b"\x00" * (self._READ_BYTES - len(data))
        return self._identify_from_header(data[: self._READ_BYTES])