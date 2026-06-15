from ..base import IStegoProcessor
from ..formats.jpeg import JpegContainer
import numpy as np


# Пока конверт-инструменты вынес в статику, в будущем может быть частью класса.

def _bytes_to_bits(data: bytes) -> np.ndarray:
    """bytes -> ndarray uint8 бит. shape=(len(data)*8,). Нужен для извлечения."""
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def _bits_to_bytes(bits: np.ndarray) -> bytes:
    """Обратная операция к _bytes_to_bits. Нужен для внедрения."""
    return np.packbits(bits.astype(np.uint8)).tobytes()


class LsbProcessor(IStegoProcessor):
    """LSB алгоритм (младший бит) - работает по координатам Spreader.
    Работает с lsb_depth=1 в MVP. Архитектурно lsb_depth пробрасывается,
    но реальная поддержка >1 - в будущем."""

    def embed(self, container: np.ndarray, payload: bytes, coords: np.ndarray, lsb_depth: int = 1) -> np.ndarray:
        if lsb_depth != 1:
            raise NotImplementedError("Пока поддержана только depth = 1")
        bits = _bytes_to_bits(payload)
        if coords.size < bits.size:
            raise ValueError(
                f"Координат меньше, чем бит payload: {coords.size} < {bits.size}"
            )
        result = container.copy()
        flat = result.reshape(-1)  # многомерный массив делает плоским, одномерным

        # Обнуляем LSB в нужных позициях и ставим бит payload.
        used = coords[:bits.size]
        flat[used] = (flat[used] & ~np.array(1, dtype=flat.dtype)) | \
                     bits.astype(flat.dtype)  # обнуляет младший бит по координатам, не затрагивая остальные
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


# Константы JSteg 
# Zigzag-порядок сканирования коэффициентов в блоке 8×8 (стандарт ISO/IEC 10918-1).
# Индекс 0 — DC (не трогаем), индексы 1..63 — AC по возрастанию частоты.
# Берутся среднечастотные (первые 27 AC): низкие "пережёвывают" квантование,
# высокие почти всегда нули — их модификация сломает Хаффман-сжатие.
_MID_FREQ_ZIGZAG = np.array([
    (0, 1), (1, 0), (2, 0), (1, 1), (0, 2), (0, 3), (1, 2), (2, 1),
    (3, 0), (4, 0), (3, 1), (2, 2), (1, 3), (0, 4), (0, 5), (1, 4),
    (2, 3), (3, 2), (4, 1), (5, 0), (6, 0), (5, 1), (4, 2), (3, 3),
    (2, 4), (1, 5), (0, 6),
], dtype=np.int8)

# Пересчёт пар (row, col) -> плоские индексы внутри блока 64: idx = row*8 + col.
# Нужен для быстрой векторной numpy-индексации.
_MID_FREQ_ZIGZAG_FLAT = (
    _MID_FREQ_ZIGZAG[:, 0].astype(np.int64) * 8
    + _MID_FREQ_ZIGZAG[:, 1].astype(np.int64)
)


class DctProcessor(IStegoProcessor[JpegContainer]):
    """JSteg-подобное встраивание в квантованные DCT-коэффициенты JPEG.

    Принципы (по ADR 007 + архитектурному чек-пойнту Архитектора):
        !! Не затрагивается DC (позиция 0 в блоке) — во избежание "шахматных" пятен.
        !! Не затрагиваются позиции со значением 0, 1 или -1: их модификация либо
           превращает коэффициент в 0 (ломает пул при extract), либо меняет знак
           (ломает Хаффман-сжатие, раздувает файл).
        !! Работаем только в среднечастотной зоне (zigzag 1..27 AC).
        !! Модификация — LSB квантованного коэффициента.
    """

    _EXCLUDED_VALUES = frozenset({-2, -1, 0, 1})

    def get_embeddable_positions(self, container: JpegContainer) -> np.ndarray:
        """Строит пул flat-индексов валидных для встраивания коэффициентов.

        Использует только Y-канал. Cb/Cr оставляем нетронутыми — это повышает скрытность.

        Returns:
            np.ndarray[int64] — flat-индексы в Y.reshape(-1), по которым стоит встраивать.
            Порядок — естественный обход массива, окончательную перестановку делает SmartSpreader по сиду.
        """
        y = container.coef_arrays[0]  # shape=(Hb, Wb, 8, 8), int16
        flat = y.reshape(-1, 64)      # каждый блок — строка из 64 коэф-тов

        # Плоские индексы внутри блока для среднечастотных позиций.
        intra_block_idx = _MID_FREQ_ZIGZAG_FLAT

        # Собираем все коэффициенты в этих позициях по всем блокам.
        candidates = flat[:, intra_block_idx]  # shape=(num_blocks, 27)

        # Фильтр JSteg: исключаем значения {-1, 0, 1}.
        mask = ~np.isin(candidates, list(self._EXCLUDED_VALUES))

        # Переводим (block_idx, intra_idx) -> глобальный flat-индекс в y.ravel().
        block_indices, intra_positions = np.where(mask)
        global_flat_indices = (
            block_indices * 64 + intra_block_idx[intra_positions]
        )
        return global_flat_indices.astype(np.int64)

    def embed(self, container: JpegContainer, payload: bytes, coords: np.ndarray, *, lsb_depth: int = 1) -> JpegContainer:
        """Встраивает payload в LSB выбранных DCT-коэффициентов Y-канала.

        Args:
            container: JpegContainer, загруженный JpegFormat.load().
            payload:   Шифротекст (уже через CryptoEngine.encrypt).
            coords:    Flat-индексы в Y.ravel(), выбранные SmartSpreader
                       из пула get_embeddable_positions.

        Returns:
            Тот же JpegContainer (коэффициенты модифицированы in-place
            для экономии памяти на больших JPEG).

        Raises:
            ValueError: Если координат меньше, чем бит в payload.
        """
        if lsb_depth != 1:
            raise NotImplementedError("DCT: поддержан только lsb_depth=1")
        bits = np.unpackbits(np.frombuffer(payload, dtype=np.uint8))
        if coords.size < bits.size:
            raise ValueError(
                f"DCT: вес координат ({coords.size}) < веса битов ({bits.size}). "
                "Проверьте пропускную способность - get_embeddable_positions()."
            )

        y = container.coef_arrays[0]
        y_flat = y.reshape(-1)

        used = coords[:bits.size]
        values = y_flat[used]  # dtype=int16
        # Зануляем LSB и вписываем бит payload. Работает и для отрицательных
        # значений, LSB хранится в младшем бите одинаково.
        y_flat[used] = (values & ~np.int16(1)) | bits.astype(np.int16)
        # Y уже модифицирован (y_flat — view на y).
        return container

    def extract(self, container: JpegContainer, coords: np.ndarray, length: int, *, lsb_depth=1) -> bytes:
        """Извлекает байт длины payload из LSB коэффициентов по координатам/coords.

        Важно: coords должны быть получены тем же способом, что при embed —
        get_embeddable_positions() + SmartSpreader с тем же сидом.
        Поскольку мы исключили {-1, 0, 1} из пула ДО модификации, а JSteg
        через LSB не меняет знак и не обнуляет оставшиеся значения, пул
        при extract восстанавливается идентично. Boom!1
        """
        bits_needed = length * 8
        if coords.size < bits_needed:
            raise ValueError(
                f"DCT: вес координат ({coords.size}) < требуемого числа бит ({bits_needed})."
            )
        y_flat = container.coef_arrays[0].reshape(-1)
        bits = (y_flat[coords[:bits_needed]] & 1).astype(np.uint8)
        return np.packbits(bits).tobytes()