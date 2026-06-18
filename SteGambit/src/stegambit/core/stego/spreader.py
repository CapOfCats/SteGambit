from typing import Optional, Set
import numpy as np

from ..base import ISpreader
from ..common.seeding import derive_rng_from_password

class SmartSpreader(ISpreader):
    """Content-aware Spreader с Edge Detection.

    Как работает:
        1. Контейнер -> grayscale (если RGB).
        2. Градиент через разность соседей (|dx| + |dy|).
        3. Пул = координаты, где градиент >= искажения.
        4. Детерминированная перестановка пула через seed от пароля.
    """

    # Эмпирический порог "шумности" для edge-detection.
    #
    # Подобран для 8-bit изображений (uint8, шкала 0-255): порог 8 ≈ 3%
    # от диапазона, осмысленно отсеивает гладкие области (небо, заливки).
    # На реальных фото отсеивает ~85% пикселей (см. profiling/docs/baseline_wav.md).
    #
    # Для WAV (int16, шкала -32768..+32767) порог 8 = 0.024% от диапазона
    # и почти ничего не фильтрует на шумных сигналах (>99% сэмплов в пуле).
    # Это намеренный trade-off: алгоритм остаётся единым для всех форматов,
    # детерминированный shuffle обеспечивает рассеивание независимо
    # от качества фильтра. Адаптивный порог отклонён в #25 (ломает
    # обратную совместимость существующих стего-файлов).
    GRADIENT_THRESHOLD = 8  # Хардкод эмпирического порога "шумности" пикселя

    def _to_grayscale_mask(self, container: np.ndarray) -> np.ndarray:
        """Возвращает 2D-массив (H,W) яркости или исходный 1D для аудио.
        Нужно для выявления шума, предварительно конвертировав изображение в черно-белое.
        Для этого используются коэффициенты стандарта ITU-R BT.601"""
        masked = container & ~np.array(1, dtype=container.dtype) # Это защита от shrinkage, чтобы граничные значения не потерлись в дешифровке
        if masked.ndim == 3:
            return (0.299 * masked[..., 0] + # чувствительность к красному спектру
                    0.587 * masked[..., 1] + # к зеленому
                    0.114 * masked[..., 2]).astype(np.int16) # к синему
        return masked.astype(np.int16)

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

    def get_max_capacity_bits(self, container: np.ndarray) -> int:
        """Возвращает реальную ёмкость пула координат после edge-detection.

        Args:
            container: Контейнер (RGB image, audio samples).

        Returns:
            Число позиций, прошедших порог GRADIENT_THRESHOLD.
            Может быть СУЩЕСТВЕННО меньше container.size: для гладких
            изображений (заливка одним цветом) может быть близко к нулю.
        """
        return int(self._build_edge_pool(container).size)

    def generate_coords(self, container: np.ndarray, payload_bits_len: int,
                        password_seed: str,
                        exclude_coords: Optional[Set[int]] = None) -> np.ndarray:
        """Генерирует payload_bits_len координат для embed.

        Алгоритм:
            1. Построить пул через edge-detection (_build_edge_pool).
            2. Если задан exclude_coords (decoy-режим) — вычесть их из пула.
            3. Проверить, что в пуле достаточно мест.
            4. Детерминированно перемешать пул seed'ом из пароля.
            5. Вернуть первые payload_bits_len координат.

        Args:
            container:        Контейнер-носитель.
            payload_bits_len: Сколько координат нужно (= размер payload в битах).
            password_seed:    Пароль для seed-генерации (см. core/common/seeding).
            exclude_coords:   Координаты, занятые decoy-payload (ADR 004).
                              Реальный payload должен внедряться в позиции,
                              отличные от decoy, иначе при extract decoy
                              мы попадём на чужие биты.

        Returns:
            1D ndarray длины payload_bits_len с flat-индексами.

        Raises:
            ValueError: Если после фильтрации в пуле меньше координат,
                        чем требуется для payload_bits_len.
                        Сообщение содержит расчёт нехватки в байтах
                        для UI-диалога.
        """
        pool = self._build_edge_pool(container)

        if exclude_coords:
            excl = np.fromiter(exclude_coords, dtype=np.int64)
            pool = pool[~np.isin(pool, excl)]

        if pool.size < payload_bits_len:
            shortage_bytes = (payload_bits_len - pool.size) // 8
            raise ValueError(
                f"Недостаточно ёмкости носителя для скрытия данных.\n"
                f"Требуется: {payload_bits_len:,} бит ({payload_bits_len // 8:,} байт)\n"
                f"Доступно:  {pool.size:,} бит ({pool.size // 8:,} байт)\n"
                f"Не хватает примерно {shortage_bytes:,} байт.\n"
                f"Возьмите контейнер большего размера или payload меньшего размера."
            )

        rng = derive_rng_from_password(password_seed)  # SHA-256 → seed (см. core/common/seeding)
        rng.shuffle(pool)  # in-place, без дополнительных аллокаций
        return pool[:payload_bits_len]