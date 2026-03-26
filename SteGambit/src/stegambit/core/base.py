from abc import ABC, abstractmethod
from pathlib import Path
import numpy as np


class IStegoProcessor(ABC):
    """Интерфейс для алгоритмов"""
    
    @abstractmethod
    def embed(self, container: np.ndarray, payload: bytes, coords: np.ndarray) -> np.ndarray:
        """
        Внедрить данные в контейнер по (координатам)
        Args: 
            coords np.ndarray формы (N, 2) с координатами пикселей/сэмплов
        """
        pass

    @abstractmethod
    def extract(self, container: np.ndarray, coords: np.ndarray, length: int) -> bytes:
        """
        Извлечь данные (по координатам)
        Args:
            length длина payload в байтах (чтобы знать, когда остановиться)
        """
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