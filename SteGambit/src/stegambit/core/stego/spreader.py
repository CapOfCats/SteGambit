from typing import Optional, Set
import hashlib
import numpy as np

from ..base import ISpreader


class SmartSpreader(ISpreader):
    """Content-aware Spreader с Edge Detection.

    Как работает:
        1. Контейнер -> grayscale (если RGB).
        2. Градиент через разность соседей (|dx| + |dy|).
        3. Пул = координаты, где градиент >= искажения.
        4. Детерминированная перестановка пула через seed от пароля.
    """

    GRADIENT_THRESHOLD = 8  # Хардкод эмпирического порога "шумности" пикселя

    def _to_grayscale_mask(self, container: np.ndarray) -> np.ndarray:
        """Возвращает 2D-массив (H,W) яркости или исходный 1D для аудио.
        Нужно для выявления шума, предварительно конвертировав изображение в черно-белое.
        Для этого используются коэффициенты стандарта ITU-R BT.601"""
        if container.ndim == 3:
            return (0.299 * container[..., 0] + # чувствительность к красному спектру
                    0.587 * container[..., 1] + # к зеленому
                    0.114 * container[..., 2]).astype(np.int16) # к синему
        return container.astype(np.int16)

    def _build_edge_pool(self, container: np.ndarray) -> np.ndarray:
        """Формирует массив flat-индексов в container.flat, прошедших порог."""
        gray = self._to_grayscale_mask(container)

        if gray.ndim == 2:
            dx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1])) # разность соседних пикселей по горизонтали
            dy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :])) # аналогично - по Y
            edge_map = dx + dy
            mask_2d = edge_map >= self.GRADIENT_THRESHOLD # итоговая маска для мест, где грандиент больше порога

            if container.ndim == 3:
                # Пиксель "шумный" - тогда все его каналы годятся.
                c = container.shape[2]
                mask_flat = np.repeat(mask_2d.ravel(), c)
            else:
                mask_flat = mask_2d.ravel()
        else:
            # 1D для WAV - тут просто разность с соседом.
            diff = np.abs(np.diff(gray, prepend=gray[:1]))
            mask_flat = diff >= self.GRADIENT_THRESHOLD

        return np.flatnonzero(mask_flat).astype(np.int64)

    def _seed_rng(self, password_seed: str) -> np.random.Generator:
        """Детерминированный RNG из пароля через SHA-256.
        Это реализация сида по паролю. Чуть отличился символ - сид уже кардинально другой,
        но абсолютно идентичен, если пароль всегда один."""
        digest = hashlib.sha256(password_seed.encode("utf-8")).digest()
        seed_int = int.from_bytes(digest[:8], "big", signed=False) # тут дергаем байты для сида
        return np.random.default_rng(seed_int)

    def get_max_capacity_bits(self, container: np.ndarray) -> int:
        return int(self._build_edge_pool(container).size)

    def generate_coords(self, container: np.ndarray, payload_bits_len: int,
                        password_seed: str,
                        exclude_coords: Optional[Set[int]] = None) -> np.ndarray:
        """Генерация координат для сокрытия, поддержана фича с фейковым payload."""
        pool = self._build_edge_pool(container)

        if exclude_coords:
            excl = np.fromiter(exclude_coords, dtype=np.int64)
            pool = pool[~np.isin(pool, excl)]

        if pool.size < payload_bits_len:
            raise ValueError(
                f"Недостаточно 'шумных' координат: нужно {payload_bits_len}, "
                f"доступно {pool.size}. Снизить порог или взять другой контейнер."
            )

        rng = self._seed_rng(password_seed) # перемешивает пул в соответствии с seed-фразой
        rng.shuffle(pool) # shuffle, без дополнительных аллокаций
        return pool[:payload_bits_len]