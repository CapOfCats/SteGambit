"""Unit tests for core/common/seeding.py — deterministic seeding from a password."""
import numpy as np
import pytest

from stegambit.core.common.seeding import (
    derive_rng_from_password,
    shuffle_pool_by_password,
)


class TestShufflePoolByPassword:
    """Deterministic pool shuffle via a seed from the password."""

    def test_same_password_same_shuffle(self):
        """One password — an identical permutation."""
        pool = np.arange(100, dtype=np.int64)
        r1 = shuffle_pool_by_password(pool, "secret")
        r2 = shuffle_pool_by_password(pool, "secret")
        np.testing.assert_array_equal(r1, r2)

    def test_different_passwords_different_shuffle(self):
        """Different passwords — different permutations."""
        pool = np.arange(100, dtype=np.int64)
        r1 = shuffle_pool_by_password(pool, "secret1")
        r2 = shuffle_pool_by_password(pool, "secret2")
        assert not np.array_equal(r1, r2)

    def test_shuffle_preserves_elements(self):
        """The permutation contains the same elements as the original pool."""
        pool = np.arange(100, dtype=np.int64)
        shuffled = shuffle_pool_by_password(pool, "x")
        np.testing.assert_array_equal(np.sort(shuffled), pool)

    def test_does_not_mutate_input(self):
        """The original pool is not mutated."""
        pool = np.arange(100, dtype=np.int64)
        backup = pool.copy()
        shuffle_pool_by_password(pool, "x")
        np.testing.assert_array_equal(pool, backup)


class TestDeriveRngFromPassword:
    """SHA-256 → seed_int → numpy RNG."""

    def test_returns_numpy_generator(self):
        """The return type is numpy.random.Generator."""
        rng = derive_rng_from_password("any")
        assert isinstance(rng, np.random.Generator)

    def test_same_password_same_sequence(self):
        """Idempotence: the same password → the same sequence."""
        rng1 = derive_rng_from_password("password")
        rng2 = derive_rng_from_password("password")
        assert rng1.integers(0, 1_000_000) == rng2.integers(0, 1_000_000)

    def test_empty_password_works(self):
        """Boundary case: an empty password is allowed (password policy lives higher up)."""
        rng = derive_rng_from_password("")
        # Must not raise.
        _ = rng.integers(0, 100)

    def test_different_passwords_different_sequence(self):
        """A one-character difference — a different RNG output (SHA-256 avalanche effect)."""
        rng_a = derive_rng_from_password("password123")
        rng_b = derive_rng_from_password("password124")
        assert rng_a.integers(0, 10**9) != rng_b.integers(0, 10**9)

    def test_unicode_password_works(self):
        """A UTF-8 password is handled correctly (the encoding is fixed in encode)."""
        rng_a = derive_rng_from_password("пароль☺♂♀")
        rng_b = derive_rng_from_password("пароль☺♂♀")
        assert rng_a.integers(0, 10**9) == rng_b.integers(0, 10**9)