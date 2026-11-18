# SteGambit testing guide

This document describes the test layout, how to run the tests, the fixtures, and known limitations.

## Contents

- [Test structure](#test-structure)
- [Running tests](#running-tests)
- [pytest markers](#pytest-markers)
- [Coverage](#coverage)
- [Fixtures](#fixtures)
- [Artifacts](#artifacts)
- [Conventions and principles](#conventions-and-principles)
- [Troubleshooting](#troubleshooting)

---

## Test structure
tests/
├── conftest.py # Root fixtures (artifacts_dir, safe_png, safe_jpeg, safe_wav, rng, and so on)
├── TESTING.md # This document
├── artifacts/ # Read-only reference files
│ ├── carriers/ # Test carriers (PNG/JPEG/WAV)
│ └── payloads/ # Test payload files (PDF/ZIP/TXT)
│
├── unit/ # Unit tests (mirror of src/stegambit/)
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
└── test_smoke_pipeline.py # End-to-end pipeline smoke tests



**Mirror principle:** the `tests/unit/` layout repeats `src/stegambit/`. A new module in `src/` gets a matching `test_*.py` file in `tests/unit/`.

---

## Running tests

### All tests
pytest



### Unit only
pytest tests/unit



### Smoke only
pytest tests/integration -m smoke



### A specific module
pytest tests/unit/core/test_lsb_processor.py



### A specific class or test
pytest tests/unit/core/test_lsb_processor.py::TestRoundTrip
pytest tests/unit/core/test_lsb_processor.py::TestRoundTrip::test_round_trip_various_sizes



### Verbose mode
pytest -v



### Stop on the first failure
pytest -x



---

## pytest markers

Markers are registered in `pyproject.toml` (or `pytest.ini`):

| Marker | Purpose | When it applies |
|---|---|---|
| `smoke` | Minimal end-to-end set | Critical scenarios in `tests/integration/` |
| `integration` | Integration tests | Tests that use several modules at once |
| `io` | Tests that use the real filesystem / external libraries (PIL, wave, jpeglib) | Format I/O tests |

### Examples of running by marker

Fast tests only (no I/O):
pytest tests/unit -m "not io"



I/O tests only:
pytest tests/unit -m "io"



Smoke only:
pytest -m smoke



Combinations:
pytest -m "smoke and not io"



---

## Coverage

### Measure coverage
pytest tests/unit --cov=src/stegambit --cov-report=term-missing



### HTML report
pytest tests/unit --cov=src/stegambit --cov-report=html



After the run, open `htmlcov/index.html` in a browser.

### Coverage targets

| Module | Minimum | Ideal |
|---|---|---|
| `models/dto.py` | 100% | 100% |
| `core/common/format_id.py` | 95% | 100% |
| `core/stego/strategies.py` | 90% | 95% |
| `core/stego/spreader.py` | 90% | 95% |
| `core/crypto/engine.py` | 90% | 95% |
| `core/formats/*.py` | 70% | 90% |
| `services/stego_service.py` | 75% | 85% |
| `services/metrics.py` | 90% | 100% |

Coverage below 100% is acceptable for platform-specific branches, external I/O, and dead code.

---

## Fixtures

All shared fixtures live in the root `tests/conftest.py`. Local fixtures (used in a single file) live inside that test module.

### Root fixtures

| Fixture | Purpose | Scope |
|---|---|---|
| `artifacts_dir` | Path to `tests/artifacts/` | session |
| `carriers_dir` | Path to `tests/artifacts/carriers/` | session |
| `payloads_dir` | Path to `tests/artifacts/payloads/` | session |
| `safe_png` | Copy of the PNG carrier in `tmp_path` | function |
| `safe_jpeg` | Copy of the JPEG carrier in `tmp_path` (workaround for the jpeglib bug with Cyrillic paths) | function |
| `safe_wav` | Copy of the WAV carrier in `tmp_path` | function |
| `rng` | Deterministic `np.random.default_rng(seed=42)` | function |

### Safe-copy principle

Files in `tests/artifacts/` are **read-only** — tests must not mutate them. Every `safe_*` fixture copies the file into `tmp_path` through the `_copy_artifact()` helper. This:

1. Protects the reference files from accidental mutation.
2. Works around the `jpeglib` bug with Cyrillic in paths on Windows (see [Troubleshooting](#troubleshooting)).
3. Provides automatic cleanup through pytest.

---

## Artifacts

`tests/artifacts/` holds the **reference** files. Layout:
artifacts/
├── carriers/
│ ├── photo.png
│ ├── photo.jpg
│ └── sound.wav
└── payloads/
├── document.pdf
├── archive.zip
└── tiny.txt



### Adding a new artifact

1. Place the file in the appropriate subdirectory.
2. If needed, add a fixture in `tests/conftest.py` via `_copy_artifact()`.
3. Use it in tests through the fixture, **not** through a direct path.

**Do not** modify artifacts inside tests. Use the `safe_*` copies.

---

## Conventions and principles

### Test design techniques

Each test must name the technique used in the first line of its docstring:

- **Equivalence** — partitioning into equivalence classes.
- **Boundary** — boundary values.
- **Negative** — an expected `raises` check.
- **Property** — an invariant (property).
- **Decision Table** — a decision table.
- **Round-trip** — operation reversibility.
- **State-based** — checking a state change.

### TROUBLESHOOTING 
----
**Warning PytestUnknownMarkWarning**
The marker is not registered in pyproject.toml. Add it to this section:


[tool.pytest.ini_options]
markers = [
    "smoke: critical end-to-end scenarios",
    "integration: tests involving multiple modules",
    "io: tests touching real file system / external libraries",
]
