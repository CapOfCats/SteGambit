from ..base import IStegoProcessor
from ..formats.jpeg import JpegContainer
import numpy as np


# Conversion helpers live in module scope for now; later they may become part of a class.

def _bytes_to_bits(data: bytes) -> np.ndarray:
    """bytes -> uint8 bit ndarray. shape=(len(data)*8,). Needed for extraction."""
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def _bits_to_bytes(bits: np.ndarray) -> bytes:
    """Inverse of _bytes_to_bits. Needed for embedding."""
    return np.packbits(bits.astype(np.uint8)).tobytes()


class LsbProcessor(IStegoProcessor):
    """LSB algorithm (least significant bit) — operates on Spreader coordinates.
    Runs with lsb_depth=1 in the MVP. Architecturally lsb_depth is threaded through,
    but real support for >1 is future work."""

    def embed(self, container: np.ndarray, payload: bytes, coords: np.ndarray, lsb_depth: int = 1) -> np.ndarray:
        if lsb_depth != 1:
            raise NotImplementedError("Пока поддержана только depth = 1")
        bits = _bytes_to_bits(payload)
        if coords.size < bits.size:
            raise ValueError(
                f"Координат меньше, чем бит payload: {coords.size} < {bits.size}"
            )
        result = container.copy()
        flat = result.reshape(-1)  # flattens a multidimensional array into one dimension

        # Clear the LSB at the chosen positions and set the payload bit.
        used = coords[:bits.size]
        flat[used] = (flat[used] & ~np.array(1, dtype=flat.dtype)) | \
                     bits.astype(flat.dtype)  # clears the least significant bit at the coordinates without touching the rest
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


# JSteg constants
# Zigzag scan order of coefficients in an 8×8 block (ISO/IEC 10918-1).
# Index 0 is DC (left untouched); indices 1..63 are AC in order of increasing frequency.
# Mid-frequency coefficients are used (the first 27 AC): low frequencies are chewed up by quantization,
# high ones are almost always zero — modifying them would break Huffman compression.
_MID_FREQ_ZIGZAG = np.array([
    (0, 1), (1, 0), (2, 0), (1, 1), (0, 2), (0, 3), (1, 2), (2, 1),
    (3, 0), (4, 0), (3, 1), (2, 2), (1, 3), (0, 4), (0, 5), (1, 4),
    (2, 3), (3, 2), (4, 1), (5, 0), (6, 0), (5, 1), (4, 2), (3, 3),
    (2, 4), (1, 5), (0, 6),
], dtype=np.int8)

# Map (row, col) pairs to flat indices inside a 64-element block: idx = row*8 + col.
# Needed for fast vectorized numpy indexing.
_MID_FREQ_ZIGZAG_FLAT = (
    _MID_FREQ_ZIGZAG[:, 0].astype(np.int64) * 8
    + _MID_FREQ_ZIGZAG[:, 1].astype(np.int64)
)


class DctProcessor(IStegoProcessor[JpegContainer]):
    """JSteg-like embedding into quantized JPEG DCT coefficients.

    Principles (per ADR 007 + the Architect's architectural checkpoint):
        !! DC is not touched (position 0 in the block) — to avoid checkerboard blotches.
        !! Positions with value 0, 1, or -1 are not touched: modifying them either
           turns the coefficient into 0 (breaks the pool on extract) or changes the sign
           (breaks Huffman compression and inflates the file).
        !! Work only in the mid-frequency zone (zigzag AC 1..27).
        !! The modification is the LSB of the quantized coefficient.
    """

    _EXCLUDED_VALUES = frozenset({-2, -1, 0, 1})

    def get_embeddable_positions(self, container: JpegContainer) -> np.ndarray:
        """Builds a pool of flat indices of coefficients valid for embedding.

        Uses only the Y channel. Cb/Cr are left untouched — this improves stealth.

        Returns:
            np.ndarray[int64] — flat indices into Y.reshape(-1) that are worth embedding into.
            The order is the natural array traversal; SmartSpreader applies the final permutation from the seed.
        """
        y = container.coef_arrays[0]  # shape=(Hb, Wb, 8, 8), int16
        flat = y.reshape(-1, 64)      # each block is a row of 64 coefficients

        # Flat indices inside the block for the mid-frequency positions.
        intra_block_idx = _MID_FREQ_ZIGZAG_FLAT

        # Gather every coefficient at these positions across all blocks.
        candidates = flat[:, intra_block_idx]  # shape=(num_blocks, 27)

        # JSteg filter: exclude the values {-1, 0, 1}.
        mask = ~np.isin(candidates, list(self._EXCLUDED_VALUES))

        # Map (block_idx, intra_idx) to a global flat index in y.ravel().
        block_indices, intra_positions = np.where(mask)
        global_flat_indices = (
            block_indices * 64 + intra_block_idx[intra_positions]
        )
        return global_flat_indices.astype(np.int64)

    def embed(self, container: JpegContainer, payload: bytes, coords: np.ndarray, *, lsb_depth: int = 1) -> JpegContainer:
        """Embeds the payload into the LSB of the selected Y-channel DCT coefficients.

        Args:
            container: JpegContainer loaded by JpegFormat.load().
            payload:   Ciphertext (already passed through CryptoEngine.encrypt).
            coords:    Flat indices into Y.ravel(), chosen by SmartSpreader
                       from the get_embeddable_positions pool.

        Returns:
            The same JpegContainer (coefficients modified in place
            to save memory on large JPEGs).

        Raises:
            ValueError: If there are fewer coordinates than bits in the payload.
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
        # Clear the LSB and write the payload bit. This also works for negative
        # values: the LSB is stored in the least significant bit the same way.
        y_flat[used] = (values & ~np.int16(1)) | bits.astype(np.int16)
        # Y is already modified (y_flat is a view of y).
        return container

    def extract(self, container: JpegContainer, coords: np.ndarray, length: int, *, lsb_depth=1) -> bytes:
        """Extracts payload bytes of the given length from coefficient LSBs at coords.

        Important: coords must be obtained the same way as during embed —
        get_embeddable_positions() + SmartSpreader with the same seed.
        Because {-1, 0, 1} were excluded from the pool BEFORE modification, and JSteg
        via LSB does not change the sign and does not zero out the remaining values, the pool
        is restored identically on extract. Boom!1
        """
        if lsb_depth != 1:
            raise NotImplementedError("DCT: поддержан только lsb_depth=1")
        bits_needed = length * 8
        if coords.size < bits_needed:
            raise ValueError(
                f"DCT: вес координат ({coords.size}) < требуемого числа бит ({bits_needed})."
            )
        y_flat = container.coef_arrays[0].reshape(-1)
        bits = (y_flat[coords[:bits_needed]] & 1).astype(np.uint8)
        return np.packbits(bits).tobytes()
