"""Unit tests for DctProcessor — strategies.py.

Tests work with a synthetic JpegContainer.
Integration with jpeglib and a file round-trip live in test_jpeg_format.py.
"""
import numpy as np
import pytest

from stegambit.core.stego.strategies import DctProcessor
from stegambit.core.formats.jpeg import JpegContainer
from stegambit.core.stego.strategies import _MID_FREQ_ZIGZAG_FLAT


@pytest.fixture
def processor():
    return DctProcessor()


def _make_container(y_array: np.ndarray, with_chroma: bool = True) -> JpegContainer:
    """Creates a minimal JpegContainer for unit tests without jpeglib."""
    coef_arrays = [y_array]
    if with_chroma:
        cb = np.zeros_like(y_array)
        cr = np.zeros_like(y_array)
        coef_arrays.extend([cb, cr])
    h_pixels = y_array.shape[0] * 8
    w_pixels = y_array.shape[1] * 8
    return JpegContainer(
        coef_arrays=coef_arrays,
        dimensions=(h_pixels, w_pixels),
        _raw=None,
    )


def _make_y_with_value(blocks_h: int, blocks_w: int, fill: int = 50) -> np.ndarray:
    """Y channel of shape=(Hb, Wb, 8, 8) with a fixed value in every cell."""
    return np.full((blocks_h, blocks_w, 8, 8), fill, dtype=np.int16)


class TestGetEmbeddablePositions:
    """Tests of the pool of valid DCT positions."""

    def test_excludes_dc_coefficient(self, processor):
        """Position (0,0) of every block is DC and must not enter the pool."""
        y = _make_y_with_value(2, 2, fill=50)
        container = _make_container(y)
        pool = processor.get_embeddable_positions(container)

        y_flat_size = y.size
        dc_positions = np.arange(0, y_flat_size, 64)
        assert not np.any(np.isin(pool, dc_positions))

    def test_excludes_high_frequency_positions(self, processor):
        """Property: every intra-block position belongs to the first 27."""
        
        y = _make_y_with_value(2, 2, fill=50)
        container = _make_container(y)
        pool = processor.get_embeddable_positions(container)

        intra_positions = pool % 64
        allowed = set(_MID_FREQ_ZIGZAG_FLAT.tolist())
        assert set(intra_positions.tolist()).issubset(allowed)

    @pytest.mark.parametrize("excluded_value", [-2, -1, 0, 1])
    def test_excludes_dead_zone_values(self, processor, excluded_value):
        """Decision table: values {-2, -1, 0, 1} are fully excluded from the pool."""
        y = _make_y_with_value(2, 2, fill=excluded_value)
        container = _make_container(y)
        pool = processor.get_embeddable_positions(container)
        assert pool.size == 0

    @pytest.mark.parametrize("valid_value", [-10, -3, 2, 5, 100])
    def test_includes_valid_values(self, processor, valid_value):
        """Decision table: values outside {-2,-1,0,1} enter the pool."""
        y = _make_y_with_value(2, 2, fill=valid_value)
        container = _make_container(y)
        pool = processor.get_embeddable_positions(container)
        assert pool.size > 0

    def test_pool_is_int64(self, processor):
        """The result dtype is int64."""
        y = _make_y_with_value(2, 2, fill=50)
        pool = processor.get_embeddable_positions(_make_container(y))
        assert pool.dtype == np.int64

    def test_pool_indices_in_bounds(self, processor):
        """Every index is valid for y.ravel()."""
        y = _make_y_with_value(2, 2, fill=50)
        container = _make_container(y)
        pool = processor.get_embeddable_positions(container)
        assert pool.min() >= 0
        assert pool.max() < y.size

    def test_pool_has_no_duplicates(self, processor):
        """Indices in the pool are unique."""
        y = _make_y_with_value(3, 3, fill=50)
        pool = processor.get_embeddable_positions(_make_container(y))
        assert len(np.unique(pool)) == pool.size

    def test_ignores_chroma_channels(self, processor):
        """Cb/Cr do not affect the pool."""
        y = _make_y_with_value(2, 2, fill=50)
        c_with_chroma = _make_container(y, with_chroma=True)
        c_without = _make_container(y, with_chroma=False)
        pool_with = processor.get_embeddable_positions(c_with_chroma)
        pool_without = processor.get_embeddable_positions(c_without)
        np.testing.assert_array_equal(pool_with, pool_without)

    def test_dead_zone_filtering_per_position(self, processor):
        """Decision table: mixed values — correct per-position filtering."""
        y = np.full((1, 1, 8, 8), 50, dtype=np.int16)
        y[0, 0, 0, 1] = 0
        y[0, 0, 1, 0] = 1
        y[0, 0, 2, 0] = -1

        pool = processor.get_embeddable_positions(_make_container(y))
        excluded_flat_indices = {1, 8, 16}
        for excluded in excluded_flat_indices:
            assert excluded not in pool.tolist()


class TestRoundTrip:
    """The main invariant: embed then extract restores the payload."""

    @pytest.mark.parametrize("payload_size", [1, 8, 64, 256])
    def test_round_trip_various_sizes(self, processor, rng, payload_size):
        """Equivalence: round-trip at different payload sizes."""
        y = rng.integers(-50, 50, size=(12, 12, 8, 8), dtype=np.int16)
        y[np.isin(y, [-2, -1, 0, 1])] = 10
        container = _make_container(y)

        payload = rng.bytes(payload_size)
        pool = processor.get_embeddable_positions(container)
        coords = pool[:payload_size * 8]

        processor.embed(container, payload, coords)
        recovered = processor.extract(container, coords, payload_size)
        assert recovered == payload

    def test_pool_stable_after_embed(self, processor, rng):
        """The pool after embed is identical to the pool before embed."""
        y = rng.integers(-50, 50, size=(4, 4, 8, 8), dtype=np.int16)
        y[np.isin(y, [-2, -1, 0, 1])] = 10
        container = _make_container(y)

        pool_before = processor.get_embeddable_positions(container)
        payload = rng.bytes(32)
        processor.embed(container, payload, pool_before[:32 * 8])
        pool_after = processor.get_embeddable_positions(container)

        np.testing.assert_array_equal(pool_before, pool_after)


class TestSideEffects:
    """Embed contracts about what stays unchanged."""

    def test_embed_mutates_in_place_and_returns_same_object(self, processor, rng):
        """embed returns the same JpegContainer (in-place)."""
        y = rng.integers(10, 50, size=(2, 2, 8, 8), dtype=np.int16)
        container = _make_container(y)
        result = processor.embed(container, b"X", np.array([1, 2, 3, 4, 5, 6, 7, 8], dtype=np.int64))
        assert result is container

    def test_embed_only_modifies_lsb(self, processor, rng):
        """For every used position |before - after| <= 1."""
        y = rng.integers(10, 50, size=(2, 2, 8, 8), dtype=np.int16)
        container = _make_container(y)
        y_before = container.coef_arrays[0].copy()

        payload = b"AB"
        pool = processor.get_embeddable_positions(container)
        coords = pool[:16]
        processor.embed(container, payload, coords)

        y_after_flat = container.coef_arrays[0].reshape(-1)
        y_before_flat = y_before.reshape(-1)
        deltas = np.abs(y_after_flat[coords].astype(np.int32) -
                        y_before_flat[coords].astype(np.int32))
        assert deltas.max() <= 1

    def test_embed_preserves_sign(self, processor, rng):
        """The sign of the coefficient does not change."""
        y = rng.choice([-50, -30, -10, 10, 30, 50], size=(2, 2, 8, 8)).astype(np.int16)
        container = _make_container(y)
        y_before_flat = container.coef_arrays[0].reshape(-1).copy()

        payload = b"signtest"
        coords = processor.get_embeddable_positions(container)[:len(payload) * 8]
        processor.embed(container, payload, coords)

        y_after_flat = container.coef_arrays[0].reshape(-1)
        sign_before = np.sign(y_before_flat[coords])
        sign_after = np.sign(y_after_flat[coords])
        np.testing.assert_array_equal(sign_before, sign_after)

    def test_embed_does_not_touch_chroma(self, processor, rng):
        """Cb/Cr stay untouched."""
        y = rng.integers(10, 50, size=(2, 2, 8, 8), dtype=np.int16)
        container = _make_container(y)
        cb_before = container.coef_arrays[1].copy()
        cr_before = container.coef_arrays[2].copy()

        coords = processor.get_embeddable_positions(container)[:16]
        processor.embed(container, b"AB", coords)

        np.testing.assert_array_equal(container.coef_arrays[1], cb_before)
        np.testing.assert_array_equal(container.coef_arrays[2], cr_before)

    def test_embed_does_not_touch_unused_positions(self, processor, rng):
        """Coefficients outside coords stay unchanged."""
        y = rng.integers(10, 50, size=(2, 2, 8, 8), dtype=np.int16)
        container = _make_container(y)
        y_before = container.coef_arrays[0].copy()

        coords = processor.get_embeddable_positions(container)[:8]
        processor.embed(container, b"X", coords)

        y_after = container.coef_arrays[0]
        unused_mask = np.ones(y_after.size, dtype=bool)
        unused_mask[coords] = False
        np.testing.assert_array_equal(
            y_before.reshape(-1)[unused_mask],
            y_after.reshape(-1)[unused_mask],
        )


class TestBoundaries:
    """Boundary cases by size."""

    def test_empty_payload(self, processor, rng):
        """An empty payload — embed does not fail and does not change Y."""
        y = rng.integers(10, 50, size=(2, 2, 8, 8), dtype=np.int16)
        container = _make_container(y)
        y_before = container.coef_arrays[0].copy()

        processor.embed(container, b"", np.array([], dtype=np.int64))
        np.testing.assert_array_equal(container.coef_arrays[0], y_before)

    def test_extract_zero_length_returns_empty(self, processor, rng):
        """extract(length=0) → b''."""
        y = rng.integers(10, 50, size=(2, 2, 8, 8), dtype=np.int16)
        container = _make_container(y)
        assert processor.extract(container, np.array([], dtype=np.int64), 0) == b""

    def test_embed_coords_one_short_raises(self, processor, rng):
        """Negative: coords.size = bits - 1 → ValueError."""
        y = rng.integers(10, 50, size=(2, 2, 8, 8), dtype=np.int16)
        container = _make_container(y)
        coords = np.arange(15, dtype=np.int64)
        with pytest.raises(ValueError, match="вес координат"):
            processor.embed(container, b"AB", coords)

    def test_extract_coords_one_short_raises(self, processor, rng):
        """Negative: the symmetric case for extract."""
        y = rng.integers(10, 50, size=(2, 2, 8, 8), dtype=np.int16)
        container = _make_container(y)
        coords = np.arange(15, dtype=np.int64)
        with pytest.raises(ValueError, match="вес координат"):
            processor.extract(container, coords, length=2)


class TestUnsupportedFeatures:
    """Architectural guards."""

    @pytest.mark.parametrize("depth", [0, 2, 3, 8])
    def test_embed_rejects_non_one_lsb_depth(self, processor, rng, depth):
        """Negative case: lsb_depth != 1 → NotImplementedError."""
        y = rng.integers(10, 50, size=(2, 2, 8, 8), dtype=np.int16)
        container = _make_container(y)
        coords = np.arange(8, dtype=np.int64)
        with pytest.raises(NotImplementedError):
            processor.embed(container, b"X", coords, lsb_depth=depth)

    @pytest.mark.parametrize("depth", [0, 2, 3, 8])
    def test_extract_rejects_non_one_lsb_depth(self, processor, rng, depth):
        """Negative case: the symmetric case for extract."""
        y = rng.integers(10, 50, size=(2, 2, 8, 8), dtype=np.int16)
        container = _make_container(y)
        coords = np.arange(8, dtype=np.int64)
        with pytest.raises(NotImplementedError):
            processor.extract(container, coords, length=1, lsb_depth=depth)