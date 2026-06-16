"""Unit-тесты для SmartSpreader spreader.py."""
import numpy as np
import pytest

from stegambit.core.stego.spreader import SmartSpreader


@pytest.fixture
def spreader():
    return SmartSpreader()


def _make_noisy_image(rng_obj, shape=(64, 64, 3)) -> np.ndarray:
    """Шумное изображение - каждый пиксель отличается от соседей - много edge-точек."""
    return rng_obj.integers(0, 256, size=shape, dtype=np.uint8)


def _make_flat_image(shape=(64, 64, 3), value=128) -> np.ndarray:
    """Плоское изображение одного цвета - нет градиентов."""
    return np.full(shape, value, dtype=np.uint8)


class TestEdgePoolBuilding:
    """Тесты приватного _build_edge_pool: формирование пула edge-координат."""

    def test_flat_image_yields_empty_pool(self, spreader):
        """Граничный кейз: однотонное изображение - пул пуст."""
        container = _make_flat_image()
        pool = spreader._build_edge_pool(container)
        assert pool.size == 0

    def test_noisy_image_yields_non_empty_pool(self, spreader, rng):
        """Положительный кейз: шумное изображение - пул не пуст."""
        container = _make_noisy_image(rng)
        pool = spreader._build_edge_pool(container)
        assert pool.size > 0

    def test_pool_indices_are_in_bounds(self, spreader, rng):
        """Property: все индексы пула - валидные для container.flat."""
        container = _make_noisy_image(rng, shape=(32, 32, 3))
        pool = spreader._build_edge_pool(container)
        assert pool.min() >= 0
        assert pool.max() < container.size

    def test_pool_has_no_duplicates(self, spreader, rng):
        """Каждый индекс встречается ровно один раз."""
        container = _make_noisy_image(rng)
        pool = spreader._build_edge_pool(container)
        assert len(np.unique(pool)) == pool.size

    def test_works_on_3d_rgb(self, spreader, rng):
        """Эквивалентность: 3D RGB-ndarray."""
        container = _make_noisy_image(rng, shape=(32, 32, 3))
        pool = spreader._build_edge_pool(container)
        assert pool.dtype == np.int64

    def test_works_on_2d_grayscale(self, spreader, rng):
        """Эквивалентность: 2D grayscale-ndarray."""
        container = rng.integers(0, 256, size=(32, 32), dtype=np.uint8)
        pool = spreader._build_edge_pool(container)
        assert pool.size > 0

    def test_works_on_1d_audio(self, spreader, rng):
        """Эквивалентность: 1D int16-массив (живой пример - WAV-семплы)."""
        container = rng.integers(-32768, 32768, size=10000, dtype=np.int16)
        pool = spreader._build_edge_pool(container)
        assert pool.size > 0
        assert pool.dtype == np.int64

    def test_lsb_mask_makes_pool_stable(self, spreader, rng):
        """Пул на исходном и LSB-модифицированном контейнере идентичен."""
        container = _make_noisy_image(rng)
        modified = container.copy()
        modified ^= 1  # инверт LSB всех пикселей
        pool_original = spreader._build_edge_pool(container)
        pool_modified = spreader._build_edge_pool(modified)
        np.testing.assert_array_equal(pool_original, pool_modified)


class TestSeedRng:
    """Тесты приватного _seed_rng: детерминизм генерации RNG из пароля."""

    def test_same_password_same_rng_state(self, spreader):
        """Один пароль - идентичный RNG-выход."""
        rng_a = spreader._seed_rng("password123")
        rng_b = spreader._seed_rng("password123")
        assert rng_a.integers(0, 10**9) == rng_b.integers(0, 10**9)

    def test_different_passwords_different_rng_state(self, spreader):
        """Один символ разницы - разный RNG-выход."""
        rng_a = spreader._seed_rng("password123")
        rng_b = spreader._seed_rng("password124")
        assert rng_a.integers(0, 10**9) != rng_b.integers(0, 10**9)

    def test_empty_password_does_not_crash(self, spreader):
        """Граничный кейз: пустой пароль допустим."""
        rng = spreader._seed_rng("")
        rng.integers(0, 10)

    def test_unicode_password_works(self, spreader):
        """UTF-8 пароль."""
        rng_a = spreader._seed_rng("пароль☺♂♀")
        rng_b = spreader._seed_rng("пароль☺♂♀")
        assert rng_a.integers(0, 10**9) == rng_b.integers(0, 10**9)


class TestGetMaxCapacityBits:
    """Тесты get_max_capacity_bits."""

    def test_capacity_equals_pool_size(self, spreader, rng):
        """Сapacity ровно совпадает с размером edge-пула."""
        container = _make_noisy_image(rng)
        pool = spreader._build_edge_pool(container)
        assert spreader.get_max_capacity_bits(container) == pool.size

    def test_capacity_zero_on_flat_image(self, spreader):
        """Граничный кейз: плоское изображение - 0 бит ёмкости."""
        assert spreader.get_max_capacity_bits(_make_flat_image()) == 0


class TestGenerateCoords:
    """Тесты главной публичной функции generate_coords."""

    def test_same_password_yields_same_coords(self, spreader, rng):
        """Детерминизм по паролю."""
        container = _make_noisy_image(rng)
        coords_a = spreader.generate_coords(container, 256, "secret")
        coords_b = spreader.generate_coords(container, 256, "secret")
        np.testing.assert_array_equal(coords_a, coords_b)

    def test_different_passwords_yield_different_coords(self, spreader, rng):
        """Чувствительность к паролю."""
        container = _make_noisy_image(rng)
        coords_a = spreader.generate_coords(container, 256, "secret1")
        coords_b = spreader.generate_coords(container, 256, "secret2")
        assert not np.array_equal(coords_a, coords_b)

    def test_coords_length_matches_payload_bits(self, spreader, rng):
        """Размер выходного массива = запрошенному числу бит."""
        container = _make_noisy_image(rng)
        coords = spreader.generate_coords(container, 100, "pwd")
        assert coords.size == 100

    def test_coords_are_subset_of_pool(self, spreader, rng):
        """Каждая координата - из edge-пула."""
        container = _make_noisy_image(rng)
        pool = spreader._build_edge_pool(container)
        coords = spreader.generate_coords(container, 200, "pwd")
        assert np.all(np.isin(coords, pool))

    def test_coords_have_no_duplicates(self, spreader, rng):
        """Внутри одной выборки координаты уникальны."""
        container = _make_noisy_image(rng)
        coords = spreader.generate_coords(container, 500, "pwd")
        assert len(np.unique(coords)) == coords.size

    def test_zero_bits_returns_empty_array(self, spreader, rng):
        """Граничный кейз: 0 запрошенных бит - пустой массив."""
        container = _make_noisy_image(rng)
        coords = spreader.generate_coords(container, 0, "pwd")
        assert coords.size == 0

    def test_overflow_raises_value_error(self, spreader):
        """Негативный кейз: запрошено больше бит, чем в пуле."""
        container = _make_flat_image(shape=(8, 8, 3))
        with pytest.raises(ValueError, match="Недостаточно ёмкости"):
            spreader.generate_coords(container, 1000000, "pwd") # мильон, но можно больше - не критично

    def test_overflow_message_contains_numbers(self, spreader):
        """UX-контракт: сообщение содержит цифры о требуемом и доступном."""
        container = _make_flat_image(shape=(8, 8, 3))
        with pytest.raises(ValueError) as exc_info:
            spreader.generate_coords(container, 1000, "pwd")
        msg = str(exc_info.value)
        assert "1,000" in msg or "1000" in msg

    def test_exclude_coords_filters_pool(self, spreader, rng):
        """Координаты из exclude_coords не появляются в результате."""
        container = _make_noisy_image(rng)
        pool = spreader._build_edge_pool(container)
        excluded = set(int(x) for x in pool[:50])
        coords = spreader.generate_coords(container, 100, "pwd", exclude_coords=excluded)
        assert not any(int(c) in excluded for c in coords)

    def test_exclude_coords_none_equals_empty(self, spreader, rng):
        """Эквивалентность: exclude_coords=None ведёт себя как пустое множество."""
        container = _make_noisy_image(rng)
        coords_none = spreader.generate_coords(container, 100, "pwd", exclude_coords=None)
        coords_empty = spreader.generate_coords(container, 100, "pwd", exclude_coords=set())
        np.testing.assert_array_equal(coords_none, coords_empty)

    def test_overflow_with_exclusion(self, spreader, rng):
        """Негативный кейз: exclude_coords может перевести валидный запрос в overflow."""
        container = _make_noisy_image(rng, shape=(16, 16, 3))
        pool = spreader._build_edge_pool(container)
        excluded = set(int(x) for x in pool[:-10])
        with pytest.raises(ValueError, match="Недостаточно ёмкости"):
            spreader.generate_coords(container, 500, "pwd", exclude_coords=excluded)