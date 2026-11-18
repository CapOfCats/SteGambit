from ..base import FileFormat
from pathlib import Path
from PIL import Image, ImageFile
import numpy as np

from stegambit.core.exceptions import CorruptedCarrierError


# Disable PIL DoS protection for large stego carriers.
#
# Pillow by default rejects images larger than ~178M pixels (protection against decompression-bomb attacks on web servers).
# In a steganography context this gets in the way: the user deliberately chooses a large carrier for the sake of capacity.
Image.MAX_IMAGE_PIXELS = None

# Tolerance for slightly truncated PNGs. Without this, PIL fails on
# the last IDAT chunk given the slightest bit-level corruption of the file.
ImageFile.LOAD_TRUNCATED_IMAGES = True


class PngFormat(FileFormat):
    """FileFormat implementation for PNG carriers.

    Semantics:
        * Load via Pillow with forced conversion to RGB —
          single-channel / paletted PNGs are brought to 3-channel form
          for consistency with LsbProcessor.
        * Save via Pillow in PNG mode (lossless).
        * PIL DoS protection is disabled at module level (see the comment above).

    Note:
        PNG-LSB is sensitive to any lossy transform. Therefore save()
        goes strictly through the PNG encoder; conversion to JPEG / other formats is forbidden
        by the anti-conversion policy (see StegoService.hide_data).
    """

    @property
    def magic(self) -> bytes:
        """PNG magic bytes: \\x89PNG (the full signature prefix is 8 bytes,
        but the first 4 are enough for identification)."""
        return b'\x89PNG'

    def load(self, path: Path) -> np.ndarray:
        """Decodes a PNG into an RGB ndarray of shape=(H, W, 3), dtype=uint8.

        Args:
            path: Path to an existing .png file.

        Returns:
            RGB array. The alpha channel and palette are converted to RGB.

        Raises:
            FileNotFoundError:     The file does not exist.
            CorruptedCarrierError: Pillow failed to decode (corrupt PNG,
                                   wrong format, truncated file).
        """
        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {path}")
        try:
            img = Image.open(path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            return np.array(img)
        except FileNotFoundError:
            raise
        except Exception as e:
            raise CorruptedCarrierError(
                f"Не удалось прочитать PNG-файл: {path.name}. Возможно, файл повреждён или не является PNG."
            ) from e

    def save(self, data: np.ndarray, path: Path) -> None:
        """Saves an RGB ndarray as PNG.

        Args:
            data: RGB array of shape=(H, W, 3), dtype=uint8.
            path: Save path with a .png extension.

        Note:
            Compression is Pillow's default (deflate). Optimization is skipped so
            we do not spend time on the heavy optimize=True.
        """
        with open(path, "wb") as f:
            Image.fromarray(data).save(f, "PNG")
