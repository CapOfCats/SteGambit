from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, Optional, Set, Tuple, TypeVar
import numpy as np

T = TypeVar("T")

class IStegoProcessor(ABC, Generic[T]):
    """Контракт стратегии стеганографического внедрения/извлечения.

    Параметризован типом контейнера T:
        - LsbProcessor:  T = np.ndarray (пиксели PNG / семплы WAV).
        - DctProcessor:  T = JpegContainer (квантованные DCT-коэффициенты + метаданные).

    Контракт coords неизменен для всех реализаций: одномерный массив int64
    с плоскими индексами позиций, куда встраивать / откуда извлекать биты.
    """

    @abstractmethod
    def embed(self, container: T, payload: bytes, coords: np.ndarray, *, lsb_depth: int = 1) -> T:
        """Внедрить payload в контейнер по координатам.

        Args:
            container: Контейнер-носитель.
                       Для LSB: ndarray (H, W, 3) uint8 для изображений или
                                (N,) int16 для WAV.
                       Для DCT: JpegContainer с квантованными коэффициентами.
            payload:   Готовый бинарный блоб (шифротекст из CryptoEngine).
            coords:    int64-массив плоских индексов.
                       Для LSB — индексы в container.flat.
                       Для DCT — индексы в JpegContainer.coef_arrays[0].ravel(),
                                 отфильтрованные через get_embeddable_positions().
            lsb_depth: Сколько младших бит использовать на элемент (1..4).
                       В MVP поддерживается только lsb_depth=1.

        Returns:
            Модифицированный контейнер того же типа. Для DCT может быть тот же
            объект (локальная модификация экономит память на больших JPEG).
        """
        ...

    @abstractmethod
    def extract(self, container: T, coords: np.ndarray, length: int, *, lsb_depth: int = 1) -> bytes:
        """Извлечь length байт payload из контейнера по координатам.

        Args:
            length: Длина payload в байтах (нужна, чтобы остановиться после нужного числа бит).
        """
        ...


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