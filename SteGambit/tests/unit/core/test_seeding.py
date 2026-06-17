"""Unit-тесты для core/common/seeding.py — детерминированный seeding по паролю."""
import numpy as np
import pytest

from stegambit.core.common.seeding import (
    derive_rng_from_password,
    shuffle_pool_by_password,
)


class TestShufflePoolByPassword:
    """Детерминированный шафл пула через seed от пароля."""

    def test_same_password_same_shuffle(self):
        """Один пароль - идентичная перестановка."""
        pool = np.arange(100, dtype=np.int64)
        r1 = shuffle_pool_by_password(pool, "secret")
        r2 = shuffle_pool_by_password(pool, "secret")
        np.testing.assert_array_equal(r1, r2)

    def test_different_passwords_different_shuffle(self):
        """Разные пароли - разные перестановки."""
        pool = np.arange(100, dtype=np.int64)
        r1 = shuffle_pool_by_password(pool, "secret1")
        r2 = shuffle_pool_by_password(pool, "secret2")
        assert not np.array_equal(r1, r2)

    def test_shuffle_preserves_elements(self):
        """Перестановка содержит те же элементы, что и исходный пул."""
        pool = np.arange(100, dtype=np.int64)
        shuffled = shuffle_pool_by_password(pool, "x")
        np.testing.assert_array_equal(np.sort(shuffled), pool)

    def test_does_not_mutate_input(self):
        """Исходный пул не мутируется."""
        pool = np.arange(100, dtype=np.int64)
        backup = pool.copy()
        shuffle_pool_by_password(pool, "x")
        np.testing.assert_array_equal(pool, backup)


class TestDeriveRngFromPassword:
    """SHA-256 → seed_int → numpy RNG."""

    def test_returns_numpy_generator(self):
        """Тип возвращаемого значения — numpy.random.Generator."""
        rng = derive_rng_from_password("any")
        assert isinstance(rng, np.random.Generator)

    def test_same_password_same_sequence(self):
        """Идемпотентность: одинаковый пароль → одинаковая последовательность."""
        rng1 = derive_rng_from_password("password")
        rng2 = derive_rng_from_password("password")
        assert rng1.integers(0, 1_000_000) == rng2.integers(0, 1_000_000)

    def test_empty_password_works(self):
        """Граничный кейз: пустой пароль допустим (политика паролей — выше)."""
        rng = derive_rng_from_password("")
        # Не должно быть исключения.
        _ = rng.integers(0, 100)

    def test_different_passwords_different_sequence(self):
        """Один символ разницы — разный RNG-выход (avalanche-эффект SHA-256)."""
        rng_a = derive_rng_from_password("password123")
        rng_b = derive_rng_from_password("password124")
        assert rng_a.integers(0, 10**9) != rng_b.integers(0, 10**9)

    def test_unicode_password_works(self):
        """UTF-8 пароль обрабатывается корректно (кодировка зафиксирована в encode)."""
        rng_a = derive_rng_from_password("пароль☺♂♀")
        rng_b = derive_rng_from_password("пароль☺♂♀")
        assert rng_a.integers(0, 10**9) == rng_b.integers(0, 10**9)