from ..base import IStegoProcessor
import numpy as np


class LsbProcessor(IStegoProcessor):
    """LSB алгоритм(младший бит) - с фичей координат"""
    
def embed(self, container: np.ndarray, payload: bytes, coords: np.ndarray) -> np.ndarray:
    # TODO: векторизованная LSB-подстановка по coords
    raise NotImplementedError("LSB embed будет реализован в #3")

def extract(self, container: np.ndarray, coords: np.ndarray, length: int) -> bytes:
    # TODO: чтение length*8 битов из coords-позиций, упаковка обратно в bytes
    raise NotImplementedError("LSB extract будет реализован в #3")


class DctProcessor(IStegoProcessor):
    """DCT-алгоритм (частотный домен)"""
    
def embed(self, container: np.ndarray, payload: bytes, coords: np.ndarray) -> np.ndarray:
    raise NotImplementedError("DCT — на будущее, после LSB MVP")

def extract(self, container: np.ndarray, coords: np.ndarray, length: int) -> bytes:
    raise NotImplementedError("DCT — на будущее, после LSB MVP")