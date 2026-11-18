"""Unit tests for SmartSpreader in spreader.py."""
import numpy as np
import pytest

from stegambit.core.stego.spreader import SmartSpreader


@pytest.fixture
def spreader():
    return SmartSpreader()


def _make_noisy_image(rng_obj, shape=(64, 64, 3)) -> np.ndarray:
    """A noisy image — every pixel differs from its neighbors — many edge points."""
    return rng_obj.integers(0, 256, size=shape, dtype=np.uint8)


def _make_flat_image(shape=(64, 64, 3), value=128) -> np.ndarray:
    """A flat single-color image — no gradients."""
    return np.full(shape, value, dtype=np.uint8)


class TestEdgePoolBuilding:
    """Tests of private _build_edge_pool: building the pool of edge coordinates."""

    def test_flat_image_yields_empty_pool(self, spreader):
        """Boundary case: a uniform image — the pool is empty."""
        container = _make_flat_image()
        pool = spreader._build_edge_pool(container)
        assert pool.size == 0

    def test_noisy_image_yields_non_empty_pool(self, spreader, rng):
        """Positive case: a noisy image — the pool is not empty."""
        container = _make_noisy_image(rng)
        pool = spreader._build_edge_pool(container)
        assert pool.size > 0

    def test_pool_indices_are_in_bounds(self, spreader, rng):
        """Property: every pool index is valid for container.flat."""
        container = _make_noisy_image(rng, shape=(32, 32, 3))
        pool = spreader._build_edge_pool(container)
        assert pool.min() >= 0
        assert pool.max() < container.size

    def test_pool_has_no_duplicates(self, spreader, rng):
        """Each index occurs exactly once."""
        container = _make_noisy_image(rng)
        pool = spreader._build_edge_pool(container)
        assert len(np.unique(pool)) == pool.size

    def test_works_on_3d_rgb(self, spreader, rng):
        """Equivalence: a 3D RGB ndarray."""
        container = _make_noisy_image(rng, shape=(32, 32, 3))
        pool = spreader._build_edge_pool(container)
        assert pool.dtype == np.int64

    def test_works_on_2d_grayscale(self, spreader, rng):
        """Equivalence: a 2D grayscale ndarray."""
        container = rng.integers(0, 256, size=(32, 32), dtype=np.uint8)
        pool = spreader._build_edge_pool(container)
        assert pool.size > 0

    def test_works_on_1d_audio(self, spreader, rng):
        """Equivalence: a 1D int16 array (a live example — WAV samples)."""
        container = rng.integers(-32768, 32768, size=10000, dtype=np.int16)
        pool = spreader._build_edge_pool(container)
        assert pool.size > 0
        assert pool.dtype == np.int64

    def test_lsb_mask_makes_pool_stable(self, spreader, rng):
        """The pool on the original and the LSB-modified container is identical."""
        container = _make_noisy_image(rng)
        modified = container.copy()
        modified ^= 1  # flip the LSB of every pixel
        pool_original = spreader._build_edge_pool(container)
        pool_modified = spreader._build_edge_pool(modified)
        np.testing.assert_array_equal(pool_original, pool_modified)


class TestGetMaxCapacityBits:
    """Tests of get_max_capacity_bits."""

    def test_capacity_equals_pool_size(self, spreader, rng):
        """Capacity matches the size of the edge pool exactly."""
        container = _make_noisy_image(rng)
        pool = spreader._build_edge_pool(container)
        assert spreader.get_max_capacity_bits(container) == pool.size

    def test_capacity_zero_on_flat_image(self, spreader):
        """Boundary case: a flat image — 0 bits of capacity."""
        assert spreader.get_max_capacity_bits(_make_flat_image()) == 0


class TestGenerateCoords:
    """Tests of the main public function generate_coords."""

    def test_same_password_yields_same_coords(self, spreader, rng):
        """Determinism by password."""
        container = _make_noisy_image(rng)
        coords_a = spreader.generate_coords(container, 256, "secret")
        coords_b = spreader.generate_coords(container, 256, "secret")
        np.testing.assert_array_equal(coords_a, coords_b)

    def test_different_passwords_yield_different_coords(self, spreader, rng):
        """Sensitivity to the password."""
        container = _make_noisy_image(rng)
        coords_a = spreader.generate_coords(container, 256, "secret1")
        coords_b = spreader.generate_coords(container, 256, "secret2")
        assert not np.array_equal(coords_a, coords_b)

    def test_coords_length_matches_payload_bits(self, spreader, rng):
        """The output array size equals the requested number of bits."""
        container = _make_noisy_image(rng)
        coords = spreader.generate_coords(container, 100, "pwd")
        assert coords.size == 100

    def test_coords_are_subset_of_pool(self, spreader, rng):
        """Every coordinate comes from the edge pool."""
        container = _make_noisy_image(rng)
        pool = spreader._build_edge_pool(container)
        coords = spreader.generate_coords(container, 200, "pwd")
        assert np.all(np.isin(coords, pool))

    def test_coords_have_no_duplicates(self, spreader, rng):
        """Coordinates within one sample are unique."""
        container = _make_noisy_image(rng)
        coords = spreader.generate_coords(container, 500, "pwd")
        assert len(np.unique(coords)) == coords.size

    def test_zero_bits_returns_empty_array(self, spreader, rng):
        """Boundary case: 0 requested bits — an empty array."""
        container = _make_noisy_image(rng)
        coords = spreader.generate_coords(container, 0, "pwd")
        assert coords.size == 0

    def test_overflow_raises_value_error(self, spreader):
        """Negative case: more bits requested than the pool holds."""
        container = _make_flat_image(shape=(8, 8, 3))
        with pytest.raises(ValueError, match="Недостаточно ёмкости"):
            spreader.generate_coords(container, 1000000, "pwd") # a million, but more is fine — not critical

    def test_overflow_message_contains_numbers(self, spreader):
        """UX contract: the message contains numbers for required and available."""
        container = _make_flat_image(shape=(8, 8, 3))
        with pytest.raises(ValueError) as exc_info:
            spreader.generate_coords(container, 1000, "pwd")
        msg = str(exc_info.value)
        assert "1,000" in msg or "1000" in msg

    def test_exclude_coords_filters_pool(self, spreader, rng):
        """Coordinates from exclude_coords do not appear in the result."""
        container = _make_noisy_image(rng)
        pool = spreader._build_edge_pool(container)
        excluded = set(int(x) for x in pool[:50])
        coords = spreader.generate_coords(container, 100, "pwd", exclude_coords=excluded)
        assert not any(int(c) in excluded for c in coords)

    def test_exclude_coords_none_equals_empty(self, spreader, rng):
        """Equivalence: exclude_coords=None behaves like an empty set."""
        container = _make_noisy_image(rng)
        coords_none = spreader.generate_coords(container, 100, "pwd", exclude_coords=None)
        coords_empty = spreader.generate_coords(container, 100, "pwd", exclude_coords=set())
        np.testing.assert_array_equal(coords_none, coords_empty)

    def test_overflow_with_exclusion(self, spreader, rng):
        """Negative case: exclude_coords can turn a valid request into an overflow."""
        container = _make_noisy_image(rng, shape=(16, 16, 3))
        pool = spreader._build_edge_pool(container)
        excluded = set(int(x) for x in pool[:-10])
        with pytest.raises(ValueError, match="Недостаточно ёмкости"):
            spreader.generate_coords(container, 500, "pwd", exclude_coords=excluded)