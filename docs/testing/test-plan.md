# SteGambit System Test Plan

## 1. Introduction
This document describes the strategy, test levels, and acceptance criteria for testing the cross-platform steganography tool SteGambit.

## 2. Test levels. What is taken from the testing pyramid
The testing strategy is based on a three-layer pyramid:

1. **Unit tests (White Box):** Isolated testing of atomic mathematical and cryptographic functions.
2. **Integration tests (White Box):** Testing interaction between the Core and Service layers, and full end-to-end Encode -> Decode runs on real media files.
3. **Smoke/Acceptance tests (Black Box):** Manual user-interface testing based on critical scenarios.

## 3. Test scope
Testing is split into 9 independent domain areas that cover the full system lifecycle:
1. **Cryptography (Core/Crypto):** AES-GCM, KDF, compression.
2. **Format identification:** Magic Bytes checks, RIFF protection.
3. **Spatial domain (LSB):** vectorized operations on ndarray.
4. **Frequency domain (DCT):** JSteg filtering (exclusion of the dead zone `{-2, -1, 0, 1}`).
5. **Spreading (Spreader):** PRNG determinism, LSB invariance with respect to the pool.
6. **Input/output operations (I/O):** preservation of structures (including Huffman tables for JPEG).
7. **Service facade (StegoService):** orchestration, anti-conversion protection.
8. **Quality metrics:** PSNR, SSIM, Deviation %.
9. **Data contracts (DTO):** model immutability.

## 4. Exclusions
*   E2E GUI automation (via `pytest-qt`). Justified by manual testing.
*   Load testing of containers larger than 100 MB.
*   Steganalysis (performed during algorithm design).

## 5. Tooling and metrics
*   **Framework:** `pytest`, `pytest-cov`, `pytest-html`.
*   **Target coverage:** At least 70% for the `core/` and `services/` packages. `gui/` code is excluded from coverage metrics.
*   **Report generation:** `pytest --html=docs/testing/report.html --cov=src`
