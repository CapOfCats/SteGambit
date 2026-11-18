```markdown
System coverage checklist

## Domain 1: Cryptography (Core/Crypto)
- [ ] Encrypt/decrypt round-trip succeeds for different data sizes.
- [ ] An incorrect password raises `InvalidFrameError`.
- [ ] Flipping 1 bit in the ciphertext or header causes an authentication error.
- [ ] zlib compression turns on automatically for low-entropy data.

## Domain 2: Format identification (FormatIdentifier)
- [ ] PNG/JPEG/WAV detection by Magic Bytes is correct.
- [ ] A RIFF header without the WAVE subtype raises an error (protection against AVI/WebP).
- [ ] `identify_bytes()` correctly reads an extracted binary blob (extension recovery).
- [ ] Short files (<12 bytes) are handled without a crash (graceful failure).

## Domain 3: LSB Spatial Domain (LsbProcessor)
- [ ] Vectorized round-trip works on 1D (audio) and 3D (RGB) `ndarray` values.
- [ ] Only the least significant bits are modified (the original histogram is preserved).
- [ ] An exception is raised when the operation goes past the physical array bounds.

## Domain 4: DCT Frequency Domain (DctProcessor)
- [ ] Round-trip works on `JpegContainer` objects without re-quantization.
- [ ] The forbidden zone `{-2, -1, 0, 1}` is strictly excluded from the pool (fix for classic shrinkage).
- [ ] Sanity check: the pipeline stops if the Y channel did not change (`Zero-Embed`).

## Domain 5: Smart spreading (SmartSpreader)
- [ ] Coordinates are fully deterministic from a `seed` derived from the password.
- [ ] LSB invariance (the bit is cleared with `& ~1` before the pool is computed, to avoid a shift).
- [ ] The `exclude_coords` parameter correctly filters out occupied pixels.

## Domain 6: Input/output operations (Format I/O)
- [ ] `PngFormat` and `WavFormat` store tensors with a lossless algorithm.
- [ ] `JpegFormat` extracts Huffman tables and stores them unchanged.

## Domain 7: Service facade (StegoService)
- [ ] End-to-end `hide_data` → `extract_data` succeeds for all 3 formats.
- [ ] The anti-conversion error is caught (an attempt to save PNG as JPEG).
- [ ] The original payload extension is recovered (for example, PNG-in-JPEG → `extracted.png`).

## Domain 8: Metrics
- [ ] PSNR math matches the formula (10 * log10(MAX^2 / MSE)).
- [ ] SSIM is computed correctly through `scikit-image`.
- [ ] `analyze_capacity` returns an honest CapacityReport that accounts for crypto overhead.

## Domain 9: DTO and models
- [ ] Frozen dataclasses are immutable.
- [ ] Quality-status enum values match (`OK`, `WARNING`, `ANOMALY`).
```
