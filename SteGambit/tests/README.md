```markdown
Testing (SteGambit)

Unit tests for the SteGambit project. Framework: `pytest`.

🗂 Structure

tests/
├── __init__.py
├── README.md               # This file
├── test_crypto.py          # Tests for core/crypto (CryptoEngine, KeyManager)
└── ...                     # New test_*.py files as coverage grows
```

**Organization rule:** One module from `core/` equals one file `test_<module>.py`. Inside the file, tests are grouped into classes `Test<Component>`.

---

## 🚀 Running tests

Before you start, make sure the project's dev dependencies are installed in editable mode:

```bash
python -m pip install -e ".[dev]"
```

### Run options

*   **All project tests:**
    ```bash
    python -m pytest
    ```
*   **A specific module (file):**
    ```bash
    python -m pytest tests/test_crypto.py
    ```
*   **A specific test class:**
    ```bash
    python -m pytest tests/test_crypto.py::TestCompression
    ```
*   **A single test:**
    ```bash
    python -m pytest tests/test_crypto.py::TestCompression::test_compressed_roundtrip
    ```

---

## 🛠 Useful Pytest flags

Use the following flags when debugging:

| Flag | Purpose |
| :--- | :--- |
| `-v` | Verbose output (each test on its own line). |
| `-x` | Stop at the first failure (fast fail). |
| `--tb=short` | Short traceback when tests fail. |
| `--tb=line` | One-line traceback (minimal visual noise). |
| `-k "query"` | Run tests whose names contain `"query"`. |
| `--lf` | Run only the tests that failed on the previous run (last failed). |

**Example debug command:**
```bash
python -m pytest tests/test_crypto.py -v -x --tb=short
```

---

## How to add a new unit test

1.  Create a file `tests/test_<module>.py`.
2.  Import the units under test:
    ```python
    from stegambit.core.<module> import ...
    ```
3.  **Group** tests into `TestXxx` classes (optional, but strongly recommended by the architect for cleaner logs).
4.  **Naming convention:** methods must start with `test_<what_is_checked>`.
5.  **Exceptions:** use `pytest.raises(ExceptionType)` to check expected errors.
6.  **Parametrization:** when testing several input variants, use the decorator. **Always** set `ids=[...]` (otherwise Pytest tries to paste the raw data into the console):
    ```python
    @pytest.mark.parametrize("payload", [b"A" * 1024], ids=["1kb_data"])
    ```

---

## Common problems (Troubleshooting)

### 1. `ModuleNotFoundError: No module named 'stegambit'`
The dev dependencies are not installed, or the `stegambit` package is not initialized locally.
**Fix:**
```bash
python -m pip install -e ".[dev]" --force-reinstall --no-deps
```

### 2. `ValueError: environment variable is longer than 32767 characters` (Windows)
This happens when `@pytest.mark.parametrize` is given a large payload without the `ids` parameter. Pytest tries to put the entire large byte string into the test name.
**Fix:** Add human-readable identifiers.
```python
# BAD:
@pytest.mark.parametrize("payload", [b"A" * 1_000_000])

# GOOD:
@pytest.mark.parametrize("payload", [b"A" * 1_000_000], ids=["1mb_payload"])
```

### 3. Pytest runs the wrong Python
This happens when several Python versions are installed, or virtual environments (`venv`) conflict. Check where your interpreter sits relative to pytest. A common failure is that one cannot see the other, which causes a conflict.
**Fix:** Always invoke tests through the interpreter module `python -m pytest`, not through the `pytest` binary directly. That uses the intended environment.
