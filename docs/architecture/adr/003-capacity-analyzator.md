# ADR 003: Carrier Capacity Model (Capacity Analysis) and LSB Degradation Control

**Date:** 2026-03-24
**Status:** Approved
**Context:** Implementation of `analyze_capacity()` in `services/analytics/` and a mathematical bound on media-file degradation.

## 1. Problem
Before encryption and embedding, the system must answer: "Will file B (payload) fit inside file A (carrier) while keeping PSNR ≥ 40 dB?". A hard mathematical rule is required so that `CapacityAnalyzer` can disable GUI sliders (the dry-run mechanism).

## 2. Architectural and Mathematical Justification of Capacity (LSB)

With the spatial LSB (Least Significant Bit) method, the least significant bits of each carrier byte are modified.

For an RGB carrier image converted to `numpy.ndarray`:
- Array shape: `[Width, Height, Channels]`.
- Total available bytes (pixels * channels): $N_{bytes} = W \times H \times C$.

**Theoretical capacity ($E_{max}$):**
If 1 bit is used per color channel (1 LSB), exactly 1 payload bit can be hidden in one carrier byte.
Pure capacity in bytes:
$$E_{max} = \lfloor \frac{N_{bytes}}{8} \rfloor$$

**Overhead:**
The Defense-in-Depth architecture requires `AES-GCM`.
- `Nonce` (initialization vector): 12 bytes.
- `MAC Tag` (authentication tag): 16 bytes.
- Header with the original payload size (so `extract` knows when to stop): 8 bytes (unsigned long long).
*Total constant overhead:* $O_{crypto} = 36$ bytes.

**Final available-capacity formula ($Capacity$):**
$$Capacity = E_{max} - O_{crypto}$$

*Any payload whose size exceeds $Capacity$ must be rejected at validation (business process: BP-1).*

## 3. Degradation and Noise-Level Justification (PSNR)

Per the requirements, **PSNR ≥ 40 dB** must be maintained.

*Mathematical note:*
$$PSNR = 10 \cdot \log_{10}\left(\frac{MAX_I^2}{MSE}\right)$$
Where $MAX_I = 255$, and $MSE$ is the mean squared error.

- **Scenario 1 (using 1 least significant bit):** With a pseudo-random replacement of 1 least significant bit (LSB1), the expected error per modified pixel is $MSE = 0.5$.
  At $MSE = 0.5$:
  $$PSNR = 10 \cdot \log_{10}\left(\frac{65025}{0.5}\right) \approx 51.13 \text{ dB}$$
  *Conclusion:* 1-bit LSB is fully safe. Even at 100% carrier fill, PSNR is ~51 dB, which comfortably exceeds the ≥40 dB requirement.

- **Scenario 2 (using 2 least significant bits — LSB2):** If the user wants more capacity (degradation override), the expected $MSE$ rises to $2.5$.
  At $MSE = 2.5$:
  $$PSNR = 10 \cdot \log_{10}\left(\frac{65025}{2.5}\right) \approx 44.15 \text{ dB}$$
  *Conclusion:* 2-bit LSB is still within the requirements (≥ 40 dB), but visual artifacts on gradients (especially in dark regions) can become noticeable.

**Architectural decision:**
By default, `analyze_capacity()` must use the **1-bit LSB (Strict Mode)** profile. If the payload does not fit, the service returns `False`. LSB2 is left as a feature for version 2.0 (or an optional "High Capacity Mode" checkbox in settings, if time allows).

## 4. Contract for the Backend Developer

In `services/analytics/capacity.py` (or the corresponding class), a function of the following form must be implemented:

```python
def analyze_capacity(container_matrix: np.ndarray, payload_size_bytes: int, lsb_depth: int = 1) -> bool:
    """
    Checks whether payload_size_bytes can be embedded into container_matrix.
    :param container_matrix: numpy array of the carrier.
    :param payload_size_bytes: size of the file to hide, in bytes.
    :param lsb_depth: number of least significant bits used (default 1).
    :return: True if embedding is possible without violating PSNR > 40dB, otherwise False.
    """
    overhead = 36 # AES Nonce (12) + MAC (16) + SizeHeader (8)
    
    # 1. Count available bits inside the matrix
    total_container_bits = container_matrix.size * lsb_depth
    
    # 2. Convert to bytes
    max_capacity_bytes = total_container_bits // 8
    
    # 3. Subtract crypto overhead
    available_bytes = max_capacity_bytes - overhead
    
    return payload_size_bytes <= available_bytes
