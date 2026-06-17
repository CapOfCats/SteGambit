"""Утилиты детерминированного seeding для стегоалгоритмов.

Все алгоритмы spreading как LSB через SmartSpreader, так и DCT через PasswordShuffler
используют SHA-256 → 8 bytes → seed_int для воспроизводимости при extract.

Логика вынесена сюда, чтобы избежать дублирования и иметь единую точку изменения seed-схемы.
"""
import hashlib
import numpy as np


def derive_rng_from_password(password: str) -> np.random.Generator:
    """Возвращает детерминированный numpy RNG, заведённый от пароля.

    Схема:
        SHA-256 -> первые 8 байт -> big-endian uint64 -> seed.

    Тот же пароль на разных машинах даст тот же поток случайных чисел - это критично для воспроизводимости 
    перестановок пула координат на стороне embed/extract.

    Args:
        password: Произвольная строка.

    Returns:
        numpy.random.Generator, готовый к shuffle() integers()
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    seed_int = int.from_bytes(digest[:8], "big", signed=False)
    return np.random.default_rng(seed_int)


def shuffle_pool_by_password(pool: np.ndarray, password: str) -> np.ndarray:
    """Детерминированно перемешивает пул координат seed'ом из пароля.

    Возвращает КОПИЮ - не модифицирует входной массив. Это безопаснее в условиях, когда пул переиспользуется/

    Args:
        pool:     1D numpy-массив координат.
        password: Строка-сид.

    Returns:
        Перемешанная копия pool.
    """
    rng = derive_rng_from_password(password)
    pool_copy = pool.copy()
    rng.shuffle(pool_copy)
    return pool_copy