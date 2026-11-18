SteGambit follows **Clean Architecture**, with a clear boundary between layers:

```text
┌─────────────────────────────────────────────────────────┐
│                    GUI Layer (PyQt6)                    │
│  MainWindow → EncodePanel / DecodePanel / SettingsDlg   │
└─────────────────────────────────────────────────────────┘
                             │
                             │ StegoTaskRequest (DTO)
                             ▼
┌─────────────────────────────────────────────────────────┐
│                  Async Layer (QThread)                  │
│  StegoWorker — isolates heavy work from the UI thread   │
└─────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│                 Service Layer (Facade)                  │
│ StegoService — orchestration: validate → crypto →       │
│ spread → embed → save → metrics                         │
└─────────────────────────────────────────────────────────┘
                             │
       ┌─────────────────────┼─────────────────────┐
       ▼                     ▼                     ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ CryptoEngine │     │   Spreader   │     │  Processor   │
│ (AES-GCM-256)│     │ (Smart/DCT)  │     │  (LSB/DCT)   │
└──────────────┘     └──────────────┘     └──────────────┘
       │                     │                     │
       └─────────────────────┼─────────────────────┘
                             ▼
                     ┌──────────────┐
                     │  Format I/O  │
                     │ PNG/WAV/JPEG │
                     └──────────────┘
```

The GUI **knows nothing** about `numpy`, `AES`, or `DCT coefficients`. The service layer **knows nothing** about `QtWidgets`. They communicate through DTOs (`StegoTaskRequest` / `StegoResponse`).

### Cryptographic frame

Before embedding, the payload is wrapped in a `CryptoFrame` — a self-describing binary block:

```text
┌────────┬───────┬──────────┬───────────┬─────────┬──────────────────────┐
│ MAGIC  │ FLAGS │   SALT   │   NONCE   │  LENGTH │      CIPHERTEXT      │
│ 4 byte │ 1 byte│ 16 bytes │  12 bytes │ 8 bytes │      + GCM-TAG       │
└────────┴───────┴──────────┴───────────┴─────────┴──────────────────────┘
  "STGB"   v1.0     random      random    big-end       AES-GCM-256
```

- **MAGIC** — the `STGB` signature. Checked first on extraction: if it does not match, either the password is wrong or the file contains no payload.
- **SALT** — 128 random bits (16 bytes). Fed into PBKDF2 together with the password, so the same password on two different stego files yields **different** AES keys.
- **NONCE** — the IV for AES-GCM (12 bytes, as required by NIST SP 800-38D).
- **LENGTH** — ciphertext length in bytes. Extraction reads exactly that many bits, and no more.
- **CIPHERTEXT + GCM-TAG** — the encrypted payload plus a 16-byte authentication tag. Changing even one bit of the ciphertext raises `InvalidTag` on decrypt — that is the tamper detector.

### LSB Spreading (PNG/WAV)

Naive LSB writes bits into the first N pixels in a row, and a statistical χ²-test detects that in milliseconds. **SmartSpreader** does three things:

1. **Edge detection** — the Sobel operator on the grayscale projection; smooth regions are discarded (that is where LSB noise is visible to the eye).
2. **Pool pruning** — candidates are filtered down to pixels with a high gradient.
3. **Password-seeded shuffle** — the pool is shuffled with a permutation seeded from `SHA-256(password)`. Without the password the coordinates cannot be recovered.

The payload ends up scattered across the "noisy" zones of the carrier, in an order that is deterministic but cryptographically unpredictable.

### DCT Spreading (JPEG)

For JPEG, spatial pixels are useless: recompression would destroy the changes. **DctProcessor** works on the **quantized DCT coefficients** directly (no re-encode):

1. `jpegio` extracts `coef_arrays[0]`, the Y channel of the 8×8 blocks.
2. Each block contributes **mid-frequency AC** coefficients (zigzag 1..27). DC is left untouched (changing it causes "checkerboard" artifacts). High frequencies are almost always zero, and modifying them would break Huffman compression.
3. The values `{-2, -1, 0, 1}` are excluded from the pool. An LSB change there either flips the sign (which breaks the decoder) or zeroes the coefficient (which breaks the pool on extraction).
4. The permutation is the same `password-seeded shuffle`.

The result is a JSteg-like pipeline with an extended filter, robust to re-save in most viewers.

### Performance

- **NumPy vectorization:** every bitwise operation (`unpackbits` / `packbits` / masks `& ~1 | bit`) runs on whole arrays, with no Python loops.
- **Async UI:** heavy work goes to `StegoWorker(QThread)`, so the GUI stays responsive even on a 68 MB WAV.
- **Optional SSIM:** the psychovisual metric can be turned off in settings (saves ~1.5 s on a 2 MB PNG).

Detailed UML/C4 diagrams and Architectural Decision Records (ADR) are in the `docs/` folder.
