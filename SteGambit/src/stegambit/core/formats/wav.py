from ..base import FileFormat
from pathlib import Path
import wave
import numpy as np


class WavFormat(FileFormat):
    """WAV аудиоформат"""
    
    @property
    def magic(self) -> bytes:
        return b'RIFF'
    
    def load(self, path: Path) -> np.ndarray:
        with wave.open(str(path), 'rb') as w:
            n_frames = w.getnframes()
            data = w.readframes(n_frames)
            return np.frombuffer(data, dtype=np.int16)
    
    def save(self, data: np.ndarray, path: Path) -> None:
        with wave.open(str(path), 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(data.astype(np.int16).tobytes())