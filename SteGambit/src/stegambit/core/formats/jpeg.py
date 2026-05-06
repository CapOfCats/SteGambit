"""JPEG IO через jpeglib — доступ к квантованным DCT-коэффициентам.

JPEG, в отличие от PNG/WAV, не может быть представлен единым ndarray:
при сохранении нужны таблицы квантования и Хаффмана. Поэтому load()
возвращает составной объект JpegContainer, сохраняющий контекст.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jpeglib
import numpy as np


@dataclass
class JpegContainer:
    """JPEG-состояние, достаточное для lossless round-trip через jpeglib.

    Attributes:
        coef_arrays: Квантованные DCT-коэффициенты по каналам (обычно Y, Cb, Cr).
                     Каждый элемент — ndarray shape=(Hb, Wb, 8, 8), dtype=int16.
                     Модифицируются на месте в DctProcessor.
        dimensions:  (H, W) исходного изображения в пикселях — для удобства.
        _raw:        Внутренний jpeglib.DCTJPEG. Хранит таблицы квантования
                     и Хаффмана; используется для записи через write_dct().
    """
    coef_arrays: list[np.ndarray]
    dimensions: tuple[int, int]
    _raw: Any = field(repr=False)


class JpegFormat:
    """Загрузка/сохранение JPEG на уровне DCT-коэффициентов (JSteg-pipeline).

    Важно: save() пишет обратно те же quant/Huffman-таблицы, что были
    при загрузке. Защита от "двойного квантования".
    """

    def load(self, path: Path) -> JpegContainer:
        """Парсит JPEG и возвращает квантованные DCT-коэффициенты.

        Args:
            path: Путь к исходному JPEG-файлу.

        Returns:
            JpegContainer с коэффициентами и скрытым jpeglib-объектом.

        Raises:
            FileNotFoundError: Если файл не существует.
            RuntimeError: Если jpeglib не смог распарсить файл.
        """
        raw = jpeglib.read_dct(str(path))
        # jpeglib возвращает Y, Cb, Cr как отдельные атрибуты.
        coef_arrays = [raw.Y]
        if raw.Cb is not None and raw.Cr is not None:
            coef_arrays.extend([raw.Cb, raw.Cr])
        h, w = raw.height, raw.width
        return JpegContainer(coef_arrays=coef_arrays, dimensions=(h, w), _raw=raw)

    def save(self, container: JpegContainer, path: Path) -> None:
        """Записывает модифицированные коэффициенты обратно в JPEG.

        Использует исходные таблицы квантования и Хаффмана — перекодирования
        пикселей не происходит, payload не теряется.
        """
        # Синхронизируем обратно возможно-модифицированные каналы.
        container._raw.Y = container.coef_arrays[0]
        if len(container.coef_arrays) == 3:
            container._raw.Cb = container.coef_arrays[1]
            container._raw.Cr = container.coef_arrays[2]
        container._raw.write_dct(str(path))