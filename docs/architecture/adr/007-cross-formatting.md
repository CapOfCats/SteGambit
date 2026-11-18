# ADR 007: Format Routing Policy and "Anti-Conversion"

**Date:** 2026-05-06
**Status:** Approved
**Context:** Guarantee survival of hidden data by binding embedding algorithms tightly to the physical properties of carrier files, and by forbidding lossy conversion.

## 1. Problem (Anti-Conversion Constraint)
Different media formats store data differently. Embedding the least significant bit (LSB) into a lossy format (JPEG) destroys the payload when the file is saved. Conversely, applying DCT (a frequency transform) to mathematically exact formats (WAV) is redundant and causes unjustified distortion.
**Anti-conversion rule:** The format of the output file must match the format of the source file exactly.

## 2. Architectural Compatibility Matrix (Routing Matrix)
The system uses strict routing: the carrier format uniquely dictates the allowed processor (algorithm).

| Carrier format | Signature (Magic Bytes) | Characteristic | Assigned algorithm | Embedding domain |
| :--- | :--- | :--- | :--- | :--- |
| **PNG** | `89 50 4E 47` | Lossless Image | **LSB** (`LsbProcessor`) | Spatial |
| **WAV** | `52 49 46 46` | Lossless Audio | **LSB** (`LsbProcessor`) | Temporal-spatial |
| **JPEG** | `FF D8 FF E0` | Lossy Image | **DCT** (`DctProcessor`) | Frequency |

## 3. Architectural Contract (Validation Layer)
The validation layer (the facade, or `StrategoService`) must, when handling `StegoTaskRequest`:
1. Read the carrier file header and determine the real format (ignoring the extension in the file name).
2. Select the matching Processor from the Compatibility Matrix.
3. Reject the request by raising `CompatibilityError` if:
   * An illegal combination is requested (for example, the user forces `LSB` for `JPEG`).
   * The `output_path` extension differs from the source carrier format (a conversion attempt).
