from ..base import FileFormat
from pathlib import Path
from PIL import Image
import numpy as np

from stegambit.core.exceptions import CorruptedCarrierError


class PngFormat(FileFormat):
    """Реализация FileFormat для PNG-контейнеров.

    Семантика:
        * Загрузка через Pillow с принудительной конвертацией в RGB —
          одноканальные / палитровые PNG приводятся к 3-канальному виду
          для единообразия с LsbProcessor.
        * Сохранение через Pillow в режиме PNG (lossless).

    Note:
        PNG-LSB чувствителен к любым lossy-преобразованиям. Поэтому save()
        строго через PNG-encoder; конвертация в JPEG / другие форматы запрещена
        на уровне политики анти-конверсии (см. StegoService.hide_data).
    """
    
    @property
    def magic(self) -> bytes:
        """Magic bytes PNG: \\x89PNG (полный сигнатурный префикс — 8 байт,
        но первых 4 достаточно для идентификации)."""
        return b'\x89PNG'
    
    def load(self, path: Path) -> np.ndarray:
        """Декодирует PNG в RGB ndarray shape=(H, W, 3), dtype=uint8.

        Args:
            path: Путь к существующему .png файлу.

        Returns:
            RGB-массив. Альфа-канал и палитра конвертируются в RGB.

        Raises:
            FileNotFoundError:     Файл не существует.
            CorruptedCarrierError: Pillow не смог декодировать (битый PNG,
                                   неверный формат, обрезанный файл).
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
        """Сохраняет RGB ndarray в PNG (lossless).

        Args:
            data: RGB-массив shape=(H, W, 3), dtype=uint8.
            path: Путь сохранения с расширением .png.

        Note:
            Сжатие — стандартное Pillow (deflate). Без оптимизации, чтобы
            не тратить время на тяжёлый optimize=True.
        """
        with open(path, "wb") as f:
            Image.fromarray(data).save(f, "PNG")