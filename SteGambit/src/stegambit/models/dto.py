"""SteGambit DTO layer.

All DTOs are immutable (frozen=True) and validate inputs
via __post_init__. Architectural rationale: see ADR 009.
"""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any


class QualityStatus(str, Enum):
    """Operation quality trigger. Used by the UI for color indication of the result:
        OK       (PSNR >= 40 dB, deviation <= 30%).
        WARNING  (30 <= PSNR < 40, potentially detectable).
        ANOMALY  (PSNR < 30 or deviation > 30%).
    """
    OK = "OK"
    WARNING = "WARNING"
    ANOMALY = "ANOMALY"


@dataclass(frozen=True)
class StegoTaskRequest:
    """Request to hide or extract data.

    Fields are validated in __post_init__:
        * carrier_path - must exist and be a file.
        * payload_path - must exist and be a file.
        * output_path  - the parent directory must exist.
        * password     - an empty string is allowed.
        * compute_visual_metrics - flag for optional SSIM computation
          (heavy metric, ~1.5s on a 2MB PNG). Off by default.

    Paths are normalized via Path(...).resolve().

    Raises:
        FileNotFoundError: If output_path.parent is missing.
        ValueError:        If carrier/payload are not files.
        TypeError:         If password is not a string.
    """
    carrier_path: Path
    payload_path: Path
    output_path: Path
    password: str
    compute_visual_metrics: bool = False
    

    def __post_init__(self):
        carrier = Path(self.carrier_path).resolve()
        if not carrier.exists():
            raise FileNotFoundError(f"Carrier not found: {carrier}")
        if not carrier.is_file():
            raise ValueError(f"Carrier is not a file: {carrier}")
        object.__setattr__(self, "carrier_path", carrier)

        payload = Path(self.payload_path).resolve()
        if not payload.exists():
            raise FileNotFoundError(f"Payload not found: {payload}")
        if not payload.is_file():
            raise ValueError(f"Payload is not a file: {payload}")
        object.__setattr__(self, "payload_path", payload)

        output = Path(self.output_path).resolve()
        if not output.parent.exists():
            raise FileNotFoundError(
                f"Output directory does not exist: {output.parent}"
            )
        object.__setattr__(self, "output_path", output)

        if not isinstance(self.password, str):
            raise TypeError(
                f"Password must be str, got {type(self.password).__name__}"
            )


@dataclass(frozen=True)
class StegoResponse:
    """Operation result."""
    success: bool
    output_path: Optional[Path] = None
    metrics: Optional[Dict[str, Any]] = None  # PSNR, time, etc.
    error: Optional[str] = None


@dataclass(frozen=True)
class CapacityReport:
    """Container capacity report for preliminary validation.

    Returned by StegoService.analyze_capacity() before the actual hiding operation.
    """
    fits: bool
    format: str
    algorithm: str
    capacity_bits: int
    required_bits: int
    payload_size_bytes: int
    header_size_bytes: int
    utilization_percent: float