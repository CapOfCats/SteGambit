# Гайд по тестированию SteGambit

Документ описывает структуру тестов, способы запуска, фикстуры и известные ограничения.

## Содержание

- [Структура тестов](#структура-тестов)
- [Запуск тестов](#запуск-тестов)
- [Маркеры pytest](#маркеры-pytest)
- [Coverage](#coverage)
- [Фикстуры](#фикстуры)
- [Артефакты](#артефакты)
- [Соглашения и принципы](#соглашения-и-принципы)
- [Troubleshooting](#troubleshooting)

---

## Структура тестов
tests/
├── conftest.py # Корневые фикстуры (artifacts_dir, safe_png, safe_jpeg, safe_wav, rng, и т.д.)
├── TESTING.md # Этот документ
├── artifacts/ # Read-only эталонные файлы
│ ├── carriers/ # Тестовые носители (PNG/JPEG/WAV)
│ └── payloads/ # Тестовые payload-файлы (PDF/ZIP/TXT)
│
├── unit/ # Unit-тесты (зеркало src/stegambit/)
│ ├── models/
│ │ └── test_dto.py
│ ├── core/
│ │ ├── test_format_id.py
│ │ ├── test_lsb_processor.py
│ │ ├── test_dct_processor.py
│ │ ├── test_spreader.py
│ │ ├── test_crypto.py
│ │ ├── test_png_format.py
│ │ ├── test_jpeg_format.py
│ │ └── test_wav_format.py
│ └── services/
│ ├── test_stego_service.py
│ └── test_metrics.py
│
└── integration/
└── test_smoke_pipeline.py # Сквозные smoke-тесты пайплайна



**Принцип зеркала:** структура `tests/unit/` повторяет `src/stegambit/`. Новый модуль в `src/` — соответствующий файл `test_*.py` в `tests/unit/`.

---

## Запуск тестов

### Все тесты
pytest



### Только unit
pytest tests/unit



### Только smoke
pytest tests/integration -m smoke



### Конкретный модуль
pytest tests/unit/core/test_lsb_processor.py



### Конкретный класс или тест
pytest tests/unit/core/test_lsb_processor.py::TestRoundTrip
pytest tests/unit/core/test_lsb_processor.py::TestRoundTrip::test_round_trip_various_sizes



### Verbose режим
pytest -v



### Остановиться на первом падении
pytest -x



---

## Маркеры pytest

Маркеры зарегистрированы в `pyproject.toml` (или `pytest.ini`):

| Маркер | Назначение | Когда применяется |
|---|---|---|
| `smoke` | Минимальный сквозной набор | Критичные сценарии в `tests/integration/` |
| `integration` | Интеграционные тесты | Тесты, использующие несколько модулей одновременно |
| `io` | Тесты, использующие реальную ФС / внешние библиотеки (PIL, wave, jpeglib) | Format I/O тесты |

### Примеры запуска по маркерам

Только быстрые тесты (без I/O):
pytest tests/unit -m "not io"



Только I/O тесты:
pytest tests/unit -m "io"



Только smoke:
pytest -m smoke



Комбинации:
pytest -m "smoke and not io"



---

## Coverage

### Замер покрытия
pytest tests/unit --cov=src/stegambit --cov-report=term-missing



### HTML-отчёт
pytest tests/unit --cov=src/stegambit --cov-report=html



После прогона открыть `htmlcov/index.html` в браузере.

### Целевые цифры покрытия

| Модуль | Минимум | Идеал |
|---|---|---|
| `models/dto.py` | 100% | 100% |
| `core/common/format_id.py` | 95% | 100% |
| `core/stego/strategies.py` | 90% | 95% |
| `core/stego/spreader.py` | 90% | 95% |
| `core/crypto/engine.py` | 90% | 95% |
| `core/formats/*.py` | 70% | 90% |
| `services/stego_service.py` | 75% | 85% |
| `services/metrics.py` | 90% | 100% |

Coverage < 100% допустим для платформенно-специфичных веток, внешних I/O и dead code.

---

## Фикстуры

Все общие фикстуры — в корневом `tests/conftest.py`. Локальные фикстуры (используемые в одном файле) — внутри тестового модуля.

### Корневые фикстуры

| Фикстура | Назначение | Scope |
|---|---|---|
| `artifacts_dir` | Путь к `tests/artifacts/` | session |
| `carriers_dir` | Путь к `tests/artifacts/carriers/` | session |
| `payloads_dir` | Путь к `tests/artifacts/payloads/` | session |
| `safe_png` | Копия PNG-носителя в `tmp_path` | function |
| `safe_jpeg` | Копия JPEG-носителя в `tmp_path` (обход бага jpeglib + кириллица) | function |
| `safe_wav` | Копия WAV-носителя в `tmp_path` | function |
| `rng` | Детерминированный `np.random.default_rng(seed=42)` | function |

### Принцип "safe-копий"

Артефакты в `tests/artifacts/` **read-only** — тесты не должны их мутировать. Все фикстуры `safe_*` копируют файл в `tmp_path` через хелпер `_copy_artifact()`. Это:

1. Защищает эталоны от случайной мутации.
2. Обходит баг `jpeglib` с кириллицей в путях на Windows (см. [Troubleshooting](#troubleshooting)).
3. Обеспечивает автоматическую очистку через pytest.

---

## Артефакты

В `tests/artifacts/` лежат **эталонные** файлы. Структура:
artifacts/
├── carriers/
│ ├── photo.png
│ ├── photo.jpg
│ └── sound.wav
└── payloads/
├── document.pdf
├── archive.zip
└── tiny.txt



### Добавление нового артефакта

1. Положить файл в нужную подпапку.
2. При необходимости — добавить фикстуру в `tests/conftest.py` через `_copy_artifact()`.
3. Использовать в тестах через фикстуру, **не** через прямой путь.

**Запрещено:** модифицировать артефакты в тестах. Используй `safe_*` копии.

---

## Соглашения и принципы

### Техники тест-дизайна

Каждый тест должен явно указывать применённую технику в первой строке docstring:

- **Equivalence** — разбиение на классы эквивалентности.
- **Boundary** / **Граничный кейз** — граничные значения.
- **Negative** / **Негативный кейз** — проверка `raises`.
- **Property** — инвариант (свойство).
- **Decision Table** — таблица решений.
- **Round-trip** — обратимость операции.
- **State-based** — проверка изменения состояния.

### TROUBLESHOOTING 
----
**Warning PytestUnknownMarkWarning**
Маркер не зарегистрирован в pyproject.toml. Добавь в секцию:


[tool.pytest.ini_options]
markers = [
    "smoke: critical end-to-end scenarios",
    "integration: tests involving multiple modules",
    "io: tests touching real file system / external libraries",
]