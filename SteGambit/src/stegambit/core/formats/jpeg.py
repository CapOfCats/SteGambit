"""JPEG IO via jpeglib — access to quantized DCT coefficients.

JPEG, unlike PNG/WAV, cannot be represented as a single ndarray:
saving requires quantization and Huffman tables. Therefore load()
returns a composite JpegContainer that preserves that context.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tempfile
import shutil
import jpeglib
import numpy as np

from stegambit.core.exceptions import CorruptedCarrierError


@dataclass
class JpegContainer:
    """JPEG state sufficient for a lossless round-trip via jpeglib.

    JPEG does not fit the ndarray model of FileFormat, so a
    dedicated container is used: coefficients + dimensions + the raw jpeglib object
    for the final write through the saved quantization and Huffman tables.

    Attributes:
        coef_arrays: Quantized DCT coefficients per channel (usually Y, Cb, Cr).
                     Each element is an ndarray of shape=(Hb, Wb, 8, 8), dtype=int16.
                     Modified IN-PLACE in DctProcessor.
        dimensions:  (H, W) of the source image in pixels — informational.
        _raw:        INTERNAL jpeglib.DCTJPEG. Holds the quantization
                     and Huffman tables; used by JpegFormat.save() to write
                     via write_dct(). Do NOT modify from the outside — that would break
                     the "lossless re-encoding" invariant.
    """
    coef_arrays: list[np.ndarray]
    dimensions: tuple[int, int]
    _raw: Any = field(repr=False)


class JpegFormat:
    """JPEG load/save at the DCT-coefficient level (JSteg pipeline).

    Important: save() writes back the same quant/Huffman tables that were
    present at load. Protection against "double quantization".
    """

    def load(self, path: Path) -> JpegContainer:
        """Parses a JPEG and returns quantized DCT coefficients.

        Args:
            path: Path to the source JPEG file.

        Returns:
            JpegContainer with coefficients and a hidden jpeglib object.

        Raises:
            FileNotFoundError: If the file does not exist.
            CorruptedCarrierError: If jpeglib failed to parse the file.
        """
        if not path.exists():
            raise FileNotFoundError(f"JPEG-файл не найден: {path}")

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            shutil.copyfile(path, tmp_path)
            try:
                raw = jpeglib.read_dct(tmp_path)
            except Exception as e:
                raise CorruptedCarrierError(
                    f"Не удалось прочитать JPEG-файл '{path.name}'. "
                    f"Возможно, файл повреждён, не является JPEG или содержит неподдерживаемый цветовой профиль."
                ) from e
        finally:
            if Path(tmp_path).exists():
                Path(tmp_path).unlink()

        coef_arrays = [raw.Y]
        if raw.Cb is not None and raw.Cr is not None:
            coef_arrays.extend([raw.Cb, raw.Cr])
        h, w = raw.height, raw.width
        return JpegContainer(coef_arrays=coef_arrays, dimensions=(h, w), _raw=raw)

    def save(self, container: JpegContainer, path: Path) -> None:
        """Writes the modified coefficients back to a JPEG file.

        Uses the ORIGINAL quantization and Huffman tables from container._raw —
        pixels are not re-encoded, so the payload is not lost.

        Args:
            container: JpegContainer after embed/extract.
            path:      Save path with a .jpg/.jpeg extension.

        Note:
            The method accesses container._raw directly — this is intentional
            tight coupling of JpegFormat and JpegContainer (see TODO #25:
            a possible refactor via a write_back() method on the container itself).
        """
        # Sync possibly modified channels back.
        container._raw.Y = container.coef_arrays[0]
        if len(container.coef_arrays) == 3:
            container._raw.Cb = container.coef_arrays[1]
            container._raw.Cr = container.coef_arrays[2]

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            container._raw.write_dct(tmp_path)
            shutil.move(tmp_path, str(path))
        except Exception:
            if Path(tmp_path).exists():
                Path(tmp_path).unlink()
            raise
