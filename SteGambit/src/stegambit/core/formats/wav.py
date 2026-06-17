"""WAV-формат для стеганографии.

Контейнер сохраняет метаданные при load, чтобы save мог восстановить файл с исходными параметрами.

Без этого моно-файл из стерео-источника превращается в МОНСТРА, еще и с замедлением.
"""
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from stegambit.core.exceptions import CorruptedCarrierError


@dataclass
class WavContainer:
    """Контейнер для WAV-данных + метадата.

    Совместим с ndarray-API через __array__.

    Атрибуты:
        samples: 1D-массив int16 PCM семплов.
        n_channels: Количество каналов (1 = mono, 2 = stereo).
        sampwidth: Байтов в сэмпле (1, 2, 4).
        framerate: Частота в герцах (44100, 48000).
    """
    samples: np.ndarray
    n_channels: int
    sampwidth: int
    framerate: int

    def __array__(self, dtype=None) -> np.ndarray:
        """Прозрачное преобразование в ndarray для np.asarray/LSB-процессора."""
        return self.samples if dtype is None else self.samples.astype(dtype)

    @property
    def size(self) -> int:
        """Количество элементов в массиве семплов."""
        return self.samples.size

    @property
    def shape(self) -> tuple:
        return self.samples.shape

    @property
    def dtype(self):
        return self.samples.dtype

    def reshape(self, *args, **kwargs):
        """Прокси к samples.reshape для совместимости с LSB-процессором."""
        return self.samples.reshape(*args, **kwargs)
    
    def copy(self) -> "WavContainer":
        """Возвращает копию контейнера с независимым массивом семплов.

        Нужен для LsbProcessor.embed который копирует перед модификацией, чтобы не трогать исходник.
        """
        return WavContainer(
            samples=self.samples.copy(),
            n_channels=self.n_channels,
            sampwidth=self.sampwidth,
            framerate=self.framerate,
        )


class WavFormat:
    """Загружалка/сохранялка WAV с сохранением метадаты."""

    magic = b"RIFF"

    def load(self, path: Path) -> WavContainer:
        """Читает WAV и возвращает WavContainer с метаданными.

        Args:
            path: Путь к файлу.

        Returns:
            WavContainer с 1D-массивом int16 семплов и параметрами файла.

        Raises:
            FileNotFoundError: Если файл не существует.
            CorruptedCarrierError: Если файл повреждён или не является WAV.
        """
        if not path.exists():
            raise FileNotFoundError(f"WAV-файл не найден: {path}")

        try:
            with wave.open(str(path), "rb") as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)
        except wave.Error as e:
            raise CorruptedCarrierError(
                f"Не удалось прочитать WAV-файл '{path.name}'. "
                f"Возможно, файл повреждён или не является корректным WAV."
            ) from e

        dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}
        dtype = dtype_map.get(sampwidth, np.int16)
        samples = np.frombuffer(raw, dtype=dtype).copy()

        if dtype is not np.int16:
            samples = samples.astype(np.int16)

        return WavContainer(
            samples=samples,
            n_channels=n_channels,
            sampwidth=sampwidth,
            framerate=framerate,
        )

    def save(self, container: WavContainer | np.ndarray, path: Path) -> None:
        """Сохраняет WAV с сохранением исходных метаданных.

        Принимает либо WavContainer (предпочтительно), либо голый ndarray.

        Args:
            container: WavContainer с семплами и метаданными или ndarray.
            path: Путь для записи.
        """
        if isinstance(container, WavContainer):
            samples = container.samples
            n_channels = container.n_channels
            sampwidth = container.sampwidth
            framerate = container.framerate
        else:
            # Fallback для совместимости со легаси кодом и тестами
            samples = np.asarray(container)
            n_channels = 1
            sampwidth = 2
            framerate = 44100

        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(n_channels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(framerate)
            wf.writeframes(samples.astype(np.int16).tobytes())