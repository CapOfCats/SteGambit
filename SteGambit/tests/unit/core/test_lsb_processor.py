"""Unit-тесты для LsbProcessor - strategies.py.

Изоляция:
    Тесты НЕ используют SmartSpreader. Координаты генерируются как
    np.arange(N) для детерминированности и независимости от другого модуля.
"""
import numpy as np
import pytest

from stegambit.core.stego.strategies import LsbProcessor


@pytest.fixture
def processor():
    return LsbProcessor()


class TestRoundTrip:
    """Главный инвариант: extract(embed(c, p, coords), coords, len(p)) == p."""

    @pytest.mark.parametrize("payload_size", [1, 16, 256, 1024])
    def test_round_trip_various_sizes(self, processor, rng, payload_size):
        """Эквивалентность - по размеру payload: малый / средний / крупный."""
        container = rng.integers(0, 256, size=10_000, dtype=np.uint8)
        payload = rng.bytes(payload_size)
        coords = np.arange(payload_size * 8, dtype=np.int64)

        stego = processor.embed(container, payload, coords)
        recovered = processor.extract(stego, coords, payload_size)

        assert recovered == payload

    def test_round_trip_on_3d_rgb_array(self, processor, rng):
        """LSB должен работать на 3D ndarray - RGB изображении."""
        container = rng.integers(0, 256, size=(50, 50, 3), dtype=np.uint8)
        payload = b"FFF RGB stego!!111!!ahahah"
        coords = np.arange(len(payload) * 8, dtype=np.int64)

        stego = processor.embed(container, payload, coords)
        recovered = processor.extract(stego, coords, len(payload))

        assert recovered == payload

    def test_round_trip_on_int16_audio_like(self, processor, rng):
        """WAV-семплы - int16."""
        container = rng.integers(-32768, 32768, size=5_000, dtype=np.int16)
        payload = b"AudioPayload"
        coords = np.arange(len(payload) * 8, dtype=np.int64)

        stego = processor.embed(container, payload, coords)
        recovered = processor.extract(stego, coords, len(payload))

        assert recovered == payload


class TestSideEffects:
    """Неизменность - что embed НЕ должен трогать."""

    def test_embed_does_not_mutate_original_container(self, processor, rng):
        """embed возвращает копию, оригинал не меняет."""
        original = rng.integers(0, 256, size=1_000, dtype=np.uint8)
        backup = original.copy()
        payload = b"test"
        coords = np.arange(32, dtype=np.int64)

        processor.embed(original, payload, coords)

        np.testing.assert_array_equal(original, backup)

    def test_embed_preserves_high_bits(self, processor, rng):
        """Старшие 7 бит каждого изменённого байта должны остаться нетронутыми."""
        container = rng.integers(0, 256, size=1_000, dtype=np.uint8)
        payload = b"X"  # восьмой бит0чек
        coords = np.arange(8, dtype=np.int64)

        stego = processor.embed(container, payload, coords)

        np.testing.assert_array_equal(
            container[coords] & 0b11111110,
            stego[coords] & 0b11111110,
        )

    def test_embed_does_not_touch_unused_positions(self, processor, rng):
        """Позиции вне coords должны остаться идентичными."""
        container = rng.integers(0, 256, size=1_000, dtype=np.uint8)
        payload = b"Y"
        coords = np.arange(8, dtype=np.int64)

        stego = processor.embed(container, payload, coords)

        unused_mask = np.ones(container.size, dtype=bool)
        unused_mask[coords] = False
        np.testing.assert_array_equal(container[unused_mask], stego[unused_mask])


class TestBoundaries:

    def test_empty_payload(self, processor, rng):
        """Пустой payload - допустим, embed не меняет контейнер."""
        container = rng.integers(0, 256, size=100, dtype=np.uint8)
        payload = b""
        coords = np.arange(0, dtype=np.int64)

        stego = processor.embed(container, payload, coords)
        np.testing.assert_array_equal(container, stego)

    def test_extract_zero_length_returns_empty(self, processor, rng):
        """extract(length=0) - пустой байт на выходе"""
        container = rng.integers(0, 256, size=100, dtype=np.uint8)
        coords = np.arange(0, dtype=np.int64)
        assert processor.extract(container, coords, length=0) == b""

    def test_coords_exactly_fit_payload(self, processor, rng):
        """Граничный кейз: coords.size == payload_bits - это успешное условие."""
        container = rng.integers(0, 256, size=1_000, dtype=np.uint8)
        payload = b"AB"  # 16 бит
        coords = np.arange(16, dtype=np.int64)

        stego = processor.embed(container, payload, coords)
        assert processor.extract(stego, coords, 2) == payload

    def test_coords_one_short_raises(self, processor, rng):
        """coords.size = payload_bits - 1 -> ValueError."""
        container = rng.integers(0, 256, size=1_000, dtype=np.uint8)
        payload = b"AB"  # 16 бит
        coords = np.arange(15, dtype=np.int64)

        with pytest.raises(ValueError, match="Координат меньше"):
            processor.embed(container, payload, coords)

    def test_extract_coords_one_short_raises(self, processor, rng):
        """Симметричная граница для extract."""
        container = rng.integers(0, 256, size=1_000, dtype=np.uint8)
        coords = np.arange(15, dtype=np.int64)
        with pytest.raises(ValueError, match="Координат меньше"):
            processor.extract(container, coords, length=2)


class TestUnsupportedFeatures:
    """Гарды, защищающие незавершённые фичи."""

    @pytest.mark.parametrize("depth", [0, 2, 3, 8, -1])
    def test_embed_rejects_non_one_lsb_depth(self, processor, rng, depth):
        """lsb_depth != 1 -> NotImplementedError. Архитектурный гард."""
        container = rng.integers(0, 256, size=100, dtype=np.uint8)
        coords = np.arange(8, dtype=np.int64)
        with pytest.raises(NotImplementedError):
            processor.embed(container, b"X", coords, lsb_depth=depth)

    @pytest.mark.parametrize("depth", [0, 2, 3, 8, -1])
    def test_extract_rejects_non_one_lsb_depth(self, processor, rng, depth):
        container = rng.integers(0, 256, size=100, dtype=np.uint8)
        coords = np.arange(8, dtype=np.int64)
        with pytest.raises(NotImplementedError):
            processor.extract(container, coords, length=1, lsb_depth=depth)


class TestDeterminism:
    """Повторный embed одинаковых данных - идентичный результат."""

    def test_embed_is_deterministic(self, processor, rng):
        container = rng.integers(0, 256, size=1_000, dtype=np.uint8)
        payload = b"DeterministicTest"
        coords = np.arange(len(payload) * 8, dtype=np.int64)

        stego1 = processor.embed(container, payload, coords)
        stego2 = processor.embed(container, payload, coords)

        np.testing.assert_array_equal(stego1, stego2)

    def test_extract_is_deterministic(self, processor, rng):
        container = rng.integers(0, 256, size=1_000, dtype=np.uint8)
        payload = b"DeterministicExtract"
        coords = np.arange(len(payload) * 8, dtype=np.int64)
        stego = processor.embed(container, payload, coords)

        assert processor.extract(stego, coords, len(payload)) == \
               processor.extract(stego, coords, len(payload))