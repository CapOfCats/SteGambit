"""DctSpreader - content-aware spreader для DCT-домена.

В отличие от SmartSpreader LSB, здесь нет edge-detection — пул формируется фильтром среднечастотных коэффициентов внутр
DctProcessor. Spreader отвечает только за:
    1. Получение пула через DctProcessor.get_embeddable_positions.
    2. Детерминированное перемешивание seeded-RNG от пароля.
    3. Возврат среза нужной длины.

Архитектурный принцип: сервисный слой не должен знать про seeding - это деталь spreaderа.
"""
from typing import Any, Optional

import numpy as np

from stegambit.core.common.seeding import shuffle_pool_by_password
from stegambit.core.stego.strategies import DctProcessor


class DctSpreader:
    """Spreader для JSteg-пайплайна.

    Симметричен SmartSpreader по контракту (generate_coords +
    get_max_capacity_bits), но без edge-detection.
    """

    def __init__(self, dct_processor: Optional[DctProcessor] = None) -> None:
        self._dct = dct_processor or DctProcessor()

    def generate_coords(
        self,
        container: Any,
        payload_bits_len: int,
        password_seed: str,
    ) -> np.ndarray:
        """Возвращает детерминированную перестановку координат пула
        длины payload_bits_len.

        Raises:
            ValueError: если пула недостаточно для требуемого числа бит.
        """
        pool = self._dct.get_embeddable_positions(container)
        if pool.size < payload_bits_len:
            raise ValueError(
                f"Недостаточно ёмкости DCT-носителя: доступно {pool.size} бит, "
                f"требуется {payload_bits_len}."
            )
        shuffled = shuffle_pool_by_password(pool, password_seed)
        return shuffled[:payload_bits_len]

    def get_max_capacity_bits(self, container: Any) -> int:
        """Максимальная ёмкость DCT-носителя в битах.

        Делегирует подсчёт DctProcessor (фильтр среднечастотных AC).
        """
        pool = self._dct.get_embeddable_positions(container)
        return int(pool.size)