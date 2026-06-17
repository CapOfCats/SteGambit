from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, Optional, Set, Tuple, TypeVar
import numpy as np

T = TypeVar("T")

class IStegoProcessor(ABC, Generic[T]):
    """Контракт стратегии стеганографического внедрения/извлечения.

    Параметризован типом контейнера T:
        - LsbProcessor:  T = np.ndarray (пиксели PNG / семплы WAV).
        - DctProcessor:  T = JpegContainer (квантованные DCT-коэффициенты + метаданные).

    Контракт coords неизменен для всех реализаций: одномерный массив int64
    с плоскими индексами позиций, куда встраивать / откуда извлекать биты.
    """

    @abstractmethod
    def embed(self, container: T, payload: bytes, coords: np.ndarray, *, lsb_depth: int = 1) -> T:
        """Внедрить payload в контейнер по координатам.

        Args:
            container: Контейнер-носитель.
                       Для LSB: ndarray (H, W, 3) uint8 для изображений или
                                (N,) int16 для WAV.
                       Для DCT: JpegContainer с квантованными коэффициентами.
            payload:   Готовый бинарный блоб (шифротекст из CryptoEngine).
            coords:    int64-массив плоских индексов.
                       Для LSB — индексы в container.flat.
                       Для DCT — индексы в JpegContainer.coef_arrays[0].ravel(),
                                 отфильтрованные через get_embeddable_positions().
            lsb_depth: Сколько младших бит использовать на элемент (1..4).
                       В MVP поддерживается только lsb_depth=1.

        Returns:
            Модифицированный контейнер того же типа. Для DCT может быть тот же
            объект (локальная модификация экономит память на больших JPEG).
        """
        ...

    @abstractmethod
    def extract(self, container: T, coords: np.ndarray, length: int, *, lsb_depth: int = 1) -> bytes:
        """Извлечь length байт payload из контейнера по координатам.

        Args:
            length: Длина payload в байтах (нужна, чтобы остановиться после нужного числа бит).
        """
        ...


class ISpreader(ABC):
    """Контракт генератора координат внедрения payload в контейнер.

    Реализация определяет стратегию выбора позиций — равномерную, content-aware
    (по edge detection), частотно-ограниченную (для DCT) и т.д. Контракт
    одинаков для всех вариантов: вход — контейнер + длина payload + пароль,
    выход — массив координат.

    Note:
        Все реализации должны быть детерминированными: один и тот же пароль
        на одном и том же контейнере даёт ту же последовательность координат.
        Это критично для корректной работы extract.
    """

    @abstractmethod
    def get_max_capacity_bits(self, container: np.ndarray) -> int:
        """Возвращает доступную ёмкость контейнера в битах.

        Считается ПОСЛЕ применения всех фильтров (edge-detection, маски и пр.),
        поэтому отражает реальное число позиций, а не геометрический размер.

        Args:
            container: Любой ndarray-контейнер (RGB image, audio samples).

        Returns:
            Число свободных позиций в пуле координат.
        """
        ...

    @abstractmethod
    def generate_coords(self, container: np.ndarray, payload_bits_len: int, password_seed: str,
                        exclude_coords: Optional[Set[int]] = None) -> np.ndarray:
        """Возвращает payload_bits_len flat-индексов в `container.flat`.

        Args:
            container:        Контейнер-носитель.
            payload_bits_len: Сколько координат нужно (= число бит в payload).
            password_seed:    Пароль для детерминированной перестановки.
            exclude_coords:   Координаты, исключаемые из пула — задел на
                              Plausible Deniability (ADR 004, флаг IS_DECOY).
                              При extract decoy эти позиции должны быть
                              запрещены для реального payload.

        Returns:
            1D ndarray длины payload_bits_len с flat-индексами.

        Raises:
            ValueError: Если пул после фильтрации меньше payload_bits_len.
        """
        pass


class FileFormat(ABC):
    """Базовый интерфейс для контейнеров-носителей (PNG, WAV, JPEG, ...).

    Каждая реализация инкапсулирует:
        * Magic bytes для идентификации формата (см. FormatIdentifier).
        * Декодирование файла в numpy-представление, удобное для embed/extract.
        * Сериализацию модифицированного представления обратно на диск
          БЕЗ потерь относительно исходного формата (анти-конверсия, ADR 003).

    Note:
        Для форматов, где numpy-массива недостаточно (например, JPEG нужен
        целый набор коэф-таблиц + кватаблицы), реализация возвращает
        собственный контейнерный объект (JpegContainer). В таком случае
        возврат типизирован как ndarray для общего интерфейса, но фактически
        это конкретный контейнер.
    """

    @property
    @abstractmethod
    def magic(self) -> bytes:
        """Magic bytes-маркер для идентификации формата по сырому потоку байт.

        Returns:
            Префикс файла, уникальный для данного формата. Используется
            FormatIdentifier для определения типа до открытия файла.
        """
        ...

    @abstractmethod
    def load(self, path: Path) -> np.ndarray:
        """Декодирует файл в numpy-представление.

        Args:
            path: Абсолютный путь к существующему файлу.

        Returns:
            ndarray (или контейнерный объект для сложных форматов),
            готовый к передаче в стего-процессор.

        Raises:
            FileNotFoundError:     Файл не найден.
            CorruptedCarrierError: Файл повреждён или не соответствует формату.
        """
        ...

    @abstractmethod
    def save(self, data: np.ndarray, path: Path) -> None:
        """Сериализует numpy-представление обратно в файл.

        Args:
            data: Контейнер после embed/extract.
            path: Путь сохранения. Расширение должно соответствовать формату.

        Raises:
            OSError: Если запись на диск невозможна (нет прав, нет места).
        """
        ...