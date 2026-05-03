from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Set, Tuple
import numpy as np


class IStegoProcessor(ABC):
    """Контракт стратегии стеганографического внедрения/извлечения."""
    
    @abstractmethod
    def embed(self, container: np.ndarray, payload: bytes, coords: np.ndarray, *, lsb_depth=1) -> np.ndarray:
        """
        Внедрить данные в контейнер по (координатам)
         Args:
            container: numpy-массив с данными файла-носителя.
                       Для изображений: shape=(H, W, 3), dtype=uint8 — 
                       то есть трёхмерный массив высота×ширина×каналы (RGB), каждое значение 0..255.
                       Для WAV: shape=(N,), dtype=int16 — одномерный массив аудио-сэмплов.
            payload: готовый бинарный блоб, сокрываемая информация.
            coords: одномерный массив int64 с "плоскими" индексами позиций, куда внедрять биты.
            lsb_depth: сколько младших бит использовать на элемент (1..4).

        Returns:
            Новый numpy-массив той же формы и того же типа данныъ, что container,
            но с модифицированными младшими битами. Оригинал не меняется.
        """
        pass

    @abstractmethod
    def extract(self, container: np.ndarray, coords: np.ndarray, length: int, *, lsb_depth=1) -> bytes:
        """
        Извлечь данные (по координатам)
        Args:
            length длина payload в байтах (чтобы знать, когда остановиться)
        """
        pass


class ISpreader(ABC):
    """Контракт генератора координат внедрения (ADR 005)."""

    @abstractmethod
    def get_max_capacity_bits(self, container: np.ndarray) -> int:
        """Размер пула безопасных координат после edge detection."""
        ...

    @abstractmethod
    def generate_coords(self, container: np.ndarray, payload_bits_len: int, password_seed: str,
                        exclude_coords: Optional[Set[int]] = None) -> np.ndarray:
        """Выдать payload_bits_len flat-индексов из пула.

        exclude_coords — задел на Plausible Deniability (ADR 004, IS_DECOY). """
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