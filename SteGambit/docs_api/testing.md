# Testing

SteGambit is covered by a multi-level test pyramid:

## Running all tests

```bash
pytest tests/
```

### Unit tests
Isolated tests of individual components: `CryptoEngine`, `SmartSpreader`, `DctProcessor`, `StegoService`, `FormatIdentifier`.

```bash
pytest tests/unit/ -v
```

### Integration tests
Tests with real I/O and the full component chain, checking that the layers work together.

```bash
pytest tests/integration/ -m integration -v
```

### E2E Smoke
The full pipeline *encode → save to disk → extract* on every supported carrier format. A quick check that the system as a whole works.

```bash
pytest tests/e2e/ -v
```

### E2E Load (load tests)
Heavy scenarios on large media files (memory use and performance). Skipped by default so they do not slow down CI/CD.

```bash
pytest tests/e2e/test_e2e_load.py -m load -v -s
```
