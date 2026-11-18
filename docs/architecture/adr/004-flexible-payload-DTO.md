# ADR 004: Smart Binary Protocol (Flexible Payload DTO)

**Date:** 2026-03-24
**Status:** Approved (Revision 2)
**Context:** Defining the payload structure before embedding into the carrier. The protocol must support optional compression and a "plausible deniability" architecture.

## 1. Problem
The carrier must be able to answer reliably:
- Is the password correct? (protection against reading noise)
- Were the data compressed beforehand?
- Is this secret a decoy or the primary secret?

## 2. Adaptive Data-Preparation Pipeline
Before `embed()` is called, data goes through the following pipeline:
1. **Entropy analysis (optional):** If the file compresses well (text/JSON), `zlib` (level=9) is applied. Otherwise compression is skipped.
2. **Encryption:** The payload is encrypted with `AES-256-GCM`.
3. **Packing (header):** Assemble a 41-byte header.

## 3. DTO Structure (Header = 41 bytes)
Any embedded data must be wrapped in this frame:

| Block | Size | Description |
| :--- | :--- | :--- |
| `MAGIC` | 4 bytes | SteGambit signature (for example, `b'SGB1'`). |
| `FLAGS` | 1 byte | Configuration bit mask. |
| `NONCE` | 12 bytes | Initialization vector (IV) for AES-GCM. |
| `LENGTH`| 8 bytes | True payload size (int64). |
| `MAC`   | 16 bytes | Authentication tag (AES-GCM auth tag). |
| `DATA`  | N bytes | Ciphertext. |

**FLAGS byte layout (bit masks):**
- `0x01` (bit 0): **COMPRESSED** -> Zlib compression was applied (decompression is required on extraction).
- `0x02` (bit 1): **IS_DECOY** -> (placeholder for the plausible-deniability feature) The flag marks this as a decoy payload.
- `0x04`...`0x80`: Reserved for future versions (for example, an EOF-mode flag).

## 4. Extract Contract (Extraction Process)
1. Compute the Spreader seed -> obtain coordinates.
2. Read exactly **41 bytes** at those coordinates.
3. Check `MAGIC`. No match means a wrong password or an empty carrier.
4. Check the `COMPRESSED` bit in `FLAGS`.
5. Read `LENGTH` bytes of ciphertext.
6. Call decryption (a wrong password or a damaged MAC tag raises an error).
7. If `COMPRESSED == 1`, run `zlib.decompress()`.
