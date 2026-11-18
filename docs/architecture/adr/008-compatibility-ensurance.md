# ADR 008: Threading Model and Graphical Interface Isolation

**Date:** 2026-05-07
**Status:** Approved
**Context:** Building a responsive user interface on `PyQt6` under resource-heavy mathematical and cryptographic computation.

## 1. Problem
Steganography algorithms (especially DCT) and the aggressive PBKDF2 key-generation parameters of 480 000 iterations from ADR 006 create a significant computational load. A synchronous call to `StegoService` from the application's main thread causes the operating system to block interface painting. The application freezes into a "Not Responding" state: the operation cannot be cancelled, there is no user feedback, and the interface locks up.

## 2. Architectural Decision

To keep the interface continuously responsive, the **Background Worker Thread** pattern is adopted.

1.  **Reject `asyncio` and the standard `threading` module:** The application is built on the event-driven patterns of `PyQt6`. Using the standard Python `threading.Thread` or `asyncio` can cause data races when interacting with Qt C++ objects.
2.  **Approved basis:** `PyQt6.QtCore.QThread` is the exclusive base class for background computation.
3.  **Implementation:** The `async_worker.py` layer contains the classes `StegoEncoderWorker` and `StegoDecoderWorker`.

## 3. Cross-Thread Communication Contract

The most critical failure point in a multithreaded GUI is a background thread changing widget state directly (for example, `self.label.setText()`). That is strictly forbidden.

A rigid communication contract is introduced:
*   **Isolation:** The worker thread holds no references to the main window (`MainWindow`) or any UI elements.
*   **Signals & Slots:** Threads communicate exclusively through the event-generation mechanism.
*   **Immutability:** Data crosses threads only through frozen DTOs from the ADR 002 contract (for example, passing `StegoResponse` through a signal). Memory consistency is guaranteed by immutability (`@dataclass(frozen=True)`).

## 4. Thread Lifecycle (Encode Example)
1.  **Preparation (Main Thread):** The user clicks "HIDE DATA". The main thread collects data from the UI and builds a frozen `StegoTaskRequest` DTO.
2.  **Initialization (Main Thread):** A `StegoEncoderWorker(request)` instance is created. The main thread subscribes to the worker signals (`.finished`, `.error`, `.progress`).
3.  **Computation (Background Thread):** The worker calls the business logic `StegoService.hide_data()`. The load falls on a separate CPU core. The GUI stays fully responsive.
4.  **Completion (Cross-Boundary):** On completion, the background thread emits `finished.emit(response)`.
5.  **Rendering (Main Thread):** Qt's main event loop receives the signal and safely renders the updated metrics from the incoming `response`.

## 5. Conclusion
This threading model guarantees the absence of data races, prevents the application window from freezing, and keeps the business-logic layer (`core` and `services`) fully independent of the GUI framework in use (Defense-in-Depth).
