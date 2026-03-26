from ..base import IStegoProcessor
import numpy as np


class LsbProcessor(IStegoProcessor):
    """LSB алгоритм - с фичей координат"""
    
    def embed(self, container: np.ndarray, payload: bytes, coords: np.ndarray) -> np.ndarray:
        # TODO: Проверить, что len(coords) >= len(payload) * 8
        # TODO: Векторизованная замена битов по координатам
        pass
    
    def extract(self, container: np.ndarray) -> bytes:
        # TODO: Читать length * 8 битов из coords позиций
        pass


class DctProcessor(IStegoProcessor):
    """DCT для JPEG"""
    
    def embed(self, container: np.ndarray, payload: bytes, coords: np.ndarray) -> np.ndarray:
        pass
    
    def extract(self, container: np.ndarray, coords: np.ndarray) -> bytes:
        pass