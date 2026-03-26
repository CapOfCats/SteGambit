from abc import ABC, abstractmethod
from pathlib import Path
import numpy as np


class StegoAlgorythm(ABC):
    """Базовый класс для алгоритмов"""
    
    @abstractmethod
    def embed(self, container: np.ndarray, payload: bytes) -> np.ndarray:
        """Внедрить данные в контейнер"""
        pass

    @abstractmethod
    def extract(self, container: np.ndarray) -> bytes:
        """Извлечь данные"""
        pass


class FileFormat(ABC):
    """Базовый класс для форматов файлов"""
    
    @property
    @abstractmethod
    def magic(self) -> bytes:
        """Magic bytes, маркер для определения типа файла"""
        pass
    
    @abstractmethod
    def load(self, path: Path) -> np.ndarray:
        """Загрузить файл в numpy array"""
        pass
    
    @abstractmethod
    def save(self, data: np.ndarray, path: Path) -> None:
        """Сохранить array в файл"""
        pass