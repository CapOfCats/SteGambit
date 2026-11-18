from typing import Optional, Set
import numpy as np

from ..base import ISpreader
from ..common.seeding import derive_rng_from_password

class SmartSpreader(ISpreader):
    """Content-aware spreader with edge detection.

    How it works:
        1. Container -> grayscale (if RGB).
        2. Gradient via neighbor differences (|dx| + |dy|).
        3. Pool = coordinates where the gradient >= the distortion.
        4. Deterministic permutation of the pool via a seed from the password.
    """

    # Empirical "noisiness" threshold for edge detection.
    #
    # Tuned for 8-bit images (uint8, scale 0-255): a threshold of 8 is about 3%
    # of the range and meaningfully filters out smooth regions (sky, flat fills).
    # On real photos it filters out ~85% of pixels (see profiling/docs/baseline_wav.md).
    #
    # For WAV (int16, scale -32768..+32767) a threshold of 8 is 0.024% of the range
    # and filters almost nothing on noisy signals (>99% of samples stay in the pool).
    # This is an intentional trade-off: the algorithm stays the same for every format,
    # and the deterministic shuffle provides spreading regardless
    # of filter quality. An adaptive threshold was rejected in #25 (it breaks
    # backward compatibility of existing stego files).
    GRADIENT_THRESHOLD = 8  # Hardcoded empirical pixel "noisiness" threshold

    def _to_grayscale_mask(self, container: np.ndarray) -> np.ndarray:
        """Returns a 2D (H, W) luminance array, or the original 1D array for audio.
        Needed to detect noise, after first converting the image to black and white.
        The ITU-R BT.601 standard coefficients are used for that."""
        masked = container & ~np.array(1, dtype=container.dtype) # Shrinkage protection so boundary values are not wiped out during decryption
        if masked.ndim == 3:
            return (0.299 * masked[..., 0] + # sensitivity to the red spectrum
                    0.587 * masked[..., 1] + # to green
                    0.114 * masked[..., 2]).astype(np.int16) # to blue
        return masked.astype(np.int16)

    def _build_edge_pool(self, container: np.ndarray) -> np.ndarray:
        """Builds an array of flat indices into container.flat that passed the threshold."""
        gray = self._to_grayscale_mask(container)

        if gray.ndim == 2:
            dx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1])) # difference of neighboring pixels along the horizontal
            dy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :])) # likewise along Y
            edge_map = dx + dy
            mask_2d = edge_map >= self.GRADIENT_THRESHOLD # final mask of places where the gradient exceeds the threshold

            if container.ndim == 3:
                # The pixel is "noisy", so all of its channels are usable.
                c = container.shape[2]
                mask_flat = np.repeat(mask_2d.ravel(), c)
            else:
                mask_flat = mask_2d.ravel()
        else:
            # 1D for WAV — here it is simply the difference with the neighbor.
            diff = np.abs(np.diff(gray, prepend=gray[:1]))
            mask_flat = diff >= self.GRADIENT_THRESHOLD

        return np.flatnonzero(mask_flat).astype(np.int64)

    def get_max_capacity_bits(self, container: np.ndarray) -> int:
        """Returns the real capacity of the coordinate pool after edge detection.

        Args:
            container: Container (RGB image, audio samples).

        Returns:
            Number of positions that passed GRADIENT_THRESHOLD.
            Can be SUBSTANTIALLY smaller than container.size: for smooth
            images (a single-color fill) it can be close to zero.
        """
        return int(self._build_edge_pool(container).size)

    def generate_coords(self, container: np.ndarray, payload_bits_len: int,
                        password_seed: str,
                        exclude_coords: Optional[Set[int]] = None) -> np.ndarray:
        """Generates payload_bits_len coordinates for embed.

        Algorithm:
            1. Build the pool via edge detection (_build_edge_pool).
            2. If exclude_coords is set (decoy mode) — subtract them from the pool.
            3. Check that the pool has enough positions.
            4. Deterministically shuffle the pool with a seed from the password.
            5. Return the first payload_bits_len coordinates.

        Args:
            container:        Carrier container.
            payload_bits_len: How many coordinates are needed (= payload size in bits).
            password_seed:    Password for seed generation (see core/common/seeding).
            exclude_coords:   Coordinates occupied by the decoy payload (ADR 004).
                              The real payload must be embedded at positions
                              different from the decoy; otherwise, on decoy extract,
                              we would land on someone else's bits.

        Returns:
            1D ndarray of length payload_bits_len with flat indices.

        Raises:
            ValueError: If, after filtering, the pool has fewer coordinates
                        than payload_bits_len requires.
                        The message includes the shortage calculated in bytes
                        for the UI dialog.
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

        rng = derive_rng_from_password(password_seed)  # SHA-256 → seed (see core/common/seeding)
        rng.shuffle(pool)  # in-place, without extra allocations
        return pool[:payload_bits_len]
