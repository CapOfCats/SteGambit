# ADR 002: Cross-Layer Contracts and Base Interfaces

**Date:** 2026-03-23

**Status:** Approved

**Context:** Development of the multi-format steganography tool SteGambit.

## 1. Problem
Without strict contracts, the `gui` and `core` layers will merge: the graphical interface will start passing raw dictionaries or strings, and the core will raise uncontrolled exceptions. The file-in-file protection concept needs rigid data-transfer structures (DTOs) and abstract classes (ABC) for the Strategy and Facade patterns.

## 2. DTO (Data Transfer Objects)
The `models/dto.py` layer contains only immutable data structures (in Python, `@dataclass(frozen=True)`). That guarantees no intermediate process accidentally changes file paths or the password.

*   `StegoTaskRequest`: Request from the GUI to the service for embedding.
*   `ExtractTaskRequest`: Request for extraction.
*   `StegoResponse`: Universal service response for the GUI, containing metrics (PSNR, time) and status.

## 3. UML Class Diagram (Abstract Interfaces)

The figure Core_UML_Interfaces.png, located in docs/architecture, shows the abstract-class (ABC) structure of the `core` and `services` layers, which forms the contract for the backend developer.

## 4. Sequence Diagram (File-in-File Embedding Lifecycle)
The full Data -> Encrypt -> Encode -> Save pipeline in the Defense-in-Depth paradigm is shown in the figure File-in-File Lifecycle.png located in docs/architecture.
