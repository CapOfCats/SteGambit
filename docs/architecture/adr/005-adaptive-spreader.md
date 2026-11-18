# ADR 005: Adaptive Spreader (Content-Dependent Steganography)

**Date:** 2026-03-24
**Status:** Approved
**Related:** Supplements and modifies ADR 003.

## 1. Context and Problem
To improve stealth (lower visual detection and reduce banding artifacts), blind bit spreading is rejected. The system must avoid "smooth" regions of the carrier and embed data only in high-frequency areas (edge detection).

## 2. Architectural Decision (Smart Spreader)
LSB coordinate generation now has two stages:
1. **Masking:** Compute the image gradient (Sobel filter or pixel differences via `numpy`). Build a pool of available (safe) coordinates.
2. **Scattering (Spreading):** Pseudo-random selection of $N$ coordinates from the pool using a cryptographically secure PRNG (or password-based ChaCha20/AES-CTR), where $N$ is the payload length in bits.

## 3. Capacity Estimate Modification (Change to ADR 003)
The theoretical carrier capacity is no longer the constant $\lfloor \frac{W \times H}{8} \rfloor$.
**New formula:**
$$Capacity = \lfloor \frac{E_{safe}}{8} \rfloor - O_{crypto}$$
Where $E_{safe}$ is the number of carrier elements that pass the edge-detection threshold.
In `CapacityAnalyzer`, `analyze_capacity` MUST first call `spreader.get_capacity(container_matrix)`.

## 4. `ISpreader` Contract (Updated)
```python
class ISpreader(ABC):
    @abstractmethod
    def get_max_capacity_bits(self, container: np.ndarray) -> int:
        """Estimates the maximum number of bits that can be embedded safely"""
        pass

    @abstractmethod
    def generate_coords(self, container: np.ndarray, payload_bits_len: int, password_seed: str, exclude_coords: Optional[set] = None) -> np.ndarray:
        """
        Generates an array of N coordinates (payload_bits_len).
        exclude_coords is a placeholder for the "plausible deniability" feature
        """
        pass
