"""File identification by magic bytes per ADR 007."""
from pathlib import Path

_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "PNG"),
    (b"RIFF", "WAV"),   # extra WAVE check below
    (b"\xff\xd8\xff", "JPEG"),
)

_FORMAT_TO_EXT = {
    "PNG":  ".png",
    "JPEG": ".jpg",
    "WAV":  ".wav",
}

def get_default_extension(fmt: str) -> str:
    """Returns the default extension for a known format.

    Returns:
        '.png' / '.jpg' / '.wav' for known formats, .bin for everything else (text or an unsupported binary)
    """
    return _FORMAT_TO_EXT.get(fmt, ".bin")

class FormatIdentifier:
    """Determines the real file format from magic bytes, ignoring the extension."""

    _READ_BYTES = 12 # agreed nonce length

    def _validate_riff_subtype(self, header: bytes) -> bool:
        """RIFF is a container wrapper. Check that WAVE is inside, not some other relative such as AVI/WebP."""
        return header[8:12] == b"WAVE"
    
    def _identify_from_header(self, header: bytes) -> str:
        """Core format-detection logic for an already-read buffer.

        Used by both identify and identify_bytes (works on ready bytes in memory).
        """
        for magic, fmt in _SIGNATURES:
            if header.startswith(magic):
                # RIFF needs an extra subtype check (WAVE vs AVI/WebP).
                if fmt == "WAV" and not self._validate_riff_subtype(header):
                    # This is RIFF, but NOT WAVE -> not supported yet :((((.
                    raise ValueError(
                        "RIFF контейнер не является WAVE (возможно AVI/WebP)."
                    )
                return fmt
        raise ValueError("Unsupported or unknown format.")

    def identify(self, file_path: Path) -> str:
        """Reads the file header and returns 'PNG' | 'WAV' | 'JPEG'.

        Raises:
            ValueError: if the format is not recognized or is not supported.
            FileNotFoundError: if the file is missing.
        """
        with open(file_path, "rb") as f:
            header = f.read(self._READ_BYTES)
        try:
            return self._identify_from_header(header)
        except ValueError as e:
            raise ValueError(f"{e} ({file_path.name})") from e
    

    def identify_bytes(self, data: bytes) -> str:
        """Determines the format from the magic bytes of a ready in-memory buffer.

        Used after payload extraction from a stego container,
        when the file has not yet been saved to disk.

        Returns:
            'PNG' | 'WAV' | 'JPEG'.

        Raises:
            ValueError: if the format is not recognized or this is not a WAV RIFF.
        """
        if len(data) < self._READ_BYTES:
            # Small buffer — short data; the magic bytes may not fit.
            # Pad with zeros so _identify_from_header does not fail on a slice.
            data = data + b"\x00" * (self._READ_BYTES - len(data))
        return self._identify_from_header(data[: self._READ_BYTES])
