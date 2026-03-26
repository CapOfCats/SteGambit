from ..base import FileFormat
from pathlib import Path
from PIL import Image
import numpy as np


class JpegFormat(FileFormat):
    """JPEG формат"""
    
    @property
    def magic(self) -> bytes:
        return b'\xff\xd8\xff'
    
    def load(self, path: Path) -> np.ndarray:
        img = Image.open(path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        return np.array(img)
    
    def save(self, data: np.ndarray, path: Path) -> None:
        Image.fromarray(data).save(path, 'JPEG', quality=95)