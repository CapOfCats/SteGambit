from ..base import IStegoProcessor
import numpy as np


#Пока конверт-инструменты вынес в статику, о в будущем может быть частью класса.

def _bytes_to_bits(data: bytes) -> np.ndarray:
    """bytes -> ndarray uint8 бит. shape=(len(data)*8,). Нужен для извлечения."""
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def _bits_to_bytes(bits: np.ndarray) -> bytes:
    """Обратная операция к _bytes_to_bits. Нужен для внедрения."""
    return np.packbits(bits.astype(np.uint8)).tobytes()


class LsbProcessor(IStegoProcessor):
    """LSB алгоритм(младший бит) - работает по координатам Spreader.
    Работает с lsb_depth=1 в MVP. Архитектурно lsb_depth пробрасывается,
    но реальная поддержка >1"""
    
def embed(self, container: np.ndarray, payload: bytes, coords: np.ndarray, lsb_depth: int = 1) -> np.ndarray:
    if lsb_depth != 1:
        raise NotImplementedError("Пока поддержана только depth = 1")
    bits = _bytes_to_bits(payload)
    if coords.size < bits.size:
        raise ValueError(
            f"Координат меньше, чем бит payload: {coords.size} < {bits.size}"
        )
    result = container.copy()
    flat = result.reshape(-1) # многомерный массив делает плоским, одномерным

    # Обнуляем LSB в нужных позициях и ставим бит payload.
    used = coords[:bits.size]
    flat[used] = (flat[used] & ~np.array(1, dtype=flat.dtype)) | \
                 bits.astype(flat.dtype) # обнуляет младший бит по координатам, не затрагивая остальные
    return result

def extract(self, container: np.ndarray, coords: np.ndarray, length: int, lsb_depth: int = 1) -> bytes:
    if lsb_depth != 1:
        raise NotImplementedError("Пока поддержана только depth = 1")
    bits_needed = length * 8
    if coords.size < bits_needed:
        raise ValueError(
            f"Координат меньше, чем требуется бит: {coords.size} < {bits_needed}"
        )
    flat = container.reshape(-1)
    bits = (flat[coords[:bits_needed]] & 1).astype(np.uint8)
    return _bits_to_bytes(bits)


class DctProcessor(IStegoProcessor):
    """DCT-алгоритм (частотный домен)"""
    
    def embed(self, container: np.ndarray, payload: bytes, coords: np.ndarray) -> np.ndarray:
        raise NotImplementedError("DCT — на будущее, после LSB MVP")

    def extract(self, container: np.ndarray, coords: np.ndarray, length: int) -> bytes:
        raise NotImplementedError("DCT — на будущее, после LSB MVP")