# ADR 005: Адаптивный Spreader (Контентно-зависимая стеганография)

**Дата:** 2026-03-24
**Статус:** Утверждено
**Связь:** Дополняет и модифицирует ADR 003.

## 1. Контекст и Проблематика
Для повышения скрытности (снижения визуального детектирования и нивелирования banding-артефактов) принято решение отказаться от слепого разброса битов. Система должна избегать "гладких" участков контейнера и внедрять данные только в высокочастотные области (Edge Detection).

## 2. Архитектурное решение (Smart Spreader)
Генерация координат для LSB теперь проходит в два этапа:
1. **Masking (Маскирование):** Вычисление градиента изображения (фильтр Собеля или разность пикселей через `numpy`). Формирование пула доступных (безопасных) координат.
2. **Scattering (Разброс):** Псевдослучайная выборка $N$ координат из пула с использованием Cryptographically Secure PRNG (или ChaCha20/AES-CTR на базе пароля), где $N$ — длина payload в битах.

## 3. Модификация оценки емкости (Изменение ADR 003)
Теоретическая емкость контейнера больше не является константой $\lfloor \frac{W \times H}{8} \rfloor$.
**Новая формула:**
$$Capacity = \lfloor \frac{E_{safe}}{8} \rfloor - O_{crypto}$$
Где $E_{safe}$ — количество элементов контейнера, проходящих порог Edge Detection. 
В классе `CapacityAnalyzer` метод `analyze_capacity` теперь ОБЯЗАН предварительно вызывать метод `spreader.get_capacity(container_matrix)`.

## 4. Контракт `ISpreader` (Обновленный)
```python
class ISpreader(ABC):
    @abstractmethod
    def get_max_capacity_bits(self, container: np.ndarray) -> int:
        """Оценивает максимальное количество бит, которое можно безопасно внедрить"""
        pass

    @abstractmethod
    def generate_coords(self, container: np.ndarray, payload_bits_len: int, password_seed: str, exclude_coords: Optional[set] = None) -> np.ndarray:
        """
        Генерирует массив N координат (payload_bits_len).
        exclude_coords - задел для фичи "Двойное дно" (Plausible Deniability)
        """
        pass