"""Иерархия пользовательских исключений SteGambit.

Все исключения наследуются от StegambitError, что позволяет ловить их одним except на границе UI

Каждое исключение несёт человекочитаемую ошибку.
"""


class StegambitError(Exception):
    """Базовое исключение приложения. Все доменные ошибки наследуются от него."""


class CompatibilityError(StegambitError):
    """Формат не поддержан, не хватает ёмкости, конверсия запрещена."""


class CapacityExceededError(CompatibilityError):
    """Payload не помещается в контейнер. Специализация CompatibilityError.

    Зарезервировано на будущее: если захотим отличать "формат не поддержан"
    от "формат ОК, но мало места" - фронт сможет проверить через isinstance.
    """


class InvalidFrameError(StegambitError):
    """В контейнере не найдены MAGIC-байты или повреждён header.

    Скорее всего: пароль неверный, либо файл вообще не содержит данных.
    """

class InvalidPasswordError(InvalidFrameError):
    """Неверный пароль или повреждённые данные.

    AES-GCM не может различить "неверный ключ" и "битые данные" - оба дают одинаковый результат: tag mismatch.
    """

class CorruptedCarrierError(StegambitError):
    """Контейнер не может быть прочитан (побитый жизнью)."""