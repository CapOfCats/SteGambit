from ..base import FileFormat
from pathlib import Path
from PIL import Image
import numpy as np


class PngFormat(FileFormat):
    """PNG формат"""
    
    @property
    def magic(self) -> bytes:
        return b'\x89PNG'
    
    def load(self, path: Path) -> np.ndarray:
        img = Image.open(path)
        return np.array(img)
    
    def save(self, data: np.ndarray, path: Path) -> None:
        Image.fromarray(data).save(path, 'PNG')