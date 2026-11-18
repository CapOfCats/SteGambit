# ADR 001: Core Architectural Patterns and Directory Structure

**Date:** 2026-03-22
**Status:** Approved
**Context:** Development of the multi-format steganography tool SteGambit.

## 1. Problem
The project has hard metrics: PSNR $\ge 40$ dB, size growth $\le 30\%$, and strict performance timings ($\le 1$ sec/2MB) including cryptographic transforms (AES-GCM). There is one month for the MVP.
If PyQt6 progress-bar rendering is mixed with `numpy` matrix computation and cryptography, the project becomes an untestable monolith. Clear cross-layer contracts and strict encapsulation of the mathematics are required.

## 2. Approved Interaction Patterns

To keep layers independent (Defense-in-Depth) within MVC and the Service Layer, the following patterns are fixed:

### 2.1 Facade (Service Layer)
*   **Implementation:** `StegoController` (in `src/services/`).
*   **Rationale:** The GUI layer (PyQt6) must know nothing about `numpy`, byte shifts, AES vector generation, and the rest of the low-level details. The frontend only handles button-click events and passes primitives (paths, password strings) to the facade. The facade orchestrates `AsyncWorker` threads, calls crypto, passes the array into the core, and returns a ready DTO with metrics to the UI.

### 2.2 Strategy (Core Steganography)
*   **Implementation:** A single `IStegoProcessor` interface with concrete implementations (`LsbProcessor`, `DctProcessor`).
*   **Rationale:** No spaghetti of `if/else` blocks. Embedding in the spatial domain (.png) is fundamentally different from work in the frequency domain (.wav). Each algorithm is encapsulated in its own "strategy" with its own mathematical apparatus. The core does not care what is being hidden; it simply calls `embed()` on the supplied strategy.

### 2.3 Factory Method + Magic Bytes Analysis
*   **Implementation:** `ProcessorFactory` together with the `FormatIdentifier` utility.
*   **Rationale:** Trusting the file extension (for example, a user renamed `malware.exe` to `cat.png`) is a security hole. The factory reads the first bytes (magic numbers) of the input file, reliably determines the real format, and only then instantiates the required strategy from section 2.2. Defensive validation at the architecture level.

### 2.4 Cross-Cutting Concerns
*   **Implementation:** Module `infrastructure/logger.py`
*   **Rationale:** Every application layer needs logging to control metrics, timings, and debugging (per the requirements). To avoid cyclic dependencies, the logger lives in an isolated infrastructure module
*   **Security requirements:** A strict filter forbids cryptographic keys, passwords, and the original payload bit sequences from appearing in log output files. Violating this rule is a fatal failure.

## 3. Directory Structure (Component Level)

The `src/` layout is adopted to avoid import problems and to isolate sources from environment configuration.

```text
stegambit_project/
├── .venv/                      # Isolated environment (dev only)
├── data/                       # Test sandboxes (gitignored)
├── tests/                      # QA infrastructure (unit and e2e tests)
├── docs/                       # C4 diagrams, ADRs, and requirements
├── main.py                     # Application entry point (bootstrapping)
└── src/                        # Sources
    ├── __init__.py
    ├── core/                   # [CORE] Mathematics and crypto. Isolated from everything.
    │   ├── stego/              
    │   │   ├── factory.py      # Factory Method implementation
    │   │   ├── strategies.py   # LsbProcessor, DctProcessor
    │   │   └── spreader.py     # PRNG path generator
    │   ├── crypto/             
    │   │   ├── engine.py       # AES-GCM
    │   │   └── key_manager.py  # Key derivation (SHA-512)
    │   └── common/             
    │       └── format_id.py    # Magic-bytes analyzer
    │
    ├── services/               # [FACADE] Coordination
    │   ├── stego_service.py    # The Facade for the GUI
    │   ├── async_worker.py     # Wrappers for background threads
    │   └── analytics/          # Metrics module (PSNR, capacity)
    │
    ├── models/                 # [DATA TRANSFER] DTO contracts
    │   └── dto.py              # Only @dataclass and Enum
    │
    ├── gui/                    # [FRONTEND] PyQt6
    │   ├── main_window.py      
    │   └── widgets/
    │
    └── infrastructure/         # Block for cross-cutting functionality
        ├── __init__.py
        ├── config.py           # Settings loading
        └── logger.py           # Logger
