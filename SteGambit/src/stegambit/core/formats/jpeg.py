"""JPEG IO через jpeglib — доступ к квантованным DCT-коэффициентам.

JPEG, в отличие от PNG/WAV, не может быть представлен единым ndarray:
при сохранении нужны таблицы квантования и Хаффмана. Поэтому load()
возвращает составной объект JpegContainer, сохраняющий контекст.
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
    """JPEG-состояние, достаточное для lossless round-trip через jpeglib.

    JPEG не вписывается в ndarray-модель FileFormat, поэтому используется
    собственный контейнер: коэффициенты + размеры + сырой jpeglib-объект
    для финальной записи через сохранённые таблицы квантования и Хаффмана.

    Attributes:
        coef_arrays: Квантованные DCT-коэффициенты по каналам (обычно Y, Cb, Cr).
                     Каждый элемент — ndarray shape=(Hb, Wb, 8, 8), dtype=int16.
                     Модифицируются IN-PLACE в DctProcessor.
        dimensions:  (H, W) исходного изображения в пикселях — справочно.
        _raw:        ВНУТРЕННИЙ jpeglib.DCTJPEG. Хранит таблицы квантования
                     и Хаффмана; используется JpegFormat.save() для записи
                     через write_dct(). НЕ модифицировать снаружи — нарушит
                     инвариант "перекодирование без потерь".
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
            CorruptedCarrierError: Если jpeglib не смог распарсить файл.
        """
        if not path.exists():
            raise FileNotFoundError(f"JPEG-файл не найден: {path}")

        try:
            raw = jpeglib.read_dct(str(path))
        except Exception as e:
            raise CorruptedCarrierError(
                f"Не удалось прочитать JPEG-файл '{path.name}'. "
                f"Возможно, файл повреждён, не является JPEG или содержит неподдерживаемый цветовой профиль."
            ) from e

        coef_arrays = [raw.Y]
        if raw.Cb is not None and raw.Cr is not None:
            coef_arrays.extend([raw.Cb, raw.Cr])
        h, w = raw.height, raw.width
        return JpegContainer(coef_arrays=coef_arrays, dimensions=(h, w), _raw=raw)

    def save(self, container: JpegContainer, path: Path) -> None:
        """Записывает модифицированные коэффициенты обратно в JPEG-файл.

        Использует ИСХОДНЫЕ таблицы квантования и Хаффмана из container._raw —
        перекодирования пикселей не происходит, payload не теряется.

        Args:
            container: JpegContainer после embed/extract.
            path:      Путь сохранения с расширением .jpg/.jpeg.

        Note:
            Метод обращается к container._raw напрямую — это намеренный
            tight coupling JpegFormat и JpegContainer (см. TODO #25:
            возможный рефактор через write_back() метод на самом контейнере).
        """
        # Синхронизируем обратно возможно-модифицированные каналы.
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