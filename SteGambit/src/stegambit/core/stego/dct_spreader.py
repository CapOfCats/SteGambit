"""DctSpreader — content-aware spreader for the DCT domain.

Unlike LSB SmartSpreader, there is no edge detection here — the pool is formed by the mid-frequency coefficient filter inside
DctProcessor. The spreader is responsible only for:
    1. Obtaining the pool via DctProcessor.get_embeddable_positions.
    2. Deterministic shuffling with a password-seeded RNG.
    3. Returning a slice of the required length.

Architectural principle: the service layer must not know about seeding — that is a spreader detail.
"""
from typing import Any, Optional

import numpy as np

from stegambit.core.common.seeding import shuffle_pool_by_password
from stegambit.core.stego.strategies import DctProcessor


class DctSpreader:
    """Spreader for the JSteg pipeline.

    Symmetric with SmartSpreader by contract (generate_coords +
    get_max_capacity_bits), but without edge detection.
    """

    def __init__(self, dct_processor: Optional[DctProcessor] = None) -> None:
        self._dct = dct_processor or DctProcessor()

    def generate_coords(
        self,
        container: Any,
        payload_bits_len: int,
        password_seed: str,
    ) -> np.ndarray:
        """Returns a deterministic permutation of pool coordinates
        of length payload_bits_len.

        Raises:
            ValueError: if the pool is too small for the required number of bits.
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
        """Maximum DCT carrier capacity in bits.

        Delegates the count to DctProcessor (mid-frequency AC filter).
        """
        pool = self._dct.get_embeddable_positions(container)
        return int(pool.size)
