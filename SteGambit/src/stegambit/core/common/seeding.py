"""Deterministic seeding utilities for stego algorithms.

Every spreading algorithm, both LSB via SmartSpreader and DCT via PasswordShuffler,
uses SHA-256 → 8 bytes → seed_int so that extract stays reproducible.

The logic lives here to avoid duplication and to keep a single place to change the seed scheme.
"""
import hashlib
import numpy as np


def derive_rng_from_password(password: str) -> np.random.Generator:
    """Returns a deterministic numpy RNG seeded from the password.

    Scheme:
        SHA-256 -> first 8 bytes -> big-endian uint64 -> seed.

    The same password on different machines yields the same random-number stream — this is critical for reproducibility
    of coordinate-pool permutations on the embed/extract side.

    Args:
        password: Arbitrary string.

    Returns:
        numpy.random.Generator, ready for shuffle() integers()
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    seed_int = int.from_bytes(digest[:8], "big", signed=False)
    return np.random.default_rng(seed_int)


def shuffle_pool_by_password(pool: np.ndarray, password: str) -> np.ndarray:
    """Deterministically shuffles the coordinate pool with a seed from the password.

    Returns a COPY — does not modify the input array. This is safer when the pool is reused.

    Args:
        pool:     1D numpy array of coordinates.
        password: Seed string.

    Returns:
        Shuffled copy of pool.
    """
    rng = derive_rng_from_password(password)
    pool_copy = pool.copy()
    rng.shuffle(pool_copy)
    return pool_copy
