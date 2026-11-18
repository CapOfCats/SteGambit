from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, Optional, Set, Tuple, TypeVar
import numpy as np

T = TypeVar("T")

class IStegoProcessor(ABC, Generic[T]):
    """Contract for a steganographic embedding/extraction strategy.

    Parameterized by container type T:
        - LsbProcessor:  T = np.ndarray (PNG pixels / WAV samples).
        - DctProcessor:  T = JpegContainer (quantized DCT coefficients + metadata).

    The coords contract is unchanged for every implementation: a one-dimensional int64
    array of flat indices of the positions to embed into / extract bits from.
    """

    @abstractmethod
    def embed(self, container: T, payload: bytes, coords: np.ndarray, *, lsb_depth: int = 1) -> T:
        """Embed the payload into the container at the given coordinates.

        Args:
            container: Carrier container.
                       For LSB: ndarray (H, W, 3) uint8 for images or
                                (N,) int16 for WAV.
                       For DCT: JpegContainer with quantized coefficients.
            payload:   Ready binary blob (ciphertext from CryptoEngine).
            coords:    int64 array of flat indices.
                       For LSB — indices into container.flat.
                       For DCT — indices into JpegContainer.coef_arrays[0].ravel(),
                                 filtered via get_embeddable_positions().
            lsb_depth: How many least significant bits to use per element (1..4).
                       The MVP supports only lsb_depth=1.

        Returns:
            Modified container of the same type. For DCT it may be the same
            object (in-place modification saves memory on large JPEGs).
        """
        ...

    @abstractmethod
    def extract(self, container: T, coords: np.ndarray, length: int, *, lsb_depth: int = 1) -> bytes:
        """Extract length bytes of payload from the container at the given coordinates.

        Args:
            length: Payload length in bytes (needed in order to stop after the required number of bits).
        """
        ...


class ISpreader(ABC):
    """Contract for a generator of payload embedding coordinates in a container.

    The implementation defines the position-selection strategy — uniform, content-aware
    (via edge detection), frequency-limited (for DCT), and so on. The contract
    is the same for every variant: input is the container + payload length + password,
    output is an array of coordinates.

    Note:
        Every implementation must be deterministic: the same password
        on the same container yields the same coordinate sequence.
        This is critical for extract to work correctly.
    """

    @abstractmethod
    def get_max_capacity_bits(self, container: np.ndarray) -> int:
        """Returns the available carrier capacity in bits.

        Counted AFTER all filters are applied (edge detection, masks, and so on),
        so it reflects the real number of positions, not the geometric size.

        Args:
            container: Any ndarray container (RGB image, audio samples).

        Returns:
            Number of free positions in the coordinate pool.
        """
        ...

    @abstractmethod
    def generate_coords(self, container: np.ndarray, payload_bits_len: int, password_seed: str,
                        exclude_coords: Optional[Set[int]] = None) -> np.ndarray:
        """Returns payload_bits_len flat indices into `container.flat`.

        Args:
            container:        Carrier container.
            payload_bits_len: How many coordinates are needed (= number of bits in the payload).
            password_seed:    Password for the deterministic permutation.
            exclude_coords:   Coordinates excluded from the pool — a provision for
                              Plausible Deniability (ADR 004, IS_DECOY flag).
                              On decoy extract these positions must be
                              forbidden for the real payload.

        Returns:
            1D ndarray of length payload_bits_len with flat indices.

        Raises:
            ValueError: If the pool after filtering is smaller than payload_bits_len.
        """
        pass


class FileFormat(ABC):
    """Base interface for carrier containers (PNG, WAV, JPEG, ...).

    Each implementation encapsulates:
        * Magic bytes for format identification (see FormatIdentifier).
        * Decoding a file into a numpy representation suitable for embed/extract.
        * Serializing the modified representation back to disk
          WITHOUT loss relative to the original format (anti-conversion, ADR 003).

    Note:
        For formats where a numpy array is not enough (for example, JPEG needs
        a whole set of coefficient tables + quantization tables), the implementation returns
        its own container object (JpegContainer). In that case
        the return type is annotated as ndarray for the common interface, but in practice
        it is a concrete container.
    """

    @property
    @abstractmethod
    def magic(self) -> bytes:
        """Magic-byte marker for identifying the format from a raw byte stream.

        Returns:
            File prefix unique to this format. Used by
            FormatIdentifier to determine the type before the file is opened.
        """
        ...

    @abstractmethod
    def load(self, path: Path) -> np.ndarray:
        """Decodes a file into a numpy representation.

        Args:
            path: Absolute path to an existing file.

        Returns:
            ndarray (or a container object for complex formats),
            ready to pass to the stego processor.

        Raises:
            FileNotFoundError:     File not found.
            CorruptedCarrierError: The file is corrupt or does not match the format.
        """
        ...

    @abstractmethod
    def save(self, data: np.ndarray, path: Path) -> None:
        """Serializes the numpy representation back to a file.

        Args:
            data: Container after embed/extract.
            path: Save path. The extension must match the format.

        Raises:
            OSError: If writing to disk is impossible (no permissions, no space).
        """
        ...
