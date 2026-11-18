### Legend

- **A** — Architect
- **BE** — Back-end developer
- **FE** — Front-end developer
- **QA** — QA Engineer
- **—** — No active tasks (waiting on dependencies)

# Project plan

## Day 1: Project initialization and architectural design

| Role | Tasks |
|------|--------|
| **A** | Define the project structure; create `README.md` and `requirements.txt`; approve the architecture: MVC plus a service layer for steganography; choose design patterns (Strategy for algorithms, Factory for formats) |
| **BE** | Set up a virtual environment (`venv`) and initialize the repository; create the base directory layout: `src/core`, `src/gui`, `src/utils`, `tests` |
| **FE** | — |
| **QA** | — |

---

## Day 2: Steganography-module API design and UI mockups

| Role | Tasks |
|------|--------|
| **A** | Design the `SteganographyEngine` and `EncryptionService` interfaces; define the contracts for `encode()`, `decode()`, and `analyze_capacity()`; document the architectural decisions in `ARCHITECTURE.md` |
| **BE** | Create abstract classes in `src/core/base.py`: `StegoAlgorithm`, `FileFormat`; implement the structure that supports PNG, JPEG, and WAV |
| **FE** | Create UI mockups in Figma or a prototype: main window, encode dialog, decode dialog, settings window; define a wireframe for the metrics display |
| **QA** | — |

---

## Day 3: LSB algorithm for images

| Role | Tasks |
|------|--------|
| **A** | Review the architectural decisions; help choose the bit depth for LSB |
| **BE** | Implement the `LSBStego` class in `src/core/algorithms/lsb.py`: methods `encode(image, data, key)` and `decode(stego_image, key)`; integrate `Pillow` for pixel access; convert the data into a bit stream |
| **FE** | — |
| **QA** | — |

---

## Day 4: Encryption (AES-256) and integration

| Role | Tasks |
|------|--------|
| **A** | Advise on the encryption mode (CBC vs GCM); review the security of the implementation |
| **BE** | Implement `EncryptionService` in `src/core/crypto.py`: AES-256 encryption and decryption with `cryptography`; implement `HashService` for SHA-512; integrate encryption into the LSB pipeline: `data → encrypt → encode` |
| **FE** | Start the PyQt6 project; create the main window (`MainWindow`) with a basic menu structure |
| **QA** | — |

---

## Day 5: JPEG and audio (WAV) support

| Role | Tasks |
|------|--------|
| **A** | Check that the implementation is correct for each format; discuss the method for WAV (DCT steganography) |
| **BE** | Implement `WavStego` with the DCT method in `src/core/algorithms/dct.py`; implement `WavStego` (DCT on audio samples) in `src/core/algorithms/audio_dct.py`; do the same for LSB in JPEG, and add BMP as a fallback format; create `FormatFactory` so the algorithm is chosen from the file extension |
| **FE** | Continue the GUI: file-picker widgets, key fields, and mode switches (encode/decode) |
| **QA** | — |

---

## Day 6: Quality metrics and optimization

| Role | Tasks |
|------|--------|
| **A** | Check compliance with the EPP metrics (PSNR ≥ 40 dB); approve the evaluation methods |
| **BE** | Implement `QualityMetrics` in `src/utils/metrics.py`: PSNR and SSIM; add profiling with `cProfile`; optimize LSB embedding to ≤ 1 sec/2 MB; implement the capacity check (`analyze_capacity()`) |
| **FE** | Build a metrics widget: PSNR, file size, processing time; add a before/after view (pixel comparison) |
| **QA** | Start the test plan (`tests/plan.md`): define test cases for each format and method |

---

## Day 7: Frontend — main interface and backend integration

| Role | Tasks |
|------|--------|
| **A** | Check that the GUI and the core modules are architecturally compatible |
| **BE** | Create the API layer `src/api/service.py` between the GUI and the core; add asynchronous methods for heavy operations; add logging with `loguru` |
| **FE** | Implement the full main-window UI: mode panel, file loading, preview; add a progress bar; lay out the dialogs (about, settings) |
| **QA** | Write unit tests for the core modules (`tests/test_lsb.py`, `tests/test_crypto.py`); prepare test data (images, audio) |

---

## Day 8: Frontend — before/after features and visualization

| Role | Tasks |
|------|--------|
| **A** | — |
| **BE** | Add methods that read file metadata (size, format, resolution); implement export of operation logs |
| **FE** | Implement the before/after comparison widget: two images side by side, a slider for the overlay; add zoom; show histograms (distortion analysis); export results (screenshots, reports) |
| **QA** | Continue the tests; add coverage for JPEG and WAV steganography |

---

## Day 9: Integration, error handling, UI polish

| Role | Tasks |
|------|--------|
| **A** | Final architecture review; confirm that every EPP requirement is met |
| **BE** | Implement full error handling: wrong key, capacity exceeded, corrupted file; validate input with `pydantic`; document the API in docstrings |
| **FE** | Add clear error messages (QMessageBox); implement dark and light themes; add loading animations; run usability testing |
| **QA** | Start integration testing: the full encode → decode cycle for every format |

---

## Day 10: QA — comprehensive testing

| Role | Tasks |
|------|--------|
| **A** | — |
| **BE** | Fix the bugs found by QA; optimize performance from the test results |
| **FE** | Fix UI bugs; improve interface responsiveness |
| **QA** | Full functional testing: every format, every mode (encode/decode); load testing (files of 1–100 MB); check PSNR and processing time; test boundary conditions (maximum capacity, wrong key); write the final test report |

---

## Day 11: Build, documentation, presentation prep

| Role | Tasks |
|------|--------|
| **A** | Review the final architecture; prepare a presentation of the architectural decisions |
| **BE** | Package the application as an .exe with PyInstaller; write `USER_GUIDE.md`; document every method in `docs/` |
| **FE** | Create the application icon; capture the final UI screenshot for the documentation |
| **QA** | Final regression testing; verify that the .exe runs; list the known limitations |

---

## Day 12: Finalization and project delivery

| Role | Tasks |
|------|--------|
| **A** | Diagrams, the defense, and a presentation of the architectural vision. |
| **BE** | DEMO of the backend capabilities (algorithms, encryption); fix the last minor remarks |
| **FE** | Demo the GUI; confirm the application is stable on the target machine |
| **QA** | Prepare the test report for the course paper; do a final check of every EPP requirement |
