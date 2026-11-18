"""WAV format for steganography.

The container keeps metadata at load so that save can restore the file with the original parameters.

Without that, a mono file taken from a stereo source turns into a MONSTER, and a slowed-down one at that.
"""
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from stegambit.core.exceptions import CorruptedCarrierError


@dataclass
class WavContainer:
    """Container for WAV data plus metadata.

    Compatible with the ndarray API via __array__.

    Attributes:
        samples: 1D array of int16 PCM samples.
        n_channels: Number of channels (1 = mono, 2 = stereo).
        sampwidth: Bytes per sample (1, 2, 4).
        framerate: Sample rate in hertz (44100, 48000).
    """
    samples: np.ndarray
    n_channels: int
    sampwidth: int
    framerate: int

    def __array__(self, dtype=None) -> np.ndarray:
        """Transparent conversion to an ndarray for np.asarray / the LSB processor."""
        return self.samples if dtype is None else self.samples.astype(dtype)

    @property
    def size(self) -> int:
        """Number of elements in the sample array."""
        return self.samples.size

    @property
    def shape(self) -> tuple:
        return self.samples.shape

    @property
    def dtype(self):
        return self.samples.dtype

    def reshape(self, *args, **kwargs):
        """Proxy to samples.reshape for compatibility with the LSB processor."""
        return self.samples.reshape(*args, **kwargs)
    
    def copy(self) -> "WavContainer":
        """Returns a copy of the container with an independent sample array.

        Needed for LsbProcessor.embed, which copies before modification so the original is left untouched.
        """
        return WavContainer(
            samples=self.samples.copy(),
            n_channels=self.n_channels,
            sampwidth=self.sampwidth,
            framerate=self.framerate,
        )


class WavFormat:
    """WAV loader/saver that preserves metadata."""

    magic = b"RIFF"

    def load(self, path: Path) -> WavContainer:
        """Reads a WAV and returns a WavContainer with metadata.

        Args:
            path: Path to the file.

        Returns:
            WavContainer with a 1D int16 sample array and the file parameters.

        Raises:
            FileNotFoundError: If the file does not exist.
            CorruptedCarrierError: If the file is corrupt or is not a WAV.
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
        """Saves a WAV while preserving the original metadata.

        Accepts either a WavContainer (preferred) or a bare ndarray.

        Args:
            container: WavContainer with samples and metadata, or an ndarray.
            path: Path to write to.
        """
        if isinstance(container, WavContainer):
            samples = container.samples
            n_channels = container.n_channels
            sampwidth = container.sampwidth
            framerate = container.framerate
        else:
            # Fallback for compatibility with legacy code and tests
            samples = np.asarray(container)
            n_channels = 1
            sampwidth = 2
            framerate = 44100

        with open(path, "wb") as f, wave.open(f, "wb") as wf:
            wf.setnchannels(n_channels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(framerate)
            wf.writeframes(samples.astype(np.int16).tobytes())
